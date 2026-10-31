#!/usr/bin/env bash
# Membangun ulang seluruh dataset dari awal:
# unduh korpus terbuka -> saring kalimat sesuai EYD -> buat pasangan salah/benar.
# Butuh: git, Python 3.8+, dan Sastrawi (pip install Sastrawi).
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p unduhan
for repo in UD_Indonesian-GSD UD_Indonesian-CSUI UD_Indonesian-PUD; do
  [ -d "unduhan/$repo" ] || git clone -q --depth 1 "https://github.com/UniversalDependencies/$repo.git" "unduhan/$repo"
done
[ -d unduhan/idn-tagged-corpus ] || git clone -q --depth 1 https://github.com/famrashel/idn-tagged-corpus.git unduhan/idn-tagged-corpus

TULISAN="data/kalimat_bersih.txt data/tambahan_skripsi.txt"

python3 saring_korpus.py --output data/korpus_ud.txt \
  unduhan/UD_Indonesian-GSD/*.conllu unduhan/UD_Indonesian-CSUI/*.conllu unduhan/UD_Indonesian-PUD/*.conllu \
  --hindari $TULISAN --kosakata $TULISAN

python3 saring_korpus.py --output data/korpus_idn.txt \
  unduhan/idn-tagged-corpus/Indonesian_Manually_Tagged_Corpus.tsv \
  --hindari $TULISAN data/korpus_ud.txt --kosakata $TULISAN

# Kalimat bergaya skripsi diberi lebih banyak varian karena paling sesuai dengan tujuan.
python3 buat_dataset.py --input \
  data/kalimat_bersih.txt:10 data/tambahan_skripsi.txt:10 \
  data/korpus_ud.txt:8 data/korpus_idn.txt:8 \
  --output output --contoh 5

# Gabungkan data sintetis dan data uji asli menjadi dataset/dataset_lengkap.jsonl
python3 gabung_dataset.py
