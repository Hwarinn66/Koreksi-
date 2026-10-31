#!/usr/bin/env python3
"""
Menggabungkan berkas per skripsi (skripsiXX/) menjadi semua_pasangan_asli.jsonl,
semua_token_asli.jsonl, semua_tinjau.csv, dan statistik_asli.json.

Pakai (dari folder data_uji_asli): python alat/gabung_asli.py
"""
import csv, json
from collections import Counter
from pathlib import Path

DIR = Path(__file__).resolve().parents[1]
stat_lama = DIR / "statistik_asli.json"
bidang = {}
if stat_lama.exists():
    bidang = {x["id"]: x["bidang"] for x in json.loads(stat_lama.read_text(encoding="utf-8"))["per_skripsi"]}

folders = sorted(p for p in DIR.glob("skripsi*") if p.is_dir())
pasangan, token, tinjau, per_skripsi, label = [], [], [], [], Counter()
header = None
for f in folders:
    ps = [json.loads(b) for b in open(f / "pasangan_asli.jsonl", encoding="utf-8")]
    ts = [json.loads(b) for b in open(f / "token_asli.jsonl", encoding="utf-8")]
    with open(f / "tinjau.csv", encoding="utf-8-sig") as fh:
        r = list(csv.reader(fh)); header = r[0]; tinjau += r[1:]
    pasangan += ps; token += ts
    lab = Counter(x for t in ts for l in t["labels"] if l != "O" for x in l.split("+"))
    label += lab
    per_skripsi.append({"id": f.name, "bidang": bidang.get(f.name, ""), "kalimat": len(ps),
                        "berkesalahan": sum(p["salah"] != p["benar"] for p in ps),
                        "token_salah": sum(l != "O" for t in ts for l in t["labels"]),
                        "ragu": sum(p["status"] == "ragu" for p in ps)})

with open(DIR / "semua_pasangan_asli.jsonl", "w", encoding="utf-8") as fh:
    fh.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in pasangan)
with open(DIR / "semua_token_asli.jsonl", "w", encoding="utf-8") as fh:
    fh.writelines(json.dumps(t, ensure_ascii=False) + "\n" for t in token)
with open(DIR / "semua_tinjau.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh); w.writerow(header); w.writerows(tinjau)
stat = {"per_skripsi": per_skripsi, "total_kalimat": len(pasangan),
        "total_berkesalahan": sum(x["berkesalahan"] for x in per_skripsi),
        "token_per_label": dict(label.most_common())}
stat_lama.write_text(json.dumps(stat, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in stat.items() if k != "per_skripsi"}, ensure_ascii=False))
for x in per_skripsi:
    print(x)
