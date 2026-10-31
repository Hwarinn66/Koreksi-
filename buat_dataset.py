#!/usr/bin/env python3
"""
buat_dataset.py
Membuat dataset sintetis untuk pendeteksi kesalahan penulisan bahasa Indonesia
(typo, huruf kapital, tanda koma, tanda titik, kata depan, kata tidak baku, dll.).

Cara kerja: setiap kalimat bersih (sudah sesuai EYD V) dirusak secara acak
dengan 1-3 kesalahan. Hasilnya berupa pasangan (salah -> benar) dan label per
token yang siap dipakai untuk melatih IndoBERT (token classification) atau
model seq2seq (IndoBART/T5).

Pakai:
    python buat_dataset.py
    python buat_dataset.py --input data/kalimat_bersih.txt --varian 8 --seed 42
    python buat_dataset.py --input korpus_wikipedia.txt --varian 3 --contoh 10

Hanya memakai pustaka standar Python 3.8+.
"""
import argparse
import csv
import json
import random
import re
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------
LABELS = [
    "O",             # benar
    "TYPO",          # salah ketik
    "TIDAK_BAKU",    # kata tidak baku (analisa -> analisis)
    "KAPITAL",       # seharusnya diawali/ditulis huruf kapital
    "HURUF_KECIL",   # seharusnya huruf kecil
    "TAMBAH_KOMA",   # perlu koma setelah token ini
    "TAMBAH_TITIK",  # perlu titik setelah token ini (akhir kalimat/singkatan)
    "HAPUS",         # token ini (koma/titik) seharusnya tidak ada
    "PISAH",         # token ini seharusnya dipisah (dirumah -> di rumah)
    "GABUNG",        # token ini seharusnya digabung dengan token berikutnya
    "FORMAT_ANGKA",  # format angka salah (0.05 -> 0,05)
    "GANTI_TITIK",   # koma ini seharusnya titik (dua kalimat disambung koma)
]

DESKRIPSI_LABEL = {
    "O": "Benar, tidak perlu diubah.",
    "TYPO": "Salah ketik; lihat kolom perbaikan.",
    "TIDAK_BAKU": "Kata tidak baku; ganti dengan bentuk baku.",
    "KAPITAL": "Seharusnya memakai huruf kapital.",
    "HURUF_KECIL": "Seharusnya memakai huruf kecil.",
    "TAMBAH_KOMA": "Tambahkan koma setelah token ini.",
    "TAMBAH_TITIK": "Tambahkan titik setelah token ini.",
    "HAPUS": "Hapus token ini (tanda baca berlebih).",
    "PISAH": "Pisahkan token ini menjadi dua kata.",
    "GABUNG": "Gabungkan token ini dengan token berikutnya.",
    "FORMAT_ANGKA": "Format angka salah (desimal memakai koma, ribuan memakai titik).",
    "GANTI_TITIK": "Koma seharusnya titik (kalimat yang disambung koma dipecah).",
}

# ---------------------------------------------------------------------------
# Daftar aturan
# ---------------------------------------------------------------------------
# Bentuk baku -> bentuk tidak baku yang sering muncul di skripsi.
BAKU = {
    "analisis": "analisa", "menganalisis": "menganalisa", "dianalisis": "dianalisa",
    "hipotesis": "hipotesa", "praktik": "praktek", "kualitas": "kwalitas",
    "kuantitas": "kwantitas", "risiko": "resiko", "aktivitas": "aktifitas",
    "efektivitas": "efektifitas", "produktivitas": "produktifitas",
    "kreativitas": "kreatifitas", "objek": "obyek", "objektif": "obyektif",
    "subjek": "subyek", "izin": "ijin", "jadwal": "jadual", "dijadwalkan": "dijadualkan",
    "frekuensi": "frekwensi", "teknik": "tehnik", "standar": "standart",
    "metode": "metoda", "mengubah": "merubah", "diubah": "dirubah",
    "kategori": "katagori", "persentase": "prosentase", "sistematis": "sistimatis",
    "memengaruhi": "mempengaruhi", "teoretis": "teoritis", "saksama": "seksama",
    "kompleks": "komplek", "provinsi": "propinsi", "detail": "detil",
    "sekadar": "sekedar", "februari": "pebruari", "november": "nopember",
    "jumat": "jum'at", "ramadan": "ramadhan", "antrean": "antrian",
    "terorganisasi": "terorganisir", "manajemen": "menejemen", "manajer": "menejer",
    "sistem": "sistim", "telepon": "telpon", "karena": "karna", "tetapi": "tapi",
    "kuesioner": "kuisioner", "akhir": "ahir", "kedaluwarsa": "kadaluarsa",
    "menyimulasikan": "mensimulasikan", "cokelat": "coklat", "hektare": "hektar",
    "rezeki": "rejeki", "kelembapan": "kelembaban",
    # sering muncul di surat
    "silakan": "silahkan", "fotokopi": "fotocopy", "ijazah": "ijasah",
    "kuitansi": "kwitansi", "keterampilan": "ketrampilan", "imbauan": "himbauan",
    "mengimbau": "menghimbau", "diimbau": "dihimbau", "nasihat": "nasehat",
    "apotek": "apotik", "koordinasi": "kordinasi", "karier": "karir",
    "kualifikasi": "kwalifikasi", "sekretaris": "sekertaris", "zaman": "jaman",
    "khawatir": "kuatir", "mengizinkan": "mengijinkan", "perizinan": "perijinan",
    "menaati": "mentaati", "mengonfirmasi": "mengkonfirmasi",
    "menyukseskan": "mensukseskan", "senin": "senen", "legalisasi": "legalisir",
}

