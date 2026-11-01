#!/usr/bin/env python3
"""
Menggabungkan berkas per dokumen (skripsiXX/, jurnalXX/) menjadi semua_pasangan_asli.jsonl,
semua_token_asli.jsonl, semua_tinjau.csv, dan statistik_asli.json.

Pembagian split per dokumen dibaca dari pembagian.json (test_asli atau train_asli).
Kalimat benar dari dokumen train_asli juga ditulis ke ../data/kalimat_asli_train.txt
agar bisa dipakai sebagai bahan data sintetis.

Pakai (dari folder data_uji_asli): python alat/gabung_asli.py
"""
import csv, json
from collections import Counter
from pathlib import Path

DIR = Path(__file__).resolve().parents[1]
pembagian = json.loads((DIR / "pembagian.json").read_text(encoding="utf-8"))["dokumen"]

folders = sorted(p for p in DIR.iterdir() if p.is_dir() and (p / "pasangan_asli.jsonl").exists())
if not folders:   # repo publik: kutipan dokumen tidak disertakan
    (DIR.parent / "data" / "kalimat_asli_train.txt").write_text("", encoding="utf-8")
    print("[info] tidak ada folder dokumen di data_uji_asli/; dilewati.")
    raise SystemExit(0)
tanpa_split = [f.name for f in folders if f.name not in pembagian]
if tanpa_split:
    raise SystemExit(f"Belum ada di pembagian.json: {tanpa_split}")

pasangan, token, tinjau, per_dok, header = [], [], [], [], None
label = {"test_asli": Counter(), "train_asli": Counter()}
kalimat_train = []
for f in folders:
    info = pembagian[f.name]
    ps = [json.loads(b) for b in open(f / "pasangan_asli.jsonl", encoding="utf-8")]
    ts = [json.loads(b) for b in open(f / "token_asli.jsonl", encoding="utf-8")]
    with open(f / "tinjau.csv", encoding="utf-8-sig") as fh:
        r = list(csv.reader(fh)); header = r[0]; tinjau += r[1:]
    pasangan += ps; token += ts
    label[info["split"]] += Counter(x for t in ts for l in t["labels"] if l != "O" for x in l.split("+"))
    if info["split"] == "train_asli":
        kalimat_train += [p["benar"] for p in ps if p["status"] == "pasti"]
    per_dok.append({"id": f.name, "split": info["split"], "jenis": info["jenis"], "bidang": info["bidang"],
                    "kalimat": len(ps), "berkesalahan": sum(p["salah"] != p["benar"] for p in ps),
                    "token_salah": sum(l != "O" for t in ts for l in t["labels"]),
                    "ragu": sum(p["status"] == "ragu" for p in ps)})

with open(DIR / "semua_pasangan_asli.jsonl", "w", encoding="utf-8") as fh:
    fh.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in pasangan)
with open(DIR / "semua_token_asli.jsonl", "w", encoding="utf-8") as fh:
    fh.writelines(json.dumps(t, ensure_ascii=False) + "\n" for t in token)
with open(DIR / "semua_tinjau.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh); w.writerow(header); w.writerows(tinjau)

unik = list(dict.fromkeys(kalimat_train))
(DIR.parent / "data" / "kalimat_asli_train.txt").write_text("\n".join(unik) + "\n", encoding="utf-8")

ringkas = {}
for s in ("test_asli", "train_asli"):
    d = [x for x in per_dok if x["split"] == s]
    ringkas[s] = {"dokumen": len(d), "kalimat": sum(x["kalimat"] for x in d),
                  "berkesalahan": sum(x["berkesalahan"] for x in d),
                  "token_salah": sum(x["token_salah"] for x in d),
                  "token_per_label": dict(label[s].most_common())}
stat = {"per_dokumen": per_dok, "per_split": ringkas,
        "total_kalimat": len(pasangan), "total_berkesalahan": sum(x["berkesalahan"] for x in per_dok)}
(DIR / "statistik_asli.json").write_text(json.dumps(stat, ensure_ascii=False, indent=2), encoding="utf-8")
for s, v in ringkas.items():
    print(s, {k: v[k] for k in ("dokumen", "kalimat", "berkesalahan", "token_salah")})
print("kalimat benar train_asli untuk data sintetis:", len(unik))
