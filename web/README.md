# Web Koreksi

Web untuk memeriksa ejaan naskah bahasa Indonesia. Pengguna mengunggah PDF, DOCX, TXT, atau MD
(atau menempel teks). Hasilnya ditampilkan per halaman: kalimat asli dengan kata yang salah
ditandai, kalimat versi benar, dan penjelasan setiap perubahan. Berkas asli tidak diubah dan
tidak disimpan di server setelah diproses.

## Menjalankan

Butuh Python 3.10 atau lebih baru.

1. Letakkan model hasil training di folder `model_ejaan/` di akar repo (lihat README utama).
   Isinya cukup `model.safetensors`, `config.json`, `tokenizer.json`, dan `tokenizer_config.json`.
2. Pasang pustaka dan jalankan server dari akar repo:

```bash
pip install -r web/requirements.txt
uvicorn web.app:app --reload
```

3. Buka http://127.0.0.1:8000

Model dimuat sekali saat server menyala (beberapa detik). Model berjalan di CPU; GPU dipakai
otomatis jika ada. Skripsi 60 halaman biasanya selesai diperiksa dalam kurang dari satu menit di CPU.

Pengaturan lewat variabel lingkungan:

| Variabel | Arti | Bawaan |
|---|---|---|
| `MODEL_DIR` | folder model | `model_ejaan/` di akar repo |
| `MAKS_MB` | batas ukuran unggahan (MB) | `25` |

## Cara kerja

```
berkas ──> ekstrak.py ──> kalimat + nomor halaman ──> model (periksa.py) ──> koreksi.py ──> JSON ──> static/
```

| Berkas | Isi |
|---|---|
| `app.py` | API FastAPI: `POST /api/periksa` (berkas atau teks), `GET /api/hasil/{id}` (progres dan hasil), `GET /api/status` |
| `ekstrak.py` | Membaca PDF (PyMuPDF), DOCX (python-docx), TXT/MD. Menyambung baris dan kata yang terpotong, membuang catatan kaki dan nomor halaman, melewati judul, daftar isi, daftar pustaka, tabel, keterangan gambar, dan paragraf berbahasa asing, lalu memecah paragraf menjadi kalimat |
| `koreksi.py` | Mengubah label model menjadi saran: kamus tidak baku, saran ejaan, pemecahan/penggabungan kata, huruf kapital, tanda baca, format angka. Lalu menyusun kalimat benar |
| `leksikon.py` | Daftar kata baku dan saran ejaan (SymSpell + pelepasan imbuhan: *mencangkup → mencakup*) |
| `data/leksikon.tsv`, `data/kata_dasar.txt` | Dibuat oleh `buat_leksikon.py` dari `data/*.txt` dan kata dasar Sastrawi |
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
dengan koreksi manual pada 91% kalimat; saran ejaan untuk salah ketik tepat sekitar 80%.
Temuan dengan peluang di bawah 0,7 diberi tanda "perlu dicek" dan bisa disembunyikan.

## Keterbatasan

- PDF hasil pindai (gambar) tidak bisa dibaca karena tidak berisi teks.
- Format `.doc` lama belum didukung; simpan ulang sebagai `.docx`.
- Tabel, rumus, dan daftar pustaka tidak diperiksa.
- Kesalahan yang berupa kata benar tetapi salah tempat (*bias* untuk *bisa*) sering tidak terdeteksi.
- PyMuPDF berlisensi AGPL. Untuk dipakai di layanan komersial tertutup, ganti dengan pustaka lain
  (mis. `pdfplumber`) atau beli lisensi komersialnya.