# Kata yang diawali "di" tetapi BUKAN awalan di-.
DI_BUKAN_AWALAN = {
    "dia", "diri", "dirinya", "dimensi", "digital", "digitalisasi", "diagram",
    "diskusi", "distribusi", "distributor", "dinas", "dinamis", "dinamika",
    "disiplin", "dini", "diskon", "divisi", "direktur", "dioda", "diagnosis",
    "diagnosa", "dialog", "dinding", "diet", "diploma", "diktat", "dikte",
    "dingin", "disertasi", "diskriminasi", "dividen", "diversifikasi", "dirut",
    "dirgantara", "dimana", "diantara",
}

# Ordinal: kedua -> "ke dua" (salah)
ORDINAL = {"kedua", "ketiga", "keempat", "kelima", "keenam", "ketujuh",
           "kedelapan", "kesembilan", "kesepuluh"}

# Kata yang harus serangkai; kesalahannya: dipisah.
SERANGKAI = {
    "antarmuka": ("antar", "muka"), "antarentitas": ("antar", "entitas"),
    "antarkata": ("antar", "kata"), "antarbaris": ("antar", "baris"),
    "antarbagian": ("antar", "bagian"), "antarvariabel": ("antar", "variabel"),
    "subbab": ("sub", "bab"), "subsistem": ("sub", "sistem"),
    "pascasarjana": ("pasca", "sarjana"), "nonaktif": ("non", "aktif"),
    "nonfungsional": ("non", "fungsional"), "dinonaktifkan": ("di", "nonaktifkan"),
    "praproses": ("pra", "proses"), "semiterstruktur": ("semi", "terstruktur"),
    "pertanggungjawaban": ("pertanggung", "jawaban"), "olahraga": ("olah", "raga"),
    "daripada": ("dari", "pada"), "idulfitri": ("Idul", "Fitri"),
    "multikolinearitas": ("multi", "kolinearitas"), "ditandatangani": ("ditanda", "tangani"),
    "antarmodul": ("antar", "modul"), "antaranotator": ("antar", "anotator"),
    "antarpengguna": ("antar", "pengguna"), "prasiklus": ("pra", "siklus"),
    "antarkaryawan": ("antar", "karyawan"),
    "pasfoto": ("pas", "foto"), "antarinstansi": ("antar", "instansi"),
    "antarwarga": ("antar", "warga"), "serbaguna": ("serba", "guna"),
    "menindaklanjuti": ("menindak", "lanjuti"), "ditindaklanjuti": ("ditindak", "lanjuti"),
    "menandatangani": ("menanda", "tangani"), "penandatanganan": ("penanda", "tanganan"),
    "sebagaimana": ("sebagai", "mana"), "ketidakhadiran": ("ketidak", "hadiran"),
    "ketidaknyamanan": ("ketidak", "nyamanan"), "berdukacita": ("berduka", "cita"),
    "diberitahukan": ("diberi", "tahukan"), "memberitahukan": ("memberi", "tahukan"),
    "pemberitahuan": ("pemberi", "tahuan"),
}

