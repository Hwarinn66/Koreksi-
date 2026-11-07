"""
konteks.py
Memilih saran ejaan menurut kalimatnya dengan model pengisi kata (fill-mask).

Kata yang ditandai salah ketik ditutup dengan [MASK], lalu model menilai calon mana yang paling cocok
di posisi itu. Modelnya sudah jadi, tidak perlu dilatih, dan hanya dipanggil untuk kata yang ditandai.
Jika folder model tidak ada, saran tetap jalan tanpa konteks.

Unduh model (sekali saja, sekitar 450 MB): python web/unduh_model_konteks.py
"""
import os
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FOLDER_MODEL = Path(os.environ.get("MODEL_KONTEKS", REPO / "model_konteks"))
LEBAR = 25              # kata di kiri dan kanan yang ikut dibaca model
MAKS_SUBTOKEN = 6


class Konteks:
    def __init__(self, folder=FOLDER_MODEL):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(str(folder))
        self.model = AutoModelForMaskedLM.from_pretrained(str(folder)).eval()
        if torch.cuda.is_available():
            self.model.to("cuda")

    def _ids(self, kata):
        return self.tok(" ".join(kata), add_special_tokens=False)["input_ids"] if kata else []

    def skor(self, kata, i, calon):
        """kata: token kalimat; i: posisi yang diperiksa. Mengembalikan {calon: rata-rata log-peluang per subtoken}."""
        torch = self.torch
        kiri, kanan = self._ids(kata[max(0, i - LEBAR):i]), self._ids(kata[i + 1:i + 1 + LEBAR])
        per_panjang = {}
        for c in calon:
            sub = self._ids([c])[:MAKS_SUBTOKEN]
            if sub:
                per_panjang.setdefault(len(sub), []).append((c, sub))
        hasil = {}
        with torch.no_grad():
            for n, daftar in per_panjang.items():
                ids = [self.tok.cls_token_id] + kiri + [self.tok.mask_token_id] * n + kanan + [self.tok.sep_token_id]
                masuk = torch.tensor([ids], device=self.model.device)
                logit = self.model(input_ids=masuk).logits[0, len(kiri) + 1:len(kiri) + 1 + n]
                logp = torch.log_softmax(logit, -1)
                for c, sub in daftar:
                    hasil[c] = float(sum(logp[j, s] for j, s in enumerate(sub))) / n
        return hasil


_konteks = {"objek": None, "selesai": False}
_kunci = threading.Lock()


def muat():
    """Model konteks, atau None jika belum diunduh atau gagal dimuat."""
    with _kunci:
        if not _konteks["selesai"]:
            _konteks["selesai"] = True
            if (FOLDER_MODEL / "config.json").exists():
                try:
                    _konteks["objek"] = Konteks()
                except Exception as e:  # noqa: BLE001
                    print("[peringatan] model konteks gagal dimuat:", e)
            else:
                print(f"[info] model konteks tidak ada di {FOLDER_MODEL}; saran ejaan tanpa konteks kalimat")
    return _konteks["objek"]
