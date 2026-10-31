"""Audit kolom 'benar' dengan penyaring EYD; tampilkan bendera selain yang wajar."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import saring_korpus as sk
kamus = sk.Kamus()
ABAI = {"karakter_tidak_sah", "tokenisasi", "panjang", "tanda_baca_lain", "kata_tidak_dikenal", "titik_di_tengah", None}
pola = r"\b(mempengaruhi|menunjukan|dimana|diantara|didalam|diluar|dibawah|diatas|kerjasama|bekerjasama|aktifitas|kreatifitas|produktifitas|presentase|negative|popular|trend|hoax|di gunakan|praktek|merubah|linier|sistim|analisa|apapun|siapapun|sekedar|resiko|obyek|subyek|kontinyu|pembaharuan|personil|merespon|dimasukan)\b"
for l in open(sys.argv[1], encoding="utf-8"):
    h = json.loads(l)
    r = sk.periksa(h["benar"], kamus, maks_oov=99)
    if r not in ABAI:
        print(f"{r:22} {h['id']} | {h['benar'][:160]}")
    for m in re.finditer(pola, h["benar"]):
        print("SISA", h["id"], m.group(0))
    for m in re.finditer(r".{0,30}, (sehingga|karena|bahwa)\b", h["benar"]):
        print("KOMA", h["id"], m.group(0))
    if "LAIN" in h.get("kesalahan", []):
        print("LAIN", h["id"], h["salah"][:100], "=>", h["benar"][:100])
