"""Membangun latih_model.ipynb dari sel-sel di bawah (python buat_notebook.py)."""
import nbformat as nbf
from pathlib import Path

SEL = []


def md(teks):
    SEL.append(nbf.v4.new_markdown_cell(teks.strip()))


def code(teks, tag=None):
    c = nbf.v4.new_code_cell(teks.strip())
    if tag:
        c.metadata["tags"] = [tag]
    SEL.append(c)


md("""
# Melatih Model Pendeteksi Kesalahan Penulisan Bahasa Indonesia

Notebook ini melatih model **klasifikasi token**: setiap kata diberi label seperti `TYPO`,
`KAPITAL`, `TAMBAH_KOMA`, atau `O` (benar).

**Sebelum mulai:** menu *Runtime → Change runtime type → T4 GPU*.

Alur:
1. Siapkan data (`dataset/dataset_lengkap.jsonl`)
2. Latih dengan split `train`, pantau dengan `valid`
3. Uji di `test_sintetis` dan **`test_asli`** (kalimat skripsi sungguhan), skor ini yang paling penting
4. Simpan model dan coba pada teks sendiri
""")

code("""
!pip -q install -U transformers datasets accelerate
""", tag="setup")

md("""
## 1. Siapkan data

**Opsi A (disarankan):** unggah `dataset_ejaan_final.zip` ke Google Drive (folder `MyDrive`),
lalu jalankan sel ini. Zip itu sudah berisi data uji asli dari 6 skripsi.

**Opsi B:** jika zip tidak ada, sel ini akan meng-clone repo dan membangun data sintetis saja
(tanpa `test_asli`).
""")

code("""
import os, subprocess
from pathlib import Path

DATA_PATH = Path("dataset-ejaan/dataset/dataset_lengkap.jsonl")
ZIP_DI_DRIVE = "/content/drive/MyDrive/dataset_ejaan_final.zip"

if not DATA_PATH.exists():
    try:
        from google.colab import drive
        drive.mount("/content/drive")
    except Exception as e:
        print("Google Drive tidak terpasang:", e)
    if os.path.exists(ZIP_DI_DRIVE):
        subprocess.run(["unzip", "-q", "-o", ZIP_DI_DRIVE], check=True)
    else:
        print("Zip tidak ditemukan di Drive, membangun data sintetis dari repo...")
        subprocess.run(["git", "clone", "-q", "https://github.com/Hwarinn66/Koreksi-.git", "dataset-ejaan"], check=True)
        subprocess.run(["pip", "-q", "install", "Sastrawi"], check=True)
        subprocess.run(["bash", "jalankan_semua.sh"], cwd="dataset-ejaan", check=True)

print("Data:", DATA_PATH, DATA_PATH.exists())
""", tag="setup")

md("""
## 2. Pengaturan

- `MODEL_NAME` **harus cased** (membedakan huruf besar dan kecil). Jika tidak, model tidak bisa
  mendeteksi kesalahan huruf kapital. IndoBERT dari IndoNLU (`indobenchmark/indobert-*`) bersifat
  uncased, jadi tidak dipakai. Bawaan: `xlm-roberta-base` (cased, mendukung bahasa Indonesia).
- `PORSI_TRAIN`: isi 0.25 atau 0.5 untuk melatih dengan sebagian data (uji perlu-tidaknya tambah data).
- `PAKAI_BOBOT`: True untuk memberi bobot lebih pada label yang jarang (recall naik, presisi biasanya turun).
""")

code("""
MODEL_NAME = "xlm-roberta-base"
MAX_LEN = 128
EPOCHS = 3
BATCH = 32
LR = 3e-5
PORSI_TRAIN = 1.0
PAKAI_BOBOT = False
SEED = 42
OUTPUT_DIR = "model_ejaan"
MAX_STEPS = -1          # biarkan -1; hanya untuk uji cepat
""", tag="config")

