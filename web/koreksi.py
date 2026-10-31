"""
koreksi.py
Memeriksa kalimat dengan model, lalu menyusun saran perbaikan dan versi benar setiap kalimat.

Model hanya menandai jenis kesalahan per kata. Bentuk benarnya disusun di sini dengan aturan:
kamus tidak baku, saran ejaan (SymSpell), pemecahan/penggabungan kata, huruf kapital, tanda baca,
dan format angka.
"""
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from buat_dataset import SERANGKAI, TERPISAH  # noqa: E402
from kamus_baku import KAMUS_PERIKSA, TIDAK_BAKU  # noqa: E402

from leksikon import LEKSIKON  # noqa: E402

PENJELASAN = {
    "TYPO": "Salah ketik",
    "TIDAK_BAKU": "Kata tidak baku",
    "KAPITAL": "Seharusnya diawali huruf kapital",
    "HURUF_KECIL": "Seharusnya huruf kecil",
    "TAMBAH_KOMA": "Perlu tanda koma",
    "TAMBAH_TITIK": "Perlu tanda titik",
    "HAPUS": "Tanda baca/kata ini sebaiknya dihapus",
    "PISAH": "Seharusnya ditulis terpisah",
    "GABUNG": "Seharusnya ditulis serangkai",
    "FORMAT_ANGKA": "Format angka (desimal memakai koma, ribuan memakai titik, jam memakai titik)",
    "GANTI_TITIK": "Dua kalimat disambung koma; ganti dengan titik",
}
BATAS_YAKIN = 0.70
SINGKATAN_TITIK = {"dkk.", "dll.", "dsb.", "dst.", "hlm.", "tbk.", "swt.", "yth.", "sdr."}
TANPA_TITIK = {s[:-1] for s in SINGKATAN_TITIK}
DEPAN = "([{“\"'‘"
BELAKANG = ",.;:?!)]}”\"'’"
PECAH_TERPISAH = {a + b: f"{a} {b}" for a, b in TERPISAH}
GABUNG_SERANGKAI = {f"{a} {b}".lower(): k for k, (a, b) in SERANGKAI.items()}


# --------------------------------------------------------------------------- token
def tokenisasi(kalimat):
    """Memecah kalimat menjadi token beserta posisinya: [(teks, awal, akhir), ...]."""
    hasil = []
    for m in re.finditer(r"\S+", kalimat):
        chunk, s = m.group(), m.start()
        depan, belakang = [], []
        while len(chunk) > 1 and chunk[0] in DEPAN:
            depan.append((chunk[0], s, s + 1)); chunk = chunk[1:]; s += 1
        e = s + len(chunk)
        while len(chunk) > 1 and chunk[-1] in BELAKANG and chunk.lower() not in SINGKATAN_TITIK:
            belakang.insert(0, (chunk[-1], e - 1, e)); chunk = chunk[:-1]; e -= 1
        hasil += depan + [(chunk, s, e)] + belakang
    return hasil


def samakan_kapital(baru, lama):
    if lama.isupper() and len(lama) > 1:
        return baru.upper()
    if lama[:1].isupper():
        return baru[:1].upper() + baru[1:]
    return baru


def huruf_awal_kapital(kata):
    for i, c in enumerate(kata):
        if c.isalpha():
            return kata[:i] + c.upper() + kata[i + 1:]
    return kata


# --------------------------------------------------------------------------- saran per label
def saran_ejaan(kata):
    asing = LEKSIKON.bentuk_asing(kata)              # mengupload -> meng-upload
    if asing:
        return samakan_kapital(asing, kata)
    s = LEKSIKON.saran(kata)
    return samakan_kapital(s[0], kata) if s else None


def saran_tidak_baku(kata):
    k = kata.lower()
    baku = KAMUS_PERIKSA.get(k) or TIDAK_BAKU.get(k)
    if baku:
        return samakan_kapital(baku, kata)
    return saran_ejaan(kata)


def saran_pisah(kata):
    k = kata.lower()
    if k in PECAH_TERPISAH:
        return samakan_kapital(PECAH_TERPISAH[k], kata)
    for awal in ("di", "ke"):
        sisa = k[len(awal):]
        if k.startswith(awal) and len(sisa) >= 3:
            if sisa in PECAH_TERPISAH:                  # dimanapun -> di mana pun
                return samakan_kapital(f"{awal} {PECAH_TERPISAH[sisa]}", kata)
            if LEKSIKON.kenal(sisa):
                return samakan_kapital(f"{awal} {sisa}", kata)
    terbaik, skor = None, 0
    for i in range(2, len(k) - 1):
        a, b = k[:i], k[i:]
        fa, fb = LEKSIKON.frek.get(a, 0), LEKSIKON.frek.get(b, 0)
        if fa >= 2 and fb >= 2 and fa * fb > skor:
            terbaik, skor = f"{a} {b}", fa * fb
    return samakan_kapital(terbaik, kata) if terbaik else None


