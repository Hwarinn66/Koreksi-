#!/usr/bin/env python3
"""
Membuat web/data/leksikon.tsv: daftar kata baku beserta frekuensi dan bentuk tulisnya.

Dipakai untuk saran ejaan (typo), memecah kata (dirumah -> di rumah), dan mengenali
paragraf berbahasa asing. Sumber: kalimat bersih di data/*.txt (sudah sesuai EYD),
kata dasar Sastrawi, bentuk baku dari kamus_baku.py, dan frekuensi kata dari wordfreq.

wordfreq berisi banyak nama, kata Inggris, dan salah ketik, jadi saringan kata barunya ketat (lihat
kata_indonesia). Selebihnya wordfreq hanya memberi frekuensi. Kata yang lolos saringan tidak perlu
semuanya ada di kamus: kata bentukan juga dirakit saat saran dicari.

Pakai (dari folder repo):
    pip install Sastrawi wordfreq
    python web/buat_leksikon.py
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "web"))
from buat_dataset import BAKU_SEMUA, TERPISAH, tokenisasi  # noqa: E402
from kamus_baku import TIDAK_BAKU  # noqa: E402
from leksikon import bentukan  # noqa: E402

HURUF = "abcdefghijklmnopqrstuvwxyz"

# Kata lazim yang bukan bentukan kata dasar Sastrawi. Kata tidak baku (gak, udah) sengaja tidak dimasukkan.
KATA_TAMBAHAN = {"ya", "yah", "nah", "ah", "eh", "masing", "gara", "kupu", "kanak", "tips", "promo", "ilmuwan",
                 "wartawan", "bangsawan", "kenangan", "kehendak", "herbal", "audisi", "memberitahu", "futsal",
                 "luring", "daring"}
# Ragam lisan dan kata kasar: tidak boleh menjadi saran, jadi tidak mendapat frekuensi dari wordfreq.
TANPA_FREKUENSI = {"aja", "banget", "bikin", "kalo", "tau", "liat", "nih", "sih", "dong", "deh", "kok", "kayak", "gimana",
                   "gitu", "gini", "doang", "nggak", "enggak", "ngga", "gak", "udah", "dapet", "pake", "bener", "temen",
                   "maen", "memek", "memeknya", "kontol", "ngentot", "jembut", "pepek"}
PECAH_TERPISAH = {a + b for a, b in TERPISAH}


def skala_wordfreq(z):
    """Frekuensi Zipf wordfreq -> hitungan, disamakan kira-kira dengan hitungan korpus (Zipf 2,5 = 1)."""
    return round(10 ** (z - 2.5))


def tetangga(k):
    """Semua bentuk yang berbeda satu huruf dari k."""
    for i in range(len(k) + 1):
        for h in HURUF:
            yield k[:i] + h + k[i:]
        if i < len(k):
            yield k[:i] + k[i + 1:]
            for h in HURUF:
                yield k[:i] + h + k[i + 1:]
        if i < len(k) - 1:
            yield k[:i] + k[i + 1] + k[i] + k[i + 2:]


def kata_indonesia(k, dasar, zipf):
    """Apakah kata baru dari wordfreq layak masuk kamus."""
    if not k.isalpha() or len(k) < 7 or k in TANPA_FREKUENSI or k in PECAH_TERPISAH:
        return False                    # kata pendek terlalu mudah cocok secara kebetulan (dani = dan + i)
    if k.startswith(("di", "ke")):      # di + kata (dilantai, dibumi) lebih mungkin salah pisah; calon itu dirakit saat dicari
        if k[2:] in dasar or not bentukan(k, dasar, akhiran=("kan", "i", "an")):
            return False
    elif not bentukan(k, dasar):
        return False
    # Jauh lebih jarang daripada kata yang beda satu huruf: hampir pasti salah ketik (memilik, sekaran).
    return not any(zipf.get(t, 0) >= zipf[k] + 1 for t in tetangga(k))


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

for b in (*BAKU_SEMUA, *KATA_TAMBAHAN):
    frek[b] += 1

zipf = {}
try:
    import wordfreq
    zipf = {k: wordfreq.zipf_frequency(k, "id") for k in wordfreq.top_n_list("id", 100_000, wordlist="small")}
except ImportError:
    print("[peringatan] wordfreq tidak terpasang; frekuensi hanya dari korpus sendiri")

# Nama yang hanya muncul sekali dua kali di korpus (Bandar Udara Bou Sfer) tidak boleh menjadi saran.
# Akronim tetap disimpan karena bentuk tulisnya dipakai untuk koreksi kapital (spss -> SPSS).
for k in [k for k, n in frek.items() if n <= 2 and k not in dasar and not zipf.get(k)
          and bentuk[k] and all(t[:1].isupper() and not t.isupper() for t in bentuk[k])]:
    del frek[k]
for k, z in zipf.items():
    if k in frek:
        if k not in TANPA_FREKUENSI:
            frek[k] += skala_wordfreq(z)
    elif kata_indonesia(k, dasar, zipf):
        frek[k] = skala_wordfreq(z) or 1

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
