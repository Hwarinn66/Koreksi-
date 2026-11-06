"""
ekstrak.py
Membaca dokumen (PDF, DOCX, TXT, MD) menjadi paragraf dan kalimat yang tahu letak halamannya.

Bagian yang tidak diperiksa: judul/subjudul, daftar isi/tabel/gambar, daftar pustaka, tabel,
keterangan gambar/tabel, catatan kaki, nomor halaman, dan paragraf berbahasa asing.
"""
import codecs
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from leksikon import LEKSIKON

AKHIR_KALIMAT = (".", "?", "!", ".”", ".\"", "?”", "!”", ".)", ":")
# Judul bagian yang dilewati harus berupa judul utuh: "Lampiran: 1 berkas" pada surat bukan judul.
DAFTAR_DEPAN = re.compile(r"^DAFTAR (ISI|TABEL|GAMBAR|LAMPIRAN|SINGKATAN|SIMBOL)$", re.I)
DAFTAR_BELAKANG = re.compile(
    r"^(DAFTAR (PUSTAKA|REFERENSI)|REFERENSI|BIBLIOGRAFI|REFERENCES|BIBLIOGRAPHY|LAMPIRAN(-LAMPIRAN)?)$", re.I)
JUDUL_LAMPIRAN = re.compile(r"^(?i:lampiran)\s+(\d+|[A-Z]|[IVXLC]+)(\s*[:.\-–]?\s+[A-Z].*)?$")
JUDUL_LANJUT = re.compile(
    r"^(BAB\s+[IVXLC\d]+|((\d+|[A-Z]|[IVXLC]+)[.)]?\s+)?(KATA PENGANTAR|ABSTRAK|ABSTRACT|PENDAHULUAN))\b", re.I)
# Tanda bahwa baris pendek tanpa titik adalah kalimat, bukan judul.
PREDIKAT = re.compile(r"\b(adalah|merupakan|tidak|dapat|akan|telah|sudah|sedang|harus|perlu|di[a-z]{3,}kan)\b")
KETERANGAN = re.compile(r"^(Gambar|Tabel|Grafik|Diagram|Bagan|Lampiran|Sumber)\s*\d", re.I)
NOMOR_HALAMAN = re.compile(r"^\s*(\d{1,4}|[ivxlcdm]{1,7})\s*$", re.I)


@dataclass
class Paragraf:
    teks: str
    halaman: list = field(default_factory=list)   # [(offset_karakter, nomor_halaman), ...]
    gaya: str = ""                                 # nama gaya (DOCX) atau ""
    judul: bool = False                            # ditandai sebagai judul oleh dokumennya

    def halaman_di(self, offset):
        hal = None
        for off, h in self.halaman:
            if off <= offset:
                hal = h
        return hal


@dataclass
class Kalimat:
    teks: str
    halaman: object          # int, (awal, akhir), atau None
    paragraf: int


# --------------------------------------------------------------------------- pembersih
def bersihkan(teks):
    teks = teks.replace("­", "").replace(" ", " ").replace("\t", " ")
    teks = re.sub(r"[  -​]+", " ", teks)
    return teks.strip()


def sambung_baris(a, b):
    """Menyambung dua baris; menangani kata yang terpotong tanda hubung di akhir baris."""
    if not a:
        return b
    if a.endswith("-") and b[:1].islower():
        kiri = re.search(r"(\w+)-$", a)
        kanan = re.match(r"(\w+)", b)
        if kiri and kanan:
            gabung = (kiri.group(1) + kanan.group(1)).lower()
            if gabung in LEKSIKON.frek and (kiri.group(1) + "-" + kanan.group(1)).lower() not in LEKSIKON.frek:
                return a[:-1] + b                  # pengem- bangan -> pengembangan
        return a + b                               # sehari- hari -> sehari-hari
    return a + " " + b


def bahasa_asing(teks):
    kata = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", teks)]
    if len(kata) < 6:
        return False
    kenal = sum(w in LEKSIKON.frek for w in kata)
    return kenal / len(kata) < 0.45


def kalimat_tanpa_titik(t, kata):
    """Kalimat pendek yang titiknya hilang. Sengaja ketat: judul yang lolos akan ditandai kurang titik."""
    if len(kata) < 5 or not t[:1].isupper() or re.match(r"(\d+(\.\d+)*|[A-Za-z])[.)]\s", t):
        return False
    return sum(w[:1].isupper() for w in kata[1:]) <= 1 and PREDIKAT.search(t.lower()) is not None


