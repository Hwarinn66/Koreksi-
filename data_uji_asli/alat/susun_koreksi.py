#!/usr/bin/env python3
"""
Menyusun data uji kesalahan ASLI dari koreksi manual skripsi.

Pakai: python susun_koreksi.py <folder_skripsi> <id_sumber>
Folder harus berisi bab*.tsv (hasil ekstrak.py) dan koreksi.txt.
Keluaran (di folder yang sama):
  pasangan_asli.jsonl, token_asli.jsonl, tinjau.csv, kalimat_benar.txt
"""
import csv, difflib, json, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from buat_dataset import BAKU_SEMUA, gabung_token, tokenisasi  # noqa: E402
from kamus_baku import TIDAK_BAKU as KAMUS_TIDAK_BAKU  # noqa: E402

folder = sumber = None  # diisi di __main__

# Bentuk tidak baku tambahan yang ditemui di skripsi asli
TIDAK_BAKU_EKSTRA = {"presentase", "negative", "popular", "trend", "hoax", "kerjasama",
                     "prakteknya", "merubah", "audience", "bahwasannya", "linier", "subyek",
                     "sample", "variable", "merespon", "ibukota", "creatore", "atau pun"}
TIDAK_BAKU = {x for v in BAKU_SEMUA.values() for x in v} | set(KAMUS_TIDAK_BAKU) | TIDAK_BAKU_EKSTRA


def normalisasi_artefak(s):
    s = s.replace("‟", "'").replace("’", "'")
    s = re.sub(r"(?<=\w)- (?=\w)", "-", s)                     # "anak- anak" (pindah baris)
    s = re.sub(r"(?i)\b(\w{3,})\1\b", lambda m: f"{m.group(0)[:len(m.group(1))]}-{m.group(0)[len(m.group(1)):]}", s)
    s = re.sub(r"(?<=[a-z\)]),\d{1,2}(?= [A-Za-z])", ",", s)   # nomor catatan kaki setelah koma
    s = re.sub(r"(?<=\.)\s+(?:\d{1,2}|[a-h])\.$", "", s)        # penanda daftar di akhir
    return " ".join(s.split())


def muat_bab():
    bab = {}
    for p in sorted(folder.glob("bab*.tsv")):
        if ".lama" in p.name:
            continue
        bab[p.stem] = [b.split("\t", 1)[1] for b in p.read_text(encoding="utf-8").splitlines() if "\t" in b]
    return bab


def urai_koreksi(path):
    entri, bab, cur = [], None, None
    for baris in path.read_text(encoding="utf-8").splitlines():
        if not baris.strip() or baris.startswith("#"):
            continue
        if baris.startswith("@"):
            bab = baris[1:].strip()
        elif baris.startswith("> "):
            kunci, _, akhir = baris[2:].partition(" || ")
            cur = {"bab": bab, "kunci": kunci.strip(), "akhir": akhir.strip() or None,
                   "A": None, "S": None, "B": None, "status": "pasti", "catatan": ""}
            entri.append(cur)
        elif baris.startswith("A: "):
            cur["A"] = baris[3:].strip()
        elif baris.startswith("S: "):
            cur["S"] = [x.split(" => ") for x in baris[3:].split(" ;; ")]
        elif baris.startswith("B: "):
            cur["B"] = baris[3:].strip()
        elif baris.startswith("! "):
            st, _, cat = baris[2:].partition(":")
            cur["status"], cur["catatan"] = st.strip(), cat.strip()
        else:
            raise ValueError(f"baris tidak dikenal: {baris}")
    return entri


def cari_asli(bab, e):
    kandidat = [s for s in bab[e["bab"]] if e["kunci"] in s]
    if not kandidat:  # batas bab di PDF tidak selalu tepat; cari di bab lain
        kandidat = [s for b in bab.values() for s in b if e["kunci"] in s]
    if len(kandidat) != 1:
        raise ValueError(f"[{e['bab']}] kunci '{e['kunci']}' cocok {len(kandidat)} kalimat")
    s = kandidat[0]
    s = s[s.index(e["kunci"]):]
    if e["akhir"]:
        s = s[:s.index(e["akhir"]) + len(e["akhir"])]
    return s


