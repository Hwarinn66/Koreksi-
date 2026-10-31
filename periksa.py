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
from kamus_baku import KAMUS_PERIKSA  # noqa: E402

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


class Pemeriksa:
    def __init__(self, model_dir="model_ejaan"):
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir).eval()
        if torch.cuda.is_available():
            self.model.to("cuda")

    def periksa_kalimat(self, kalimat):
        """Mengembalikan daftar (kata, label, saran) untuk satu kalimat."""
        kata = pecah_token(kalimat)
        if not kata:
            return []
        enc = self.tok(kata, is_split_into_words=True, truncation=True, max_length=MAX_LEN,
                       return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            pred = self.model(**enc).logits.argmax(-1)[0].tolist()
        label, prev = {}, None
        for pos, w in enumerate(enc.word_ids()):
            if w is not None and w != prev:
                label[w] = self.model.config.id2label[pred[pos]]
            prev = w
        for i, k in enumerate(kata):  # kamus kata tidak baku
            if k.lower() in KAMUS_PERIKSA and not k.isupper():
                label[i] = "TIDAK_BAKU"
        hasil = []
        for i in sorted(label):
            if label[i] == "O":
                continue
            saran = KAMUS_PERIKSA.get(kata[i].lower()) if label[i] == "TIDAK_BAKU" else None
            hasil.append((kata[i], label[i], saran))
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
