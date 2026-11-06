// Koreksi: unggah naskah, pantau proses, tampilkan temuan per halaman.
"use strict";

const NAMA_LABEL = {
  TYPO: "Salah ketik",
  TIDAK_BAKU: "Kata tidak baku",
  KAPITAL: "Perlu huruf kapital",
  HURUF_KECIL: "Perlu huruf kecil",
  TAMBAH_KOMA: "Koma kurang",
  TAMBAH_TITIK: "Titik kurang",
  HAPUS: "Tanda baca berlebih",
  GANTI_TITIK: "Kalimat disambung koma",
  PISAH: "Harus ditulis terpisah",
  GABUNG: "Harus ditulis serangkai",
  FORMAT_ANGKA: "Format angka",
};
const KELOMPOK = {
  TYPO: "k-ejaan", TIDAK_BAKU: "k-ejaan", KAPITAL: "k-kapital", HURUF_KECIL: "k-kapital",
  TAMBAH_KOMA: "k-baca", TAMBAH_TITIK: "k-baca", HAPUS: "k-baca", GANTI_TITIK: "k-baca",
  PISAH: "k-kata", GABUNG: "k-kata", FORMAT_ANGKA: "k-angka",
};
const SISIP = new Set(["TAMBAH_KOMA", "TAMBAH_TITIK"]);

const $ = (id) => document.getElementById(id);
const el = (tag, kelas, teks) => {
  const e = document.createElement(tag);
  if (kelas) e.className = kelas;
  if (teks !== undefined) e.textContent = teks;
  return e;
};

let berkasDipilih = null;
let laporan = null;
const saring = { mati: new Set(), hanyaYakin: false };

// ---------------------------------------------------------------- layar
function tampilkan(layar) {
  for (const id of ["layar-unggah", "layar-proses", "layar-hasil"]) $(id).hidden = id !== layar;
  window.scrollTo({ top: 0 });
}

// ---------------------------------------------------------------- tab
const tabBerkas = $("tab-berkas"), tabTeks = $("tab-teks");
function pilihTab(tab) {
  const berkas = tab === tabBerkas;
  tabBerkas.setAttribute("aria-selected", berkas);
  tabTeks.setAttribute("aria-selected", !berkas);
  tabBerkas.tabIndex = berkas ? 0 : -1;
  tabTeks.tabIndex = berkas ? -1 : 0;
  $("form-berkas").hidden = !berkas;
  $("form-teks").hidden = berkas;
  $("galat-unggah").hidden = true;
}
tabBerkas.addEventListener("click", () => pilihTab(tabBerkas));
tabTeks.addEventListener("click", () => pilihTab(tabTeks));
for (const t of [tabBerkas, tabTeks]) {
  t.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      const lain = t === tabBerkas ? tabTeks : tabBerkas;
      pilihTab(lain); lain.focus();
    }
  });
}

// ---------------------------------------------------------------- pilih berkas
const zona = $("zona"), input = $("input-berkas");
function setBerkas(f) {
  berkasDipilih = f || null;
  zona.classList.toggle("ada-berkas", !!f);
  $("zona-judul").textContent = f ? f.name : "Pilih berkas atau seret ke sini";
  $("zona-ket").textContent = f ? `${(f.size / 1048576).toFixed(1)} MB. Klik untuk mengganti.` : "PDF, DOCX, TXT, atau MD. Maksimal 25 MB.";
  $("tombol-berkas").disabled = !f;
  $("galat-unggah").hidden = true;
}
input.addEventListener("change", () => setBerkas(input.files[0]));
["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("seret"); }));
["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove("seret"); }));
zona.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) setBerkas(e.dataTransfer.files[0]); });

function galat(pesan) {
  const g = $("galat-unggah");
  g.textContent = pesan;
  g.hidden = false;
}

// ---------------------------------------------------------------- kirim
async function kirim(data, nama) {
  $("galat-unggah").hidden = true;
  let res;
  try {
    res = await fetch("/api/periksa", { method: "POST", body: data });
  } catch {
    return galat("Server tidak bisa dihubungi. Pastikan server masih berjalan, lalu coba lagi.");
  }
  const json = await res.json().catch(() => ({}));
  if (!res.ok) return galat(json.detail || "Naskah tidak bisa diproses.");
  $("proses-nama").textContent = nama;
  setProgres(null, "Menunggu giliran…");
  tampilkan("layar-proses");
  pantau(json.id);
}