def saran_gabung(bagian):
    """bagian: daftar kata yang harus digabung, mis. ["di", "lakukan"]."""
    teks = " ".join(bagian).lower()
    awal, sisa = bagian[0].lower(), "".join(bagian[1:]).lower()
    if teks in GABUNG_SERANGKAI:
        hasil = GABUNG_SERANGKAI[teks]
    elif len(bagian) == 2 and len(awal) >= 3 and (sisa == awal or sisa.endswith(awal[1:])):
        hasil = f"{awal}-{sisa}"                            # kata ulang: kelompok kelompok
    else:
        hasil = "".join(bagian).lower()
        if (awal in ("di", "ke", "meng", "me", "ter", "ber") and not LEKSIKON.kenal(hasil)
                and LEKSIKON.kenal(sisa) and sisa not in LEKSIKON.dasar and sisa.isalpha()
                and not sisa.endswith(("kan", "an", "i", "nya"))):
            hasil = f"{awal}-{sisa}"                        # imbuhan + kata asing: di-update
        if hasil in KAMUS_PERIKSA:                          # di analisa -> dianalisis
            hasil = KAMUS_PERIKSA[hasil]
    bentuk = LEKSIKON.bentuk_tulis(hasil)                   # Tik Tok -> TikTok
    if bentuk and bentuk.lower() == hasil:
        return bentuk
    return samakan_kapital(hasil, bagian[0])


def saran_angka(t):
    if re.fullmatch(r"\d{1,2}:\d{2}", t):
        return t.replace(":", ".")                          # 08:00 -> 08.00
    if re.fullmatch(r"(Rp)?\d{1,3}(,\d{3})+(\.\d+)?", t):
        return t.replace(",", "#").replace(".", ",").replace("#", ".")   # 12,500.50 -> 12.500,50
    if re.fullmatch(r"(Rp)?\d+\.\d+%?", t) and not re.fullmatch(r"(Rp)?\d{1,3}(\.\d{3})+", t):
        return t.replace(".", ",")                          # 0.05 -> 0,05
    return None


# --------------------------------------------------------------------------- satu kalimat
def susun_temuan(kalimat, token, label, frek_dok):
    """Mengubah label model menjadi daftar suntingan dan temuan."""
    n = len(token)
    edit = {}           # i -> ("ganti", teks) | ("sisip", tanda) | ("hapus",) | ("gabung", j, teks)
    temuan = []
    lewati = set()

    def catat(i, lab, saran, peluang, j=None):
        a, b = token[i][1], token[j if j is not None else i][2]
        temuan.append({"awal": a, "akhir": b, "teks": kalimat[a:b], "label": lab,
                       "penjelasan": PENJELASAN.get(lab, lab), "saran": saran,
                       "peluang": round(peluang, 3), "yakin": peluang >= BATAS_YAKIN})

    for i, (t, s, e) in enumerate(token):
        if i in lewati:
            continue
        lab, p = label[i]
        if t.lower() in KAMUS_PERIKSA and not t.isupper():
            lab, p = "TIDAK_BAKU", 1.0                      # kamus selalu menang
        if lab == "O":
            continue

        if lab == "TYPO":
            if not re.search(r"[^\W\d_]", t) or any(c.isdigit() for c in t) or (t.isupper() and len(t) > 1):
                continue                                    # angka, singkatan
            saran = saran_ejaan(t)
            tengah = i > 0 and t[:1].isupper()
            if saran is None and (tengah or frek_dok[t] >= 3):
                continue                                    # kemungkinan nama/istilah
            if saran:
                edit[i] = ("ganti", saran)
            catat(i, lab, saran, p)

        elif lab == "TIDAK_BAKU":
            saran = saran_tidak_baku(t)
            if saran and saran != t:
                edit[i] = ("ganti", saran)
            catat(i, lab, saran, p)

        elif lab == "KAPITAL":
            bentuk = LEKSIKON.bentuk_tulis(t)
            saran = bentuk if bentuk and bentuk != t and bentuk.lower() == t.lower() else huruf_awal_kapital(t)
            if saran == t:
                continue
            edit[i] = ("ganti", saran)
            catat(i, lab, saran, p)

        elif lab == "HURUF_KECIL":
            if not t[:1].isupper() or i == 0:
                continue
            saran = t[:1].lower() + t[1:]
            edit[i] = ("ganti", saran)
            catat(i, lab, saran, p)

        elif lab in ("TAMBAH_KOMA", "TAMBAH_TITIK"):
            tanda = "," if lab == "TAMBAH_KOMA" else "."
            if i + 1 < n and token[i + 1][0] in (",", ".", ";", ":"):
                continue
            if lab == "TAMBAH_TITIK" and t.lower() in TANPA_TITIK:
                edit[i] = ("ganti", t + ".")
            else:
                edit[i] = ("sisip", tanda)
            catat(i, lab, t + tanda, p)

        elif lab == "HAPUS":
            edit[i] = ("hapus",)
            catat(i, lab, "", p)

        elif lab == "PISAH":
            saran = saran_pisah(t)
            if saran:
                edit[i] = ("ganti", saran)
            catat(i, lab, saran, p)

        elif lab == "GABUNG":
            j = i                                           # GABUNG = gabung dengan token berikutnya
            while j + 1 < n and (j == i or label[j][0] == "GABUNG") and token[j + 1][0][:1].isalnum():
                j += 1
            if j == i:
                continue
            saran = saran_gabung([token[k][0] for k in range(i, j + 1)])
            edit[i] = ("gabung", j, saran)
            lewati.update(range(i + 1, j + 1))
            catat(i, lab, saran, p, j)

        elif lab == "FORMAT_ANGKA":
            saran = saran_angka(t)
            if saran is None:
                continue
            edit[i] = ("ganti", saran)
            catat(i, lab, saran, p)

        elif lab == "GANTI_TITIK":
            if t != ",":
                continue
            edit[i] = ("ganti", ".")
            catat(i, lab, ".", p)
            k = i + 1
            if k < n and token[k][0][:1].islower() and k not in edit:
                edit[k] = ("ganti", huruf_awal_kapital(token[k][0]))
    return edit, temuan


