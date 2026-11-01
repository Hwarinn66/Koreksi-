#!/usr/bin/env python3
"""
susun_daftar.py
Alur koreksi berbasis daftar kalimat bernomor (dipakai untuk jurnal dan skripsi batch kedua).

1) Ambil kalimat isi dari PDF (memakai web/ekstrak.py), sampel merata sepanjang dokumen:
       python alat/susun_daftar.py ambil dokumen.pdf folder/ --jumlah 60
   -> folder/kalimat.tsv   (nomor, halaman, kalimat)

2) Tulis folder/koreksi.txt. Kalimat yang tidak disebut dianggap sudah benar. Format per baris:
       12 S: lama => baru ;; *lama => baru     (substitusi; * = ganti semua kemunculan)
       13 A: kalimat asli yang diperbaiki      (ganti teks asli jika hasil ekstraksi rusak)
       14 X                                    (lewati kalimat: rusak, tabel, data pribadi)
       15 ! ragu: catatan                      (tandai kalimat sebagai ragu)

3) Susun data:
       python alat/susun_daftar.py susun folder/ jurnal01
   -> pasangan_asli.jsonl, token_asli.jsonl, tinjau.csv, kalimat_benar.txt
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ALAT = Path(__file__).resolve().parent
REPO = ALAT.parents[1]
sys.path.insert(0, str(ALAT))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "web"))      # web/ekstrak.py, bukan alat/ekstrak.py
import susun_koreksi as sk  # noqa: E402


def ambil(pdf, folder, jumlah, lewati_awal):
    from ekstrak import ekstrak
    kalimat, info = ekstrak(pdf)
    calon = [k for k in kalimat
             if 8 <= len(k.teks.split()) <= 60 and k.teks[:1].isupper()
             and not re.search(r"https?://|www\.|@|\.{3,}|\b(doi|ISSN|ISBN)\b", k.teks, re.I)]
    calon = calon[int(len(calon) * lewati_awal):]          # lewati abstrak/halaman awal
    if len(calon) > jumlah:
        langkah = len(calon) / jumlah
        calon = [calon[int(i * langkah)] for i in range(jumlah)]
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "kalimat.tsv", "w", encoding="utf-8") as f:
        for n, k in enumerate(calon, 1):
            hal = k.halaman if isinstance(k.halaman, int) else k.halaman[0]
            f.write(f"{n}\t{hal}\t{k.teks}\n")
    print(f"{len(calon)} kalimat -> {folder / 'kalimat.tsv'} ({info['jumlah_halaman']} halaman)")


def urai(path):
    aturan = defaultdict(lambda: {"S": [], "A": None, "X": False, "ragu": []})
    if not path.exists():
        return aturan
    for baris in path.read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#"):
            continue
        m = re.match(r"(\d+)\s+(S:|A:|X\b|!)\s*(.*)", baris)
        if not m:
            raise ValueError(f"baris koreksi tidak dikenali: {baris}")
        n, jenis, isi = int(m.group(1)), m.group(2), m.group(3)
        if jenis == "S:":
            for bagian in isi.split(";;"):
                lama, baru = bagian.split("=>")
                aturan[n]["S"].append((lama.strip(), baru.strip()))
        elif jenis == "A:":
            aturan[n]["A"] = isi
        elif jenis == "X":
            aturan[n]["X"] = True
        else:
            aturan[n]["ragu"].append(re.sub(r"^ragu:\s*", "", isi))
    return aturan


def susun(folder, sumber):
    kal = []
    for baris in (folder / "kalimat.tsv").read_text(encoding="utf-8").splitlines():
        n, hal, teks = baris.split("\t", 2)
        kal.append((int(n), int(hal), teks))
    aturan = urai(folder / "koreksi.txt")
    masalah, hasil = [], []
    for n, hal, teks in kal:
        a = aturan[n]
        if a["X"]:
            continue
        asli = sk.normalisasi_artefak(a["A"] or teks)
        benar = asli
        for lama, baru in a["S"]:
            semua = lama.startswith("*")
            lama = lama.lstrip("*")
            if lama not in benar:
                masalah.append(f"#{n}: '{lama}' tidak ditemukan")
                continue
            benar = benar.replace(lama, baru) if semua else benar.replace(lama, baru, 1)
        hasil.append({"id": f"{sumber}-{n:04d}", "sumber": sumber, "bab": f"hal{hal}", "salah": asli,
                      "benar": benar, "status": "ragu" if a["ragu"] else "pasti",
                      "catatan": "; ".join(a["ragu"])})
    if masalah:
        print("\n".join(masalah))
        raise SystemExit(f"{len(masalah)} substitusi gagal")

    stat = Counter()
    with open(folder / "pasangan_asli.jsonl", "w", encoding="utf-8") as fp, \
         open(folder / "token_asli.jsonl", "w", encoding="utf-8") as ft:
        for h in hasil:
            ta, tb = sk.tokenisasi_asli(h["salah"]), sk.tokenisasi_asli(h["benar"])
            ok = sk.sama_tanpa_spasi(ta, h["salah"]) and sk.sama_tanpa_spasi(tb, h["benar"])
            if ok:
                labs, perb = sk.label_token(ta, tb)
                jenis = sorted({x for l in labs if l != "O" for x in l.split("+")})
                ft.write(json.dumps({"id": h["id"], "tokens": ta, "labels": labs, "perbaikan": perb},
                                    ensure_ascii=False) + "\n")
            else:
                jenis = ["?"] if h["salah"] != h["benar"] else []
            h["kesalahan"] = jenis
            h["token_tersedia"] = ok
            stat.update(jenis or ["TANPA_KESALAHAN"])
            fp.write(json.dumps(h, ensure_ascii=False) + "\n")
    with open(folder / "tinjau.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "bab", "status", "kesalahan", "salah (asli skripsi)", "benar (koreksi)",
                    "catatan", "setuju? (isi Y/T)"])
        for h in hasil:
            w.writerow([h["id"], h["bab"], h["status"], ";".join(h["kesalahan"]), h["salah"],
                        h["benar"], h["catatan"], ""])
    (folder / "kalimat_benar.txt").write_text("\n".join(h["benar"] for h in hasil if h["status"] == "pasti") + "\n",
                                              encoding="utf-8")
    salah = sum(h["salah"] != h["benar"] for h in hasil)
    print(f"{sumber}: {len(hasil)} kalimat, {salah} berkesalahan | {dict(stat.most_common())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="perintah", required=True)
    a = sub.add_parser("ambil")
    a.add_argument("pdf"); a.add_argument("folder", type=Path)
    a.add_argument("--jumlah", type=int, default=60)
    a.add_argument("--lewati-awal", type=float, default=0.08)
    s = sub.add_parser("susun")
    s.add_argument("folder", type=Path); s.add_argument("sumber")
    args = ap.parse_args()
    if args.perintah == "ambil":
        ambil(args.pdf, args.folder, args.jumlah, args.lewati_awal)
    else:
        susun(args.folder, args.sumber)
