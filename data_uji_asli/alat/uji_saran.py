#!/usr/bin/env python3
"""
Mengukur saran ejaan pada typo asli di semua_token_asli.jsonl.

Dua ukuran:
  A. Saran untuk kata yang menurut koreksi manual salah ketik: apakah sama dengan koreksinya.
  B. Alur lengkap dengan label model: apa yang terjadi pada setiap kata yang ditandai TYPO, termasuk
     kata benar yang keliru ditandai. Butuh --model, atau --prediksi jika labelnya sudah disimpan.

Pakai (dari folder repo):
    python data_uji_asli/alat/uji_saran.py --data data_uji_asli --dokumen skripsi02,skripsi05 --model model_ejaan

Tanpa model konteks (--tanpa-konteks), saran dipilih tanpa membaca kalimat.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "web")]

# Di data ini perbaikannya bergeser karena kata yang salah pisah; bukan kasus saran ejaan.
SALAH_SEJAJAR = {"Chin", "Byte", "Dance", "perusahaanasal"}
JARAK_MAKS = 4      # lebih jauh dari ini berarti penggantian kata, bukan salah ketik


def baca(folder, dokumen):
    sumber = {}
    with open(Path(folder) / "semua_pasangan_asli.jsonl", encoding="utf-8") as f:
        for b in f:
            x = json.loads(b)
            sumber[x["id"]] = x
    with open(Path(folder) / "semua_token_asli.jsonl", encoding="utf-8") as f:
        token = [json.loads(b) for b in f]
    return [(sumber[t["id"]], t) for t in token if not dokumen or sumber[t["id"]]["sumber"] in dokumen]


def emas(w, label, perbaikan):
    """Bentuk benar kata ini menurut koreksi manual, atau None jika kata ini bukan typo yang bisa dinilai."""
    from leksikon import jarak_dl
    if "TYPO" not in label or w in SALAH_SEJAJAR or not perbaikan:
        return None
    p = perbaikan.strip(",.;:").lower()
    return p if jarak_dl(w.lower(), p) <= JARAK_MAKS else None


def uji_saran(data, konteks):
    """A. Mengembalikan Counter: tepat, salah, tanpa_saran, dianggap_benar."""
    import koreksi as ko
    hasil, gagal = Counter(), []
    for _, t in data:
        for i, (w, lab, per) in enumerate(zip(t["tokens"], t["labels"], t["perbaikan"])):
            p = emas(w, lab, per)
            if p is None:
                continue
            if konteks:
                saran, _yakin = ko.saran_konteks(w, t["tokens"], i, konteks)
            else:
                saran = ko.saran_ejaan(w)
            if saran is getattr(ko, "BUKAN_SALAH", ()):
                hasil["dianggap_benar"] += 1
            elif saran is None:
                hasil["tanpa_saran"] += 1
            elif saran.lower() == p:
                hasil["tepat"] += 1
            else:
                hasil["salah"] += 1
            if saran is None or saran is getattr(ko, "BUKAN_SALAH", ()) or saran.lower() != p:
                gagal.append((w, p, saran if isinstance(saran, str) else None))
    return hasil, gagal


def uji_alur(data, prediksi, konteks):
    """B. Hasil setiap kata yang ditandai TYPO, per kelompok (typo sungguhan atau bukan)."""
    import koreksi as ko
    hasil = Counter()
    contoh = {"salah": [], "kata_benar_diganti": []}
    for _, t in data:
        kalimat = " ".join(t["tokens"])
        token, pos = [], 0
        for w in t["tokens"]:
            token.append((w, pos, pos + len(w)))
            pos += len(w) + 1
        label = [tuple(x) for x in prediksi[t["id"]]]
        frek = Counter(t["tokens"])
        tambahan = {"konteks": konteks} if konteks else {}
        temuan = {x["awal"]: x for x in ko.susun_temuan(kalimat, token, label, frek, **tambahan)}
        for i, (w, s, _) in enumerate(token):
            if label[i][0] != "TYPO" or ko.kena_kamus(w, i):
                continue
            x = temuan.get(s)
            p = emas(w, t["labels"][i], t["perbaikan"][i])
            kelompok = "typo" if p else ("bukan_kesalahan" if t["labels"][i] == "O" else "label_lain")
            if x is None:
                hasil[kelompok, "dilewati"] += 1
            elif x["saran"] is None:
                hasil[kelompok, "tanpa_saran"] += 1
            elif p and x["saran"].lower() == p:
                hasil[kelompok, "tepat_yakin" if x["yakin"] else "tepat_ragu"] += 1
            else:
                hasil[kelompok, "salah_yakin" if x["yakin"] else "salah_ragu"] += 1
                if p:
                    contoh["salah"].append((w, p, x["saran"]))
                elif kelompok == "bukan_kesalahan":
                    contoh["kata_benar_diganti"].append((w, x["saran"]))
    return hasil, contoh


def lapor_a(hasil):
    n = sum(hasil.values())
    print(f"A. saran untuk {n} typo asli: tepat {hasil['tepat']} ({hasil['tepat'] / n:.1%}), salah {hasil['salah']}, "
          f"tanpa saran {hasil['tanpa_saran']}, dianggap kata benar {hasil['dianggap_benar']}")


def lapor_b(hasil):
    print("B. kata yang ditandai TYPO oleh model:")
    for kelompok in ("typo", "label_lain", "bukan_kesalahan"):
        isi = {k[1]: v for k, v in sorted(hasil.items()) if k[0] == kelompok}
        print(f"   {kelompok:16} {sum(isi.values()):4}  {isi}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="folder berisi semua_token_asli.jsonl dan semua_pasangan_asli.jsonl")
    ap.add_argument("--dokumen", default="", help="daftar dokumen dipisah koma; kosong = semua")
    ap.add_argument("--model", help="folder model_ejaan, untuk ukuran B")
    ap.add_argument("--prediksi", help="berkas JSON {id: [[label, peluang], ...]}, pengganti --model")
    ap.add_argument("--tanpa-konteks", action="store_true")
    ap.add_argument("--rinci", action="store_true", help="tampilkan saran yang salah")
    args = ap.parse_args()

    k = None
    if not args.tanpa_konteks:
        import konteks
        k = konteks.muat()
        if k is None:
            sys.exit("Model konteks belum ada. Jalankan web/unduh_model_konteks.py atau pakai --tanpa-konteks.")
    data = baca(args.data, set(filter(None, args.dokumen.split(","))))

    hasil, gagal = uji_saran(data, k)
    lapor_a(hasil)
    if args.rinci:
        print("   gagal (kata, koreksi manual, saran):", sorted(set(gagal), key=str))

    prediksi = None
    if args.prediksi:
        prediksi = json.loads(Path(args.prediksi).read_text(encoding="utf-8"))
    elif args.model:
        from periksa import Pemeriksa
        label = Pemeriksa(args.model).prediksi([t["tokens"] for _, t in data])
        prediksi = {t["id"]: h for (_, t), h in zip(data, label)}
    if prediksi:
        hasil_b, contoh = uji_alur(data, prediksi, k)
        lapor_b(hasil_b)
        if args.rinci:
            print("   typo dengan saran salah:", sorted(set(contoh["salah"])))
            print("   kata benar yang tetap diganti:", sorted(set(contoh["kata_benar_diganti"])))


if __name__ == "__main__":
    main()