# Gabungan kata yang harus ditulis terpisah; kesalahannya: disatukan.
TERPISAH = {
    ("kerja", "sama"), ("bekerja", "sama"), ("tanggung", "jawab"),
    ("bertanggung", "jawab"), ("terima", "kasih"), ("berterima", "kasih"),
    ("orang", "tua"), ("apa", "pun"), ("siapa", "pun"), ("tanda", "tangan"),
    ("rumah", "sakit"), ("sumber", "daya"), ("tata", "letak"), ("uji", "coba"),
    ("lalu", "lintas"), ("tumpang", "tindih"), ("kata", "kunci"), ("kata", "sandi"),
    ("dua", "belas"), ("dua", "puluh"), ("empat", "puluh"), ("rumah", "tangga"),
    ("daya", "beli"), ("tumbuh", "kembang"), ("sehari", "hari"),
    ("bertanda", "tangan"), ("serah", "terima"), ("mana", "pun"), ("kapan", "pun"),
    ("memberi", "tahu"), ("beri", "tahu"), ("tindak", "lanjut"), ("wali", "kota"),
    ("tata", "tertib"), ("kerja", "bakti"), ("lima", "belas"), ("uang", "muka"),
}

KATA_DEPAN = {"di", "ke"}

# Singkatan yang memang memakai titik.
SINGKATAN_BERTITIK = {"dkk.", "dll.", "dsb.", "dst.", "hlm.", "Tbk.", "Swt.", "Yth.", "Sdr."}
# Singkatan nama badan yang TIDAK memakai titik (kesalahan: "PT.").
SINGKATAN_TANPA_TITIK = {"PT", "CV"}

# Kalimat yang diawali kata ini: koma pertamanya opsional (keterangan di awal
# kalimat), jadi tidak dihapus agar label tidak ambigu.
PEMBUKA_KOMA_OPSIONAL = {
    "Berdasarkan", "Pada", "Dalam", "Dari", "Untuk", "Dengan", "Menurut",
    "Sesuai", "Selama", "Melalui", "Di", "Sebagai", "Secara", "Bagi", "Terkait",
    "Mengacu", "Saat", "Kini", "Sebelumnya",
    "Sehubungan", "Bersama", "Menindaklanjuti", "Merujuk", "Menanggapi",
}
# Sapaan yang tetap berhuruf kapital walaupun berada di tengah kalimat.
SAPAAN = {"Bapak", "Ibu", "Bapak/Ibu", "Pak", "Bu", "Saudara", "Saudari", "Anda"}
# Koma sebelum kata ini tidak dihapus (penggunaannya bervariasi).
KOMA_DILINDUNGI_SEBELUM = {"yaitu", "yakni", "seperti", "misalnya", "termasuk",
                           "terutama", "khususnya", "kecuali"}
# Sisipan koma yang salah sebelum kata ini.
KOMA_SALAH_SEBELUM = {"bahwa", "sehingga", "agar", "supaya", "karena",
                      "dan", "atau", "adalah", "merupakan", "bertujuan"}

KATA_FUNGSI = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "dalam", "ini",
    "itu", "atau", "oleh", "juga", "akan", "telah", "sudah", "dapat", "tidak",
    "karena", "sehingga", "agar", "bahwa", "adalah", "merupakan", "serta",
    "secara", "sebagai", "tersebut", "lebih", "setiap", "seluruh", "para",
    "antara", "hanya", "masih", "bagi", "tetapi", "sedangkan", "melainkan",
    "kepada", "terhadap", "sangat", "harus", "belum", "saat", "yaitu", "yakni",
    "seperti", "sampai", "atas", "kemudian", "mampu", "perlu",
}
ROMAWI = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}

# ---------------------------------------------------------------------------
# Tokenisasi
# ---------------------------------------------------------------------------
TOKEN_RE = re.compile(
    r"""
      (?<!\w)(?:dkk|dll|dsb|dst|hlm|Tbk|Swt|Yth|Sdr)\.    # singkatan bertitik
    | (?<!\w)Rp\d+(?:[.,]\d+)*                   # uang: Rp9.050 Rp227,88
    | \d+(?:[.,:]\d+)*%?                         # angka: 12.500 0,05 08.00 80:10:10 25%
    | [^\W\d_]\w*(?:['’\-/]\w+)*-?               # kata: sehari-hari, karunia-Nya, di-
    | [,.;:?!()"]                                # tanda baca
    """,
    re.X,
)
TANPA_SPASI_SEBELUM = {",", ".", ";", ":", "?", "!", ")"}
TANPA_SPASI_SESUDAH = {"("}


def tokenisasi(kalimat):
    return TOKEN_RE.findall(kalimat)