# --------------------------------------------------------------------------- label token
def label_ganti(a, b):
    if a.lower() == b.lower():
        return "KAPITAL" if b[:1].isupper() and not a[:1].isupper() else "HURUF_KECIL" if a[:1].isupper() and not b[:1].isupper() else "KAPITAL"
    if re.search(r"\d", a) and re.search(r"\d", b):
        return "FORMAT_ANGKA"
    if a == "," and b == ".":
        return "GANTI_TITIK"
    if a.lower() in TIDAK_BAKU:
        return "TIDAK_BAKU"
    if re.sub(r"[-']", "", a).isalpha() and re.sub(r"[-']", "", b).isalpha():
        return "TYPO"
    return "LAIN"


SINGKATAN = {"dkk.", "dll.", "dsb.", "dst.", "hlm.", "tbk.", "swt."}


def tokenisasi_asli(s):
    """Tokenizer toleran untuk teks skripsi: pisah per spasi, lalu kupas tanda baca
    di awal/akhir. Kesalahan spasi (34,1%atau, respondensangat) tetap satu token."""
    hasil = []
    for chunk in s.split():
        depan, belakang = [], []
        while chunk and chunk[0] in "([“\"'" and len(chunk) > 1:
            depan.append(chunk[0]); chunk = chunk[1:]
        while chunk and chunk[-1] in ",.;:?!)]”\"'" and chunk.lower() not in SINGKATAN and len(chunk) > 1:
            belakang.insert(0, chunk[-1]); chunk = chunk[:-1]
        hasil += depan + ([chunk] if chunk else []) + belakang
    return hasil


def sama_tanpa_spasi(tokens, s):
    return "".join(tokens) == s.replace(" ", "")


def mirip(a, b):
    return difflib.SequenceMatcher(a=a.lower(), b=b.lower()).ratio() >= 0.75