code("""
import json, random
from collections import Counter
import numpy as np
import torch
from transformers import AutoTokenizer

random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

baris = [json.loads(b) for b in open(DATA_PATH, encoding="utf-8")]
info_label = json.load(open(DATA_PATH.parent / "label.json", encoding="utf-8"))

# GANTI_TITIK dan LAIN hanya ada di data asli; model tidak dilatih untuk keduanya.
LABELS = [l for l in info_label["labels"] if l not in info_label.get("label_khusus_data_asli", [])]
label2id = {l: i for i, l in enumerate(LABELS)}
id2label = {i: l for l, i in label2id.items()}

split = {s: [b for b in baris if b["split"] == s] for s in ("train", "valid", "test_sintetis", "test_asli")}
if PORSI_TRAIN < 1:
    random.shuffle(split["train"])
    split["train"] = split["train"][: int(len(split["train"]) * PORSI_TRAIN)]
for s, isi in split.items():
    print(f"{s:14} {len(isi):6} contoh")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
a = tokenizer("Jakarta", add_special_tokens=False)["input_ids"]
b = tokenizer("jakarta", add_special_tokens=False)["input_ids"]
assert a != b, "Tokenizer ini uncased! Ganti MODEL_NAME dengan model cased."
print("Tokenizer cased: OK")
""")

md("""
## 3. Ubah data menjadi input model

Label hanya dipasang pada sub-token pertama setiap kata; sisanya diberi -100 (diabaikan).
Untuk data asli, label yang berupa gabungan (mis. `PISAH+TYPO`) memakai label pertama,
dan token berlabel `GANTI_TITIK`/`LAIN` diabaikan saat evaluasi.
""")

code("""
from datasets import Dataset

def label_utama(l):
    for x in l.split("+"):
        if x in label2id:
            return label2id[x]
    return -100   # GANTI_TITIK / LAIN

def encode(contoh):
    enc = tokenizer(contoh["tokens"], is_split_into_words=True, truncation=True, max_length=MAX_LEN)
    hasil = []
    for i in range(len(contoh["tokens"])):
        word_ids = enc.word_ids(batch_index=i)
        prev, y = None, []
        for w in word_ids:
            y.append(-100 if w is None or w == prev else label_utama(contoh["labels"][i][w]))
            prev = w
        hasil.append(y)
    enc["labels"] = hasil
    return enc

def ke_dataset(isi):
    ds = Dataset.from_list([{"tokens": b["tokens"], "labels": b["labels"]} for b in isi])
    return ds.map(encode, batched=True, remove_columns=["tokens", "labels"])

data = {s: ke_dataset(isi) for s, isi in split.items() if isi}
data["test_asli_pasti"] = ke_dataset([b for b in split["test_asli"] if b["status"] == "pasti"]) if split["test_asli"] else None
print({k: (len(v) if v else 0) for k, v in data.items()})
""")

md("""
## 4. Metrik

Akurasi token tidak dipakai karena sekitar 90% token berlabel `O`. Model yang selalu menebak
"benar" pun akurasinya tinggi. Yang dihitung:
- **Deteksi:** apakah token salah ditandai sebagai salah (apa pun jenisnya).
- **Per label:** presisi, recall, F0.5. F0.5 lebih mementingkan presisi, karena peringatan
  palsu lebih mengganggu pengguna daripada kesalahan yang terlewat.
""")

code("""
O = label2id["O"]

def f05(p, r):
    return 0 if p + r == 0 else 1.25 * p * r / (0.25 * p + r)

def hitung_metrik(pred, gold):
    m = gold != -100
    pred, gold = pred[m], gold[m]
    tp = ((pred != O) & (gold != O)).sum(); fp = ((pred != O) & (gold == O)).sum(); fn = ((pred == O) & (gold != O)).sum()
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    hasil = {"deteksi_presisi": p, "deteksi_recall": r, "deteksi_f05": f05(p, r)}
    # per label (label harus tepat)
    benar = (pred == gold) & (gold != O)
    tp_all = benar.sum(); fp_all = ((pred != O) & ~benar).sum(); fn_all = ((gold != O) & ~benar).sum()
    p = tp_all / (tp_all + fp_all) if tp_all + fp_all else 0.0; r = tp_all / (tp_all + fn_all) if tp_all + fn_all else 0.0
    hasil.update({"label_presisi": p, "label_recall": r, "label_f05": f05(p, r)})
    return {k: float(v) for k, v in hasil.items()}

def per_label(pred, gold):
    m = gold != -100
    pred, gold = pred[m], gold[m]
    baris_tabel = []
    for l, i in label2id.items():
        if l == "O":
            continue
        tp = ((pred == i) & (gold == i)).sum(); fp = ((pred == i) & (gold != i)).sum(); fn = ((pred != i) & (gold == i)).sum()
        n = int((gold == i).sum())
        if n == 0 and fp == 0:
            continue
        p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
        baris_tabel.append((l, n, p, r, f05(p, r)))
    print(f"{'label':14}{'jumlah':>8}{'presisi':>9}{'recall':>9}{'F0.5':>8}")
    for l, n, p, r, f in sorted(baris_tabel, key=lambda x: -x[1]):
        print(f"{l:14}{n:8d}{p:9.3f}{r:9.3f}{f:8.3f}")

def compute_metrics(ev):
    logits, gold = ev
    return hitung_metrik(np.argmax(logits, -1).ravel(), gold.ravel())
""")

