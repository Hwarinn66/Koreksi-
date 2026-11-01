# Dataset Sintetis Pendeteksi Kesalahan Penulisan Bahasa Indonesia

Dataset untuk melatih model yang mendeteksi kesalahan penulisan pada skripsi, laporan, dan surat
(lamaran, izin, undangan, surat dinas, surel ke dosen): typo, huruf kapital, koma, titik, kata depan
*di/ke*, kata tidak baku, format angka, dan kalimat yang disambung koma.

## Ringkasan

69.590 contoh (train 55.754, valid 6.907, test 6.929) dari 7.248 kalimat bersih dan 1.268 pasangan
kalimat (dua kalimat berurutan yang digabung, untuk melatih kesalahan di batas kalimat):

| Sumber | Kalimat | Contoh | Varian per kalimat |
|---|---|---|---|
| `kalimat_bersih` (gaya skripsi/laporan) | 473 | 5.055 | 10 |
| `tambahan_skripsi` (gaya skripsi, berbagai bidang) | 671 | 7.234 | 10 |
| `tambahan_istilah` (istilah TI/hukum, merek, nama lembaga) | 137 | 1.502 | 10 |
| `kalimat_surat` (surat dan surel resmi) | 426 | 5.071 | 12 |
| `korpus_ud` (UD Indonesian, disaring) | 3.331 | 30.377 | 8 |
| `korpus_idn` (IDN Tagged Corpus, disaring) | 2.210 | 20.351 | 8 |

Jumlah contoh sudah termasuk pasangan kalimat (3 varian per pasangan).

Jumlah token per label: TYPO 31.680, KAPITAL 23.879, HURUF_KECIL 14.216, TAMBAH_TITIK 11.022,
TAMBAH_KOMA 8.820, HAPUS 4.981, GABUNG 4.804, TIDAK_BAKU 4.751, PISAH 2.723, GANTI_TITIK 2.154,
FORMAT_ANGKA 655. Data uji berisi minimal sekitar 200 contoh untuk setiap jenis kesalahan, kecuali
FORMAT_ANGKA (52).

Pembagian train/valid/test dilakukan **per kalimat asal**, jadi kalimat yang sama tidak
pernah muncul di dua split.

## Catatan repositori

Folder `output/`, `dataset/`, dan `unduhan/` tidak disimpan di repositori karena berukuran besar
dan bisa dibangun ulang:

```bash
pip install Sastrawi
bash jalankan_semua.sh
```

Data asli (`data_uji_asli/skripsiXX/` dan `jurnalXX/`, kutipan kalimat dari skripsi dan jurnal
orang lain) juga tidak disertakan. Tanpa folder itu, `gabung_dataset.py` tetap berjalan dan hanya memakai data sintetis.

## Dataset gabungan (pakai ini untuk melatih)

`dataset/dataset_lengkap.jsonl` menyatukan semuanya dalam satu berkas, dengan kolom `split`:

| split | Isi | Contoh |
|---|---|---|
| `train` | data sintetis untuk pelatihan | 64.785 |
| `valid` | data sintetis untuk validasi | 6.974 |
| `test_sintetis` | data sintetis untuk uji (471 di antaranya dari surat) | 6.950 |
| `train_asli` | kalimat asli dari 19 dokumen (skripsi/jurnal) yang dikoreksi manual, ikut dilatih | 967 |
| `test_asli` | kalimat asli dari 17 dokumen lain (8 skripsi lama + 9 dokumen baru), hanya untuk uji | 1.855 |

Setiap baris: `id, split, jenis_data, sumber, salah, benar, kesalahan, tokens, labels, perbaikan,
status, catatan`. `dataset/dataset_lengkap.csv` adalah versi ringkas untuk Excel, dan
`dataset/label.json` memuat semua label (termasuk `LAIN` yang hanya ada di data asli).
Bangun ulang dengan `python gabung_dataset.py`.

```python
from datasets import load_dataset
ds = load_dataset("json", data_files="dataset/dataset_lengkap.jsonl")["train"]
train = ds.filter(lambda x: x["split"] == "train")
test_asli = ds.filter(lambda x: x["split"] == "test_asli" and x["status"] == "pasti")
```

## Isi