def gabung_token(tokens):
    hasil = ""
    for i, t in enumerate(tokens):
        if i == 0:
            hasil = t
        elif t in TANPA_SPASI_SEBELUM or tokens[i - 1] in TANPA_SPASI_SESUDAH:
            hasil += t
        else:
            hasil += " " + t
    return hasil


# ---------------------------------------------------------------------------
# Typo berbasis tata letak papan ketik QWERTY
# ---------------------------------------------------------------------------
def _tetangga_keyboard():
    baris = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    geser = [0.0, 0.25, 0.75]
    posisi = {}
    for r, isi in enumerate(baris):
        for c, huruf in enumerate(isi):
            posisi[huruf] = (r, c + geser[r])
    tetangga = {}
    for a, (ra, xa) in posisi.items():
        tetangga[a] = [b for b, (rb, xb) in posisi.items()
                       if b != a and abs(ra - rb) <= 1 and abs(xa - xb) <= 1.0]
    return tetangga


TETANGGA = _tetangga_keyboard()


def samakan_kapital(huruf_baru, huruf_lama):
    return huruf_baru.upper() if huruf_lama.isupper() else huruf_baru


def buat_typo(kata, rng, kosakata):
    for _ in range(30):
        w = list(kata)
        n = len(w)
        op = rng.choices(["hapus", "sisip", "ganti", "tukar", "ganda"],
                         weights=[0.25, 0.20, 0.30, 0.15, 0.10])[0]
        i = rng.randrange(1, n) if n > 3 else rng.randrange(n)  # jarang di huruf pertama
        c = w[i].lower()
        if op == "hapus":
            del w[i]
        elif op == "sisip" and c in TETANGGA:
            w.insert(i + rng.choice([0, 1]), rng.choice(TETANGGA[c]))
        elif op == "ganti" and c in TETANGGA:
            w[i] = samakan_kapital(rng.choice(TETANGGA[c]), w[i])
        elif op == "tukar" and i < n - 1 and w[i] != w[i + 1]:
            w[i], w[i + 1] = w[i + 1], w[i]
        elif op == "ganda":
            w.insert(i, w[i].lower())
        else:
            continue
        hasil = "".join(w)
        if (len(hasil) >= 2 and hasil.lower() != kata.lower()
                and hasil.lower() not in kosakata
                and hasil.lower() not in KATA_DEPAN):
            return hasil
    return None


def samakan_bentuk(kata_baru, kata_lama):
    if kata_lama.isupper() and len(kata_lama) > 1:
        return kata_baru.upper()
    if kata_lama[0].isupper():
        return kata_baru[0].upper() + kata_baru[1:]
    return kata_baru


# ---------------------------------------------------------------------------
# Struktur token kerja
# ---------------------------------------------------------------------------
def tok(teks, asal=None, label="O", perbaikan=None, kunci=False):
    return {"teks": teks, "asal": asal, "label": label,
            "perbaikan": perbaikan, "kunci": kunci}


def bebas(t):
    return t["label"] == "O" and not t["kunci"]


def koma_dilindungi(tokens):
    """Indeks koma (pada kalimat bersih) yang tidak boleh dihapus."""
    lindung = set()
    if len(tokens) > 1:
        awal_opsional = (tokens[0] in PEMBUKA_KOMA_OPSIONAL
                         and not (tokens[0] == "Dengan" and tokens[1] in {"demikian", "hormat"}))
        if awal_opsional and "," in tokens:
            lindung.add(tokens.index(","))
    for i, t in enumerate(tokens):
        if t == "," and i + 1 < len(tokens) and tokens[i + 1].lower() in KOMA_DILINDUNGI_SEBELUM:
            lindung.add(i)
    return lindung


# ---------------------------------------------------------------------------
# Operasi perusak. Masing-masing mengembalikan True jika berhasil diterapkan.
# ---------------------------------------------------------------------------
def op_typo(W, rng, ctx):
    calon = []
    for i, t in enumerate(W):
        s = t["teks"]
        if not bebas(t) or not s.isalpha() or len(s) < 4:
            continue
        if s.islower() or (i == 0 and s[0].isupper() and s[1:].islower()):
            calon.append(i)
    if not calon:
        return False
    i = rng.choice(calon)
    baru = buat_typo(W[i]["teks"], rng, ctx["kosakata"])
    if not baru:
        return False
    W[i].update(perbaikan=W[i]["teks"], teks=baru, label="TYPO", kunci=True)
    return True


