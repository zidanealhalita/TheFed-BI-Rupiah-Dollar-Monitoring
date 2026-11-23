# Metodologi

Dokumen ini menjelaskan apa yang sebenarnya dihitung dashboard dan di mana batas kesimpulannya.

## 0. Penyatuan data

Semua seri disejajarkan pada kalender hari bursa USD/IDR (`fedbi/dataset.py`):

| Seri | Frekuensi asli | Perlakuan |
|---|---|---|
| USD/IDR | harian | kalender acuan (harga penutupan, kolom "Terakhir") |
| DXY | harian | *as-of* (nilai terakhir yang diketahui); baris akhir pekan dibuang |
| BI-Rate | per RDG | *step function*, berlaku sejak **tanggal RDG**. Sebelum RDG pertama dalam data (19 Jan 2023) = kosong |
| Fed Funds | bulanan (rata-rata) | rata-rata bulanan dipetakan ke semua hari pada bulan itu |
| Inflasi YoY | bulanan | dianggap diketahui awal bulan berikutnya (tidak dipakai di perhitungan, hanya KPI & grafik riil) |

**Implikasi Fed Funds bulanan:** nilai bulan berjalan sebenarnya baru final di akhir bulan, sehingga pada tanggal tengah bulan angka itu mengandung sedikit informasi masa depan, dan perubahan target FOMC tampak "mendadak di awal bulan". Cukup untuk analisis bulanan/mingguan; kurang tepat untuk analisis intrahari terhadap hari FOMC.

**Prinsip tampilan:** statistik bergulir dan skor risiko dihitung pada *seluruh riwayat*, lalu dipotong sesuai filter tanggal, sehingga jendela di awal rentang tidak terpotong.

Data USD/IDR berakhir lebih awal (30 Okt 2026) daripada DXY (23 Nov 2026). Analisis gabungan berhenti di tanggal terakhir yang sama; hanya level DXY yang ditampilkan lebih panjang.

## 1. Monitor

- **Spread BI−Fed** = BI-Rate − Fed Funds (poin persentase). Spread yang lebih lebar berarti selisih imbal hasil lebih mendukung rupiah, *ceteris paribus*.
- **KPI** dihitung pada tanggal akhir filter. Delta: BI-Rate = perubahan RDG terakhir; Fed Funds & inflasi = vs bulan sebelumnya; spread & USD/IDR = vs 1 bulan kalender sebelumnya.
- **Inflasi** bulan *M* baru ditampilkan jika tanggal akhir filter ≥ awal bulan *M*+1 (menghindari look-ahead saat filter diputar mundur).
- **BI-Rate riil** = BI-Rate akhir bulan − inflasi YoY bulan yang sama. Pendekatan kasar (bukan ekspektasi inflasi ke depan).

## 2. Transmisi

**Korelasi bergulir.** Pearson pada jendela *w* hari bursa (default 120).
- *Level*: Fed Funds vs ln(USD/IDR). Rawan korelasi palsu karena kedua seri bertren.
- *Perubahan 21 hari*: Δ Fed Funds (pp) vs Δ ln(USD/IDR)×100. Lebih tahan spurious tetapi berisik, dan perubahan 21 hari yang tumpang-tindih membuat titik berdekatan tidak independen.
- Jendela dengan varians nol (Fed Funds konstan sepanjang jendela, mis. Agu 2023–Agu 2024) dikembalikan sebagai kosong, bukan ±∞.

**Volatilitas bergulir.** σ = std(log-return harian) × √252 × 100 (% per tahun). "Persentil riwayat" = porsi hari dengan volatilitas ≤ nilai terakhir.

**Event study.** Untuk tiap RDG (kecuali yang pertama, karena tidak ada keputusan pembanding):
- Hari 0 = hari bursa pertama pada/setelah tanggal RDG. Basis = penutupan hari −1.
- `cum_ret(k) = [ln P(k) − ln P(−1)] × 100`; positif = rupiah melemah.
- Opsi *netralkan DXY*: P diganti dengan USD/IDR ÷ DXY.
- Kelompok: Naik / Tetap / Turun berdasarkan perubahan BI-Rate vs RDG sebelumnya.
- RDG yang jendelanya melewati ujung data dibuang; jumlah yang dipakai ditampilkan.

