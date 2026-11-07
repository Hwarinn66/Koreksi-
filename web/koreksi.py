"""
koreksi.py
Memeriksa kalimat dengan model, lalu menyusun saran perbaikan dan versi benar setiap kalimat.

Model hanya menandai jenis kesalahan per kata. Bentuk benarnya disusun di sini dengan aturan:
kamus tidak baku, saran ejaan (SymSpell, istilah asing, dan konteks kalimat), pemecahan/penggabungan
kata, huruf kapital, tanda baca, dan format angka.
"""
import math
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from buat_dataset import SERANGKAI, TERPISAH  # noqa: E402
from kamus_baku import KAMUS_PERIKSA, TIDAK_BAKU, kena_kamus  # noqa: E402

from leksikon import LEKSIKON, bentukan, jarak_dl  # noqa: E402

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
# Kata ulang berubah bunyi yang belum tentu ada di leksikon.
KATA_ULANG_BERUBAH = {"sayur-mayur", "lauk-pauk", "ramah-tamah", "gerak-gerik", "warna-warni", "hiruk-pikuk",
                      "porak-poranda", "compang-camping", "mondar-mandir", "desas-desus", "serba-serbi"}
# Angka setelah kata ini bukan desimal (Gambar 4.1, pukul 08.00).
BUKAN_DESIMAL_SETELAH = {"gambar", "tabel", "grafik", "diagram", "bagan", "bab", "subbab", "persamaan", "rumus",
                         "lampiran", "bagian", "pasal", "versi", "pukul", "jam"}
# Penilaian calon saran. Bobotnya dipilih pada dokumen pengembangan (lihat data_uji_asli/alat/uji_saran.py).
BOBOT_JARAK = 4
PENALTI_RAKITAN = 2
MAKS_CALON = 15
SELISIH_RAGU = 1.0          # calon pertama dan kedua hampir sama kuat: tetap disarankan, tetapi "perlu dicek"
BUKAN_SALAH = object()      # kata ini sah dan tidak ada calon yang lebih cocok: tanda dari model keliru


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


def saran_konteks(kata, kata_kalimat, i, konteks, harus_diganti=False):
    """Memilih saran ejaan menurut kalimatnya. Mengembalikan (saran, yakin).

    saran = BUKAN_SALAH: kata ini sah dan tidak ada calon yang lebih cocok.
    saran = None: kata tidak dikenal, tetapi tidak ada calon yang cukup kuat untuk disarankan.
    harus_diganti: model sudah menilai bentuk ini tidak baku, jadi calon terbaik tetap disarankan.
    """
    asing = LEKSIKON.bentuk_asing(kata)
    if asing:
        return samakan_kapital(asing, kata), True
    k = kata.lower()
    sah = LEKSIKON.kenal(k) or bentukan(k, LEKSIKON.dasar, min_inti=5)
    calon = LEKSIKON.calon(kata)
    pilih = LEKSIKON.urutkan(k, calon)[:MAKS_CALON]
    skor = konteks.skor(kata_kalimat, i, pilih + [k]) if pilih else {}
    # Kata rakitan yang tidak ada di kamus tidak mewarisi frekuensi kata dasarnya (info + an bukan kata lazim).
    nilai = {c: skor[c] - BOBOT_JARAK * calon[c][0] + (math.log10(calon[c][1] + 1) if LEKSIKON.kenal(c) else -PENALTI_RAKITAN)
             for c in pilih if c in skor}
    if not nilai:
        return (BUKAN_SALAH if sah else None), True
    urut = sorted(nilai, key=nilai.get, reverse=True)
    terbaik = urut[0]
    skor_asli = skor.get(k, -30.0)
    keunggulan = nilai[terbaik] - (skor_asli + math.log10(LEKSIKON.frek.get(k, 0) + 1))
    if keunggulan < 0:
        if sah:
            return BUKAN_SALAH, True
        # Istilah bidang sering dinilai rendah oleh model, jadi kata panjang yang hampir sama, atau
        # istilah asing yang sama bunyinya (jarak 0,5), tetap dipercaya.
        beda = jarak_dl(k, terbaik) / len(k)
        if not (harus_diganti or calon[terbaik][0] == 0.5 or (len(k) >= 7 and beda <= 0.2)
                or (len(k) >= 7 and beda <= 0.3 and skor[terbaik] >= skor_asli + 1)):
            return None, True
    ragu = keunggulan < 0 or (len(urut) > 1 and nilai[terbaik] - nilai[urut[1]] < SELISIH_RAGU)
    return samakan_kapital(terbaik, kata), not ragu


def saran_tidak_baku(kata, kata_kalimat=None, i=None, konteks=None):
    k = kata.lower()
    baku = KAMUS_PERIKSA.get(k) or TIDAK_BAKU.get(k)
    if baku:
        return samakan_kapital(baku, kata), True
    if konteks:
        return saran_konteks(kata, kata_kalimat, i, konteks, harus_diganti=True)
    return saran_ejaan(kata), True


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