def op_tidak_baku(W, rng, ctx):
    calon = [i for i, t in enumerate(W) if bebas(t) and t["teks"].lower() in BAKU]
    if not calon:
        return False
    i = rng.choice(calon)
    asli = W[i]["teks"]
    W[i].update(perbaikan=asli, teks=samakan_bentuk(BAKU[asli.lower()], asli),
                label="TIDAK_BAKU", kunci=True)
    return True


def op_kapital(W, rng, ctx):
    calon = []
    for i, t in enumerate(W):
        s = t["teks"]
        if (bebas(t) and len(s) > 1 and s[0].isalpha() and s[0].isupper()
                and s not in ROMAWI):
            calon.append(i)
    if not calon:
        return False
    i = 0 if (0 in calon and rng.random() < 0.4) else rng.choice(calon)
    s = W[i]["teks"]
    if s.isupper() or any(c.isupper() for c in s[1:]):
        baru = s.lower()
    else:
        baru = s[0].lower() + s[1:]
    if baru == s:
        return False
    W[i].update(perbaikan=s, teks=baru, label="KAPITAL", kunci=True)
    return True


def op_huruf_kecil(W, rng, ctx):
    calon = [i for i, t in enumerate(W)
             if i > 0 and bebas(t) and t["teks"].isalpha() and t["teks"].islower()
             and len(t["teks"]) >= 4 and t["teks"] not in KATA_FUNGSI
             and W[i - 1]["teks"] != ":"]
    if not calon:
        return False
    i = rng.choice(calon)
    s = W[i]["teks"]
    W[i].update(perbaikan=s, teks=s[0].upper() + s[1:], label="HURUF_KECIL", kunci=True)
    return True


def op_hapus_koma(W, rng, ctx):
    calon = [j for j, t in enumerate(W)
             if t["teks"] == "," and t["label"] == "O" and j > 0
             and t["asal"] not in ctx["koma_lindung"] and bebas(W[j - 1])]
    if not calon:
        return False
    j = rng.choice(calon)
    sebelum = W[j - 1]
    sebelum.update(label="TAMBAH_KOMA", perbaikan=sebelum["teks"] + ",", kunci=True)
    del W[j]
    return True


def op_koma_salah(W, rng, ctx):
    calon = []
    for i, t in enumerate(W):
        if i < 2 or t["teks"].lower() not in KOMA_SALAH_SEBELUM or t["label"] != "O":
            continue
        sebelum = W[i - 1]["teks"]
        if not (sebelum[0].isalnum()):
            continue  # sudah ada tanda baca
        kata = t["teks"].lower()
        if kata == "karena" and sebelum.lower() == "oleh":
            continue
        if kata in {"dan", "atau"} and any(x["teks"] == "," for x in W[:i]):
            continue  # dalam pemerincian, koma sebelum dan/atau justru benar
        calon.append(i)
    if not calon:
        return False
    i = rng.choice(calon)
    W.insert(i, tok(",", label="HAPUS", perbaikan="", kunci=True))
    return True


def op_hapus_titik(W, rng, ctx):
    if len(W) < 2 or W[-1]["teks"] != "." or W[-1]["label"] != "O" or not bebas(W[-2]):
        return False
    sebelum = W[-2]
    sebelum.update(label="TAMBAH_TITIK", perbaikan=sebelum["teks"] + ".", kunci=True)
    del W[-1]
    return True


def op_singkatan(W, rng, ctx):
    tanpa_titik = [i for i, t in enumerate(W) if bebas(t) and t["teks"] in SINGKATAN_BERTITIK]
    titik_salah = [i for i, t in enumerate(W)
                   if bebas(t) and t["teks"] in SINGKATAN_TANPA_TITIK
                   and (i + 1 >= len(W) or W[i + 1]["teks"] != ".")]
    pilihan = [("hilang", i) for i in tanpa_titik] + [("lebih", i) for i in titik_salah]
    if not pilihan:
        return False
    jenis, i = rng.choice(pilihan)
    if jenis == "hilang":
        s = W[i]["teks"]
        W[i].update(perbaikan=s, teks=s[:-1], label="TAMBAH_TITIK", kunci=True)
    else:
        W[i]["kunci"] = True
        W.insert(i + 1, tok(".", label="HAPUS", perbaikan="", kunci=True))
    return True


