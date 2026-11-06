"""Tes mesin koreksi dan pembaca dokumen web. Jalankan: python -m unittest discover -s tests"""
import importlib.util
import sys
import tempfile
import threading
import time
import types
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "web"))

import ekstrak as ek  # noqa: E402
import koreksi as ko  # noqa: E402
from kamus_baku import kena_kamus  # noqa: E402


def diperiksa(teks):
    paragraf, _, _ = ek.baca_teks(teks)
    return [p.teks for p in ek.saring_bagian(paragraf)[0]]


def koreksi(kalimat, label=None):
    """label: {token: label model}. Token lain berlabel O."""
    token = ko.tokenisasi(kalimat)
    lab = [((label or {}).get(t, "O"), 0.9) for t, _, _ in token]
    temuan = ko.susun_temuan(kalimat, token, lab, Counter())
    return temuan, ko.rakit(kalimat, temuan)


ISI = "Penelitian ini membahas pengaruh media sosial terhadap prestasi belajar mahasiswa di kampus."


class SaringBagian(unittest.TestCase):
    def test_lampiran_surat_bukan_judul(self):
        for baris in ("Lampiran: 1 berkas", "Lampiran : 2 lembar", "Lampiran 1 berkas"):
            self.assertEqual(diperiksa(f"{baris}\n\n{ISI}"), [ISI], baris)

    def test_kalimat_berawalan_lampiran_atau_referensi(self):
        for baris in ("Lampiran berisi data penelitian.", "Referensi ini sangat penting sekali."):
            self.assertIn(baris, diperiksa(f"{baris}\n\n{ISI}"))

    def test_judul_daftar_pustaka_dan_lampiran_tetap_dilewati(self):
        rujukan = "Sugiyono. 2019. Metode Penelitian Kuantitatif dan Kualitatif untuk Mahasiswa. Bandung: Alfabeta."
        for judul in ("DAFTAR PUSTAKA", "Daftar Pustaka", "REFERENCES", "LAMPIRAN", "Lampiran 1",
                      "Lampiran A", "Lampiran 1: Kuesioner Penelitian"):
            self.assertEqual(diperiksa(f"{ISI}\n\n{judul}\n\n{rujukan}"), [ISI], judul)

    def test_bab_mengakhiri_daftar_pustaka(self):
        teks = f"DAFTAR PUSTAKA\n\nSugiyono. 2019. Metode Penelitian.\n\nBAB II\n\n{ISI}"
        self.assertEqual(diperiksa(teks), [ISI])

    def test_daftar_isi_berakhir_di_judul_bernomor(self):
        for judul in ("1. Pendahuluan", "I. PENDAHULUAN", "A. Pendahuluan"):
            self.assertEqual(diperiksa(f"Daftar Isi\n\nBab satu 1\n\n{judul}\n\n{ISI}"), [ISI], judul)

    def test_daftar_isi_berakhir_di_kalimat_isi(self):
        teks = f"Daftar Isi\n\nLatar Belakang ........ 1\n\nMetode ........ 2\n\nLatar Belakang\n\n{ISI}"
        self.assertEqual(diperiksa(teks), [ISI])


class Keterangan(unittest.TestCase):
    def test_kalimat_isi_tetap_diperiksa(self):
        for k in ("Tabel 4.1 menunjukkan bahwa nilai rata-rata siswa meningkat pada siklus kedua.",
                  "Gambar 2 memperlihatkan arsitektur sistem yang diusulkan dalam penelitian ini.",
                  "Lampiran 1 berisi kuesioner yang disebarkan kepada seluruh responden penelitian."):
            self.assertEqual(diperiksa(k), [k])

    def test_keterangan_tetap_dilewati(self):
        for k in ("Tabel 4.1 Hasil Uji Validitas Instrumen Penelitian pada Siswa Kelas Lima Sekolah Dasar.",
                  "Gambar 2.1. Arsitektur sistem yang diusulkan untuk pengolahan data citra digital ini.",
                  "Sumber 1 Data Badan Pusat Statistik Provinsi Jawa Barat Tahun Dua Ribu Dua Puluh."):
            self.assertEqual(ek.layak_diperiksa(ek.Paragraf(teks=k)), "keterangan gambar/tabel", k)


class KalimatTanpaTitik(unittest.TestCase):
    def test_kalimat_pendek_tetap_diperiksa(self):
        for k in ("Data dikumpulkan dari responden penelitian", "Metode ini dapat digunakan untuk analisis"):
            self.assertEqual(diperiksa(k), [k])

    def test_judul_tetap_dilewati(self):
        for k in ("Pengaruh Media Sosial terhadap Prestasi Belajar Mahasiswa",
                  "Pengaruh media sosial terhadap prestasi belajar mahasiswa",
                  "2.1 Metode ini dapat digunakan untuk analisis",
                  "Latar belakang masalah"):
            self.assertEqual(diperiksa(k), [], k)


