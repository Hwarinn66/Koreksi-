#!/usr/bin/env python3
"""
gabung_dataset.py
Menyatukan data sintetis (output/) dan data uji asli (data_uji_asli/) menjadi satu dataset
dengan skema yang seragam, di folder dataset/.

Pakai:
    python gabung_dataset.py

Keluaran:
    dataset/dataset_lengkap.jsonl   satu baris per contoh, semua split, lengkap dengan label token
    dataset/dataset_lengkap.csv     versi ringkas untuk Excel (tanpa label token)
    dataset/label.json              daftar label (termasuk label khusus data asli)
    dataset/statistik.json          jumlah contoh per split, sumber, dan label
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parent
OUT = DIR / "dataset"

LABEL_ASLI_SAJA = {
    "GANTI_TITIK": "Koma seharusnya titik (kalimat yang disambung koma dipecah).",
    "LAIN": "Perubahan gabungan yang tidak masuk satu kategori (mis. 'antar class' -> 'antarclass').",
}


def baca_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(b) for b in f if b.strip()]


def main():
    OUT.mkdir(exist_ok=True)
    label_info = json.loads((DIR / "output" / "label.json").read_text(encoding="utf-8"))
    khusus = [l for l in LABEL_ASLI_SAJA if l not in label_info["labels"]]  # tidak ada di data sintetis
    labels = label_info["labels"] + khusus
    deskripsi = {**LABEL_ASLI_SAJA, **label_info["deskripsi"]}

    baris = []

    # 1) Data sintetis
    for split in ("train", "valid", "test"):
        pasangan = {p["id"]: p for p in baca_jsonl(DIR / "output" / f"pasangan_{split}.jsonl")}
        for t in baca_jsonl(DIR / "output" / f"token_{split}.jsonl"):
            p = pasangan[t["id"]]
            baris.append({
                "id": f"sin-{t['id']}",
                "split": split if split != "test" else "test_sintetis",
                "jenis_data": "sintetis",
                "sumber": p["sumber"],
                "salah": p["salah"],
                "benar": p["benar"],
                "kesalahan": p["kesalahan"],
                "tokens": t["tokens"],
                "labels": t["labels"],
                "perbaikan": t["perbaikan"],
                "status": "pasti",
                "catatan": "",
            })

    # 2) Data uji asli (koreksi manual skripsi)
    asli_dir = DIR / "data_uji_asli"
    folder_asli = sorted(asli_dir.glob("skripsi*"))
    if not folder_asli:
        print("[info] data_uji_asli/skripsi* tidak ditemukan; dataset hanya berisi data sintetis.")
    for folder in folder_asli:
        token = {t["id"]: t for t in baca_jsonl(folder / "token_asli.jsonl")}
        for p in baca_jsonl(folder / "pasangan_asli.jsonl"):
            t = token[p["id"]]
            baris.append({
                "id": f"asli-{p['id']}",
                "split": "test_asli",
                "jenis_data": "asli",
                "sumber": f"{p['sumber']}/{p['bab']}",
                "salah": p["salah"],
                "benar": p["benar"],
                "kesalahan": p["kesalahan"],
                "tokens": t["tokens"],
                "labels": t["labels"],
                "perbaikan": t["perbaikan"],
                "status": p["status"],
                "catatan": p["catatan"],
            })

    # Pemeriksaan: tidak ada kalimat benar yang sama di train dan di data uji
    benar_train = {b["benar"] for b in baris if b["split"] == "train"}
    bocor = Counter(b["split"] for b in baris if b["split"] != "train" and b["benar"] in benar_train)
    if bocor:
        raise SystemExit(f"Kebocoran data ke train: {dict(bocor)}")
    for b in baris:
        assert len(b["tokens"]) == len(b["labels"]) == len(b["perbaikan"]), b["id"]
        for l in b["labels"]:
            for x in l.split("+"):
                assert x in labels, (b["id"], x)

    with open(OUT / "dataset_lengkap.jsonl", "w", encoding="utf-8") as f:
        for b in baris:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    with open(OUT / "dataset_lengkap.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "jenis_data", "sumber", "status", "kesalahan", "salah", "benar", "catatan"])
        for b in baris:
            w.writerow([b["id"], b["split"], b["jenis_data"], b["sumber"], b["status"],
                        ";".join(b["kesalahan"]), b["salah"], b["benar"], b["catatan"]])

    (OUT / "label.json").write_text(json.dumps(
        {"labels": labels, "label2id": {l: i for i, l in enumerate(labels)},
         "label_khusus_data_asli": khusus, "deskripsi": deskripsi},
        ensure_ascii=False, indent=2), encoding="utf-8")

    per_split = Counter(b["split"] for b in baris)
    per_split_salah = Counter(b["split"] for b in baris if b["salah"] != b["benar"])
    label_split = defaultdict(Counter)
    for b in baris:
        for l in b["labels"]:
            if l != "O":
                label_split[b["split"]].update(l.split("+"))
    stat = {
        "total_contoh": len(baris),
        "contoh_per_split": dict(per_split),
        "berkesalahan_per_split": dict(per_split_salah),
        "kalimat_ragu_test_asli": sum(b["status"] == "ragu" for b in baris),
        "sumber_test_asli": dict(Counter(b["sumber"].split("/")[0] for b in baris if b["split"] == "test_asli")),
        "token_per_label_per_split": {s: dict(c.most_common()) for s, c in label_split.items()},
    }
    (OUT / "statistik.json").write_text(json.dumps(stat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: stat[k] for k in ("total_contoh", "contoh_per_split", "berkesalahan_per_split",
                                            "kalimat_ragu_test_asli")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