def op_kata_depan(W, rng, ctx):
    calon = [i for i in range(len(W) - 1)
             if W[i]["teks"].lower() in KATA_DEPAN and bebas(W[i]) and bebas(W[i + 1])
             and W[i + 1]["teks"].isalpha() and W[i + 1]["teks"][0].islower()]
    if not calon:
        return False
    i = rng.choice(calon)
    a, b = W[i]["teks"], W[i + 1]["teks"]
    W[i:i + 2] = [tok(a + b, label="PISAH", perbaikan=f"{a} {b}", kunci=True)]
    return True


def op_pisah_awalan(W, rng, ctx):
    calon = []
    for i, t in enumerate(W):
        s = t["teks"]
        if not bebas(t) or not s.isalpha():
            continue
        low = s.lower()
        if low in SERANGKAI:
            kiri, kanan = SERANGKAI[low]
            calon.append((i, samakan_bentuk(kiri, s), kanan))
        elif low in ORDINAL:
            calon.append((i, s[:2], s[2:]))
        elif (s.islower() and s.startswith("di") and len(s) >= 5
              and s not in DI_BUKAN_AWALAN):
            calon.append((i, "di", s[2:]))
    if not calon:
        return False
    i, kiri, kanan = rng.choice(calon)
    asli = W[i]["teks"]
    W[i:i + 1] = [tok(kiri, label="GABUNG", perbaikan=asli, kunci=True),
                  tok(kanan, kunci=True)]
    return True


def op_majemuk(W, rng, ctx):
    calon = [i for i in range(len(W) - 1)
             if bebas(W[i]) and bebas(W[i + 1])
             and (W[i]["teks"].lower(), W[i + 1]["teks"].lower()) in TERPISAH]
    if not calon:
        return False
    i = rng.choice(calon)
    a, b = W[i]["teks"], W[i + 1]["teks"]
    W[i:i + 2] = [tok(a + b, label="PISAH", perbaikan=f"{a} {b}", kunci=True)]
    return True


def op_format_angka(W, rng, ctx):
    calon = []
    for i, t in enumerate(W):
        s = t["teks"]
        if not bebas(t):
            continue
        if re.fullmatch(r"(?:Rp)?\d+,\d+%?", s):
            calon.append((i, s.replace(",", ".")))
        elif re.fullmatch(r"(?:Rp)?\d{1,3}(?:\.\d{3})+", s):
            calon.append((i, s.replace(".", ",")))
        elif (re.fullmatch(r"\d{2}\.\d{2}", s)
              and any(x["teks"].lower() == "pukul" for x in W[:i])):
            calon.append((i, s.replace(".", ":")))  # jam: pukul 08.00 -> 08:00
    if not calon:
        return False
    i, baru = rng.choice(calon)
    W[i].update(perbaikan=W[i]["teks"], teks=baru, label="FORMAT_ANGKA", kunci=True)
    return True


def op_ganti_titik(W, rng, ctx):
    """Dua kalimat disambung koma: '... buat. Atas ...' -> '... buat, atas ...'."""
    calon = []
    for j in range(1, len(W) - 1):
        t, nx = W[j], W[j + 1]
        s = nx["teks"]
        if (t["teks"] == "." and bebas(t) and bebas(nx) and W[j - 1]["teks"][-1:].isalnum()
                and s.isalpha() and s[0].isupper() and s[1:].islower()
                and s not in SAPAAN and s.lower() in ctx["kosakata"]):
            calon.append(j)
    if not calon:
        return False
    j = rng.choice(calon)
    s = W[j + 1]["teks"]
    W[j].update(teks=",", label="GANTI_TITIK", perbaikan=".", kunci=True)
    W[j + 1].update(teks=s.lower(), label="KAPITAL", perbaikan=s, kunci=True)
    return True


OPERASI = {
    "typo": (op_typo, 0.15),
    "kapital": (op_kapital, 0.12),
    "huruf_kecil": (op_huruf_kecil, 0.07),
    "hapus_koma": (op_hapus_koma, 0.20),
    "koma_salah": (op_koma_salah, 0.10),
    "hapus_titik": (op_hapus_titik, 0.06),
    "singkatan": (op_singkatan, 0.04),
    "kata_depan": (op_kata_depan, 0.09),
    "pisah_awalan": (op_pisah_awalan, 0.07),
    "majemuk": (op_majemuk, 0.05),
    "tidak_baku": (op_tidak_baku, 0.06),
    "format_angka": (op_format_angka, 0.05),
    "ganti_titik": (op_ganti_titik, 0.50),  # hanya berlaku pada baris berisi dua kalimat
}