$("form-berkas").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!berkasDipilih) return;
  const d = new FormData();
  d.append("berkas", berkasDipilih);
  kirim(d, berkasDipilih.name);
});
$("form-teks").addEventListener("submit", (e) => {
  e.preventDefault();
  const t = $("input-teks").value.trim();
  if (!t) return galat("Tempel teks yang ingin diperiksa terlebih dahulu.");
  const d = new FormData();
  d.append("teks", t);
  kirim(d, "Teks yang ditempel");
});

// ---------------------------------------------------------------- pantau proses
function setProgres(nilai, pesan) {
  const bar = $("bar");
  bar.classList.toggle("tak-tentu", nilai === null);
  $("bar-isi").style.width = nilai === null ? "" : `${Math.round(nilai * 100)}%`;
  bar.setAttribute("aria-valuenow", nilai === null ? 0 : Math.round(nilai * 100));
  $("proses-pesan").textContent = pesan;
}

async function pantau(id) {
  while (true) {
    await new Promise((r) => setTimeout(r, 700));
    let job;
    try {
      const res = await fetch(`/api/hasil/${id}`);
      job = await res.json();
      if (!res.ok) throw new Error(job.detail);
    } catch (e) {
      tampilkan("layar-unggah");
      return galat(e.message || "Koneksi ke server terputus.");
    }
    if (job.status === "selesai") return tampilkanHasil(job.hasil);
    if (job.status === "gagal") { tampilkan("layar-unggah"); return galat(job.pesan); }
    setProgres(job.status === "memeriksa" ? job.progres : null, job.pesan);
  }
}

// ---------------------------------------------------------------- render hasil
function namaHalaman(h) {
  if (h.halaman === null || h.halaman === undefined) return "Tanpa nomor halaman";
  return `Halaman ${h.halaman}`;
}

function lokasiTeks(k, adaHalaman) {
  const bagian = [];
  if (Array.isArray(k.halaman)) bagian.push(`Berlanjut ke halaman ${k.halaman[1]}`);
  if (!adaHalaman) bagian.push(`Paragraf ${k.paragraf}`);
  return bagian.join(", ");
}

// kalimat asli dengan tanda pada bagian yang salah
function renderAsli(kalimat, temuan) {
  const frag = document.createDocumentFragment();
  const urut = [...temuan].sort((a, b) => a.awal - b.awal);
  let pos = 0;
  for (const t of urut) {
    if (t.awal < pos) continue; // tumpang tindih: tandai yang pertama saja
    frag.append(kalimat.slice(pos, t.awal));
    const m = el("mark", `tanda ${KELOMPOK[t.label] || "k-ejaan"}`);
    if (t.label === "HAPUS") m.classList.add("hapus");
    if (/^[^\p{L}\p{N}]+$/u.test(kalimat.slice(t.awal, t.akhir))) m.classList.add("tanda-baca");
    if (!t.yakin) m.classList.add("ragu");
    m.textContent = kalimat.slice(t.awal, t.akhir);
    m.title = `${NAMA_LABEL[t.label] || t.label}${t.yakin ? "" : " (perlu dicek)"}`;
    frag.append(m);
    if (SISIP.has(t.label)) {
      const s = el("span", `sisip-tanda ${KELOMPOK[t.label]}`, "‸");
      s.setAttribute("aria-hidden", "true");
      frag.append(s);
    }
    pos = t.akhir;
  }
  frag.append(kalimat.slice(pos));
  return frag;
}