```
data/
  kalimat_bersih.txt      kalimat bergaya skripsi/laporan, ditulis sesuai EYD V
  tambahan_skripsi.txt    kalimat bergaya skripsi dari berbagai bidang ilmu
  tambahan_istilah.txt    kalimat dengan istilah asing berhuruf kecil (state, flowchart), istilah
                          hukum (wanprestasi, perikatan), nama merek (TikTok), dan nama lembaga
  kalimat_surat.txt       baris surat: lamaran, izin, cuti, undangan, permohonan, surat dinas,
                          keterangan, pernyataan, kuasa, balasan, dan surel ke dosen
  korpus_ud.txt           kalimat dari UD Indonesian GSD, CSUI, PUD (sudah disaring)
  korpus_idn.txt          kalimat dari IDN Tagged Corpus (sudah disaring)
buat_dataset.py           perusak + pelabel: kalimat bersih -> pasangan salah/benar
kamus_baku.py             kamus kata tidak baku (dipakai generator dan pemeriksaan kamus)
saring_korpus.py          penyaring kalimat korpus agar hanya yang sesuai EYD yang dipakai
jalankan_semua.sh         unduh korpus, saring, buat dataset, lalu gabungkan (satu perintah)
gabung_dataset.py         menyatukan output/ dan data_uji_asli/ menjadi dataset/
notebook/latih_model.ipynb  notebook Colab untuk melatih dan menguji model
dataset/                  DATASET GABUNGAN (lihat bagian di atas)
data_uji_asli/            2.822 kalimat skripsi/jurnal asli + koreksi manual + alat untuk menambah
output/
  pasangan_{train,valid,test}.jsonl   pasangan salah -> benar (untuk seq2seq)
  token_{train,valid,test}.jsonl      label per token (untuk IndoBERT)
  semua_pasangan.csv                  semua pasangan, bisa dibuka di Excel
  label.json                          daftar label + label2id
  statistik.json                      jumlah data per split, per label, dan per sumber
```

## Cara menjalankan

```bash
pip install Sastrawi
bash jalankan_semua.sh            # bangun ulang semuanya dari awal
```

Atau langkah per langkah:

```bash
python saring_korpus.py --output data/korpus_wiki.txt wiki.txt --laporan
python buat_dataset.py --input data/kalimat_bersih.txt:10 data/korpus_wiki.txt:4 --output output
```

Akhiran `:N` menentukan jumlah versi rusak per kalimat untuk berkas itu. Opsi lain:
`--porsi 80,10,10`, `--seed`, `--contoh N`.

## Bagaimana kalimat korpus disaring

Kalimat dari korpus hanya dipakai jika lolos pemeriksaan berikut (lihat `saring_korpus.py`):

- Diawali huruf kapital, diakhiri titik/tanda tanya, panjang 6 sampai 45 token, satu kalimat saja.
- Tidak memuat kata tidak baku atau ragam cakapan (*analisa, praktek, dimana, nggak, kenapa*, dll.).
- Kata depan dan awalan benar (*di rumah*, bukan *dirumah*; *dilakukan*, bukan *di lakukan*).
- Unsur terikat dan kata majemuk benar (*antarmuka, pascasarjana, kerja sama, daripada*).
- Koma sesuai EYD: ada setelah *Oleh karena itu/Namun/Selain itu*, ada setelah anak kalimat di
  awal, ada sebelum *tetapi/sedangkan/melainkan*, ada sebelum *dan/atau* pada pemerincian,
  dan tidak ada sebelum *bahwa/sehingga/karena/adalah*.
- Huruf kapital: nama hari dan bulan, unsur nama wilayah (*Kecamatan Paga*, bukan *kecamatan Paga*).
- Angka: desimal memakai koma, ribuan memakai titik, *Rp* tanpa spasi.
- Semua kata berhuruf kecil dikenali kamus kata dasar Sastrawi (menyaring typo dan kata asing).

Penyaringan ini ketat, jadi sebagian besar kalimat korpus ditolak. Tetap ada kemungkinan
kesalahan yang lolos, terutama kesalahan makna atau kesalahan yang berbentuk kata benar.

## Format

`pasangan_*.jsonl`
```json
{"id": "k00012-v3", "kalimat_id": 12, "sumber": "kalimat_bersih",
 "salah": "Oleh karena itu diperlukan sebuah sistim ...",
 "benar": "Oleh karena itu, diperlukan sebuah sistem ...",
 "kesalahan": ["TAMBAH_KOMA", "TIDAK_BAKU"]}
```

`token_*.jsonl` (token = token kalimat yang **salah**)
```json
{"id": "k00012-v3",
 "tokens":    ["Oleh", "karena", "itu",         "diperlukan", "sebuah", "sistim", ...],
 "labels":    ["O",    "O",      "TAMBAH_KOMA", "O",          "O",      "TIDAK_BAKU", ...],
 "perbaikan": [null,   null,     "itu,",        null,         null,     "sistem", ...]}
```