def layak_diperiksa(p):
    """Mengembalikan None jika paragraf layak diperiksa, atau alasan dilewati."""
    t = p.teks
    kata = t.split()
    if not kata:
        return "kosong"
    if p.judul:
        return "judul"
    if re.search(r"\.{4,}|…{2,}", t):
        return "daftar isi"
    if KETERANGAN.match(t):
        return "keterangan gambar/tabel"
    huruf = sum(c.isalpha() for c in t)
    if huruf < 0.6 * len(t.replace(" ", "")):
        return "tabel/angka"
    salam = len(kata) <= 4 and t.rstrip().endswith(",") and t[:1].isalpha()   # Dengan hormat, / Hormat saya,
    if not salam and (len(kata) < 4 or (len(kata) < 10 and not t.rstrip().endswith(AKHIR_KALIMAT)
                                        and not kalimat_tanpa_titik(t, kata))):
        return "judul"
    if t.isupper():
        return "judul"
    if bahasa_asing(t):
        return "bahasa asing"
    return None


def jenis_daftar(t):
    """"depan" (daftar isi dkk.), "belakang" (daftar pustaka, lampiran), atau None jika bukan judulnya."""
    if len(t.split()) > 6:
        return None
    t = t.rstrip(" .:")
    if DAFTAR_DEPAN.match(t):
        return "depan"
    if DAFTAR_BELAKANG.match(t) or JUDUL_LAMPIRAN.match(t):
        return "belakang"
    return None


def kalimat_isi(t):
    return (len(t.split()) >= 10 and t.endswith((".", "?", "!")) and not KETERANGAN.match(t)
            and not re.search(r"\.{4,}|…{2,}", t))


def saring_bagian(paragraf):
    """Membuang daftar isi (sampai kalimat isi pertama atau judul bab) dan daftar pustaka/lampiran
    (sampai judul bab berikutnya)."""
    hasil, lewati, dilewati = [], None, Counter()
    for p in paragraf:
        t = p.teks.strip()
        jenis = jenis_daftar(t)
        if jenis:
            lewati = jenis
        elif (len(t.split()) <= 8 and JUDUL_LANJUT.match(t)) or (lewati == "depan" and kalimat_isi(t)):
            lewati = None
        if lewati:
            dilewati["daftar pustaka/daftar isi"] += 1
            continue
        alasan = layak_diperiksa(p)
        if alasan:
            dilewati[alasan] += 1
            continue
        hasil.append(p)
    return hasil, dilewati