class Encoding(unittest.TestCase):
    def baca(self, raw):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_bytes(raw)
            return ek.baca_dokumen(p, "a.txt")[0][0].teks

    def test_ansi_panjang_ganjil_dan_genap(self):
        for akhir in (".", ".."):
            teks = "Penelitian “media sosial” di kampus sangat baik" + akhir
            self.assertEqual(self.baca(teks.encode("cp1252")), teks)

    def test_utf8_dan_utf16_ber_bom(self):
        teks = "Penelitian “media sosial” di kampus."
        for enc in ("utf-8", "utf-8-sig", "utf-16"):
            self.assertEqual(self.baca(teks.encode(enc)), teks, enc)


class PecahKalimat(unittest.TestCase):
    def jumlah(self, t):
        return len(ek.pecah_kalimat(t))

    def test_akronim_di_akhir_kalimat(self):
        self.assertEqual(self.jumlah("Kebijakan itu berasal dari AS. Selain itu, datanya naik."), 2)
        self.assertEqual(self.jumlah("Penelitian dilakukan pada siswa SD. Hasilnya meningkat."), 2)

    def test_dll_di_akhir_kalimat(self):
        self.assertEqual(self.jumlah("Alat tulis meliputi buku, pena, dll. Selain itu, tersedia juga spidol."), 2)
        self.assertEqual(self.jumlah("Contohnya buku, pena, dsb. Hal ini penting bagi siswa."), 2)

    def test_dll_di_tengah_kalimat(self):
        self.assertEqual(self.jumlah("Buku, pena, dll. juga tersedia di sini."), 1)

    def test_angka_di_akhir_kalimat(self):
        self.assertEqual(self.jumlah("Nilainya 3.5. Hasil itu cukup baik."), 2)
        self.assertEqual(self.jumlah("Lihat pada Gambar 4.1. Hasilnya cukup baik."), 2)

    def test_penomoran_tidak_memecah(self):
        self.assertEqual(self.jumlah("1.1. Latar belakang penelitian ini dijelaskan di sini."), 1)
        self.assertEqual(self.jumlah("1. Latar belakang penelitian ini dijelaskan di sini."), 1)

    def test_inisial_tidak_memecah(self):
        self.assertEqual(self.jumlah("Surat ditujukan a.n. Budi dan rekannya."), 1)

    def test_singkatan_tidak_memecah(self):
        for t in ("Lokasinya di RT. 05 Kelurahan Baru.", "Karyawan PT. Sejahtera hadir semua.",
                  "Data dari Rasul saw. Beliau bersabda.", "Dibimbing oleh Dr. Budi di kampus."):
            self.assertEqual(self.jumlah(t), 1, t)


class Kamus(unittest.TestCase):
    def test_aturan(self):
        self.assertTrue(kena_kamus("analisa", 3))
        self.assertTrue(kena_kamus("Analisa", 0))
        self.assertFalse(kena_kamus("Syah", 3))
        self.assertFalse(kena_kamus("ANALISA", 0))

    def test_nama_diri_tidak_diubah(self):
        k = "Penelitian ini dibimbing oleh Muhammad Syah dan Karna Wijaya."
        temuan, benar = koreksi(k)
        self.assertEqual(temuan, [])
        self.assertEqual(benar, k)

    def test_mencangkup(self):
        temuan, benar = koreksi("Penelitian ini mencangkup banyak hal.")
        self.assertEqual(benar, "Penelitian ini mencakup banyak hal.")
        self.assertEqual(temuan[0]["label"], "TIDAK_BAKU")

    def test_kata_tidak_baku_tetap_ditandai(self):
        _, benar = koreksi("Analisa data dan analisa hasil dilakukan.")
        self.assertEqual(benar, "Analisis data dan analisis hasil dilakukan.")