// kalimat benar dari temuan yang sedang ditampilkan saja (sama dengan rakit di koreksi.py)
function susunBenar(kalimat, temuan) {
  const semua = temuan.flatMap((t) => t.suntingan);
  const kapital = new Set(semua.filter((s) => s.kapital).map((s) => s.awal));
  const sunting = semua.filter((s) => !s.kapital).map((s) => (
    kapital.has(s.awal) && s.akhir > s.awal ? { ...s, teks: s.teks.replace(/\p{L}/u, (c) => c.toUpperCase()) } : s
  ));
  const sudah = new Set(sunting.filter((s) => s.akhir > s.awal).map((s) => s.awal));
  sunting.push(...semua.filter((s) => s.kapital && !sudah.has(s.awal)));
  sunting.sort((a, b) => a.awal - b.awal || a.akhir - b.akhir);

  let benar = "", pos = 0;
  const sorot = [];
  for (const s of sunting) {
    if (s.awal < pos) continue;
    benar += kalimat.slice(pos, s.awal);
    if (s.teks) sorot.push([benar.length, benar.length + s.teks.length]);
    benar += s.teks;
    pos = s.akhir;
  }
  benar += kalimat.slice(pos);
  const geser = benar.length - benar.trimStart().length; // jika token pertama dihapus
  return { benar: benar.slice(geser), sorot: sorot.map(([a, b]) => [a - geser, b - geser]) };
}

// kalimat benar dengan sorotan pada bagian yang berubah
function renderBenar(benar, sorot) {
  const frag = document.createDocumentFragment();
  let pos = 0;
  for (const [a, b] of [...sorot].sort((x, y) => x[0] - y[0])) {
    if (a < pos) continue;
    frag.append(benar.slice(pos, a));
    frag.append(el("ins", "", benar.slice(a, b)));
    pos = b;
  }
  frag.append(benar.slice(pos));
  return frag;
}

const NAMA_TANDA = { ",": "tanda koma", ".": "tanda titik", ";": "titik koma", ":": "titik dua" };

function renderPerubahan(t) {
  const li = el("li", KELOMPOK[t.label] || "k-ejaan");
  if (t.label === "HAPUS") {
    const nama = NAMA_TANDA[t.teks];
    li.append(nama ? el("span", "panah", `${nama[0].toUpperCase()}${nama.slice(1)} dihapus`)
                   : el("span", "dari", t.teks), nama ? "" : el("span", "panah", "dihapus"));
  } else if (t.saran) {
    li.append(el("span", "dari", t.teks), el("span", "panah", "→"), el("span", "ke", t.saran));
  } else {
    li.append(el("span", "dari", t.teks), el("span", "panah", "tidak ada saran otomatis, periksa kata ini"));
  }
  li.append(el("span", "alasan", NAMA_LABEL[t.label] || t.label));
  if (!t.yakin) li.append(el("span", "cek", "perlu dicek"));
  return li;
}

function lolosSaring(t) {
  return !saring.mati.has(t.label) && (!saring.hanyaYakin || t.yakin);
}

function renderIsi() {
  const wadah = $("isi-hasil");
  wadah.replaceChildren();
  const adaHalaman = laporan.info.ada_halaman;
  const tpl = $("tpl-temuan");
  const nav = $("daftar-halaman");
  nav.replaceChildren();
  let totalTampil = 0;

  for (const h of laporan.halaman) {
    const kalimat = h.kalimat
      .map((k) => ({ ...k, tampil: k.temuan.filter(lolosSaring) }))
      .filter((k) => k.tampil.length);
    if (!kalimat.length) continue;
    const jumlah = kalimat.reduce((n, k) => n + k.tampil.length, 0);
    totalTampil += jumlah;
    const idLembar = `hal-${h.halaman ?? "x"}`;

    const lembar = el("section", "lembar");
    lembar.id = idLembar;
    const kepala = el("header", "lembar-kepala");
    const judul = el("h2", "", namaHalaman(h));
    if (h.label && String(h.label) !== String(h.halaman)) {
      judul.append(" ", el("span", "tertulis", `(tertulis ${h.label})`));
    }
    kepala.append(judul, el("span", "jml", `${jumlah} temuan`));
    lembar.append(kepala);

    for (const k of kalimat) {
      const node = tpl.content.cloneNode(true);
      const lok = lokasiTeks(k, adaHalaman);
      const pLok = node.querySelector(".lokasi");
      if (lok) pLok.textContent = lok; else pLok.remove();
      node.querySelector(".asli").append(renderAsli(k.kalimat, k.tampil));
      const { benar, sorot } = susunBenar(k.kalimat, k.tampil);
      node.querySelector(".benar").append(renderBenar(benar, sorot));
      const ul = node.querySelector(".perubahan");
      for (const t of [...k.tampil].sort((a, b) => a.awal - b.awal)) ul.append(renderPerubahan(t));
      const tombol = node.querySelector(".salin");
      tombol.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(benar);
          tombol.textContent = "Tersalin";
        } catch {
          tombol.textContent = "Gagal menyalin";
        }
        setTimeout(() => (tombol.textContent = "Salin kalimat benar"), 1600);
      });
      lembar.append(node);
    }
    wadah.append(lembar);

    if (h.halaman !== null && h.halaman !== undefined) {
      const li = el("li");
      const a = el("a");
      a.href = `#${idLembar}`;
      a.append(String(h.halaman), el("small", "", String(jumlah)));
      a.setAttribute("aria-label", `Halaman ${h.halaman}, ${jumlah} temuan`);
      li.append(a);
      nav.append(li);
    }
  }
  $("judul-nav").parentElement.hidden = !nav.children.length;

  if (!totalTampil) {
    const k = el("div", "kosong");
    const semuaBersih = laporan.ringkasan.jumlah_temuan === 0;
    k.append(
      el("h2", "", semuaBersih ? "Tidak ada kesalahan yang terdeteksi." : "Tidak ada temuan untuk pilihan ini."),
      el("p", "", semuaBersih
        ? "Model tidak menemukan kesalahan ejaan atau tanda baca. Tetap baca ulang naskahmu, karena tidak semua kesalahan bisa dikenali."
        : "Aktifkan jenis kesalahan lain di panel kiri untuk melihat temuan."),
    );
    wadah.append(k);
  }
}

