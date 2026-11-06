"""
kamus_baku.py
Daftar kata tidak baku -> bentuk baku (mengacu ke KBBI dan EYD V).

Dipakai di dua tempat:
  1. buat_dataset.py: membuat kesalahan TIDAK_BAKU sintetis.
  2. Pascaproses model (notebook, fungsi periksa): kata yang ada di daftar ini langsung ditandai
     TIDAK_BAKU, karena kata tidak baku adalah daftar tertutup yang lebih andal dicek dengan kamus
     daripada ditebak model.

Hanya kata yang jelas tidak baku yang dimasukkan. Bentuk yang keduanya baku (mis. silaturahmi /
silaturahim) atau yang bisa berupa nama diri (mis. Senen) tidak dimasukkan ke KAMUS_PERIKSA.
"""

INDONESIA = {
    # --- akademik / skripsi ---
    "analisa": "analisis", "menganalisa": "menganalisis", "dianalisa": "dianalisis",
    "penganalisaan": "penganalisisan", "hipotesa": "hipotesis", "praktek": "praktik",
    "prakteknya": "praktiknya", "mempraktekkan": "mempraktikkan", "dipraktekkan": "dipraktikkan",
    "kwalitas": "kualitas", "kwantitas": "kuantitas", "kwalitatif": "kualitatif",
    "kwantitatif": "kuantitatif", "resiko": "risiko", "beresiko": "berisiko",
    "aktifitas": "aktivitas", "efektifitas": "efektivitas", "produktifitas": "produktivitas",
    "kreatifitas": "kreativitas", "sensitifitas": "sensitivitas", "obyek": "objek",
    "obyektif": "objektif", "subyek": "subjek", "subyektif": "subjektif", "jadual": "jadwal",
    "dijadualkan": "dijadwalkan", "frekwensi": "frekuensi", "tehnik": "teknik",
    "tehnis": "teknis", "tehnologi": "teknologi", "tekhnologi": "teknologi",
    "standart": "standar", "standarisasi": "standardisasi", "metoda": "metode",
    "merubah": "mengubah", "dirubah": "diubah", "katagori": "kategori",
    "prosentase": "persentase", "presentase": "persentase", "prosen": "persen",
    "sistimatis": "sistematis", "sistim": "sistem", "teoritis": "teoretis",
    "seksama": "saksama", "komplek": "kompleks", "propinsi": "provinsi", "detil": "detail",
    "sekedar": "sekadar", "pebruari": "februari", "nopember": "november", "jum'at": "jumat",
    "ramadhan": "ramadan", "antrian": "antrean", "terorganisir": "terorganisasi",
    "mengorganisir": "mengorganisasi", "diorganisir": "diorganisasi",
    "menejemen": "manajemen", "menejer": "manajer", "telpon": "telepon", "karna": "karena",
    "kuisioner": "kuesioner", "quisioner": "kuesioner", "questioner": "kuesioner",
    "ahir": "akhir", "kadaluarsa": "kedaluwarsa", "kadaluwarsa": "kedaluwarsa",
    "mensimulasikan": "menyimulasikan", "coklat": "cokelat", "hektar": "hektare",
    "rejeki": "rezeki", "kelembaban": "kelembapan", "pembaharuan": "pembaruan",
    "memperbaharui": "memperbarui", "diperbaharui": "diperbarui", "meminimalisir": "meminimalkan",
    "diminimalisir": "diminimalkan", "kontinyu": "kontinu", "autentifikasi": "autentikasi",
    "otentifikasi": "autentikasi", "efesien": "efisien", "efesiensi": "efisiensi",
    "kehandalan": "keandalan", "handal": "andal", "diskripsi": "deskripsi",
    "mendiskripsikan": "mendeskripsikan", "kongkrit": "konkret", "konkrit": "konkret",
    "personil": "personel", "bahwasannya": "bahwasanya", "berhutang": "berutang",
    "hutang": "utang", "merespon": "merespons", "respon": "respons", "direspon": "direspons",
    "linier": "linear", "realibilitas": "reliabilitas", "intepretasi": "interpretasi",
    "koefesien": "koefisien", "pratikum": "praktikum", "prilaku": "perilaku",
    "perduli": "peduli", "propesional": "profesional", "ilmiyah": "ilmiah",
    "kwartal": "kuartal", "konsekwen": "konsekuen", "konsekwensi": "konsekuensi",
    "ekstrim": "ekstrem", "hakekat": "hakikat", "realita": "realitas", "orisinil": "orisinal",
    "tradisionil": "tradisional", "nampak": "tampak", "menyolok": "mencolok",
    "nomer": "nomor", "azas": "asas", "faham": "paham", "difahami": "dipahami",
    "esei": "esai", "komplit": "komplet", "lembab": "lembap",
    "nafas": "napas", "paska": "pasca", "rapih": "rapi", "trampil": "terampil",
    "terlanjur": "telanjur", "varitas": "varietas", "atlit": "atlet", "cidera": "cedera",
    "indera": "indra", "kaos": "kaus", "mahluk": "makhluk", "ihlas": "ikhlas",
    "tauladan": "teladan", "sorga": "surga", "supir": "sopir", "syah": "sah",
    "shalat": "salat", "sholat": "salat",
    # --- imbuhan meN- yang seharusnya luluh (k, p, t, s) ---
    "mempengaruhi": "memengaruhi", "mempercayai": "memercayai", "mempesona": "memesona",
    "mempopulerkan": "memopulerkan", "mempublikasikan": "memublikasikan",
    "memparkir": "memarkir", "mengkonfirmasi": "mengonfirmasi", "mengkonsumsi": "mengonsumsi",
    "mengkomunikasikan": "mengomunikasikan", "mengkontrol": "mengontrol",
    "mengkoordinasikan": "mengoordinasikan", "mengkoordinir": "mengoordinasi",
    "dikoordinir": "dikoordinasi", "mengkonversi": "mengonversi", "mengkategorikan": "mengategorikan",
    "mengkalkulasi": "mengalkulasi", "mengkombinasikan": "mengombinasikan",
    "mengkonfigurasi": "mengonfigurasi", "mengkualifikasi": "mengualifikasi",
    "mensosialisasikan": "menyosialisasikan", "mensupervisi": "menyupervisi",
    "mensurvei": "menyurvei", "mensukseskan": "menyukseskan", "mensinkronkan": "menyinkronkan",
    "mensimulasi": "menyimulasi", "menterjemahkan": "menerjemahkan", "mentargetkan": "menargetkan",
    "mentaati": "menaati",
    "memproklamirkan": "memproklamasikan", "diproklamirkan": "diproklamasikan",
    "mengakomodir": "mengakomodasi", "diakomodir": "diakomodasi",
    "legalisir": "legalisasi", "dilegalisir": "dilegalisasi",
}