class Rakit(unittest.TestCase):
    def test_ganti_titik_tanpa_suntingan_lain(self):
        _, benar = koreksi("Data sudah dikumpulkan, proses dilakukan kemudian.", {",": "GANTI_TITIK"})
        self.assertEqual(benar, "Data sudah dikumpulkan. Proses dilakukan kemudian.")

    def test_ganti_titik_lalu_kata_kamus(self):
        _, benar = koreksi("Data sudah dikumpulkan, analisa dilakukan kemudian.", {",": "GANTI_TITIK"})
        self.assertEqual(benar, "Data sudah dikumpulkan. Analisis dilakukan kemudian.")

    def test_ganti_titik_lalu_gabung(self):
        _, benar = koreksi("Data sudah masuk, di lakukan analisis.", {",": "GANTI_TITIK", "di": "GABUNG"})
        self.assertEqual(benar, "Data sudah masuk. Dilakukan analisis.")

    def test_tanda_baca(self):
        _, benar = koreksi("Oleh karena itu data diolah, sehingga jelas",
                           {"itu": "TAMBAH_KOMA", ",": "HAPUS", "jelas": "TAMBAH_TITIK"})
        self.assertEqual(benar, "Oleh karena itu, data diolah sehingga jelas.")

    def test_koma_ditambah_tepat_sebelum_tanda_yang_dihapus(self):
        _, benar = koreksi("Data kami , olah.", {"Data": "TAMBAH_KOMA", ",": "HAPUS"})
        self.assertEqual(benar, "Data, kami olah.")

    def test_token_pertama_dihapus(self):
        _, benar = koreksi(", data diolah di sini.", {",": "HAPUS"})
        self.assertEqual(benar, "data diolah di sini.")

    def test_hanya_temuan_terpilih(self):
        k = "Data analisa dikampus sudah selesai."
        token = ko.tokenisasi(k)
        lab = [("O", 1.0)] * len(token)
        lab[2] = ("KAPITAL", 0.4)
        temuan = ko.susun_temuan(k, token, lab, Counter())
        self.assertEqual(len(temuan), 2)
        self.assertEqual(ko.rakit(k, temuan), "Data analisis Dikampus sudah selesai.")
        self.assertEqual(ko.rakit(k, [t for t in temuan if t["yakin"]]), "Data analisis dikampus sudah selesai.")
        self.assertEqual(ko.rakit(k, []), k)


class SaranAngka(unittest.TestCase):
    def test_format_salah_diperbaiki(self):
        for salah, benar in (("0.05", "0,05"), ("25.5%", "25,5%"), ("12,500", "12.500"), ("Rp12,500", "Rp12.500"),
                             ("12,500.50", "12.500,50"), ("08:00", "08.00")):
            self.assertEqual(ko.saran_angka(salah), benar, salah)

    def test_angka_benar_tidak_dirusak(self):
        self.assertIsNone(ko.saran_angka("0,812"))
        self.assertIsNone(ko.saran_angka("1:10"))
        self.assertIsNone(ko.saran_angka("25:00"))
        self.assertIsNone(ko.saran_angka("3.1.2"))
        self.assertIsNone(ko.saran_angka("12.500"))
        self.assertIsNone(ko.saran_angka("4.1", ["pada", "gambar"]))
        self.assertIsNone(ko.saran_angka("08.00", ["mulai", "pukul"]))

    def test_konteks_jam(self):
        self.assertEqual(ko.saran_angka("8:30", ["mulai", "pukul"]), "8.30")

    def test_lewat_susun_temuan(self):
        k = "Hasilnya terlihat pada Gambar 4.1 dengan nilai 0.05 saja."
        temuan, benar = koreksi(k, {"4.1": "FORMAT_ANGKA", "0.05": "FORMAT_ANGKA"})
        self.assertEqual([t["teks"] for t in temuan], ["0.05"])
        self.assertEqual(benar, "Hasilnya terlihat pada Gambar 4.1 dengan nilai 0,05 saja.")


class SaranGabung(unittest.TestCase):
    def test_kata_ulang(self):
        for bagian, hasil in ((["kelompok", "kelompok"], "kelompok-kelompok"), (["anak", "anaknya"], "anak-anaknya"),
                              (["tumbuh", "tumbuhan"], "tumbuh-tumbuhan"), (["sayur", "mayur"], "sayur-mayur"),
                              (["lauk", "pauk"], "lauk-pauk")):
            self.assertEqual(ko.saran_gabung(bagian), hasil)

    def test_bukan_kata_ulang(self):
        for bagian in (["ada", "pada"], ["data", "sata"], ["ber", "komputer"]):
            self.assertNotIn("-", ko.saran_gabung(bagian), bagian)

    def test_imbuhan_dan_serangkai(self):
        for bagian, hasil in ((["di", "lakukan"], "dilakukan"), (["di", "analisa"], "dianalisis"),
                              (["antar", "muka"], "antarmuka"), (["Tik", "Tok"], "TikTok"),
                              (["sub", "bab"], "subbab"), (["di", "update"], "di-update")):
            self.assertEqual(ko.saran_gabung(bagian), hasil)


class KataAsing(unittest.TestCase):
    def test_bentuk_asing(self):
        for salah, benar in (("mengupload", "meng-upload"), ("diupdate", "di-update"), ("mendownload", "men-download"),
                             ("membackup", "mem-backup")):
            self.assertEqual(ko.LEKSIKON.bentuk_asing(salah), benar)

    def test_kata_indonesia_tidak_dihubung(self):
        for k in ("mengedit", "mencakup", "menpemuda", "memproses"):
            self.assertIsNone(ko.LEKSIKON.bentuk_asing(k), k)