def rusak_kalimat(tokens, rng, kosakata, jumlah_kesalahan):
    W = [tok(t, asal=i) for i, t in enumerate(tokens)]
    ctx = {"kosakata": kosakata, "koma_lindung": koma_dilindungi(tokens)}
    tersedia = dict(OPERASI)
    berhasil = 0
    while berhasil < jumlah_kesalahan and tersedia:
        nama = rng.choices(list(tersedia), weights=[b for _, b in tersedia.values()])[0]
        fungsi, _ = tersedia[nama]
        if fungsi(W, rng, ctx):
            berhasil += 1
        else:
            del tersedia[nama]
    return W


# ---------------------------------------------------------------------------
# Rekonstruksi: memastikan label + perbaikan benar-benar mengembalikan kalimat
# ---------------------------------------------------------------------------
def rekonstruksi(tokens, labels, perbaikan):
    hasil, i = [], 0
    while i < len(tokens):
        t, lab, p = tokens[i], labels[i], perbaikan[i]
        if lab == "O":
            hasil.append(t)
        elif lab in {"TYPO", "TIDAK_BAKU", "KAPITAL", "HURUF_KECIL", "FORMAT_ANGKA", "GANTI_TITIK"}:
            hasil.append(p)
        elif lab in {"TAMBAH_KOMA", "TAMBAH_TITIK"}:
            hasil.extend([p] if p in SINGKATAN_BERTITIK else [t, p[-1]])
        elif lab == "HAPUS":
            pass
        elif lab == "PISAH":
            hasil.extend(p.split(" "))
        elif lab == "GABUNG":
            hasil.append(p)
            i += 1  # lewati potongan kedua
        i += 1
    return gabung_token(hasil)


# ---------------------------------------------------------------------------
# Utama
# ---------------------------------------------------------------------------
def baca_kalimat(path):
    kalimat = []
    for baris in Path(path).read_text(encoding="utf-8").splitlines():
        baris = " ".join(baris.split())
        if baris and not baris.startswith("#"):
            kalimat.append(baris)
    return list(dict.fromkeys(kalimat))  # buang duplikat, urutan tetap


def urai_input(arg, varian_bawaan):
    """'data/x.txt:4' -> ('data/x.txt', 4); tanpa akhiran memakai --varian."""
    m = re.search(r":(\d+)$", arg)
    return (arg[:m.start()], int(m.group(1))) if m else (arg, varian_bawaan)