*Keterbatasan:* tidak ada pemisahan "kejutan vs ekspektasi" (tak ada data konsensus); sampel Naik/Turun kecil (satuan—belasan); RDG berdekatan (mis. 20 Mei, 9 Jun, 18 Jun 2026) memiliki jendela yang tumpang-tindih; tidak ada uji signifikansi.

**Panel DXY.** Level DXY, USD/IDR vs DXY yang di-rebase ke 100 pada awal rentang, dan korelasi bergulir 60 hari antar return harian.

## 3. Simulator

### Model

Hull-White satu faktor:

$$dr_t = [\theta(t) - a\,r_t]\,dt + \sigma\,dW_t,\qquad \theta(t) = m'(t) + a\,m(t)$$

Diimplementasikan lewat dekomposisi eksak $r_t = m(t) + x_t$ dengan $dx_t = -a x_t\,dt + \sigma\,dW_t$, $x_0$ = shock awal. Transisi OU eksak per langkah ($\Delta = 1/12$ tahun):

$$x_{t+\Delta} = e^{-a\Delta} x_t + \sigma\sqrt{\tfrac{1-e^{-2a\Delta}}{2a}}\,Z,\quad Z\sim N(0,1)$$

sehingga tidak ada bias diskretisasi. Rata-rata dan varians teoretis:

$$E[r_t] = m(t) + x_0 e^{-at},\qquad \mathrm{Var}[r_t] = \tfrac{\sigma^2}{2a}\left(1-e^{-2at}\right)$$

Keduanya dipakai di `tests/test_hullwhite.py` untuk memvalidasi simulasi.

### Apa itu m(t)?

Pada praktik, θ(t) dikalibrasi ke kurva forward pasar. Kurva itu **tidak ada** di data yang disediakan, jadi m(t) menjadi *asumsi pengguna*:

| Pilihan | m(t) |
|---|---|
| Mean-reverting (default) | θ∞ + (r₀ − θ∞)·e^(−a t) — setara Vasicek, θ∞ default 3,50% |
| Datar | r₀ |
| Linier | r₀ → target di akhir horizon |

Default θ∞ = 3,50% adalah asumsi netral yang kasar, **bukan estimasi** dari data. Ubah sesuai pandangan Anda.

### Parameter

- Titik awal r₀ = Fed Funds bulan terakhir di data; langkah bulanan s.d. Des 2028.
- **Default a = 0,20 dan σ = 0,40 pp/√tahun** dipilih sebagai titik awal yang wajar, bukan hasil kalibrasi.
- *Estimasi dari data* (tombol di UI): AR(1) OLS pada Fed Funds bulanan, $r_{t+1}=c+\varphi r_t+\varepsilon$, lalu $a=-\ln\varphi/\Delta$ dan $\sigma=s_\varepsilon\sqrt{2a/(1-\varphi^2)}$. Pada data 2023–2026 hasilnya a ≈ 0,04 dan σ ≈ 0,39. Dengan hanya 46 observasi dalam satu siklus kebijakan, estimasi *a* sangat tidak presisi dan bias ke bawah (seri tampak hampir *random walk*). θ∞ hasil AR(1) tidak ditawarkan karena tidak masuk akal secara ekonomi (±1,8%).
- Shock awal x₀ (bps) menggeser r(0) lalu meluruh dengan laju *a*.
- Batas bawah 0% hanya memotong keluaran (tidak mengubah dinamika, tidak memengaruhi lintasan berikutnya).
- *Antithetic variates* (pasangan Z, −Z) mengurangi galat Monte Carlo. Seed bisa diatur untuk reprodusibilitas.

### Keluaran

