# Data

Semua file ada di `data/raw/`. Nama file dipetakan di `fedbi/config.py` (`FILES`).

| File | Sumber | Frekuensi | Kolom dipakai | Rentang saat ini |
|---|---|---|---|---|
| `fedfunds.csv` | [FRED — FEDFUNDS](https://fred.stlouisfed.org/series/FEDFUNDS) | bulanan | `observation_date`, `FEDFUNDS` | Jan 2023 – Okt 2026 |
| `usdidr.csv` | Investing.com — Data Historis USD/IDR | harian | `Tanggal`, `Terakhir` | 2 Jan 2023 – 30 Okt 2026 |
| `dxy.csv` | Investing.com — Data Historis US Dollar Index | harian | `Tanggal`, `Terakhir` | 3 Jan 2023 – 23 Nov 2026 |
| `bi_rate.xlsx` | Bank Indonesia — BI-7Day-RR | per RDG | kolom ke-2 (tanggal), ke-3 (nilai) | 19 Jan 2023 – 21 Okt 2026 |
| `inflasi.xlsx` | BI/BPS — Data Inflasi (YoY) | bulanan | kolom ke-2 (periode), ke-3 (nilai) | Jan 2023 – Sep 2026 |

## Format yang diharapkan

- **CSV harga**: pemisah koma, UTF-8 (BOM diperbolehkan), tanggal `dd/mm/yyyy`, angka format Indonesia (`"18.125,0"`, `"103,80"`). Hanya `Tanggal` dan `Terakhir` yang wajib; kolom lain diabaikan.
- **CSV FRED**: tanggal ISO (`2026-10-01`), nilai desimal bertitik.
- **Excel BI & inflasi**: baris judul di atas boleh berantakan; baris data dikenali dari tanggal/periode yang bisa dibaca (`21 Oktober 2026`, `Mei 2026`) dan nilai berformat `5,75 %`. Nama bulan Indonesia (dan singkatan umum) didukung.

## Cara memperbarui

1. Unduh data terbaru dari sumbernya (urutan baris bebas; loader mengurutkan).
2. Timpa file di `data/raw/` (nama tetap, atau ubah `FILES`).
3. `make data-check` — melaporkan observasi terakhir dan peringatan.
4. Jalankan ulang aplikasi (atau *Clear cache* dari menu ⋮).

Karena data USD/IDR dan Fed Funds menentukan akhir analisis gabungan, perbarui **keduanya** bersama DXY; jika DXY lebih baru, dashboard menampilkan peringatan.

## Validasi otomatis

`loaders.validate()` memeriksa: seri kosong, harga ≤ 0, perubahan harian > 4%, jeda > 7 hari, Fed Funds di luar 0–25% atau bulan hilang, BI-Rate kosong, serta hari kurs sebelum RDG pertama. Peringatan muncul di sidebar (*Sumber & kualitas data*).

## Catatan kualitas yang diketahui

- 13 hari kurs pertama (2–18 Jan 2023) tidak punya BI-Rate (RDG pertama dalam data 19 Jan 2023) → spread kosong; tidak diisi dengan karangan.
- DXY mengandung 1 baris hari Minggu (22 Nov 2026) → dibuang.
- RDG pertama dalam data tidak punya keputusan pembanding → dikecualikan dari event study dan penanda panah.
- Fed Funds = *effective rate* rata-rata bulanan, bukan batas target FOMC.

## Lisensi

FRED, BI, dan BPS menyediakan data publik (cantumkan sumber). Data Investing.com memiliki syarat penggunaan yang membatasi redistribusi — pertimbangkan itu sebelum membuat repo publik.