def kosakata_tambahan():
    """Kata dasar Sastrawi (jika terpasang) agar typo tidak kebetulan menjadi kata nyata."""
    try:
        import Sastrawi
        p = Path(Sastrawi.__file__).parent / "Stemmer" / "data" / "kata-dasar.txt"
        return {w.strip().lower() for w in p.read_text(encoding="utf-8").splitlines() if w.strip()}
    except Exception:
        return set()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", nargs="+", default=["data/kalimat_bersih.txt"],
                    help="satu atau lebih berkas; tambahkan :N untuk jumlah varian per berkas")
    ap.add_argument("--output", default="output")
    ap.add_argument("--varian", type=int, default=8, help="jumlah versi rusak per kalimat")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--porsi", default="80,10,10", help="persentase train,valid,test")
    ap.add_argument("--contoh", type=int, default=0, help="tampilkan N contoh acak")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    # Baca semua sumber, tokenisasi, cek bolak-balik, buang duplikat antarsumber
    data_bersih, dilihat_global, dilewati = [], set(), Counter()
    for arg in args.input:
        path, n_varian = urai_input(arg, args.varian)
        sumber = Path(path).stem
        for k in baca_kalimat(path):
            if k in dilihat_global:
                dilewati["duplikat"] += 1
                continue
            dilihat_global.add(k)
            tokens = tokenisasi(k)
            if gabung_token(tokens) != k:
                dilewati["tokenisasi"] += 1
                continue
            data_bersih.append((k, tokens, sumber, n_varian))
    if dilewati:
        print(f"[info] kalimat dilewati: {dict(dilewati)}")

    kosakata = {t.lower() for _, toks, _, _ in data_bersih for t in toks if t.isalpha()}
    kosakata |= set(BAKU) | {w for pasangan in TERPISAH for w in pasangan}
    kosakata |= kosakata_tambahan()

    # Pembagian berdasarkan kalimat asal (mencegah kebocoran data)
    idx = list(range(len(data_bersih)))
    rng.shuffle(idx)
    p_train, p_valid, _ = (int(x) for x in args.porsi.split(","))
    n_train = round(len(idx) * p_train / 100)
    n_valid = round(len(idx) * p_valid / 100)
    split_of = {}
    for pos, i in enumerate(idx):
        split_of[i] = "train" if pos < n_train else "valid" if pos < n_train + n_valid else "test"

    jumlah_salah = [1, 2, 3]
    bobot_salah = [0.45, 0.35, 0.20]

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    keluaran = {s: {"pasangan": [], "token": []} for s in ("train", "valid", "test")}
    statistik = {"label": Counter(), "jenis_per_contoh": Counter(), "gagal_rekonstruksi": 0,
                 "contoh_per_sumber": Counter(), "kalimat_per_sumber": Counter()}

    for kid, (bersih, tokens, sumber, n_varian) in enumerate(data_bersih):
        split = split_of[kid]
        statistik["kalimat_per_sumber"][sumber] += 1
        dilihat = set()
        varian = [None] + [rng.choices(jumlah_salah, bobot_salah)[0] for _ in range(n_varian)]
        for v, n_salah in enumerate(varian):
            if n_salah is None:  # satu versi tanpa kesalahan per kalimat
                W = [tok(t) for t in tokens]
            else:
                W = rusak_kalimat(tokens, rng, kosakata, n_salah)
            toks = [t["teks"] for t in W]
            labs = [t["label"] for t in W]
            perb = [t["perbaikan"] for t in W]
            salah = gabung_token(toks)
            if salah in dilihat:
                continue
            dilihat.add(salah)
            if rekonstruksi(toks, labs, perb) != bersih:
                statistik["gagal_rekonstruksi"] += 1
                continue
            jenis = sorted({l for l in labs if l != "O"})
            cid = f"k{kid:05d}-v{v}"
            keluaran[split]["pasangan"].append(
                {"id": cid, "kalimat_id": kid, "sumber": sumber, "salah": salah,
                 "benar": bersih, "kesalahan": jenis})
            keluaran[split]["token"].append(
                {"id": cid, "tokens": toks, "labels": labs, "perbaikan": perb})
            statistik["label"].update(labs)
            statistik["jenis_per_contoh"].update(jenis or ["TANPA_KESALAHAN"])
            statistik["contoh_per_sumber"][sumber] += 1

    # Tulis berkas
    for split, isi in keluaran.items():
        for jenis in ("pasangan", "token"):
            with open(out_dir / f"{jenis}_{split}.jsonl", "w", encoding="utf-8") as f:
                for baris in isi[jenis]:
                    f.write(json.dumps(baris, ensure_ascii=False) + "\n")

    with open(out_dir / "semua_pasangan.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "sumber", "salah", "benar", "kesalahan"])
        for split, isi in keluaran.items():
            for b in isi["pasangan"]:
                w.writerow([b["id"], split, b["sumber"], b["salah"], b["benar"],
                            ";".join(b["kesalahan"])])

    (out_dir / "label.json").write_text(json.dumps(
        {"labels": LABELS, "label2id": {l: i for i, l in enumerate(LABELS)},
         "deskripsi": DESKRIPSI_LABEL}, ensure_ascii=False, indent=2), encoding="utf-8")

    ringkas = {
        "kalimat_bersih": len(data_bersih),
        "contoh_per_split": {s: len(isi["pasangan"]) for s, isi in keluaran.items()},
        "kalimat_per_split": {s: sum(1 for k in split_of.values() if k == s)
                              for s in ("train", "valid", "test")},
        "jumlah_token_per_label": dict(statistik["label"].most_common()),
        "contoh_per_jenis_kesalahan": dict(statistik["jenis_per_contoh"].most_common()),
        "kalimat_per_sumber": dict(statistik["kalimat_per_sumber"]),
        "contoh_per_sumber": dict(statistik["contoh_per_sumber"]),
        "gagal_rekonstruksi": statistik["gagal_rekonstruksi"],
        "seed": args.seed,
        "input": args.input,
    }
    (out_dir / "statistik.json").write_text(json.dumps(ringkas, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(json.dumps(ringkas, ensure_ascii=False, indent=2))

    if args.contoh:
        semua = [b for isi in keluaran.values() for b in isi["pasangan"] if b["kesalahan"]]
        for b in random.Random(args.seed + 1).sample(semua, min(args.contoh, len(semua))):
            print(f"\n[{', '.join(b['kesalahan'])}]\n  salah: {b['salah']}\n  benar: {b['benar']}")


if __name__ == "__main__":
    main()