Setiap kalimat juga punya satu versi tanpa kesalahan, supaya model belajar untuk tidak
menandai kalimat yang sudah benar.

## Label

| Label | Arti | Contoh salah → benar |
|---|---|---|
| `TYPO` | salah ketik | *penelitain* → *penelitian* |
| `TIDAK_BAKU` | kata tidak baku | *analisa* → *analisis*, *merubah* → *mengubah* |
| `KAPITAL` | perlu huruf kapital | *jumat* → *Jumat*, awal kalimat |
| `HURUF_KECIL` | perlu huruf kecil | *... pada Siklus kedua* |
| `TAMBAH_KOMA` | perlu koma setelah token | *Oleh karena itu diperlukan* |
| `TAMBAH_TITIK` | perlu titik setelah token | akhir kalimat, *dkk* → *dkk.* |
| `HAPUS` | tanda baca berlebih | *menyatakan, bahwa*; *PT.* → *PT* |
| `PISAH` | harus dipisah | *dirumah*, *kedalam*, *kerjasama* |
| `GABUNG` | harus digabung dengan token berikutnya | *di lakukan*, *antar muka*, *sub bab* |
| `FORMAT_ANGKA` | format angka | *0.05* → *0,05*, *Rp12,500* → *Rp12.500*, *pukul 08:00* → *pukul 08.00* |
| `GANTI_TITIK` | koma seharusnya titik (dua kalimat disambung koma) | *... saya buat, atas perhatian ...* → *... saya buat. Atas perhatian ...* |

## Data surat

`kalimat_surat.txt` berisi baris-baris surat yang sudah sesuai EYD V, termasuk salam pembuka dan
penutup (*Dengan hormat,* dan *Hormat saya,*), baris tanggal, *Yth.*, dan isi surat. Semua nama orang,
instansi, dan alamat adalah rekaan. Kesalahan yang khas surat ikut dibuat:

- Salam: *Dengan Hormat* → *Dengan hormat,*, *Hormat Saya* → *Hormat saya,*.
- Sapaan berhuruf kapital: *bapak/ibu* → *Bapak/Ibu*, *saudara* → *Saudara*, *selamat pagi pak* → *Selamat pagi, Pak.*
- Singkatan: *Yth* → *Yth.*.
- Kata tidak baku: *silahkan, ijin, ijasah, fotocopy, kwitansi, ketrampilan, himbauan, karir, mentaati,
  mengkonfirmasi, legalisir, Senen*.
- Penulisan serangkai/terpisah: *bertandatangan, terimakasih, pas foto, menindak lanjuti, sebagai mana,
  ketidak hadiran, serah terima, memberi tahu*.
- Format jam: *pukul 08:00* → *pukul 08.00*.
- Kalimat yang disambung koma (`GANTI_TITIK`), dari baris yang berisi dua kalimat.

Bagian surat dievaluasi terpisah di notebook (`test_surat`).

## Kesalahan tambahan (versi 2)

Ditambahkan setelah analisis kesalahan model pertama pada `test_asli`:

- **Kamus tidak baku** (`kamus_baku.py`, 200+ kata). Selain untuk membuat kesalahan sintetis, kamus ini
  dipakai sebagai pascaproses: kata yang ada di kamus langsung ditandai `TIDAK_BAKU`. Kata tidak baku
  adalah daftar tertutup, jadi kamus lebih andal daripada tebakan model. Jumlah contoh per kata
  dibatasi agar kata yang sangat sering (*karena, persen*) tidak mendominasi.
- **Kesalahan imbuhan**: meN- yang tidak luluh (*mempengaruhi, mengkonsumsi, mensosialisasikan*),
  huruf *k* yang hilang atau berlebih (*menunjukan, penegakkan*). Dibuat dengan stemmer Sastrawi.
- **Pasangan kalimat**: dua kalimat berurutan digabung, lalu dirusak menjadi kalimat yang disambung
  koma (`GANTI_TITIK` + `KAPITAL`) atau titik yang hilang di antara kalimat (`TAMBAH_TITIK`).
- **Koma opsional**: setiap kalimat yang punya koma opsional (setelah keterangan di awal kalimat,
  atau sebelum *baik ... maupun*) juga diberi versi bersih tanpa koma itu, supaya model tidak
  menganggap ketiadaannya sebagai kesalahan.
