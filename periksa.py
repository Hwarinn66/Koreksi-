#!/usr/bin/env python3
"""
periksa.py
Memeriksa tulisan bahasa Indonesia dengan model hasil training (folder model_ejaan/).

Pakai:
    pip install torch transformers
    python periksa.py "Penelitian ini bertujuan untuk menganalisa data dikampus."
    python periksa.py --file tulisan.txt
    python periksa.py --model path/ke/model_ejaan "teks ..."

Folder model cukup berisi: model.safetensors, config.json, tokenizer.json, tokenizer_config.json.
"""
import argparse
import re
import sys
from pathlib import Path

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamus_baku import KAMUS_PERIKSA, kena_kamus  # noqa: E402

MAX_LEN = 128
SINGKATAN = {"dkk.", "dll.", "dsb.", "dst.", "hlm.", "tbk.", "swt.", "yth.", "sdr."}
PENJELASAN = {
    "TYPO": "salah ketik", "TIDAK_BAKU": "kata tidak baku", "KAPITAL": "seharusnya huruf kapital",
    "HURUF_KECIL": "seharusnya huruf kecil", "TAMBAH_KOMA": "perlu koma setelah kata ini",
    "TAMBAH_TITIK": "perlu titik setelah kata ini", "HAPUS": "tanda baca ini sebaiknya dihapus",
    "PISAH": "seharusnya ditulis terpisah", "GABUNG": "seharusnya digabung dengan kata berikutnya",
    "FORMAT_ANGKA": "format angka (desimal pakai koma, ribuan pakai titik)",
    "GANTI_TITIK": "koma ini seharusnya titik (dua kalimat disambung koma)",
}


def pecah_token(teks):
    hasil = []
    for chunk in teks.split():
        depan, belakang = [], []
        while len(chunk) > 1 and chunk[0] in "([“\"'":
            depan.append(chunk[0]); chunk = chunk[1:]
        while len(chunk) > 1 and chunk[-1] in ",.;:?!)]”\"'" and chunk.lower() not in SINGKATAN:
            belakang.insert(0, chunk[-1]); chunk = chunk[:-1]
        hasil += depan + [chunk] + belakang
    return hasil


def jendela_kata(n, maks_kata=60, tepi=10):
    """Membagi n kata menjadi jendela bertumpuk: [(mulai, akhir, inti_awal, inti_akhir), ...].

    Hanya label di bagian inti yang dipakai, karena di ujung jendela model mengira kalimatnya baru
    mulai atau sudah berakhir, lalu memberi label kapital dan titik palsu.
    """
    if n <= maks_kata:
        return [(0, n, 0, n)] if n else []
    hasil, mulai = [], 0
    while True:
        akhir = min(mulai + maks_kata, n)
        hasil.append((mulai, akhir, mulai + tepi if mulai else 0, akhir - tepi if akhir < n else n))
        if akhir == n:
            return hasil
        mulai += maks_kata - 2 * tepi


class Pemeriksa:
    def __init__(self, model_dir="model_ejaan"):
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir).eval()
        if torch.cuda.is_available():
            self.model.to("cuda")

    def prediksi(self, daftar_kata, batch=16, maks_kata=60):
        """Label per kata untuk banyak kalimat sekaligus.

        daftar_kata: list berisi list kata. Mengembalikan list berisi list (label, peluang).
        Kalimat yang lebih panjang dari maks_kata diperiksa dengan jendela bertumpuk (lihat jendela_kata).
        """
        potongan, asal = [], []
        for n, kata in enumerate(daftar_kata):
            for mulai, akhir, inti_awal, inti_akhir in jendela_kata(len(kata), maks_kata):
                potongan.append(kata[mulai:akhir]); asal.append((n, mulai, inti_awal, inti_akhir))
        hasil = [[("O", 1.0)] * len(k) for k in daftar_kata]
        id2label = self.model.config.id2label
        urut = sorted(range(len(potongan)), key=lambda x: len(potongan[x]))   # kurangi padding
        potongan = [potongan[x] for x in urut]
        asal = [asal[x] for x in urut]
        for i in range(0, len(potongan), batch):
            kelompok = potongan[i:i + batch]
            enc = self.tok(kelompok, is_split_into_words=True, truncation=True, max_length=MAX_LEN,
                           padding=True, return_tensors="pt")
            with torch.no_grad():
                logit = self.model(**{k: v.to(self.model.device) for k, v in enc.items()}).logits
            peluang = torch.softmax(logit, -1).cpu()
            for j, kata in enumerate(kelompok):
                n, mulai, inti_awal, inti_akhir = asal[i + j]
                prev = None
                for pos, w in enumerate(enc.word_ids(j)):
                    if w is not None and w != prev and inti_awal <= mulai + w < inti_akhir:
                        pr, idx = peluang[j, pos].max(-1)
                        hasil[n][mulai + w] = (id2label[int(idx)], float(pr))
                    prev = w
        return hasil

    def periksa_kalimat(self, kalimat):
        """Mengembalikan daftar (kata, label, saran) untuk satu kalimat."""
        kata = pecah_token(kalimat)
        if not kata:
            return []
        label = [lab for lab, _ in self.prediksi([kata])[0]]
        for i, k in enumerate(kata):  # kamus kata tidak baku
            if kena_kamus(k, i):
                label[i] = "TIDAK_BAKU"
        hasil = []
        for k, lab in zip(kata, label):
            if lab == "O":
                continue
            saran = KAMUS_PERIKSA.get(k.lower()) if lab == "TIDAK_BAKU" else None
            hasil.append((k, lab, saran))
        return hasil

    def periksa(self, teks):
        """Mengembalikan [(kalimat, [(kata, label, saran), ...]), ...]."""
        return [(k, self.periksa_kalimat(k)) for k in re.split(r"(?<=[.?!])\s+", teks.strip()) if k]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("teks", nargs="?", help="teks yang diperiksa")
    ap.add_argument("--file", help="berkas teks yang diperiksa")
    ap.add_argument("--model", default=str(Path(__file__).resolve().parent / "model_ejaan"))
    args = ap.parse_args()
    if not args.teks and not args.file:
        ap.error("isi teks atau --file")
    teks = Path(args.file).read_text(encoding="utf-8") if args.file else args.teks

    p = Pemeriksa(args.model)
    for kalimat, temuan in p.periksa(teks):
        print("•", kalimat)
        for kata, label, saran in temuan:
            tambahan = f" (seharusnya: {saran})" if saran else ""
            print(f"    - '{kata}': {PENJELASAN.get(label, label)}{tambahan}")
        if not temuan:
            print("    (tidak ada kesalahan terdeteksi)")


if __name__ == "__main__":
    main()
