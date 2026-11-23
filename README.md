# Fed → BI-Rate → Rupiah Monitor

Dashboard Streamlit untuk memantau bagaimana kebijakan suku bunga The Fed merambat ke BI-Rate dan nilai tukar rupiah — dari kondisi terkini, hubungan statistik, proyeksi Fed Funds, hingga indeks tekanan komposit.

| Halaman | Isi |
|---|---|
| **Monitor** | KPI (BI-Rate, Fed Funds, spread BI−Fed, USD/IDR, inflasi YoY), grafik BI-Rate vs Fed Funds + spread, USD/IDR dengan penanda tiap RDG, filter tanggal |
| **Transmisi** | Korelasi bergulir Fed Funds–USD/IDR, volatilitas kurs bergulir, event study di sekitar RDG, panel konteks DXY |
| **Simulator** | Fan chart Hull-White + Monte Carlo s.d. Des 2028; slider *a*, σ, jumlah lintasan, shock awal; kotak probabilitas (P(Fed Funds > X), ekspektasi, persentil 95); proyeksi spread BI-Rate |
| **Risk Signal** | Indeks tekanan 0–100 dari 4 komponen dengan bobot yang bisa diatur, gauge hijau/kuning/merah, grafik historis dengan penanda Mei 2026, tabel kontribusi |

## Menjalankan

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Buka http://localhost:8501. Butuh Python ≥ 3.11.

Perintah lain: `make test` · `make lint` · `make data-check` · `make docker`.

## Struktur

```
app.py                  entrypoint + navigasi + filter tanggal global
views/                  satu modul per halaman (fungsi render())
fedbi/
  config.py             path data, warna, parameter default
  loaders.py            parser format Indonesia + validasi
  dataset.py            penggabungan semua sumber ke tabel harian
  analytics.py          korelasi/volatilitas bergulir, event study
  hullwhite.py          model Hull-White + Monte Carlo, kalibrasi AR(1)
  risk.py               komponen, skor percentile, indeks komposit
  charts.py             pembuat grafik Plotly
  ui.py                 format angka, filter tanggal, cache data
data/raw/               lima file sumber (lihat docs/DATA.md)
tests/                  76 tes (unit, integrasi data nyata, smoke test Streamlit)
docs/                   METODOLOGI, DATA, ARSITEKTUR, DEPLOY
```

## Memperbarui data

Ganti isi file di `data/raw/` dengan unduhan terbaru **dengan format kolom yang sama**, lalu jalankan `make data-check`. Panduan lengkap per sumber ada di [docs/DATA.md](docs/DATA.md). Dashboard otomatis menyesuaikan rentang tanggal dan teks "per tanggal".

## Dokumentasi

- [docs/METODOLOGI.md](docs/METODOLOGI.md) — rumus, asumsi, dan keterbatasan tiap analisis
- [docs/DATA.md](docs/DATA.md) — sumber, format, dan cara memperbarui data
- [docs/ARSITEKTUR.md](docs/ARSITEKTUR.md) — alur data dan keputusan desain
- [docs/DEPLOY.md](docs/DEPLOY.md) — Streamlit Community Cloud, Docker

## Catatan penting

- Ini alat **analisis deskriptif dan skenario**, bukan prakiraan atau saran investasi. Korelasi dan event study tidak membuktikan kausalitas; simulator memakai jalur ekspektasi yang Anda pilih, bukan kurva pasar.
- **Lisensi data:** FRED, Bank Indonesia, dan BPS adalah sumber publik. File USD/IDR dan DXY berformat "Data Historis" dari Investing.com; periksa syarat penggunaan mereka sebelum mempublikasikan repo secara publik (opsi: ganti dengan sumber yang boleh didistribusikan atau jadikan repo privat).
- Kode berlisensi MIT (lihat `LICENSE`).