md("## 5. Latih")

code("""
import inspect
from transformers import (AutoModelForTokenClassification, DataCollatorForTokenClassification,
                          Trainer, TrainingArguments)

model = AutoModelForTokenClassification.from_pretrained(
    MODEL_NAME, num_labels=len(LABELS), id2label=id2label, label2id=label2id,
    ignore_mismatched_sizes=True)

bobot = None
if PAKAI_BOBOT:
    hit = Counter(label_utama(l) for b in split["train"] for l in b["labels"])
    maks = max(hit.values())
    bobot = torch.tensor([min(10.0, (maks / hit.get(i, 1)) ** 0.5) for i in range(len(LABELS))])
    print("bobot:", dict(zip(LABELS, bobot.round(decimals=2).tolist())))

class TrainerBerbobot(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        out = model(**inputs)
        w = bobot.to(out.logits.device) if bobot is not None else None
        loss = torch.nn.functional.cross_entropy(out.logits.view(-1, len(LABELS)), labels.view(-1),
                                                 weight=w, ignore_index=-100)
        return (loss, out) if return_outputs else loss

arg = dict(output_dir=OUTPUT_DIR, learning_rate=LR, num_train_epochs=EPOCHS, max_steps=MAX_STEPS,
           per_device_train_batch_size=BATCH, per_device_eval_batch_size=BATCH * 2,
           weight_decay=0.01, warmup_ratio=0.06, save_strategy="epoch", save_total_limit=1,
           load_best_model_at_end=True, metric_for_best_model="label_f05", logging_steps=100,
           fp16=torch.cuda.is_available(), report_to="none", seed=SEED)
param = inspect.signature(TrainingArguments).parameters
nama_eval = "eval_strategy" if "eval_strategy" in param else "evaluation_strategy"
arg[nama_eval] = "epoch"
if MAX_STEPS > 0:
    arg.update({nama_eval: "steps", "save_strategy": "steps", "eval_steps": MAX_STEPS, "save_steps": MAX_STEPS})
if "warmup_ratio" not in param:   # transformers versi baru: pakai jumlah langkah
    total = MAX_STEPS if MAX_STEPS > 0 else -(-len(data["train"]) // BATCH) * EPOCHS
    arg["warmup_steps"] = int(arg.pop("warmup_ratio") * total)
arg = {k: v for k, v in arg.items() if k in param}   # buang argumen yang tidak dikenal versi ini

trainer = TrainerBerbobot(model=model, args=TrainingArguments(**arg),
                          train_dataset=data["train"], eval_dataset=data["valid"],
                          data_collator=DataCollatorForTokenClassification(tokenizer),
                          compute_metrics=compute_metrics)
trainer.train()
""")

md("""
## 6. Evaluasi

Bandingkan skor `test_sintetis` dengan `test_asli`. Selisih yang besar berarti kesalahan buatan
generator belum mirip dengan kesalahan manusia. Yang perlu diperbaiki dalam kasus itu adalah
`buat_dataset.py`, bukan modelnya.
""")

code("""
def evaluasi(nama):
    ds = data.get(nama)
    if not ds:
        print(f"[{nama}] tidak tersedia"); return
    out = trainer.predict(ds)
    pred, gold = np.argmax(out.predictions, -1).ravel(), out.label_ids.ravel()
    print(f"\\n===== {nama} =====")
    for k, v in hitung_metrik(pred, gold).items():
        print(f"{k:16} {v:.3f}")
    per_label(pred, gold)

for nama in ("test_sintetis", "test_asli", "test_asli_pasti"):
    evaluasi(nama)
""")

code("""
# Skor per skripsi pada test_asli: apakah model hanya bagus di satu gaya tulisan?
if split["test_asli"]:
    per_sumber = {}
    for b in split["test_asli"]:
        per_sumber.setdefault(b["sumber"].split("/")[0], []).append(b)
    for nama, isi in sorted(per_sumber.items()):
        out = trainer.predict(ke_dataset(isi))
        m = hitung_metrik(np.argmax(out.predictions, -1).ravel(), out.label_ids.ravel())
        print(f"{nama}: deteksi F0.5 {m['deteksi_f05']:.3f} | label F0.5 {m['label_f05']:.3f} | {len(isi)} kalimat")
""")

