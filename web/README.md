# Web Koreksi

Web untuk memeriksa ejaan naskah bahasa Indonesia. Pengguna mengunggah PDF, DOCX, TXT, atau MD
(atau menempel teks). Hasilnya ditampilkan per halaman: kalimat asli dengan kata yang salah
ditandai, kalimat versi benar, dan penjelasan setiap perubahan. Berkas asli tidak diubah dan
tidak disimpan di server setelah diproses.

## Menjalankan

Butuh Python 3.10 atau lebih baru.

1. Letakkan model hasil training di folder `model_ejaan/` di akar repo (lihat README utama).
   Isinya cukup `model.safetensors`, `config.json`, `tokenizer.json`, dan `tokenizer_config.json`.
2. Pasang pustaka, unduh model konteks untuk saran ejaan (sekali saja, sekitar 450 MB), lalu jalankan
   server dari akar repo:

```bash
pip install -r web/requirements.txt
python web/unduh_model_konteks.py
uvicorn web.app:app --reload
```

3. Buka http://127.0.0.1:8000

Model dimuat sekali saat server menyala (beberapa detik sampai sekitar satu menit). Model berjalan di
CPU; GPU dipakai otomatis jika ada. Skripsi 138 halaman selesai diperiksa dalam sekitar tiga menit di CPU.
Tanpa model konteks aplikasi tetap jalan, tetapi saran ejaan dipilih tanpa membaca kalimatnya dan kata
benar yang keliru ditandai model tetap diganti.

Pengaturan lewat variabel lingkungan:

| Variabel | Arti | Bawaan |
|---|---|---|
| `MODEL_DIR` | folder model | `model_ejaan/` di akar repo |
| `MAKS_MB` | batas ukuran unggahan (MB) | `25` |
| `MODEL_KONTEKS` | folder model konteks | `model_konteks/` di akar repo |

## Cara kerja

```
berkas ──> ekstrak.py ──> kalimat + nomor halaman ──> model (periksa.py) ──> koreksi.py ──> JSON ──> static/
```

| Berkas | Isi |
|---|---|
| `app.py` | API FastAPI: `POST /api/periksa` (berkas atau teks), `GET /api/hasil/{id}` (progres dan hasil), `GET /api/status` |
| `ekstrak.py` | Membaca PDF (PyMuPDF), DOCX (python-docx), TXT/MD. Menyambung baris dan kata yang terpotong, membuang catatan kaki, kepala/kaki halaman, dan nomor halaman, melewati judul, daftar isi, daftar pustaka, tabel, keterangan gambar, dan paragraf berbahasa asing, lalu memecah paragraf menjadi kalimat |
| `koreksi.py` | Mengubah label model menjadi saran: kamus tidak baku, saran ejaan, pemecahan/penggabungan kata, huruf kapital, tanda baca, format angka. Lalu menyusun kalimat benar |
| `leksikon.py` | Daftar kata baku dan pencari calon ejaan: SymSpell, pelepasan imbuhan (*mengagenadi → mengagendai*), istilah asing menurut tulisan dan bunyinya (*sofwer → software*), dan kata panjang sampai beda tiga huruf |
| `konteks.py` | Menilai calon ejaan menurut kalimatnya dengan model pengisi kata NusaBERT (*jalas → jelas* atau *jalan*) |
| `unduh_model_konteks.py` | Mengunduh model konteks ke `model_konteks/` |
| `data/istilah_asing.txt` | Istilah asing per bidang. Boleh ditambah langsung, tidak perlu membangun ulang leksikon |
| `data/leksikon.tsv`, `data/kata_dasar.txt` | Dibuat oleh `buat_leksikon.py` dari `data/*.txt`, kata dasar Sastrawi, dan frekuensi wordfreq |
| `static/` | Tampilan (HTML, CSS, JS tanpa build) |

### Nomor halaman

- **PDF**: nomor halaman PDF (sama dengan yang terlihat di pembaca PDF). Jika halaman punya nomor
  tercetak (mis. *xiv* atau *15*), nomor itu ikut ditampilkan.
- **DOCX**: perkiraan dari pemisah halaman yang disimpan Word. Jika dokumen tidak menyimpannya,
  temuan ditunjukkan per paragraf.
- **TXT/MD dan teks tempel**: per paragraf.

### Akurasi

Model yang dilatih di notebook mencapai F0.5 deteksi sekitar 0,75 pada 1.356 kalimat skripsi asli
(dengan kamus). Jika label model benar, mesin koreksi menyusun kalimat benar yang persis sama
dengan koreksi manual pada 91% kalimat.
Temuan dengan peluang di bawah 0,7 diberi tanda "perlu dicek" dan bisa disembunyikan. Saran ejaan juga
diberi tanda itu jika dua calon hampir sama kuat atau model konteks lebih menyukai kata aslinya.

Saran ejaan diukur dengan `data_uji_asli/alat/uji_saran.py` pada 4 skripsi yang tidak dipakai saat
memilih bobotnya. Contohnya sedikit (50 typo asli dan 29 kata benar yang keliru ditandai model), jadi
angkanya hanya gambaran:

| Ukuran | Kamus lama, tanpa konteks | Sekarang |
|---|---:|---:|
| Saran tepat untuk typo asli | 38 dari 50 | 41 dari 50 |
| Saran salah untuk typo asli | 9 dari 50 | 2 dari 50 |
| Kata benar yang keliru ditandai dan tetap diganti | 23 dari 29 | 4 dari 29 |

## Keterbatasan

- PDF hasil pindai (gambar) tidak bisa dibaca karena tidak berisi teks.
- Format `.doc` lama belum didukung; simpan ulang sebagai `.docx`.
- Tabel, rumus, dan daftar pustaka tidak diperiksa.
- Kesalahan yang berupa kata benar tetapi salah tempat (*bias* untuk *bisa*) sering tidak terdeteksi.
- Istilah asing hanya bisa disarankan jika ada di `data/istilah_asing.txt`. Salah ketik yang berbeda
  tiga huruf atau lebih sering tidak diberi saran: kata itu ditandai "periksa kata ini".
- PyMuPDF berlisensi AGPL. Untuk dipakai di layanan komersial tertutup, ganti dengan pustaka lain
  (mis. `pdfplumber`) atau beli lisensi komersialnya.
- `data/leksikon.tsv` memuat frekuensi turunan data wordfreq (CC BY-SA 4.0), jadi berkas itu perlu
  menyertakan atribusi dan lisensi yang sama jika dibagikan. Model konteks NusaBERT berlisensi Apache-2.0.

## Membangun ulang kamus

Hanya perlu jika `data/*.txt` atau `kamus_baku.py` berubah:

```bash
pip install Sastrawi wordfreq
python web/buat_leksikon.py
```
