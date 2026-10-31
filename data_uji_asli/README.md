# Data uji dengan kesalahan ASLI

Kalimat dari skripsi sungguhan yang dikoreksi manual sesuai EYD V. Data ini dipakai untuk
**evaluasi**, bukan pelatihan, supaya skor model mencerminkan kinerja di naskah nyata.
Jangan masukkan kalimat dari folder ini ke data latih.

## Ringkasan

| ID | Bidang | Kalimat | Berkesalahan | Token salah | Ragu |
|---|---|---|---|---|---|
| skripsi01 | Tadris IPS (pendidikan sosial), UIN Jakarta | 427 | 182 | 321 | 7 |
| skripsi02 | Sistem Informasi, UIN Jakarta | 176 | 48 | 66 | 2 |
| skripsi04 | Sistem Informasi, UIN Suska Riau (Bab IV tidak tersedia) | 112 | 51 | 78 | 3 |
| skripsi05 | Sistem Informasi, ITS | 144 | 44 | 66 | 4 |
| skripsi06 | Sistem Informasi, UIN Alauddin Makassar | 138 | 82 | 127 | 6 |
| skripsi07 | Ilmu Perpustakaan, UIN Jakarta (hanya Bab I–II) | 123 | 47 | 75 | 8 |
| skripsi08 | Ilmu Hukum (perdata), Univ. Muhammadiyah Mataram (Bab I–III) | 128 | 60 | 92 | 1 |
| skripsi09 | Ilmu Hukum (pidana), UIN Suska Riau (Bab I–III, V) | 108 | 53 | 83 | 5 |
| **Total** | | **1.356** | **567** | **908** | **36** |

Token per label: TYPO 176, TIDAK_BAKU 167, TAMBAH_KOMA 131, PISAH 96, KAPITAL 88, HURUF_KECIL 87, HAPUS 59, GANTI_TITIK 44, GABUNG 40, LAIN 25, TAMBAH_TITIK 4, FORMAT_ANGKA 2.

skripsi03 (hasil pindai) tidak diproses karena OCR akan menambahkan typo palsu.

Revisi anotasi (setelah analisis kesalahan model pertama): koma pemerincian, koma sebelum
*tetapi*, dan koma setelah ungkapan penghubung (*Artinya,*) yang terlewat ditambahkan; koma
opsional setelah keterangan di awal kalimat yang sempat ditambahkan di beberapa skripsi dihapus
agar konsisten. Kata yang ada di `kamus_baku.py` (mis. *menunjukan, presentase*) kini berlabel
`TIDAK_BAKU`.

## Berkas

| Berkas | Isi |
|---|---|
| `semua_pasangan_asli.jsonl` | gabungan semua skripsi: `salah` → `benar`, jenis kesalahan, status, catatan |
| `semua_token_asli.jsonl` | label per token, format sama dengan `output/token_*.jsonl` |
| `semua_tinjau.csv` | semua kalimat untuk dicek di Excel (kolom terakhir isi Y/T) |
| `statistik_asli.json` | angka di atas |
| `skripsiXX/` | berkas per skripsi, termasuk `koreksi.txt` (sumber koreksi) |
| `alat/` | `ekstrak.py`, `susun_koreksi.py`, `audit.py`, `gabung_asli.py` |

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