md("""
## 7. Simpan model

Model disimpan ke Google Drive supaya tidak hilang saat sesi Colab berakhir.
""")

code("""
import shutil
trainer.save_model(OUTPUT_DIR); tokenizer.save_pretrained(OUTPUT_DIR)
if os.path.exists("/content/drive/MyDrive"):
    shutil.copytree(OUTPUT_DIR, f"/content/drive/MyDrive/{OUTPUT_DIR}", dirs_exist_ok=True)
    print("Tersimpan di Drive:", f"/content/drive/MyDrive/{OUTPUT_DIR}")
""", tag="simpan")

md("## 8. Coba pada teks sendiri")

code("""
import re

SINGKATAN = {"dkk.", "dll.", "dsb.", "dst.", "hlm.", "tbk.", "swt."}
PENJELASAN = {
    "TYPO": "salah ketik", "TIDAK_BAKU": "kata tidak baku", "KAPITAL": "seharusnya huruf kapital",
    "HURUF_KECIL": "seharusnya huruf kecil", "TAMBAH_KOMA": "perlu koma setelah kata ini",
    "TAMBAH_TITIK": "perlu titik setelah kata ini", "HAPUS": "tanda baca ini sebaiknya dihapus",
    "PISAH": "seharusnya ditulis terpisah", "GABUNG": "seharusnya digabung dengan kata berikutnya",
    "FORMAT_ANGKA": "format angka (desimal pakai koma, ribuan pakai titik)",
}

def pecah_token(teks):
    hasil = []
    for chunk in teks.split():
        depan, belakang = [], []
        while len(chunk) > 1 and chunk[0] in "([“\\"'":
            depan.append(chunk[0]); chunk = chunk[1:]
        while len(chunk) > 1 and chunk[-1] in ",.;:?!)]”\\"'" and chunk.lower() not in SINGKATAN:
            belakang.insert(0, chunk[-1]); chunk = chunk[:-1]
        hasil += depan + [chunk] + belakang
    return hasil

def periksa(teks, model_dir=None):
    mdl = trainer.model if model_dir is None else AutoModelForTokenClassification.from_pretrained(model_dir)
    tok = tokenizer if model_dir is None else AutoTokenizer.from_pretrained(model_dir)
    mdl.eval()
    for kalimat in re.split(r"(?<=[.?!])\\s+", teks.strip()):
        kata = pecah_token(kalimat)
        if not kata:
            continue
        enc = tok(kata, is_split_into_words=True, truncation=True, max_length=MAX_LEN, return_tensors="pt").to(mdl.device)
        with torch.no_grad():
            pred = mdl(**enc).logits.argmax(-1)[0].tolist()
        label_kata, prev = {}, None
        for pos, w in enumerate(enc.word_ids()):
            if w is not None and w != prev:
                label_kata[w] = mdl.config.id2label[pred[pos]]
            prev = w
        temuan = [(kata[i], l) for i, l in label_kata.items() if l != "O"]
        print("•", kalimat)
        for k, l in temuan:
            print(f"    - '{k}': {PENJELASAN.get(l, l)}")
        if not temuan:
            print("    (tidak ada kesalahan terdeteksi)")

periksa("Penelitian ini bertujuan untuk menganalisa pengaruh media sosial terhadap mahasiswa. "
        "oleh karena itu peneliti mengumpulkan data dari 120 responden dikampus. "
        "Data di analisis menggunakan SPSS, sehingga hasilnya dapat di pertanggung jawabkan")
""")

md("""
## 9. (Opsional) Perlu tambah data atau tidak?

Ubah `PORSI_TRAIN` di bagian 2 menjadi 0.25, lalu 0.5, lalu 1.0, dan jalankan ulang
bagian 2 sampai 6. Catat `label_f05` pada **test_asli**:
- Jika skor masih naik jelas dari 0.5 ke 1.0, menambah data sintetis masih membantu.
- Jika skornya sudah datar, perbaiki generator kesalahan (agar mirip kesalahan asli)
  atau tambah data uji asli, bukan menambah data sintetis.
""")

nb = nbf.v4.new_notebook()
nb.cells = SEL
nb.metadata = {"accelerator": "GPU", "colab": {"gpuType": "T4"},
               "kernelspec": {"name": "python3", "display_name": "Python 3"},
               "language_info": {"name": "python"}}
out = Path(__file__).with_name("latih_model.ipynb")
nbf.write(nb, out)
print("ditulis:", out, len(SEL), "sel")
