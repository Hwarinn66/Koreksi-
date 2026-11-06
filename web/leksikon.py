"""
leksikon.py
Daftar kata baku (web/data/leksikon.tsv) dan pencari saran ejaan.

Saran dicari dengan dua cara, lalu digabung:
  1. SymSpell langsung pada daftar kata (kata yang pernah muncul di data bersih).
  2. Sadar imbuhan: imbuhan dilepas, kata dasarnya dicari di daftar kata dasar, lalu dirakit
     ulang (mengagenadi -> me + agenda + i -> mengagendai). Ini menangani kata turunan yang tidak ada
     di daftar kata.
"""
from pathlib import Path

DIR = Path(__file__).resolve().parent / "data"
VOKAL = set("aiueo")

AWALAN = ["", "di", "ke", "se", "ber", "ter", "per", "me", "pe", "memper", "diper", "keber", "kese"]
AKHIRAN = ["", "kan", "an", "i", "nya", "kannya", "annya", "inya", "lah", "kah", "pun"]
# bentuk permukaan awalan -> (awalan dasar, huruf awal kata dasar yang mungkin luluh)
PERMUKAAN = {
    "": ("", ""), "di": ("di", ""), "ke": ("ke", ""), "se": ("se", ""), "ber": ("ber", ""),
    "be": ("ber", ""), "ter": ("ter", ""), "te": ("ter", ""), "per": ("per", ""), "pe": ("pe", ""),
    "memper": ("memper", ""), "diper": ("diper", ""), "keber": ("keber", ""), "kese": ("kese", ""),
    "me": ("me", ""), "mem": ("me", "p"), "men": ("me", "t"), "meng": ("me", "k"), "meny": ("me", "s"),
    "pem": ("pe", "p"), "pen": ("pe", "t"), "peng": ("pe", "k"), "peny": ("pe", "s"),
}
# Istilah asing yang lazim diberi imbuhan tetapi tidak ada di data bersih (meng-upload, di-update).
ISTILAH_ASING = {"upload", "download", "update", "install", "logout", "share", "backup", "print", "delete",
                 "copy", "paste", "submit", "follow"}


def pasang_awalan(awalan, dasar):
    """Merakit awalan + kata dasar dengan peluluhan meN-/peN-."""
    if not dasar:
        return awalan
    if awalan in ("me", "pe"):
        c, c2 = dasar[0], dasar[1:2]
        luluh = c2 in VOKAL
        if c in VOKAL or c in "gh":
            return awalan + "ng" + dasar
        if c == "k":
            return awalan + "ng" + (dasar[1:] if luluh else dasar)
        if c in "bfv":
            return awalan + "m" + dasar
        if c == "p":
            return awalan + "m" + (dasar[1:] if luluh else dasar)
        if c in "cdjz":
            return awalan + "n" + dasar
        if c == "t":
            return awalan + "n" + (dasar[1:] if luluh else dasar)
        if c == "s":
            return awalan + ("ny" + dasar[1:] if luluh else "n" + dasar)
        return awalan + dasar                    # l, m, n, r, w, y
    if awalan in ("ber", "ter", "per") and dasar[0] == "r":
        return awalan[:-1] + dasar
    return awalan + dasar