def label_token(ta, tb):
    lab = [[] for _ in ta]
    perb = [None] * len(ta)
    sm = difflib.SequenceMatcher(a=[x.lower() for x in ta], b=[x.lower() for x in tb], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        A, B = ta[i1:i2], tb[j1:j2]
        if op == "equal":
            for k, (a, b) in enumerate(zip(A, B)):
                if a != b:
                    lab[i1 + k].append(label_ganti(a, b)); perb[i1 + k] = b
            continue
        if op == "insert":
            tgt = i1 - 1
            if tgt < 0:
                continue
            if B == [","]:
                lab[tgt].append("TAMBAH_KOMA"); perb[tgt] = ta[tgt] + ","
            elif B == ["."]:
                lab[tgt].append("TAMBAH_TITIK"); perb[tgt] = ta[tgt] + "."
            else:
                lab[tgt].append("LAIN"); perb[tgt] = ta[tgt] + " " + " ".join(B)
        elif op == "delete":
            for i in range(i1, i2):
                lab[i].append("HAPUS" if ta[i] in {",", "."} else "LAIN"); perb[i] = ""
        elif len(A) == len(B):
            for k, (a, b) in enumerate(zip(A, B)):
                lab[i1 + k].append(label_ganti(a, b)); perb[i1 + k] = b
        elif len(A) == 1 and len(B) == 2 and B[1] not in ",." and mirip(A[0], "".join(B)):
            lab[i1].append("PISAH"); perb[i1] = " ".join(B)
            if A[0].lower() != "".join(B).lower():
                lab[i1].append("TYPO")
        elif len(A) >= 2 and len(B) == 1 and mirip("".join(A).replace("–", "-"), B[0]):
            lab[i1].append("GABUNG"); perb[i1] = B[0]
            if "".join(A).lower().replace("–", "") != B[0].lower().replace("-", ""):
                lab[i1].append("TIDAK_BAKU" if A[-1].lower() in TIDAK_BAKU else "LAIN")
        elif len(A) == 1 and len(B) == 2 and B[1] in {",", "."} and A[0] != B[0]:
            lab[i1].append(label_ganti(A[0], B[0]))
            lab[i1].append("TAMBAH_KOMA" if B[1] == "," else "TAMBAH_TITIK"); perb[i1] = B[0] + B[1]
        elif len(B) > len(A) and "".join(A).lower() == "".join(B).lower() and all(x not in ",." for x in B):
            # beberapa kata yang masing-masing perlu dipisah: "apapun diluar" -> "apa pun di luar"
            sisa = list(B)
            for i in range(i1, i2):
                bagian = []
                while sisa and len("".join(bagian)) < len(ta[i]):
                    bagian.append(sisa.pop(0))
                lab[i].append("PISAH" if len(bagian) > 1 else "O"); perb[i] = " ".join(bagian)
        else:
            # pecah: cocokkan kata per kata bila panjang beda karena tanda baca
            for i in range(i1, i2):
                lab[i].append("LAIN")
            perb[i1] = gabung_token(B)
    return ["+".join(dict.fromkeys(l)) if l else "O" for l in lab], perb


def main():
    bab = muat_bab()
    entri = urai_koreksi(folder / "koreksi.txt")
    hasil, masalah = [], []
    for n, e in enumerate(entri, 1):
        try:
            asli = normalisasi_artefak(e["A"] or cari_asli(bab, e))
            if e["S"]:
                benar = asli
                for lama, baru in e["S"]:
                    semua = lama.startswith("*")
                    lama = lama.lstrip("*")
                    if lama not in benar:
                        raise ValueError(f"substitusi '{lama}' tidak ditemukan")
                    benar = benar.replace(lama, baru) if semua else benar.replace(lama, baru, 1)
            elif e["B"] in (None, "="):
                benar = asli
            else:
                benar = e["B"]
        except ValueError as err:
            masalah.append(f"#{n} {e['kunci'][:40]}: {err}")
            continue
        hasil.append({"id": f"{sumber}-{n:04d}", "sumber": sumber, "bab": e["bab"],
                      "salah": asli, "benar": benar, "status": e["status"], "catatan": e["catatan"]})

    statistik = Counter()
    with open(folder / "pasangan_asli.jsonl", "w", encoding="utf-8") as fp, \
         open(folder / "token_asli.jsonl", "w", encoding="utf-8") as ft:
        for h in hasil:
            ta, tb = tokenisasi_asli(h["salah"]), tokenisasi_asli(h["benar"])
            ok = sama_tanpa_spasi(ta, h["salah"]) and sama_tanpa_spasi(tb, h["benar"])
            if ok:
                labs, perb = label_token(ta, tb)
                jenis = sorted({x for l in labs if l != "O" for x in l.split("+")})
                ft.write(json.dumps({"id": h["id"], "tokens": ta, "labels": labs, "perbaikan": perb},
                                    ensure_ascii=False) + "\n")
            else:
                jenis = ["?"] if h["salah"] != h["benar"] else []
            h["kesalahan"] = jenis
            h["token_tersedia"] = ok
            statistik.update(jenis or ["TANPA_KESALAHAN"])
            fp.write(json.dumps(h, ensure_ascii=False) + "\n")

    with open(folder / "tinjau.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "bab", "status", "kesalahan", "salah (asli skripsi)", "benar (koreksi)", "catatan", "setuju? (isi Y/T)"])
        for h in hasil:
            w.writerow([h["id"], h["bab"], h["status"], ";".join(h["kesalahan"]), h["salah"], h["benar"], h["catatan"], ""])

    (folder / "kalimat_benar.txt").write_text("\n".join(h["benar"] for h in hasil) + "\n", encoding="utf-8")

    print(f"{len(hasil)} kalimat, {sum(h['salah'] != h['benar'] for h in hasil)} berisi kesalahan,"
          f" token gagal: {sum(not h['token_tersedia'] for h in hasil)}")
    print(dict(statistik.most_common()))
    for m in masalah:
        print("MASALAH:", m)


if __name__ == "__main__":
    folder, sumber = Path(sys.argv[1]), sys.argv[2]
    main()