def rakit(kalimat, token, edit):
    """Menyusun kalimat benar dari suntingan. Mengembalikan (teks, [(awal, akhir), ...] yang berubah)."""
    keluar, sorot, akhir_sblm, i = "", [], 0, 0
    while i < len(token):
        t, s, e = token[i]
        jarak = kalimat[akhir_sblm:s]
        ed = edit.get(i)
        if ed is None:
            keluar += jarak + t
        elif ed[0] == "hapus":
            pass                                            # buang token beserta spasi sebelumnya
        elif ed[0] == "ganti":
            keluar += jarak
            sorot.append((len(keluar), len(keluar) + len(ed[1]))); keluar += ed[1]
        elif ed[0] == "sisip":
            keluar += jarak + t
            sorot.append((len(keluar), len(keluar) + len(ed[1]))); keluar += ed[1]
        elif ed[0] == "gabung":
            keluar += jarak
            sorot.append((len(keluar), len(keluar) + len(ed[2]))); keluar += ed[2]
            e = token[ed[1]][2]
            i = ed[1]
        akhir_sblm = e
        i += 1
    keluar += kalimat[akhir_sblm:]
    # rapikan spasi di awal (jika token pertama dihapus) dan spasi ganda
    geser = len(keluar) - len(keluar.lstrip())
    keluar = keluar.lstrip()
    sorot = [(a - geser, b - geser) for a, b in sorot]
    return keluar, sorot


# --------------------------------------------------------------------------- dokumen
def periksa_dokumen(kalimat, pemeriksa, progres=None, batch=64):
    """kalimat: daftar ekstrak.Kalimat. Mengembalikan daftar hasil per kalimat yang berkesalahan."""
    token = [tokenisasi(k.teks) for k in kalimat]
    frek_dok = Counter(t for tk in token for t, _, _ in tk)
    hasil = []
    for mulai in range(0, len(kalimat), batch):
        bagian = token[mulai:mulai + batch]
        label = pemeriksa.prediksi([[t for t, _, _ in tk] for tk in bagian])
        for k, tk, lab in zip(kalimat[mulai:mulai + batch], bagian, label):
            edit, temuan = susun_temuan(k.teks, tk, lab, frek_dok)
            if not temuan:
                continue
            benar, sorot = rakit(k.teks, tk, edit)
            hal = list(k.halaman) if isinstance(k.halaman, tuple) else k.halaman
            hasil.append({"halaman": hal, "paragraf": k.paragraf, "kalimat": k.teks,
                          "benar": benar, "sorot_benar": sorot, "temuan": temuan})
        if progres:
            progres(min(mulai + batch, len(kalimat)), len(kalimat))
    return hasil