def jarak_dl(a, b):
    """Jarak Damerau-Levenshtein (versi OSA)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            biaya = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + biaya)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


class Leksikon:
    def __init__(self, berkas=DIR / "leksikon.tsv", berkas_dasar=DIR / "kata_dasar.txt"):
        self.frek, self.bentuk = {}, {}
        for baris in berkas.read_text(encoding="utf-8").splitlines():
            if not baris or baris.startswith("#"):
                continue
            kata, n, b = (baris.split("\t") + ["", ""])[:3]
            self.frek[kata] = int(n)
            if b:
                self.bentuk[kata] = b
        self.dasar = set(berkas_dasar.read_text(encoding="utf-8").split()) if berkas_dasar.exists() else set()
        self._sym = self._sym_dasar = None

    def kenal(self, kata):
        return kata.lower() in self.frek

    def kata_asing(self, kata):
        return kata in ISTILAH_ASING or (kata in self.frek and kata not in self.dasar)

    def bentuk_tulis(self, kata):
        """Bentuk tulis yang lazim, mis. tiktok -> TikTok. None jika tidak ada bentuk khusus."""
        return self.bentuk.get(kata.lower())

    @staticmethod
    def _buat(kata_frek):
        from symspellpy import SymSpell
        sym = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        for k, n in kata_frek:
            if len(k) >= 2:
                sym.create_dictionary_entry(k, n)
        return sym

    @property
    def symspell(self):
        if self._sym is None:
            self._sym = self._buat(self.frek.items())
        return self._sym

    @property
    def symspell_dasar(self):
        if self._sym_dasar is None:
            self._sym_dasar = self._buat((k, self.frek.get(k, 1)) for k in self.dasar)
        return self._sym_dasar

    def _calon_imbuhan(self, k):
        """Calon dari pelepasan imbuhan: {kata: (jarak, frekuensi_dasar)}."""
        from symspellpy import Verbosity
        calon = {}
        for perm, (awal, luluh) in PERMUKAAN.items():
            if not k.startswith(perm):
                continue
            for akhir in AKHIRAN:
                if akhir and not k.endswith(akhir):
                    continue
                inti = k[len(perm):len(k) - len(akhir) if akhir else None]
                if len(inti) < 3:
                    continue
                for coba in {inti, luluh + inti} if luluh else {inti}:
                    for s in self.symspell_dasar.lookup(coba, Verbosity.CLOSEST, max_edit_distance=1):
                        kata = pasang_awalan(awal, s.term) + akhir
                        if kata != k and kata not in calon:
                            j = jarak_dl(kata, k)
                            if j <= 2:
                                calon[kata] = (j, s.count)
        return calon

    def saran(self, kata, maks=3):
        """Saran ejaan untuk kata yang salah ketik. Mengembalikan daftar kata (huruf kecil)."""
        from symspellpy import Verbosity
        k = kata.lower()
        if len(k) < 3:
            return []
        jarak = 1 if len(k) <= 4 else 2
        calon = {}
        for s in self.symspell.lookup(k, Verbosity.ALL, max_edit_distance=jarak):
            if s.term == k:
                continue
            # buang saran yang hanya membuang imbuhan (dianalis -> analis)
            if s.distance == 2 and len(s.term) < len(k) and (k.endswith(s.term) or k.startswith(s.term)):
                continue
            calon[s.term] = (s.distance, s.count)
        if len(k) >= 5:
            for kt, nilai in self._calon_imbuhan(k).items():
                if kt not in calon or nilai[0] < calon[kt][0]:
                    calon[kt] = nilai
        # -an + -nya yang kurang satu n: perbedaanya -> perbedaannya
        if k.endswith("anya") and k[:-3] + "n" in self.frek:
            calon[k[:-3] + "nnya"] = (0, self.frek[k[:-3] + "n"])
        # utamakan: jarak kecil, kata yang memang pernah muncul, huruf awal sama, frekuensi
        urut = sorted(calon.items(), key=lambda x: (x[1][0], x[0] not in self.frek,
                                                    k[:1] != x[0][:1], -x[1][1]))
        return [kt for kt, _ in urut[:maks]]

    def bentuk_asing(self, kata):
        """di + kata asing -> di-kata (meng-upload, di-update). None jika bukan pola itu."""
        k = kata.lower()
        if k in self.frek:
            return None
        for awal in ("meng", "men", "mem", "di", "ter", "ber", "me", "ke"):
            sisa = k[len(awal):]
            if not k.startswith(awal) or len(sisa) < 3 or sisa.endswith(("kan", "an", "nya")):
                continue
            # men-/mem- hanya untuk istilah yang pasti asing: "menpemuda" lebih mungkin salah ketik.
            if sisa in ISTILAH_ASING or (awal not in ("men", "mem") and self.kata_asing(sisa)):
                return f"{awal}-{sisa}"
        return None


LEKSIKON = Leksikon()