# Kata serapan yang ditulis dengan ejaan asing. Hanya dipakai untuk data sintetis, tidak untuk
# pemeriksaan kamus, karena kata yang sama bisa sengaja ditulis dalam frasa bahasa Inggris
# (mis. "Learning Management System", "survey research").
ASING = {
    "popular": "populer", "trend": "tren", "hoax": "hoaks", "negative": "negatif",
    "positive": "positif", "audience": "audiens", "sample": "sampel", "survey": "survei",
    "disurvey": "disurvei", "system": "sistem", "social": "sosial", "local": "lokal",
    "focus": "fokus", "parallel": "paralel", "asset": "aset", "study": "studi",
    "music": "musik", "extra": "ekstra",             }

TIDAK_BAKU_LAIN = {
    # --- sering muncul di surat ---
    "silahkan": "silakan", "fotocopy": "fotokopi", "ijasah": "ijazah", "kwitansi": "kuitansi",
    "ketrampilan": "keterampilan", "himbauan": "imbauan", "menghimbau": "mengimbau",
    "dihimbau": "diimbau", "nasehat": "nasihat", "penasehat": "penasihat", "apotik": "apotek",
    "kordinasi": "koordinasi", "karir": "karier", "kwalifikasi": "kualifikasi",
    "sekertaris": "sekretaris", "jaman": "zaman", "kuatir": "khawatir", "ijin": "izin",
    "mengijinkan": "mengizinkan", "perijinan": "perizinan", "diijinkan": "diizinkan",
    # --- salah tulis yang sangat umum ---
    "menunjukan": "menunjukkan", "ditunjukan": "ditunjukkan", "penegakkan": "penegakan",
    "sebagaian": "sebagian", "pemograman": "pemrograman", "mengelolah": "mengelola",
    "dikelolah": "dikelola", "tapi": "tetapi",
}

TIDAK_BAKU = {**INDONESIA, **TIDAK_BAKU_LAIN, **ASING}

# Bentuk baku -> semua bentuk tidak bakunya (untuk membuat kesalahan sintetis).
BAKU_KE_TIDAK_BAKU = {}
for _salah, _benar in TIDAK_BAKU.items():
    if _salah != _benar:
        BAKU_KE_TIDAK_BAKU.setdefault(_benar, []).append(_salah)

# Dipakai untuk pascaproses (pemeriksaan berbasis kamus). "tapi" dikeluarkan karena lazim di
# kutipan/dialog, dan kata berejaan asing tidak dimasukkan (lihat ASING).
KAMUS_PERIKSA = {k: v for k, v in {**INDONESIA, **TIDAK_BAKU_LAIN}.items() if k != v and k != "tapi"}


def kena_kamus(kata, posisi):
    """True jika kata pada posisi itu langsung ditandai TIDAK_BAKU. Singkatan (huruf besar semua) dan
    kata berhuruf kapital di tengah kalimat dilewati karena bisa berupa nama diri (Muhammad Syah)."""
    return (kata.lower() in KAMUS_PERIKSA and not kata.isupper()
            and (posisi == 0 or not kata[0].isupper()))
