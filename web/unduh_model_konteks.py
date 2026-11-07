#!/usr/bin/env python3
"""
Mengunduh model konteks untuk saran ejaan ke folder model_konteks/ (sekitar 450 MB).

Model: LazarusNLP/NusaBERT-base, lisensi Apache-2.0. Hanya bobot dan tokenizer yang diunduh.

Pakai (dari folder repo): python web/unduh_model_konteks.py
"""
from pathlib import Path

from huggingface_hub import snapshot_download

TUJUAN = Path(__file__).resolve().parents[1] / "model_konteks"
BERKAS = ["model.safetensors", "config.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt",
          "special_tokens_map.json"]

snapshot_download("LazarusNLP/NusaBERT-base", local_dir=TUJUAN, allow_patterns=BERKAS)
print("Model konteks tersimpan di", TUJUAN)
