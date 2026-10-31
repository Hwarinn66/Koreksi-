#!/usr/bin/env python3
"""
saring_korpus.py
Mengambil kalimat dari korpus terbuka lalu menyaring hanya kalimat yang
(sejauh bisa dicek otomatis) sudah sesuai EYD, supaya aman dijadikan
"jawaban benar" oleh buat_dataset.py.

Format masukan yang didukung:
  - .conllu  (Universal Dependencies; dibaca dari baris "# text = ...")
  - .tsv     (IDN Tagged Corpus; satu token per baris, kalimat dipisah baris kosong)
  - .txt     (satu kalimat atau paragraf per baris, misalnya teks Wikipedia)

Pakai:
    python saring_korpus.py --output data/korpus_ud.txt  folder/*.conllu
    python saring_korpus.py --output data/korpus_wiki.txt wiki.txt --laporan

Memerlukan Sastrawi (pip install Sastrawi) untuk pengecekan kosakata.
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_dataset import (BAKU, BAKU_SEMUA, KOMA_DILINDUNGI_SEBELUM, ORDINAL, PEMBUKA_KOMA_OPSIONAL,  # noqa: E402
                          SERANGKAI, TERPISAH, gabung_token,
                          tokenisasi)

# ---------------------------------------------------------------------------
# Daftar pemeriksaan
# ---------------------------------------------------------------------------
TIDAK_BAKU_LAIN = {
    # bentuk tidak baku
    "dimana", "disini", "disana", "kemana", "kesini", "kesana", "darimana",
    "ijinkan", "diijinkan", "mengijinkan", "jaman", "nasehat", "apotik", "atlit",
    "hutang", "berhutang", "kongkrit", "mengkonsumsi", "mengkoordinasi",
    "mengkoordinasikan", "menterjemahkan", "mensukseskan", "mentaati", "himbauan",
    "menghimbau", "himbau", "silahkan", "fikir", "berfikir", "faham", "nafas", "bernafas",
    "trampil", "rejeki", "ijasah", "tauladan", "tehnologi", "kwitansi", "lembab", "sholat",
    "hakekat", "do'a", "merobah", "singel", "photo", "subyektif", "idul", "nampak",
    "nampaknya", "resiko",
    # ragam cakapan dan singkatan obrolan
    "ketemu", "bikin", "dapet", "udah", "gak", "nggak", "ngga", "enggak", "aja", "banget",
    "kayak", "gimana", "dong", "sih", "deh", "kok", "nih", "gue", "gua", "lo", "lu",
    "emang", "mending", "doang", "kalo", "dgn", "yg", "tdk", "utk", "krn", "sdh", "blm",
    "tp", "dlm", "pd", "thd", "jg", "bgt", "kenapa", "cuma", "gitu", "bilang", "pengen",
    "kayaknya", "ibukota",
}
# Kata kerja tuturan: "Ia mengatakan, ..." (gaya berita, bukan EYD) ditolak
KATA_TUTURAN = {"mengatakan", "menyatakan", "menjelaskan", "mengungkapkan", "menuturkan",
                "menegaskan", "menambahkan", "menyebutkan", "berkata", "mengemukakan",
                "memaparkan", "menerangkan", "mengakui", "menilai", "berpendapat"}
# Unsur nama geografi/wilayah yang harus berhuruf kapital bila diikuti nama
UNSUR_GEOGRAFI = {"kecamatan", "kabupaten", "kota", "provinsi", "desa", "kelurahan",
                  "sungai", "gunung", "pulau", "danau", "selat", "teluk", "jalan", "laut",
                  "samudra", "tanjung", "kepulauan", "dusun"}
TIDAK_BAKU_SEMUA = TIDAK_BAKU_LAIN | {x for v in BAKU_SEMUA.values() for x in v}

# di/ke yang sering salah ditulis serangkai dengan kata benda/keterangan tempat
TEMPAT = {"rumah", "sekolah", "kantor", "kota", "desa", "atas", "bawah", "dalam", "luar",
          "sini", "sana", "mana", "antara", "samping", "depan", "belakang", "tengah",
          "sekitar", "bidang", "wilayah", "daerah", "tempat", "pasar", "kampus", "kelas",
          "jalan", "lapangan", "lantai", "pinggir", "ujung", "balik", "situ", "seberang",
          "sebelah", "hadapan", "akhir", "awal"}
# "keluar" sengaja tidak dimasukkan karena juga kata kerja yang sah.
SALAH_SERANGKAI = ({"di" + t for t in TEMPAT}
                   | {"ke" + t for t in TEMPAT if t not in {"luar", "akhir", "awal"}}
                   | {a + b for a, b in TERPISAH})

UNSUR_TERIKAT = {"antar", "pasca", "non", "pra", "sub", "multi", "semi", "anti", "infra",
                 "ekstra", "inter", "intra", "supra", "ultra"}

HARI_BULAN = {"senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "januari", "februari",
              "maret", "april", "juni", "juli", "agustus", "september", "oktober",
              "november", "desember"}

PENGHUBUNG_ANTARKALIMAT = [
    ("Oleh", "karena", "itu"), ("Oleh", "sebab", "itu"), ("Namun",), ("Selain", "itu"),
    ("Akan", "tetapi"), ("Dengan", "demikian"), ("Jadi",), ("Akibatnya",),
    ("Meskipun", "demikian"), ("Walaupun", "demikian"), ("Sementara", "itu"),
    ("Sebaliknya",), ("Setelah", "itu"), ("Karena", "itu"),
]
PEMBUKA_ANAK_KALIMAT = {"Jika", "Apabila", "Bila", "Kalau", "Karena", "Meskipun",
                        "Walaupun", "Agar", "Supaya", "Ketika", "Setelah", "Sebelum",
                        "Sejak", "Seandainya", "Andaikan", "Biarpun", "Sewaktu"}
TANPA_KOMA_SEBELUM = {"bahwa", "sehingga", "agar", "supaya", "karena", "adalah", "merupakan"}
PERLU_KOMA_SEBELUM = {"tetapi", "sedangkan", "melainkan"}

KARAKTER_SAH = re.compile(r"^[A-Za-z0-9 ,.;?()'%/\-]+$")
SINGKATAN_TITIK = re.compile(r"(?:^|\s)(?:dkk|dll|dsb|dst|hlm|Tbk|[A-Z])\.$")


# ---------------------------------------------------------------------------
# Kosakata (Sastrawi)
# ---------------------------------------------------------------------------
class Kamus:
    def __init__(self, tambahan=()):
        try:
            import Sastrawi
            from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
        except ImportError:
            sys.exit("Sastrawi belum terpasang. Jalankan: pip install Sastrawi")
        p = Path(Sastrawi.__file__).parent / "Stemmer" / "data" / "kata-dasar.txt"
        self.dasar = {w.strip().lower() for w in p.read_text(encoding="utf-8").splitlines() if w.strip()}
        self.dasar |= {w.lower() for w in tambahan}
        self.stemmer = StemmerFactory().create_stemmer()
        self._cache = {}

    def kenal(self, kata):
        kata = kata.lower()
        if kata in self._cache:
            return self._cache[kata]
        bagian = [b for b in re.split(r"[-/']", kata) if b]
        hasil = all(b in self.dasar or self.stemmer.stem(b) in self.dasar for b in bagian)
        self._cache[kata] = hasil
        return hasil


# ---------------------------------------------------------------------------
# Membaca korpus
# ---------------------------------------------------------------------------
def baca_conllu(path):
    for baris in Path(path).read_text(encoding="utf-8").splitlines():
        if baris.startswith("# text = "):
            yield baris[len("# text = "):]


def baca_tsv(path):
    tokens = []
    for baris in Path(path).read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if not baris:
            if tokens:
                yield gabung_token(tokens)
                tokens = []
            continue
        tokens.append(baris.split("\t")[0])
    if tokens:
        yield gabung_token(tokens)


def baca_txt(path):
    for baris in Path(path).read_text(encoding="utf-8").splitlines():
        if baris.strip() and not baris.startswith("#"):
            yield baris


def pecah_kalimat(teks):
    teks = teks.replace("’", "'").replace("‘", "'")
    teks = " ".join(teks.split())
    potongan = re.split(r"(?<=[.?!])\s+(?=[A-Z])", teks)
    hasil, buffer = [], ""
    for p in potongan:
        buffer = f"{buffer} {p}".strip() if buffer else p
        if SINGKATAN_TITIK.search(buffer):
            continue  # titik milik singkatan / inisial, jangan dipecah
        hasil.append(buffer)
        buffer = ""
    if buffer:
        hasil.append(buffer)
    return hasil


# ---------------------------------------------------------------------------
# Pemeriksaan satu kalimat. Mengembalikan alasan penolakan atau None.
# ---------------------------------------------------------------------------
def periksa(k, kamus, maks_oov):
    if not KARAKTER_SAH.match(k):
        return "karakter_tidak_sah"
    if not k[0].isupper():
        return "awal_bukan_kapital"
    if re.match(r"(?:Dan|Sedangkan|Tetapi|Sehingga|Serta|Atau|Tapi)\b", k):
        return "awal_konjungsi"  # konjungsi intrakalimat tidak dipakai di awal kalimat
    if re.search(r"\b(?:Dr|Prof|Ir|Drs|St|Jl|No|Hj|Mr|Ny|Tn|Sdr|Bpk|dr|Kol|Letjen|Mayjen)\.$", k):
        return "akhir_singkatan"  # potongan kalimat yang terpecah di singkatan
    if k[-1] not in ".?":
        return "akhir_tanpa_titik"
    if k.count("(") != k.count(")") or "()" in k:
        return "kurung_tidak_seimbang"
    if re.search(r"\.\.|--| - |\bet al\b|\bvs\b", k):
        return "tanda_baca_lain"
    t = tokenisasi(k)
    if gabung_token(t) != k:
        return "tokenisasi"
    if not 6 <= len(t) <= 45:
        return "panjang"
    if any(x == "." for x in t[:-1]) or "?" in t[:-1]:
        return "titik_di_tengah"
    if any(x.endswith("-") or x.startswith("-") for x in t):
        return "tanda_hubung_lepas"
    rendah = [x.lower() for x in t]

    # Angka: desimal memakai koma, ribuan memakai titik. "pukul 08.00" dan
    # "Gambar 4.1" sah. Satu kelompok tiga angka setelah koma (0,812) dianggap desimal.
    for i, x in enumerate(t):
        if re.fullmatch(r"\d+\.\d{1,2}", x):
            sebelum = t[i - 1].lower() if i else ""
            if not (sebelum == "pukul" or sebelum in {"gambar", "tabel", "bab", "subbab",
                                                      "persamaan", "lampiran", "bagian"}):
                return "desimal_bertitik"
        if re.fullmatch(r"\d{1,3}(?:,\d{3}){2,}|Rp\d{1,3}(?:,\d{3})+", x):
            return "ribuan_berkoma"

    # Kata tidak baku / informal / salah serangkai
    if any(x in TIDAK_BAKU_SEMUA for x in rendah):
        return "tidak_baku"
    if any(x in SALAH_SERANGKAI for x in rendah):
        return "salah_serangkai"
    for a, b in zip(rendah, rendah[1:]):
        if a in UNSUR_TERIKAT and b.isalpha():
            return "unsur_terikat_dipisah"
        if a + b in SERANGKAI or (a == "ke" and a + b in ORDINAL):
            return "salah_dipisah"
        if a == "di" and b.isalpha() and b not in kamus.dasar:
            akar = kamus.stemmer.stem(b)
            if akar in kamus.dasar and b in {akar + "kan", akar + "i"}:
                return "awalan_di_dipisah"  # "di lakukan", "di jelaskan" (bukan "di berbagai")
    if any(x in {"PT.", "CV."} for x in t) or re.search(r"\b(?:PT|CV)\.", k):
        return "singkatan_bertitik"
    if any(x in {"dkk", "dll", "dsb", "dst", "hlm", "Tbk"} for x in t):
        return "singkatan_tanpa_titik"
    if re.search(r"\bRp \d", k):
        return "rupiah_berspasi"
    for i, x in enumerate(t):
        if (len(x) == 1 and x.isalpha() and x.islower()
                and not (i and rendah[i - 1] in {"uji", "nilai", "koefisien", "variabel", "huruf"})):
            return "huruf_tunggal"
    if re.search(r"pada tahun \d{4}, (?:memiliki|mempunyai)", k):
        return "koma_subjek_predikat"
    for i in range(len(t) - 1):
        if rendah[i] in KATA_TUTURAN and t[i + 1] == ",":
            return "koma_kutipan"
        if t[i] == "," and rendah[i + 1] in {"kata", "ujar", "ujarnya", "katanya", "tuturnya"}:
            return "koma_kutipan"
        if t[i] in UNSUR_GEOGRAFI and t[i + 1][:1].isupper() and t[i + 1].isalpha():
            return "kapital_nama_geografi"

    # Huruf kapital
    if any(x in HARI_BULAN for x in t):
        return "hari_bulan_huruf_kecil"
    for i in range(1, len(t) - 1):
        if t[i] == "Bahasa" and t[i - 1] not in {".", "("} and t[i + 1][:1].isupper():
            return "bahasa_kapital"

    # Koma
    for frasa in PENGHUBUNG_ANTARKALIMAT:
        n = len(frasa)
        if tuple(t[:n]) == frasa and (len(t) <= n or t[n] != ","):
            return "koma_penghubung"
    if t[0] in PEMBUKA_ANAK_KALIMAT and "," not in t:
        return "koma_anak_kalimat"
    # Koma pertama setelah pembuka kalimat (penghubung, keterangan, anak kalimat)
    # bukan bagian dari pemerincian.
    koma_pembuka = None
    if "," in t and (t[0] in PEMBUKA_ANAK_KALIMAT or t[0] in PEMBUKA_KOMA_OPSIONAL
                     or any(tuple(t[:len(f)]) == f for f in PENGHUBUNG_ANTARKALIMAT)):
        koma_pembuka = t.index(",")
    for i in range(1, len(t)):
        # Pemerincian "A, B dan C" tanpa koma sebelum dan/atau (EYD: "A, B, dan C")
        if rendah[i] in {"dan", "atau"} and t[i - 1] != ",":
            awal = max(0, i - 4)
            koma = [j for j in range(awal, i) if t[j] == ","]
            if koma:
                j = koma[-1]
                isi = t[j + 1:i]
                if (j != koma_pembuka and rendah[j + 1] not in KOMA_DILINDUNGI_SEBELUM
                        and all(x[:1].isalnum() for x in isi)):
                    return "koma_pemerincian"
        if t[i - 1] == "," and rendah[i] in TANPA_KOMA_SEBELUM:
            if not (rendah[i] == "karena" and i + 1 < len(t) and rendah[i + 1] == "itu"):
                return "koma_berlebih"
        if rendah[i] in PERLU_KOMA_SEBELUM:
            sebelum = rendah[i - 1]
            if sebelum == "akan":
                if i >= 2 and t[i - 2] != ",":
                    return "koma_kurang"
            elif t[i - 1] != ",":
                return "koma_kurang"

    # Kosakata: kata huruf kecil yang tidak dikenal (kemungkinan typo/asing)
    oov = 0
    for i, x in enumerate(t):
        if not re.match(r"^[A-Za-z]", x) or x in {"di-", "Rp"}:
            continue
        if i > 0 and x[0].isupper():
            continue  # nama diri
        if i == 0 and not kamus.kenal(x):
            continue  # kata pertama berhuruf kapital yang tidak dikenal = kemungkinan nama
        if not kamus.kenal(x):
            oov += 1
    if oov > maks_oov:
        return "kata_tidak_dikenal"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("berkas", nargs="+")
    ap.add_argument("--output", required=True)
    ap.add_argument("--maks-oov", type=int, default=0,
                    help="jumlah maksimum kata huruf kecil yang tidak dikenal kamus")
    ap.add_argument("--hindari", nargs="*", default=[],
                    help="berkas kalimat lain yang tidak boleh terduplikasi")
    ap.add_argument("--kosakata", nargs="*", default=["data/kalimat_bersih.txt"],
                    help="berkas kalimat yang kosakatanya dianggap benar")
    ap.add_argument("--laporan", action="store_true", help="tampilkan contoh kalimat yang ditolak")
    args = ap.parse_args()

    tambahan = set()
    for p in args.kosakata:
        if Path(p).exists():
            tambahan |= {x.lower() for x in tokenisasi(Path(p).read_text(encoding="utf-8")) if x.isalpha()}
    kamus = Kamus(tambahan)

    def kunci(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    sudah = set()
    for p in args.hindari:
        if Path(p).exists():
            sudah |= {kunci(b) for b in Path(p).read_text(encoding="utf-8").splitlines() if b.strip()}

    alasan, contoh_tolak, lolos = Counter(), {}, []
    for berkas in args.berkas:
        ext = Path(berkas).suffix.lower()
        pembaca = baca_conllu if ext == ".conllu" else baca_tsv if ext == ".tsv" else baca_txt
        for teks in pembaca(berkas):
            for k in pecah_kalimat(teks):
                kk = kunci(k)
                if kk in sudah:
                    alasan["duplikat"] += 1
                    continue
                sudah.add(kk)
                r = periksa(k, kamus, args.maks_oov)
                if r:
                    alasan[r] += 1
                    contoh_tolak.setdefault(r, []).append(k)
                else:
                    lolos.append(k)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lolos) + "\n", encoding="utf-8")
    total = len(lolos) + sum(alasan.values())
    print(f"{args.output}: {len(lolos)} lolos dari {total} kalimat")
    for r, n in alasan.most_common():
        print(f"  ditolak {r:26} {n}")
    if args.laporan:
        for r, ks in contoh_tolak.items():
            print(f"\n== {r}")
            for k in ks[:3]:
                print("  ", k)


if __name__ == "__main__":
    main()
