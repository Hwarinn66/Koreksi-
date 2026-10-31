"""Ekstrak kalimat isi skripsi dari PDF (berbasis teks) -> satu kalimat per baris.
Pakai: python ekstrak.py berkas.pdf hal_awal hal_akhir keluaran.tsv"""
import re, subprocess, sys

pdf, awal, akhir, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]

def halaman(p):
    return subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), pdf, "-"],
                          capture_output=True, text=True).stdout

def isi_halaman(t):
    baris = [b.strip() for b in t.replace("\f", "").splitlines()]
    # buang nomor halaman di awal/akhir
    while baris and (not baris[0] or re.fullmatch(r"\d{1,3}|[ivxl]+", baris[0])):
        baris.pop(0)
    # potong catatan kaki: baris angka saja diikuti baris rujukan
    for i, b in enumerate(baris):
        if re.fullmatch(r"\d{1,3}", b):
            nxt = next((x for x in baris[i + 1:] if x), "")
            if re.match(r"[A-Z][a-zA-Z.]+.*[,“\"]|Ibid|Op\.|[A-Z][a-z]+ [A-Z][a-z]+", nxt) and i > len(baris) * 0.4:
                baris = baris[:i]
                break
    return " ".join(b for b in baris if b)

bagian = [isi_halaman(halaman(p)) for p in range(awal, akhir + 1)]
teks = ""
for b in bagian:
    # kata terpotong tanda hubung di akhir halaman: "menye-" + "lesaikan"
    teks = teks[:-1] + b if re.search(r"[a-z]-$", teks) else (teks + " " + b)
teks = re.sub(r"\s+", " ", teks)
# nomor catatan kaki menempel: "Play.9 TikTok", "creator.11 Aplikasi", "(AS).10"
teks = re.sub(r"(?<!\d)([.;:)”\"])\d{1,3}(?=\s|$)", r"\1", teks)
teks = re.sub(r"([a-z])\d{1,3}(?=[\s.,])", r"\1", teks)

kal = re.split(r"(?<=[.?!])\s+(?=[A-Z“\"])", teks)
with open(out, "w", encoding="utf-8") as f:
    n = 0
    for k in kal:
        k = k.strip()
        kata = k.split()
        if not (6 <= len(kata) <= 70): continue
        if not re.match(r"[A-Z“\"]", k) or not k.endswith((".", "?", "”")): continue
        if re.search(r"\.{4,}|Tabel \d|Gambar \d|\b\d+ \d+ \d+ \d+\b|http", k): continue
        if sum(c.isdigit() for c in k) > len(k) * 0.15: continue
        n += 1
        f.write(f"{n}\t{k}\n")
print(n, "kalimat")