# --------------------------------------------------------------------------- PDF
def baca_pdf(path):
    import pymupdf

    doc = pymupdf.open(path)
    if doc.needs_pass:
        raise ValueError("PDF dilindungi kata sandi.")
    baris_semua = []      # (halaman, x0, y0, x1, y1, ukuran, teks, tebal)
    ukuran = Counter()
    label_halaman = {}    # nomor halaman PDF -> nomor yang tercetak di halaman (mis. "xiv", "12")
    for no, page in enumerate(doc, start=1):
        tinggi = page.rect.height
        try:
            if page.get_label():
                label_halaman[no] = page.get_label()
        except Exception:
            pass
        for blok in page.get_text("dict", sort=True)["blocks"]:
            for ln in blok.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip() or s["text"] == " "]
                if not spans:
                    continue
                besar = max(s["size"] for s in spans)
                # buang angka superskrip (nomor catatan kaki di dalam kalimat)
                teks = "".join(s["text"] for s in spans
                               if not (s["flags"] & 1 and s["text"].strip().isdigit())
                               and not (s["size"] < 0.7 * besar and s["text"].strip().isdigit()))
                teks = bersihkan(teks)
                if not teks:
                    continue
                x0, y0, x1, y1 = ln["bbox"]
                if NOMOR_HALAMAN.match(teks):
                    if (y0 < 0.12 * tinggi or y1 > 0.88 * tinggi) and no not in label_halaman:
                        label_halaman[no] = teks.strip()
                    continue
                tebal = all(s["flags"] & 16 for s in spans)
                baris_semua.append((no, x0, y0, x1, y1, round(besar, 1), teks, tebal))
                ukuran[round(besar, 1)] += len(teks)
    jumlah_halaman = doc.page_count
    doc.close()
    if not baris_semua:
        raise ValueError("PDF tidak berisi teks yang bisa dibaca (kemungkinan hasil pindai/scan).")

    ukuran_isi = ukuran.most_common(1)[0][0]
    isi = [b for b in baris_semua if b[5] >= ukuran_isi - 1.0]          # buang catatan kaki
    kiri = Counter(round(b[1]) for b in isi).most_common(1)[0][0]       # margin kiri teks isi
    kanan = sorted(b[3] for b in isi)[int(0.9 * len(isi))]              # tepi kanan umum

    paragraf, cur, prev = [], None, None
    for b in isi:
        no, x0, y0, x1, y1, besar, teks, tebal = b
        mulai_baru = cur is None
        if prev is not None and not mulai_baru:
            pno, px0, py0, px1, py1, pbesar, pteks, ptebal = prev
            jarak = y0 - py1 if no == pno else 0
            akhir = pteks.rstrip().endswith(AKHIR_KALIMAT)
            if no == pno and jarak > 1.2 * (py1 - py0):
                mulai_baru = True                                         # spasi antarparagraf
            elif x0 > kiri + 15 and akhir:
                mulai_baru = True                                         # baris menjorok
            elif akhir and px1 < kanan - 40:
                mulai_baru = True                                         # baris terakhir paragraf
            elif tebal != ptebal or abs(besar - pbesar) > 0.6:
                mulai_baru = True                                         # judul
            elif no != pno and teks[:1].isupper() and akhir:
                mulai_baru = True
        if mulai_baru:
            if cur:
                paragraf.append(cur)
            cur = Paragraf(teks=teks, halaman=[(0, no)])
        else:
            if cur.halaman[-1][1] != no:
                cur.halaman.append((len(cur.teks) + 1, no))
            cur.teks = sambung_baris(cur.teks, teks)
        prev = b
    if cur:
        paragraf.append(cur)
    return paragraf, jumlah_halaman, label_halaman


# --------------------------------------------------------------------------- DOCX
def baca_docx(path):
    import docx
    from docx.oxml.ns import qn

    BR, LRPB, T = qn("w:br"), qn("w:lastRenderedPageBreak"), qn("w:t")
    d = docx.Document(path)
    paragraf, halaman, ada_info_halaman = [], 1, False
    for par in d.paragraphs:
        p = par._p
        sebelum_teks, total, sudah_teks = 0, 0, False
        ppr = p.pPr
        if ppr is not None and ppr.find(qn("w:pageBreakBefore")) is not None:
            sebelum_teks += 1; total += 1
        for el in p.iter():
            if el.tag == T and (el.text or "").strip():
                sudah_teks = True
            elif el.tag == LRPB or (el.tag == BR and el.get(qn("w:type")) == "page"):
                total += 1
                if not sudah_teks:
                    sebelum_teks += 1
        if total:
            ada_info_halaman = True
        teks = bersihkan(par.text)
        gaya = ((par.style.name if par.style is not None else "") or "").lower()
        if teks:
            judul = any(x in gaya for x in ("heading", "judul", "title", "toc", "caption", "keterangan"))
            paragraf.append(Paragraf(teks=teks, halaman=[(0, halaman + sebelum_teks)], gaya=gaya, judul=judul))
        halaman += total
    if not ada_info_halaman:
        for p in paragraf:
            p.halaman = []
    return paragraf, (halaman if ada_info_halaman else None), {}


# --------------------------------------------------------------------------- TXT / MD
def baca_teks(teks):
    """Teks polos atau Markdown: paragraf dipisah baris kosong."""
    teks = teks.replace("\r\n", "\n")
    paragraf = []
    for blok in re.split(r"\n\s*\n", teks):
        baris = [re.sub(r"^\s{0,3}(#{1,6}\s+|>\s?|[-*+]\s+(?=\S))", "", b).strip() for b in blok.split("\n")]
        judul = blok.lstrip().startswith("#")                  # judul markdown
        isi = ""
        for b in baris:
            if b:
                isi = sambung_baris(isi, bersihkan(b))
        isi = re.sub(r"(\*\*|__|\*|_|`)(\S.*?\S|\S)\1", r"\2", isi)  # **tebal**, *miring*
        if isi:
            paragraf.append(Paragraf(teks=isi, judul=judul))
    return paragraf, None, {}