def kata_ulang(awal, sisa):
    """kelompok kelompok, tumbuh tumbuhan, sayur mayur; bukan ada pada."""
    bentuk = f"{awal}-{sisa}"
    return (len(awal) >= 3 and (sisa in (awal, awal + "an", awal + "nya") or bentuk in LEKSIKON.frek
                                or bentuk in KATA_ULANG_BERUBAH))


def saran_gabung(bagian):
    """bagian: daftar kata yang harus digabung, mis. ["di", "lakukan"]."""
    teks = " ".join(bagian).lower()
    awal, sisa = bagian[0].lower(), "".join(bagian[1:]).lower()
    if teks in GABUNG_SERANGKAI:
        hasil = GABUNG_SERANGKAI[teks]
    elif len(bagian) == 2 and kata_ulang(awal, sisa):
        hasil = f"{awal}-{sisa}"
    else:
        hasil = "".join(bagian).lower()
        if (awal in ("di", "ke", "meng", "me", "ter", "ber") and not LEKSIKON.kenal(hasil)
                and LEKSIKON.kata_asing(sisa) and sisa.isalpha()
                and not sisa.endswith(("kan", "an", "i", "nya"))):
            hasil = f"{awal}-{sisa}"                        # imbuhan + kata asing: di-update
        if hasil in KAMUS_PERIKSA:                          # di analisa -> dianalisis
            hasil = KAMUS_PERIKSA[hasil]
    bentuk = LEKSIKON.bentuk_tulis(hasil)                   # Tik Tok -> TikTok
    if bentuk and bentuk.lower() == hasil:
        return bentuk
    return samakan_kapital(hasil, bagian[0])


def saran_angka(t, sebelum=()):
    """sebelum: token sebelum angka ini dalam kalimat, huruf kecil. None jika angkanya tidak perlu diubah."""
    jam = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
    if jam:                                                 # 08:00 -> 08.00; 1:10 tanpa "pukul" adalah rasio
        sah = int(jam[1]) < 24 and int(jam[2]) < 60
        return t.replace(":", ".") if sah and (len(jam[1]) == 2 or {"pukul", "jam"} & set(sebelum)) else None
    if re.fullmatch(r"(Rp)?[1-9]\d{0,2}(,\d{3})+(\.\d+)?", t):   # 0,812 sudah desimal yang benar
        return t.replace(",", "#").replace(".", ",").replace("#", ".")   # 12,500.50 -> 12.500,50
    if re.fullmatch(r"(Rp)?\d+\.\d+%?", t) and not re.fullmatch(r"(Rp)?\d{1,3}(\.\d{3})+", t):
        if sebelum and sebelum[-1] in BUKAN_DESIMAL_SETELAH:
            return None
        return t.replace(".", ",")                          # 0.05 -> 0,05
    return None


