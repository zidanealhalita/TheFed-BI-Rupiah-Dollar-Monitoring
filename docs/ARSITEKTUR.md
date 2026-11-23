# Arsitektur

```
data/raw/*.csv|xlsx
        │  loaders.py   (parse format Indonesia, validasi)
        ▼
   Bundle (dataset.py): daily · dxy_full · bi_events · fedfunds · inflasi · report
        │  ui.get_bundle()  @st.cache_data
        ▼
 views/*.render()  ──►  analytics.py / hullwhite.py / risk.py  (fungsi murni)
        │                       │
        └──────────►  charts.py (DataFrame/array → go.Figure)
```

## Keputusan desain

- **Logika terpisah dari UI.** `fedbi/analytics.py`, `hullwhite.py`, `risk.py`, `loaders.py` tidak mengimpor Streamlit, sehingga bisa diuji dan dipakai di notebook. Hanya `ui.py` dan `views/` yang memakai Streamlit.
- **Halaman = fungsi `render()`** yang didaftarkan lewat `st.navigation` di `app.py` (bukan folder `pages/`), supaya filter tanggal global bisa digambar sekali di sidebar dan halaman mudah dites.
- **Filter tanggal global.** Slider memakai kunci `global_date_range` di `st.session_state`. Streamlit membuang state widget yang tidak digambar, jadi di halaman Simulator (yang tidak memakai filter) `keep_date_filter_alive()` menyalin nilainya agar tidak reset saat berpindah halaman.
- **Hitung penuh, tampilkan sebagian.** Statistik bergulir dan skor risiko dihitung di seluruh riwayat lalu dipotong.
- **Cache.** `get_bundle()` memakai `st.cache_data`; perhitungan berat per-parameter (korelasi, volatilitas, event study, skor risiko, simulasi) juga di-cache berdasarkan argumennya. `HWParams` adalah `frozen dataclass` sehingga aman sebagai kunci cache.
- **Tanpa state tersembunyi di simulasi.** Seed eksplisit → hasil reprodusibel.
- **Format Indonesia.** Angka diformat lewat `ui.fmt_num` (1.234,56) dan grafik Plotly memakai `separators=",."`. Nama bulan pada sumbu Plotly tetap berbahasa Inggris (singkatan Jan, Feb, …) karena Streamlit tidak memuat locale Plotly.

## Menambah halaman

1. Buat `views/nama.py` dengan `def render() -> None`.
2. Tambahkan `st.Page(nama.render, title=..., url_path=...)` di `app.py`.
3. Tambahkan tes di `tests/test_app_smoke.py` (daftar `PAGES`).

## Pengujian

`pytest -q` menjalankan: parser (kasus tepi angka/tanggal Indonesia), penggabungan data (tanpa look-ahead BI-Rate), simulator (momen vs rumus analitik, seed, antithetic, floor, kalibrasi), indeks risiko (rentang, arah, bobot, kontribusi = indeks, expanding tanpa look-ahead), analitik (event study dengan lonjakan yang diketahui, korelasi, volatilitas) dan smoke test Streamlit `AppTest` untuk tiap halaman beserta interaksinya.
