# Deploy

## 1. Push ke GitHub

```bash
cd fed-bi-rupiah-monitor
git init -b main
git add .
git commit -m "Initial commit: Fed → BI-Rate → Rupiah monitor"
git remote add origin git@github.com:<username>/fed-bi-rupiah-monitor.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) otomatis menjalankan lint, validasi data, dan tes pada Python 3.11 & 3.12.

> Sebelum membuat repo **publik**, baca catatan lisensi data di `docs/DATA.md`.

## 2. Streamlit Community Cloud (gratis)

1. Buka <https://share.streamlit.io> → *Create app* → pilih repo.
2. *Main file path*: `app.py`. Branch: `main`.
3. *Advanced settings* → Python 3.12.
4. Deploy. Dependensi dibaca dari `requirements.txt`.

Memperbarui data = commit file baru di `data/raw/`; aplikasi memuat ulang otomatis setelah push.

## 3. Docker

```bash
docker build -t fed-bi-rupiah-monitor .
docker run --rm -p 8501:8501 fed-bi-rupiah-monitor
```

## 4. Pemecahan masalah

| Gejala | Penyebab / solusi |
|---|---|
| "Gagal memuat data" | File di `data/raw/` hilang atau formatnya berubah → `python scripts/validate_data.py` |
| Angka tidak berubah setelah mengganti file | Cache data: menu ⋮ → *Clear cache*, atau restart |
| `ModuleNotFoundError: fedbi` | Jalankan dari root repo (`streamlit run app.py`) |
| Simulator terasa lambat | Simulasi 20.000 lintasan hanya ±0,02 detik; jika lambat, penyebabnya biasanya render grafik — kecilkan jumlah contoh lintasan atau matikan opsi "Tampilkan contoh lintasan" |