@unittest.skipUnless(importlib.util.find_spec("symspellpy"), "symspellpy belum terpasang")
class SaranEjaan(unittest.TestCase):
    def test_istilah_asing(self):
        self.assertEqual(ko.saran_ejaan("mengupload"), "meng-upload")

    def test_kata_turunan_yang_tidak_ada_di_leksikon(self):
        self.assertNotIn("mengagendai", ko.LEKSIKON.frek)
        self.assertEqual(ko.saran_ejaan("mengagenadi"), "mengagendai")

    def test_salah_ketik_umum(self):
        for salah, benar in (("penelitain", "penelitian"), ("perbedaanya", "perbedaannya"), ("dianalis", "dianalisis"),
                             ("mahasiwa", "mahasiswa"), ("Penelitain", "Penelitian")):
            self.assertEqual(ko.saran_ejaan(salah), benar)


class BerkasRusak(unittest.TestCase):
    def galat(self, nama):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / nama
            p.write_bytes(b"bukan dokumen")
            with self.assertRaises(ValueError) as c:
                ek.ekstrak(p, nama)
        return str(c.exception)

    @unittest.skipUnless(importlib.util.find_spec("pymupdf"), "pymupdf belum terpasang")
    def test_pdf(self):
        pesan = self.galat("rusak.pdf")
        self.assertIn("PDF rusak", pesan)
        self.assertNotIn("rusak.pdf", pesan)

    @unittest.skipUnless(importlib.util.find_spec("pymupdf"), "pymupdf belum terpasang")
    def test_pdf_berkata_sandi_bisa_dihapus(self):
        import pymupdf

        with tempfile.TemporaryDirectory() as d:          # gagal di Windows jika berkasnya masih terkunci
            p = Path(d) / "sandi.pdf"
            doc = pymupdf.open()
            doc.new_page().insert_text((72, 72), "Rahasia sekali isinya.")
            doc.save(p, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="a", owner_pw="b")
            doc.close()
            with self.assertRaises(ValueError) as c:
                ek.ekstrak(p, "sandi.pdf")
        self.assertIn("kata sandi", str(c.exception))

    @unittest.skipUnless(importlib.util.find_spec("docx"), "python-docx belum terpasang")
    def test_docx(self):
        self.assertIn("DOCX rusak", self.galat("rusak.docx"))


@unittest.skipUnless(all(importlib.util.find_spec(m) for m in ("fastapi", "python_multipart")),
                     "pustaka web belum terpasang")
class GalatServer(unittest.TestCase):
    def jalankan(self, galat):
        from web import app as web_app

        with mock.patch.object(web_app, "ekstrak", side_effect=galat), \
                mock.patch.object(web_app.traceback, "print_exc"), \
                mock.patch.dict(web_app._jobs, {"j": {}}):
            web_app.proses("j", None, "a.pdf", None)
            return web_app._jobs["j"]

    def test_galat_tak_terduga_tidak_membocorkan_rincian(self):
        for galat in (OSError(r"C:\rahasia\berkas.pdf"), RuntimeError(r"C:\rahasia\berkas.pdf")):
            job = self.jalankan(galat)
            self.assertEqual(job["status"], "gagal")
            self.assertNotIn("rahasia", job["pesan"])

    def test_galat_untuk_pengguna_tetap_tampil(self):
        self.assertEqual(self.jalankan(ValueError("PDF dilindungi kata sandi."))["pesan"], "PDF dilindungi kata sandi.")


@unittest.skipUnless(all(importlib.util.find_spec(m) for m in ("fastapi", "python_multipart")),
                     "pustaka web belum terpasang")
class MuatModel(unittest.TestCase):
    def test_model_dimuat_sekali(self):
        from web import app as web_app

        dimuat = []

        class Pemeriksa:
            def __init__(self, _):
                dimuat.append(1)
                time.sleep(0.2)

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.json").write_text("{}")
            with mock.patch.object(web_app, "MODEL_DIR", Path(d)), \
                    mock.patch.dict(web_app._model, {"objek": None, "galat": None}), \
                    mock.patch.dict(sys.modules, {"periksa": types.SimpleNamespace(Pemeriksa=Pemeriksa)}):
                utas = [threading.Thread(target=web_app.model) for _ in range(4)]
                for u in utas:
                    u.start()
                for u in utas:
                    u.join()
        self.assertEqual(len(dimuat), 1)


if __name__ == "__main__":
    unittest.main()
