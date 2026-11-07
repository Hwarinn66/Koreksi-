# Data dengan kesalahan ASLI

Kalimat dari skripsi dan jurnal sungguhan yang dikoreksi manual sesuai EYD V. Yang diubah
hanya ejaan dan tanda baca, bukan pilihan kata penulis.

Pembagian dilakukan **per dokumen** di `pembagian.json`:
- `test_asli` (17 dokumen: 8 skripsi lama + 9 dokumen baru): hanya untuk evaluasi, tidak pernah dilatih.
- `train_asli` (19 dokumen): ikut dilatih, dan kalimat benarnya juga dipakai sebagai bahan data
  sintetis (`data/kalimat_asli_train.txt`, dibuat oleh `alat/gabung_asli.py`, hanya masuk split train).

Satu dokumen tidak pernah dipecah ke dua split, jadi gaya tulisan dokumen uji tidak bocor ke data latih.

| Split | Dokumen | Kalimat | Berkesalahan | Token salah |
|---|---|---|---|---|
| test_asli | 17 | 1855 | 685 | 1159 |
| train_asli | 19 | 967 | 245 | 394 |

## Dokumen batch kedua (skripsi10–11, jurnal01–26)

Kalimat diambil merata dari isi dokumen (`alat/susun_daftar.py ambil`, 120 kalimat untuk skripsi,
60 untuk jurnal), lalu kalimat yang rusak, tabel, judul yang menempel, daftar pustaka, dan kalimat
yang memuat data pribadi dilewati (`X` di `koreksi.txt`).

| ID | Split | Bidang | Kalimat | Berkesalahan | Token salah | Ragu |
|---|---|---|---|---|---|---|
| jurnal01 | train_asli | Hukum | 53 | 19 | 29 | 2 |
| jurnal02 | train_asli | Hukum (Supremasi Jurnal Hukum) | 54 | 0 | 0 | 0 |
| jurnal03 | train_asli | Hukum (Supremasi Jurnal Hukum) | 51 | 2 | 2 | 0 |
| jurnal04 | test_asli | Hukum (Supremasi Jurnal Hukum) | 58 | 0 | 0 | 0 |
| jurnal05 | train_asli | Hukum | 46 | 10 | 11 | 1 |
| jurnal06 | train_asli | Hukum | 52 | 6 | 6 | 0 |
| jurnal07 | test_asli | Hukum | 55 | 3 | 3 | 0 |
| jurnal08 | train_asli | Hukum | 43 | 8 | 10 | 3 |
| jurnal09 | test_asli | Hukum | 48 | 5 | 7 | 1 |
| jurnal10 | train_asli | Hukum | 54 | 18 | 24 | 3 |
| jurnal11 | train_asli | Hukum keluarga Islam | 49 | 4 | 4 | 0 |
| jurnal12 | test_asli | Hukum keluarga Islam | 56 | 3 | 4 | 0 |
| jurnal13 | train_asli | Hukum keluarga Islam | 38 | 3 | 4 | 1 |
| jurnal14 | train_asli | Hukum keluarga Islam | 48 | 4 | 4 | 1 |
| jurnal15 | test_asli | Hukum keluarga Islam (Al-Syakhshiyyah) | 48 | 1 | 1 | 0 |
| jurnal16 | train_asli | Hukum keluarga Islam (Al-Syakhshiyyah) | 50 | 2 | 2 | 0 |
| jurnal17 | train_asli | Akuntansi (pajak) | 37 | 8 | 8 | 0 |
| jurnal18 | test_asli | Ekonomi pembangunan | 52 | 22 | 27 | 5 |
| jurnal19 | train_asli | Akuntansi dan manajemen | 46 | 27 | 38 | 3 |
| jurnal20 | train_asli | Ekonomi Islam (zakat) | 50 | 22 | 50 | 1 |
| jurnal21 | test_asli | Ekonomi Islam (zakat) | 45 | 24 | 38 | 6 |
| jurnal22 | train_asli | Ekonomi (UMKM) | 46 | 27 | 62 | 4 |
| jurnal23 | train_asli | Ekonomi Islam (Al-Iqtishod) | 45 | 14 | 18 | 5 |
| jurnal24 | test_asli | Ekonomi Islam (Al-Iqtishod) | 34 | 8 | 12 | 3 |
| jurnal25 | train_asli | Ekonomi Islam (Al-Iqtishod) | 48 | 30 | 56 | 4 |
| jurnal26 | train_asli | Manajemen SDM | 56 | 7 | 8 | 2 |
| skripsi10 | train_asli | Ilmu Hukum, Universitas Nahdlatul Ulama Indonesia | 101 | 34 | 58 | 3 |
| skripsi11 | test_asli | Ilmu Hukum (perlindungan konsumen) | 103 | 52 | 92 | 1 |

## Skripsi batch pertama (semuanya test_asli)