# --------------------------------------------------------------------------- satu kalimat
def susun_temuan(kalimat, token, label, frek_dok, konteks=None):
    """Mengubah label model menjadi daftar temuan.

    Setiap temuan membawa suntingannya sendiri (posisi pada kalimat asli), supaya kalimat benar bisa
    disusun hanya dari temuan yang dipilih. Suntingan "kapital" hanya menaikkan huruf awal kata.
    konteks: objek konteks.Konteks untuk memilih saran ejaan menurut kalimatnya (boleh None).
    """
    n = len(token)
    temuan = []
    lewati = set()
    kata_kalimat = [x[0] for x in token]

    def catat(i, lab, saran, peluang, suntingan, j=None, yakin=True):
        a, b = token[i][1], token[j if j is not None else i][2]
        temuan.append({"awal": a, "akhir": b, "teks": kalimat[a:b], "label": lab,
                       "penjelasan": PENJELASAN.get(lab, lab), "saran": saran,
                       "peluang": round(peluang, 3), "yakin": yakin and peluang >= BATAS_YAKIN,
                       "suntingan": suntingan})

    def ganti(i, teks):
        return [{"awal": token[i][1], "akhir": token[i][2], "teks": teks}]

    for i, (t, s, e) in enumerate(token):
        if i in lewati:
            continue
        lab, p = label[i]
        if kena_kamus(t, i):
            lab, p = "TIDAK_BAKU", 1.0                      # kamus selalu menang
        if lab == "O":
            continue

        if lab == "TYPO":
            if not re.search(r"[^\W\d_]", t) or any(c.isdigit() for c in t) or (t.isupper() and len(t) > 1):
                continue                                    # angka, singkatan
            saran, yakin = saran_konteks(t, kata_kalimat, i, konteks) if konteks else (saran_ejaan(t), True)
            if saran is BUKAN_SALAH:
                continue
            tengah = i > 0 and t[:1].isupper()
            if saran is None and (tengah or frek_dok[t] >= 3):
                continue                                    # kemungkinan nama/istilah
            catat(i, lab, saran, p, ganti(i, saran) if saran else [], yakin=yakin)

        elif lab == "TIDAK_BAKU":
            saran, yakin = saran_tidak_baku(t, kata_kalimat, i, konteks)
            if saran is BUKAN_SALAH:
                continue
            catat(i, lab, saran, p, ganti(i, saran) if saran and saran != t else [], yakin=yakin)

        elif lab == "KAPITAL":
            bentuk = LEKSIKON.bentuk_tulis(t)
            saran = bentuk if bentuk and bentuk != t and bentuk.lower() == t.lower() else huruf_awal_kapital(t)
            if saran == t:
                continue
            catat(i, lab, saran, p, ganti(i, saran))

        elif lab == "HURUF_KECIL":
            if not t[:1].isupper() or i == 0:
                continue
            saran = t[:1].lower() + t[1:]
            catat(i, lab, saran, p, ganti(i, saran))

        elif lab in ("TAMBAH_KOMA", "TAMBAH_TITIK"):
            tanda = "," if lab == "TAMBAH_KOMA" else "."
            if i + 1 < n and token[i + 1][0] in (",", ".", ";", ":"):
                continue
            if lab == "TAMBAH_TITIK" and t.lower() in TANPA_TITIK:
                suntingan = ganti(i, t + ".")
            else:
                suntingan = [{"awal": e, "akhir": e, "teks": tanda}]
            catat(i, lab, t + tanda, p, suntingan)

        elif lab == "HAPUS":                                # buang token beserta spasi sebelumnya
            catat(i, lab, "", p, [{"awal": token[i - 1][2] if i else s, "akhir": e, "teks": ""}])

        elif lab == "PISAH":
            saran = saran_pisah(t)
            catat(i, lab, saran, p, ganti(i, saran) if saran else [])

        elif lab == "GABUNG":
            j = i                                           # GABUNG = gabung dengan token berikutnya
            while j + 1 < n and (j == i or label[j][0] == "GABUNG") and token[j + 1][0][:1].isalnum():
                j += 1
            if j == i:
                continue
            saran = saran_gabung([token[k][0] for k in range(i, j + 1)])
            lewati.update(range(i + 1, j + 1))
            catat(i, lab, saran, p, [{"awal": s, "akhir": token[j][2], "teks": saran}], j)

        elif lab == "FORMAT_ANGKA":
            saran = saran_angka(t, [x[0].lower() for x in token[:i]])
            if saran is None:
                continue
            catat(i, lab, saran, p, ganti(i, saran))

        elif lab == "GANTI_TITIK":
            if t != ",":
                continue
            suntingan = ganti(i, ".")
            if i + 1 < n and token[i + 1][0][:1].islower():
                awal = token[i + 1][1]
                suntingan.append({"awal": awal, "akhir": awal + 1, "teks": kalimat[awal].upper(), "kapital": True})
            catat(i, lab, ".", p, suntingan)
    return temuan


def rakit(kalimat, temuan):
    """Menyusun kalimat benar dari suntingan temuan. Versi browser: susunBenar di static/app.js."""
    semua = [s for t in temuan for s in t["suntingan"]]
    kapital = {s["awal"] for s in semua if s.get("kapital")}
    sunting = [{**s, "teks": huruf_awal_kapital(s["teks"])} if s["awal"] in kapital and s["akhir"] > s["awal"] else s
               for s in semua if not s.get("kapital")]
    # Huruf kapital setelah titik baru tetap berlaku jika kata itu punya suntingan sendiri (analisa -> Analisis).
    sudah = {s["awal"] for s in sunting if s["akhir"] > s["awal"]}
    sunting += [s for s in semua if s.get("kapital") and s["awal"] not in sudah]
    keluar, pos = "", 0
    for s in sorted(sunting, key=lambda x: (x["awal"], x["akhir"])):
        if s["awal"] < pos:
            continue
        keluar += kalimat[pos:s["awal"]] + s["teks"]
        pos = s["akhir"]
    return (keluar + kalimat[pos:]).lstrip()                # jika token pertama dihapus


# --------------------------------------------------------------------------- dokumen
def periksa_dokumen(kalimat, pemeriksa, progres=None, batch=64, konteks=None):
    """kalimat: daftar ekstrak.Kalimat. Mengembalikan daftar hasil per kalimat yang berkesalahan."""
    token = [tokenisasi(k.teks) for k in kalimat]
    frek_dok = Counter(t for tk in token for t, _, _ in tk)
    hasil = []
    for mulai in range(0, len(kalimat), batch):
        bagian = token[mulai:mulai + batch]
        label = pemeriksa.prediksi([[t for t, _, _ in tk] for tk in bagian])
        for k, tk, lab in zip(kalimat[mulai:mulai + batch], bagian, label):
            temuan = susun_temuan(k.teks, tk, lab, frek_dok, konteks)
            if not temuan:
                continue
            hal = list(k.halaman) if isinstance(k.halaman, tuple) else k.halaman
            hasil.append({"halaman": hal, "paragraf": k.paragraf, "kalimat": k.teks,
                          "benar": rakit(k.teks, temuan), "temuan": temuan})
        if progres:
            progres(min(mulai + batch, len(kalimat)), len(kalimat))
    return hasil
