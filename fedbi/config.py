"""Konfigurasi terpusat: lokasi data, palet warna, dan parameter default."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"

# Nama file di data/raw/ (ganti di sini jika nama file Anda berbeda)
FILES = {
    "fedfunds": DATA_DIR / "fedfunds.csv",
    "usdidr": DATA_DIR / "usdidr.csv",
    "dxy": DATA_DIR / "dxy.csv",
    "inflasi": DATA_DIR / "inflasi.xlsx",
    "bi_rate": DATA_DIR / "bi_rate.xlsx",
}

# --- Palet warna -----------------------------------------------------------
COLORS = {
    "bi": "#1F5FA8",
    "fed": "#E07B00",
    "spread": "#2A9D8F",
    "idr": "#264653",
    "dxy": "#8E44AD",
    "inflasi": "#B5446E",
    "naik": "#D64545",
    "tetap": "#8A8F98",
    "turun": "#2E9E5B",
    "hijau": "#2E9E5B",
    "kuning": "#F0B429",
    "merah": "#D64545",
    "event": "#C0392B",
}

# --- Parameter analitik ----------------------------------------------------
TRADING_DAYS = 252

# Episode stres yang ditandai di grafik Risk Signal (RDG BI, 20 Mei 2026)
STRESS_EVENT_DATE = "2026-05-20"
STRESS_EVENT_LABEL = "Mei 2026 — RDG BI naik 50 bps"

# Ambang zona indeks tekanan (skala 0–100)
ZONE_GREEN_MAX = 40
ZONE_YELLOW_MAX = 70

# Simulator
HORIZON_END = "2028-12-01"  # akhir horizon simulasi (bulan)
SIM_SEED_DEFAULT = 42

# Plotly: pemisah desimal "," dan ribuan "." (format Indonesia)
PLOTLY_SEPARATORS = ",."