def baca_dokumen(path, nama=None):
    nama = (nama or str(path)).lower()
    if nama.endswith(".pdf"):
        return baca_pdf(path)
    if nama.endswith(".docx"):
        return baca_docx(path)
    if nama.endswith((".txt", ".md", ".markdown")):
        raw = Path(path).read_bytes()
        # UTF-16 hanya jika ada BOM; tanpa itu, teks ANSI berpanjang genap terbaca sebagai huruf acak.
        bom16 = raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
        for enc in ("utf-16",) if bom16 else ("utf-8-sig", "cp1252"):
            try:
                return baca_teks(raw.decode(enc))
            except UnicodeDecodeError:
                continue
        raise ValueError("Berkas teks tidak bisa dibaca (encoding tidak dikenal).")
    if nama.endswith(".doc"):
        raise ValueError("Format .doc lama belum didukung. Simpan ulang sebagai .docx di Word.")
    raise ValueError("Format belum didukung. Gunakan PDF, DOCX, TXT, atau MD.")


# --------------------------------------------------------------------------- kalimat
SINGKATAN = {
    "dkk", "dll", "dsb", "dst", "hlm", "no", "yth", "sdr", "sdri", "dr", "drs", "dra", "prof", "ir",
    "h", "hj", "st", "tn", "ny", "kol", "jl", "vol", "ed", "cet", "terj", "pp", "hal", "et", "al",
    "kab", "kec", "kel", "prov", "tbk", "swt", "saw", "as", "ra", "pt", "cv", "a.n", "u.p", "s.d",
    "m.pd", "s.pd", "s.kom", "m.kom", "s.h", "m.h", "s.e", "m.m", "s.t", "m.t", "s.si", "ph.d",
    "nim", "nip", "nidn", "npm", "nis", "telp", "hp", "fax", "lt", "rt", "rw", "gg", "sd", "dsn",
}
# Jika ditulis kapital semua, ini akronim yang bisa mengakhiri kalimat (dari AS. / siswa SD.).
AKRONIM_AKHIR = {"as", "sd", "hp", "rt", "rw"}
PEMISAH = re.compile(r"(?<=[.?!])([”\"')\]]*)\s+(?=[“\"'(\[]?[A-Z0-9])")


def pecah_kalimat(teks):
    hasil, mulai = [], 0
    for m in PEMISAH.finditer(teks):
        sebelum = teks[mulai:m.start()]
        kata_akhir = re.search(r"([\w.]+)\.$", sebelum)
        if kata_akhir:
            k = kata_akhir.group(1).lower()
            akronim = (k in AKRONIM_AKHIR and kata_akhir.group(1).isupper()
                       and not teks[m.end()].isdigit())           # RT. 05 tetap singkatan
            if (k in SINGKATAN and not akronim) or (len(k) == 1 and k.isalpha()) or re.fullmatch(r"(\w\.)+\w", k):
                continue                                   # singkatan atau inisial nama
            if re.fullmatch(r"\d+", k) and len(sebelum.split()) <= 1:
                continue                                   # penomoran "1."
        akhir = m.end(1)
        hasil.append((mulai, teks[mulai:akhir].strip()))
        mulai = m.end()
    if teks[mulai:].strip():
        hasil.append((mulai, teks[mulai:].strip()))
    return hasil


def ke_kalimat(paragraf):
    kalimat = []
    for i, p in enumerate(paragraf):
        for off, k in pecah_kalimat(p.teks):
            if len(k.split()) < 3 and not (len(k.split()) == 2 and k.endswith(",")):
                continue
            h1 = p.halaman_di(off)
            h2 = p.halaman_di(off + len(k) - 1)
            hal = h1 if h1 == h2 else (h1, h2)
            kalimat.append(Kalimat(teks=k, halaman=hal, paragraf=i + 1))
    return kalimat


def ekstrak(path, nama=None):
    """Mengembalikan (daftar Kalimat, info)."""
    paragraf, jumlah_halaman, label_halaman = baca_dokumen(path, nama)
    diperiksa, dilewati = saring_bagian(paragraf)
    kalimat = ke_kalimat(diperiksa)
    info = {"jumlah_halaman": jumlah_halaman, "paragraf_total": len(paragraf),
            "paragraf_diperiksa": len(diperiksa), "dilewati": dict(dilewati),
            "kalimat": len(kalimat), "ada_halaman": jumlah_halaman is not None,
            "label_halaman": {str(k): v for k, v in label_halaman.items()}}
    return kalimat, info
