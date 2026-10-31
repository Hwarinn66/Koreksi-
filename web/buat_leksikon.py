#!/usr/bin/env python3
"""
Membuat web/data/leksikon.tsv: daftar kata baku beserta frekuensi dan bentuk tulisnya.

Dipakai untuk saran ejaan (typo), memecah kata (dirumah -> di rumah), dan mengenali
paragraf berbahasa asing. Sumber: kalimat bersih di data/*.txt (sudah sesuai EYD),
kata dasar Sastrawi, dan bentuk baku dari kamus_baku.py.

Pakai (dari folder repo): python web/buat_leksikon.py
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from buat_dataset import BAKU_SEMUA, tokenisasi  # noqa: E402
from kamus_baku import TIDAK_BAKU  # noqa: E402

frek = Counter()
bentuk = defaultdict(Counter)
for f in sorted((REPO / "data").glob("*.txt")):
    for baris in f.read_text(encoding="utf-8").splitlines():
        if not baris.strip() or baris.startswith("#"):
            continue
        for i, t in enumerate(tokenisasi(baris)):
            if not re.fullmatch(r"[^\W\d_]+(?:-[^\W\d_]+)*", t):
                continue
            k = t.lower()
            frek[k] += 1
            if i > 0 or not (t[0].isupper() and t[1:].islower()):  # huruf awal kalimat tidak dihitung
                bentuk[k][t] += 1

dasar = set()
try:
    import Sastrawi
    p = Path(Sastrawi.__file__).parent / "Stemmer" / "data" / "kata-dasar.txt"
    for w in p.read_text(encoding="utf-8").split():
        w = w.strip().lower()
        if w.isalpha():
            frek[w] += 1
            dasar.add(w)
except ImportError:
    print("[peringatan] Sastrawi tidak terpasang; kata dasar tidak ditambahkan")

for b in BAKU_SEMUA:
    frek[b] += 1
for salah in TIDAK_BAKU:          # bentuk tidak baku tidak boleh disarankan
    frek.pop(salah, None)

out = REPO / "web" / "data" / "leksikon.tsv"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as fh:
    fh.write("# kata\tfrekuensi\tbentuk_tulis (kosong = huruf kecil)\n")
    for k, n in sorted(frek.items(), key=lambda x: (-x[1], x[0])):
        b = bentuk[k].most_common(1)[0][0] if bentuk[k] else k
        fh.write(f"{k}\t{n}\t{b if b != k else ''}\n")
dasar -= set(TIDAK_BAKU)
(out.parent / "kata_dasar.txt").write_text("\n".join(sorted(dasar)) + "\n", encoding="utf-8")
print(f"{len(frek)} kata -> {out}; {len(dasar)} kata dasar -> {out.parent / 'kata_dasar.txt'}")
