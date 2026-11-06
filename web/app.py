"""
app.py
Web pemeriksa ejaan: unggah PDF/DOCX/TXT/MD (atau tempel teks), lalu lihat kesalahan per halaman
beserta versi benar setiap kalimat. Dokumen asli tidak diubah.

Jalankan (dari folder repo):
    pip install -r web/requirements.txt
    uvicorn web.app:app --reload          # buka http://127.0.0.1:8000

Variabel lingkungan:
    MODEL_DIR   folder model hasil training (bawaan: model_ejaan/ di folder repo)
    MAKS_MB     batas ukuran berkas unggahan dalam MB (bawaan: 25)
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB = Path(__file__).resolve().parent
REPO = WEB.parent
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(REPO))

from ekstrak import baca_teks, ekstrak, ke_kalimat, saring_bagian  # noqa: E402
from koreksi import PENJELASAN, periksa_dokumen  # noqa: E402

MODEL_DIR = Path(os.environ.get("MODEL_DIR", REPO / "model_ejaan"))
MAKS_MB = float(os.environ.get("MAKS_MB", 25))
FORMAT = (".pdf", ".docx", ".txt", ".md")
UMUR_JOB = 3600  # detik

@asynccontextmanager
async def lifespan(_app):
    # Muat model di latar supaya permintaan pertama tidak menunggu terlalu lama.
    def muat():
        try:
            model()
        except Exception as e:  # noqa: BLE001
            print("[peringatan]", e)
    threading.Thread(target=muat, daemon=True).start()
    yield


app = FastAPI(title="Pemeriksa Ejaan Bahasa Indonesia", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")

_pekerja = ThreadPoolExecutor(max_workers=1)   # satu dokumen diproses dalam satu waktu
_jobs = {}
_kunci = threading.Lock()
_model = {"objek": None, "galat": None}
_kunci_model = threading.Lock()


class ModelTidakTersedia(Exception):
    pass


def model():
    """Memuat model sekali saja (butuh beberapa detik). Dikunci karena dipanggil dari dua utas."""
    with _kunci_model:
        if _model["objek"] is None and _model["galat"] is None:
            if not (MODEL_DIR / "config.json").exists():
                _model["galat"] = (f"Model tidak ditemukan di {MODEL_DIR}. Unduh isi folder model_ejaan dari "
                                   "Google Drive (model.safetensors, config.json, tokenizer.json, "
                                   "tokenizer_config.json) ke folder itu, lalu jalankan ulang server.")
            else:
                from periksa import Pemeriksa
                _model["objek"] = Pemeriksa(str(MODEL_DIR))
    if _model["galat"]:
        raise ModelTidakTersedia(_model["galat"])
    return _model["objek"]


def ubah(job_id, **kw):
    with _kunci:
        _jobs[job_id].update(kw)


def bersihkan_jobs():
    batas = time.time() - UMUR_JOB
    with _kunci:
        for k in [k for k, v in _jobs.items() if v["dibuat"] < batas]:
            del _jobs[k]


def kelompokkan(hasil, info, total_kalimat):
    """Mengelompokkan temuan per halaman (atau per paragraf jika dokumen tidak punya halaman)."""
    label = info.get("label_halaman", {})
    grup = {}
    for h in hasil:
        hal = h["halaman"][0] if isinstance(h["halaman"], list) else h["halaman"]
        grup.setdefault(hal, []).append(h)
    halaman = []
    for hal in sorted(grup, key=lambda x: (x is None, x or 0)):
        isi = sorted(grup[hal], key=lambda h: h["paragraf"])
        halaman.append({"halaman": hal, "label": label.get(str(hal)) if hal is not None else None,
                        "jumlah": sum(len(h["temuan"]) for h in isi), "kalimat": isi})
    per_label = Counter(t["label"] for h in hasil for t in h["temuan"])
    return {
        "ringkasan": {"kalimat_diperiksa": total_kalimat, "kalimat_bermasalah": len(hasil),
                      "jumlah_temuan": sum(per_label.values()), "per_label": dict(per_label.most_common())},
        "halaman": halaman,
        "penjelasan_label": PENJELASAN,
    }


def proses(job_id, path, nama, teks):
    try:
        ubah(job_id, status="membaca", pesan="Membaca dokumen…")
        if teks is not None:
            paragraf, _, _ = baca_teks(teks)
            diperiksa, dilewati = saring_bagian(paragraf)
            kalimat = ke_kalimat(diperiksa)
            info = {"jumlah_halaman": None, "ada_halaman": False, "dilewati": dict(dilewati),
                    "paragraf_total": len(paragraf), "paragraf_diperiksa": len(diperiksa),
                    "kalimat": len(kalimat), "label_halaman": {}}
        else:
            kalimat, info = ekstrak(path, nama)
        if not kalimat:
            raise ValueError("Tidak ada kalimat yang bisa diperiksa di dokumen ini.")

        ubah(job_id, status="memuat", pesan="Menyiapkan model…")
        pemeriksa = model()

        def progres(selesai, total):
            ubah(job_id, status="memeriksa", progres=selesai / total,
                 pesan=f"Memeriksa kalimat {selesai} dari {total}…")

        ubah(job_id, status="memeriksa", progres=0.0, pesan=f"Memeriksa {len(kalimat)} kalimat…")
        hasil = periksa_dokumen(kalimat, pemeriksa, progres)
        laporan = kelompokkan(hasil, info, len(kalimat))
        laporan.update({"nama_berkas": nama, "info": info})
        ubah(job_id, status="selesai", progres=1.0, pesan="Selesai", hasil=laporan)
    except (ValueError, ModelTidakTersedia) as e:
        ubah(job_id, status="gagal", pesan=str(e))
    except Exception:  # noqa: BLE001
        traceback.print_exc()                              # rinciannya hanya untuk log server
        ubah(job_id, status="gagal", pesan="Terjadi kesalahan saat memproses dokumen. Coba lagi beberapa saat lagi.")
    finally:
        if path:
            shutil.rmtree(Path(path).parent, ignore_errors=True)


@app.get("/")
def beranda():
    return FileResponse(WEB / "static" / "index.html")


@app.get("/api/status")
def status():
    ada = (MODEL_DIR / "config.json").exists()
    return {"model_tersedia": ada, "model_dimuat": _model["objek"] is not None,
            "format": FORMAT, "maks_mb": MAKS_MB,
            "pesan": None if ada else f"Model belum ada di {MODEL_DIR}."}


@app.post("/api/periksa")
async def periksa(berkas: UploadFile | None = File(None), teks: str | None = Form(None)):
    bersihkan_jobs()
    path, nama = None, None
    if berkas is not None and berkas.filename:
        nama = Path(berkas.filename).name
        if not nama.lower().endswith(FORMAT):
            if nama.lower().endswith(".doc"):
                raise HTTPException(400, "Format .doc lama belum didukung. Simpan ulang sebagai .docx di Word.")
            raise HTTPException(400, "Format belum didukung. Gunakan PDF, DOCX, TXT, atau MD.")
        isi = await berkas.read()
        if len(isi) > MAKS_MB * 1024 * 1024:
            raise HTTPException(400, f"Berkas terlalu besar (maksimal {MAKS_MB:g} MB).")
        folder = tempfile.mkdtemp(prefix="ejaan_")
        path = str(Path(folder) / ("dokumen" + Path(nama).suffix.lower()))
        Path(path).write_bytes(isi)
        teks = None
    elif teks and teks.strip():
        nama = "Teks yang ditempel"
        if len(teks) > 300_000:
            raise HTTPException(400, "Teks terlalu panjang. Unggah sebagai berkas saja.")
    else:
        raise HTTPException(400, "Unggah berkas atau tempel teks terlebih dahulu.")

    job_id = uuid.uuid4().hex
    with _kunci:
        _jobs[job_id] = {"status": "antre", "progres": 0.0, "pesan": "Menunggu giliran…",
                         "dibuat": time.time(), "nama": nama, "hasil": None}
    _pekerja.submit(proses, job_id, path, nama, teks)
    return {"id": job_id}


@app.get("/api/hasil/{job_id}")
def hasil(job_id: str):
    with _kunci:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Pemeriksaan tidak ditemukan atau sudah kedaluwarsa.")
        return {k: v for k, v in job.items() if k != "dibuat"}