- **Nama merek**: *TikTok* juga dirusak menjadi *Tiktok*, bukan hanya *tiktok*.

## Melatih model

Buka `notebook/latih_model.ipynb` di Google Colab (Runtime → T4 GPU) lalu jalankan semua sel.
Notebook itu menyiapkan data, melatih model klasifikasi token, mengevaluasi di `test_sintetis`
dan `test_asli`, menyimpan model ke Google Drive, dan menyediakan fungsi `periksa(teks)`.

Model yang dipakai **harus cased**. IndoBERT dari IndoNLU (`indobenchmark/indobert-*`) bersifat
uncased (semua huruf dijadikan kecil), sehingga tidak bisa mendeteksi kesalahan huruf kapital.
Bawaan notebook adalah `xlm-roberta-base`, dan notebook menolak tokenizer uncased secara otomatis.

Ukur dengan presisi, recall, dan F0.5 per label (abaikan label `O`). Untuk melihat kinerja pada
gaya skripsi, perhatikan skor `test_asli` dan skor per skripsi. Notebook juga menampilkan skor
"+ kamus" (model + pemeriksaan kamus tidak baku) dan menyimpan prediksi `test_asli` ke
`hasil_test_asli.csv` di Drive untuk analisis kesalahan.

Notebook dibangun dari `notebook/buat_notebook.py` (`pip install nbformat`, lalu
`python notebook/buat_notebook.py`) supaya isinya mudah ditinjau di Git.

## Memakai model hasil training

Unduh isi folder `model_ejaan` dari Google Drive (cukup `model.safetensors`, `config.json`,
`tokenizer.json`, dan `tokenizer_config.json`; folder `checkpoint-*` tidak perlu) ke folder
`model_ejaan/` di dalam repo ini, lalu:

```bash
pip install torch transformers
python periksa.py "Penelitian ini bertujuan untuk menganalisa data dikampus."
python periksa.py --file tulisan.txt
```

Dari kode Python lain:

```python
from periksa import Pemeriksa
p = Pemeriksa("model_ejaan")
for kalimat, temuan in p.periksa("Data di analisis menggunakan SPSS."):
    print(kalimat, temuan)   # temuan: [(kata, label, saran), ...]
```

Folder `model_ejaan/` sudah masuk `.gitignore` karena ukurannya sekitar 1,1 GB (batas berkas
GitHub 100 MB).

## Web

Folder `web/` berisi aplikasi web: unggah PDF/DOCX/TXT, lalu lihat kesalahan per halaman beserta
versi benarnya. Cara menjalankan ada di [`web/README.md`](web/README.md):

```bash
pip install -r web/requirements.txt
uvicorn web.app:app --reload      # http://127.0.0.1:8000
```

## Lisensi sumber

- `kalimat_bersih.txt`, `tambahan_skripsi.txt`, dan kode: bebas dipakai.
- `korpus_ud.txt`: turunan Universal Dependencies Indonesian GSD dan CSUI (CC BY-SA 4.0)
  serta PUD (CC BY-SA 3.0). Jika dataset ini dibagikan ulang, gunakan lisensi yang sama.
- `korpus_idn.txt`: turunan IDN Tagged Corpus (Dinakaramani dkk., Universitas Indonesia),
  **CC BY-NC-SA 4.0, nonkomersial**. Untuk penggunaan komersial, jalankan ulang
  `buat_dataset.py` tanpa berkas ini.

Cantumkan sumber-sumber di atas jika dataset ini dipakai dalam skripsi atau publikasi.

## Keterbatasan

- Kesalahannya sintetis. Evaluasi akhir sebaiknya memakai kesalahan asli (misalnya korpus
  SPECIL atau draf skripsi yang dikoreksi manual).
- Kalimat korpus kebanyakan bergaya berita dan ensiklopedia, bukan skripsi. Kalimat bergaya
  skripsi sengaja diberi lebih banyak varian untuk mengimbanginya.
- Koma setelah keterangan di awal kalimat (*Berdasarkan hasil analisis, ...*) bersifat opsional
  menurut EYD, jadi sengaja tidak dihapus agar labelnya tidak ambigu.
- Huruf miring untuk istilah asing tidak terwakili karena datanya teks polos.
- Satu token hanya punya satu label per contoh.
- Data surat masih sintetis seluruhnya; belum ada surat asli yang dikoreksi manual. Contoh
  `GANTI_TITIK` juga masih sedikit dan hanya berasal dari surat.