| ID | Bidang | Kalimat | Berkesalahan | Token salah | Ragu |
|---|---|---|---|---|---|
| skripsi01 | Tadris IPS (pendidikan sosial), UIN Jakarta | 427 | 182 | 388 | 7 |
| skripsi02 | Sistem Informasi, UIN Jakarta | 176 | 48 | 66 | 2 |
| skripsi04 | Sistem Informasi, UIN Suska Riau (Bab IV tidak tersedia) | 112 | 51 | 78 | 3 |
| skripsi05 | Sistem Informasi, ITS | 144 | 44 | 66 | 4 |
| skripsi06 | Sistem Informasi, UIN Alauddin Makassar | 138 | 82 | 127 | 6 |
| skripsi07 | Ilmu Perpustakaan, UIN Jakarta (hanya Bab I–II) | 123 | 47 | 75 | 8 |
| skripsi08 | Ilmu Hukum (perdata), Univ. Muhammadiyah Mataram (Bab I–III) | 128 | 60 | 92 | 1 |
| skripsi09 | Ilmu Hukum (pidana), UIN Suska Riau (Bab I–III, V) | 108 | 53 | 83 | 5 |
| **Total** | | **1.356** | **567** | **975** | **36** |

Token per label: TYPO 176, TIDAK_BAKU 167, TAMBAH_KOMA 130, KAPITAL 122, PISAH 96, HURUF_KECIL 87, GANTI_TITIK 77, HAPUS 59, GABUNG 40, LAIN 25, TAMBAH_TITIK 5, FORMAT_ANGKA 2.

skripsi03 (hasil pindai) tidak diproses karena OCR akan menambahkan typo palsu.

Revisi anotasi (setelah analisis kesalahan model pertama): koma pemerincian, koma sebelum
*tetapi*, dan koma setelah ungkapan penghubung (*Artinya,*) yang terlewat ditambahkan; kalimat yang disambung
koma (*..., hal tersebut menunjukkan*) dipecah secara konsisten di seluruh skripsi01; koma
opsional setelah keterangan di awal kalimat yang sempat ditambahkan di beberapa skripsi dihapus
agar konsisten. Kata yang ada di `kamus_baku.py` (mis. *menunjukan, presentase*) kini berlabel
`TIDAK_BAKU`.

## Berkas

| Berkas | Isi |
|---|---|
| `pembagian.json` | split per dokumen (test_asli / train_asli) dan bidangnya |
| `semua_pasangan_asli.jsonl` | gabungan semua dokumen: `salah` → `benar`, jenis kesalahan, status, catatan |
| `semua_token_asli.jsonl` | label per token, format sama dengan `output/token_*.jsonl` |
| `semua_tinjau.csv` | semua kalimat untuk dicek di Excel (kolom terakhir isi Y/T) |
| `statistik_asli.json` | angka di atas |
| `skripsiXX/`, `jurnalXX/` | berkas per dokumen, termasuk `koreksi.txt` (sumber koreksi) |
| `alat/` | `ekstrak.py`, `susun_koreksi.py`, `audit.py`, `gabung_asli.py`, `uji_saran.py` (mengukur saran ejaan pada typo asli) |

## Aturan koreksi

- Yang diperbaiki hanya: typo, kata tidak baku, huruf kapital, koma, titik, spasi/serangkai.
  Pilihan kata dan struktur kalimat penulis dibiarkan.
- Imbuhan Indonesia + kata asing memakai tanda hubung (*di-update, meng-upload*), bukan diganti padanannya.
- Koma opsional setelah keterangan di awal kalimat (*Berdasarkan ..., Menurut ..., Dari ...*) tidak
  ditambah/dihapus, kecuali untuk menghindari salah baca. Koma setelah ungkapan penghubung
  (*Oleh karena itu, Untuk itu, Artinya, Dengan demikian*) dan setelah anak kalimat di awal
  (*Apabila ..., Setelah ...*) tetap wajib.
- Koma sebelum *sehingga/karena/bahwa* dihapus jika anak kalimat mengikuti induk kalimat,
  kecuali koma itu penutup sisipan (ditandai `ragu`).
- Kalimat yang disambung koma dipecah dengan titik: label `GANTI_TITIK`.
- *namun* di tengah kalimat dan kalimat yang diawali *Sedangkan/Tetapi* tidak diubah (`ragu`).
- Kalimat teracak saat ekstraksi PDF, terpotong, berupa tabel/rumus/daftar, atau menempel
  dengan sitasi setelah titik dilewati.

## Label tambahan

`LAIN` (perubahan gabungan, misalnya *antar class* → *antarclass*) tidak ada di data sintetis,
jadi diabaikan saat evaluasi. `GANTI_TITIK` (koma → titik) sekarang juga ada di data sintetis
(dari baris surat yang berisi dua kalimat), sehingga ikut dilatih dan dievaluasi.

## Saran evaluasi

- Laporkan presisi, recall, dan F0.5 per label, dan pisahkan hasil per skripsi supaya terlihat
  apakah model hanya bagus di satu gaya tulisan.
- Jalankan dua kali: dengan dan tanpa kalimat berstatus `ragu`.

## Menambah skripsi baru

```bash
python alat/ekstrak.py skripsi.pdf <hal_awal> <hal_akhir> s08/bab1.tsv   # per bab
# tulis s08/koreksi.txt (lihat format di skripsi01/koreksi.txt)
python alat/susun_koreksi.py s08 skripsi08
python alat/audit.py s08/pasangan_asli.jsonl
# salin hasilnya ke skripsi08/, lalu perbarui berkas gabungan dan statistik:
python alat/gabung_asli.py
```