function renderSamping() {
  const r = laporan.ringkasan, info = laporan.info;
  $("nama-berkas").textContent = laporan.nama_berkas;
  const ringkas = $("ringkas");
  ringkas.replaceChildren();
  const hal = info.jumlah_halaman ? ` dari ${info.jumlah_halaman} halaman` : "";
  ringkas.append(
    el("strong", "", `${r.jumlah_temuan} temuan`),
    ` di ${r.kalimat_bermasalah} kalimat. ${r.kalimat_diperiksa} kalimat diperiksa${hal}.`,
  );

  const daftar = $("daftar-jenis");
  daftar.replaceChildren();
  for (const [lab, n] of Object.entries(r.per_label)) {
    const label = el("label", `jenis ${KELOMPOK[lab] || "k-ejaan"}`);
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = !saring.mati.has(lab);
    cb.addEventListener("change", () => {
      cb.checked ? saring.mati.delete(lab) : saring.mati.add(lab);
      label.classList.toggle("mati", !cb.checked);
      renderIsi();
    });
    const kunci = el("span", "kunci");
    kunci.setAttribute("aria-hidden", "true");
    label.append(cb, kunci, el("span", "nama", NAMA_LABEL[lab] || lab), el("span", "jml", String(n)));
    daftar.append(label);
  }
  $("daftar-jenis").parentElement.hidden = !Object.keys(r.per_label).length;

  const lewati = Object.entries(info.dilewati || {}).filter(([, n]) => n > 0);
  $("info-lewati").hidden = !lewati.length;
  $("teks-lewati").textContent = lewati.length
    ? `Bagian ini dilewati karena bukan kalimat isi: ${lewati.map(([a, n]) => `${a} (${n} bagian)`).join(", ")}.`
    : "";
}

function tampilkanHasil(hasil) {
  laporan = hasil;
  saring.mati.clear();
  $("hanya-yakin").checked = saring.hanyaYakin;
  renderSamping();
  renderIsi();
  $("panel-saring").open = window.innerWidth > 900;
  tampilkan("layar-hasil");
}

$("hanya-yakin").addEventListener("change", (e) => {
  saring.hanyaYakin = e.target.checked;
  renderIsi();
});
$("tombol-baru").addEventListener("click", () => {
  setBerkas(null);
  input.value = "";
  tampilkan("layar-unggah");
});

// ---------------------------------------------------------------- status model
fetch("/api/status").then((r) => r.json()).then((s) => {
  if (!s.model_tersedia) {
    const c = $("catatan-model");
    c.textContent = "Model belum terpasang di server, jadi pemeriksaan belum bisa dijalankan. Lihat web/README.md.";
    c.hidden = false;
  }
}).catch(() => {});