- Fan chart: persentil 5/25/50/75/95 lintas lintasan per bulan + rata-rata.
- P(Fed Funds > X) pada bulan evaluasi; P(pernah > X) = peluang max lintasan bulan 1…T melampaui X; galat baku MC ≈ √(p(1−p)/N).
- Ekspektasi terminal = rata-rata lintasan; persentil 95 pada bulan evaluasi.

### Proyeksi spread

Spread = BI-Rate − Fed Funds (per lintasan). Asumsi BI-Rate: **tetap**; **linier** ke target; atau **pass-through** BI_t = BI₀ + β·(Fed_t − Fed₀) (β=1 → spread konstan). Ambang spread kritis adalah asumsi pengguna (default 1,00 pp ≈ median historis spread di sampel, 1,03 pp; minimum sampel 0,42 pp).

### Keterbatasan

Model Gaussian satu faktor: tanpa lompatan 25 bps diskret, tanpa reaction function The Fed (data inflasi/tenaga kerja), simetris, dan tanpa korelasi dengan BI-Rate kecuali lewat mode pass-through. Baca ekor distribusi sebagai **skenario**, bukan probabilitas riil.

## 4. Risk Signal

### Komponen (nilai mentah)

| # | Komponen | Definisi | Arah tekanan |
|---|---|---|---|
| 1 | Spread BI−Fed | BI-Rate − Fed Funds (pp) | makin **sempit** → makin menekan |
| 2 | Volatilitas kurs | std log-return USD/IDR 20 hari × √252 (%) | makin tinggi |
| 3 | Penguatan DXY | DXY_t / DXY_{t−20} − 1 (%) | makin positif (dolar menguat) |
| 4 | Depresiasi USD/IDR | USD/IDR_t / USD/IDR_{t−20} − 1 (%) | makin positif (rupiah melemah) |

Jendela (20 hari) dapat diubah di *Parameter lanjutan*.

### Skor & indeks

1. Tiap komponen → **percentile rank** *mid-rank* (0–100) terhadap riwayatnya sendiri; skor spread dibalik (100 − rank).
2. Indeks = Σ wᵢ·sᵢ / Σ wᵢ, bobot dinormalisasi otomatis (semua nol → sama rata). Jika satu komponen kosong pada suatu hari, bobot dinormalisasi ulang ke komponen tersedia.
3. Kontribusi komponen = wᵢ·sᵢ (jumlahnya = indeks).
4. Zona: hijau < 40, kuning 40–70, merah ≥ 70 (konvensi tampilan, dapat diubah).

### Mode normalisasi

- **Seluruh sampel**: rank terhadap semua data (mengandung look-ahead; bagus untuk membaca kondisi relatif).
- **Expanding**: rank hanya terhadap data s.d. tanggal itu; indeks mulai ±6 bulan setelah awal data. Tes `test_expanding_has_no_lookahead` memastikan menambah data masa depan tidak mengubah skor lampau.

### Interpretasi & keterbatasan

- Skor **relatif terhadap sampel** (~3,8 tahun, tanpa krisis besar). Indeks rata-rata ≈ 50 *by construction*; "merah" berarti "termasuk ±10% hari paling menekan dalam sampel" (pada bobot default, 9,8% hari ≥ 70), bukan ambang risiko absolut.
- Komponen 2 dan 4 berkorelasi alami (kurs bergejolak ↔ kurs bergerak besar), sehingga gerak kurs terhitung ganda bila bobot keduanya besar.
- Penanda **Mei 2026** = RDG 20 Mei 2026 (BI naik 50 bps ke 5,25%). Pada pengaturan default, indeks saat itu 60,2 (kuning) dan mencapai puncak pasca-penanda 69,0 pada 8 Jun 2026 — naik tajam dibanding rata-rata 30 hari sebelumnya (48,8), tetapi tidak menembus zona merah.
- Indeks ini tidak divalidasi sebagai prediktor; ia adalah ringkasan kondisi, bukan alat peramal.
