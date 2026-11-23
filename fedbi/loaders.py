"""Loader & parser data mentah.

Semua file sumber memakai format Indonesia (titik ribuan, koma desimal, nama
bulan Indonesia), jadi parsing dilakukan eksplisit — bukan ``pd.to_numeric``
mentah — supaya "18.125,0" tidak terbaca sebagai 18,125.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

# --------------------------------------------------------------------------
# Parser primitif
# --------------------------------------------------------------------------
_MONTHS_ID = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2, "pebruari": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "agu": 8, "agt": 8, "ags": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11, "nop": 11,
    "desember": 12, "des": 12, "dec": 12,
}  # fmt: skip


def parse_id_number(value) -> float:
    """'18.125,0' -> 18125.0 ; '103,80' -> 103.8 ; '-0,03%' -> -0.03 ; '3,28 %' -> 3.28."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    s = str(value).replace("\u00a0", " ").replace("%", "").strip()
    if s in {"", "-", "--", "nan", "NaN"}:
        return np.nan
    s = s.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_id_date(value) -> pd.Timestamp:
    """'21 Oktober 2026' -> 2026-10-21 ; 'Mei 2026' -> 2026-05-01 (tanggal 1 bila hari tidak ada)."""
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value)
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return pd.Timestamp(value)
    s = str(value).strip().lower()
    m = re.fullmatch(r"(?:(\d{1,2})\s+)?([a-z]+)\.?\s+(\d{4})", s)
    if not m:
        return pd.NaT
    day, month_name, year = m.groups()
    month = _MONTHS_ID.get(month_name)
    if month is None:
        return pd.NaT
    return pd.Timestamp(year=int(year), month=month, day=int(day) if day else 1)


# --------------------------------------------------------------------------
# Loader per sumber
# --------------------------------------------------------------------------
def _read_price_csv(path: Path, name: str) -> pd.Series:
    """CSV 'Data Historis' (format investing.com versi Indonesia) -> Series harga penutupan."""
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    if not {"Tanggal", "Terakhir"} <= set(df.columns):
        raise ValueError(f"{path.name}: kolom 'Tanggal' dan 'Terakhir' tidak ditemukan ({list(df.columns)})")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Tanggal"], format="%d/%m/%Y", errors="coerce"),
            "close": df["Terakhir"].map(parse_id_number),
        }
    ).dropna()
    out = out.drop_duplicates("date", keep="last").sort_values("date")
    s = out.set_index("date")["close"].astype(float)
    s.name = name
    s.index.name = "date"
    return s


def load_usdidr(path: Path | None = None) -> pd.Series:
    return _read_price_csv(path or config.FILES["usdidr"], "usdidr")


def load_dxy(path: Path | None = None) -> pd.Series:
    s = _read_price_csv(path or config.FILES["dxy"], "dxy")
    # Sumber kadang menyertakan baris akhir pekan (kuotasi indikatif) — buang.
    return s[s.index.dayofweek < 5]


def load_fedfunds(path: Path | None = None) -> pd.Series:
    """FRED FEDFUNDS: rata-rata bulanan Effective Federal Funds Rate (%), indeks = awal bulan."""
    df = pd.read_csv(path or config.FILES["fedfunds"])
    date_col, val_col = df.columns[0], df.columns[1]
    s = pd.Series(
        pd.to_numeric(df[val_col], errors="coerce").to_numpy(),
        index=pd.to_datetime(df[date_col]),
        name="fedfunds",
    ).dropna()
    s.index = s.index.to_period("M").to_timestamp()
    s.index.name = "date"
    return s.sort_index()


def _read_two_col_excel(path: Path) -> pd.DataFrame:
    """Excel BI/BPS: header berantakan di baris atas; ambil dua kolom pertama yang valid."""
    raw = pd.read_excel(path, header=None, dtype=object)
    return raw.iloc[:, 1:3].rename(columns={1: "label", 2: "value"})


def load_bi_rate(path: Path | None = None) -> pd.DataFrame:
    """Keputusan RDG: DataFrame indeks = tanggal RDG, kolom ``bi_rate`` (%) dan ``delta_bps``."""
    raw = _read_two_col_excel(path or config.FILES["bi_rate"])
    df = pd.DataFrame({"date": raw["label"].map(parse_id_date), "bi_rate": raw["value"].map(parse_id_number)}).dropna()
    df = df.drop_duplicates("date", keep="last").sort_values("date").set_index("date")
    df["delta_bps"] = (df["bi_rate"].diff() * 100).round(0)
    df["keputusan"] = np.select(
        [df["delta_bps"] > 0, df["delta_bps"] < 0, df["delta_bps"] == 0],
        ["Naik", "Turun", "Tetap"],
        default="Awal",
    )
    return df


def load_inflasi(path: Path | None = None) -> pd.Series:
    """Inflasi YoY bulanan (%), indeks = awal bulan periode."""
    raw = _read_two_col_excel(path or config.FILES["inflasi"])
    df = pd.DataFrame({"date": raw["label"].map(parse_id_date), "inflasi": raw["value"].map(parse_id_number)}).dropna()
    s = df.drop_duplicates("date", keep="last").sort_values("date").set_index("date")["inflasi"]
    s.index = s.index.to_period("M").to_timestamp()
    s.index.name = "date"
    return s


# --------------------------------------------------------------------------
# Validasi
# --------------------------------------------------------------------------
@dataclass
class DataReport:
    """Ringkasan kualitas data: terakhir diamati, jumlah observasi, dan peringatan."""

    last_obs: dict[str, pd.Timestamp] = field(default_factory=dict)
    n_obs: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def validate(
    usdidr: pd.Series,
    dxy: pd.Series,
    fedfunds: pd.Series,
    bi: pd.DataFrame,
    inflasi: pd.Series,
) -> DataReport:
    rep = DataReport()
    for name, s in {"usdidr": usdidr, "dxy": dxy, "fedfunds": fedfunds, "bi_rate": bi["bi_rate"], "inflasi": inflasi}.items():
        if len(s) == 0:
            raise ValueError(f"Data '{name}' kosong — periksa file di data/raw/.")
        rep.last_obs[name] = s.index.max()
        rep.n_obs[name] = len(s)

    for name, s in {"usdidr": usdidr, "dxy": dxy}.items():
        if (s <= 0).any():
            rep.warnings.append(f"{name}: ada harga ≤ 0.")
        big = np.log(s).diff().abs()
        n_big = int((big > 0.04).sum())
        if n_big:
            rep.warnings.append(f"{name}: {n_big} perubahan harian > 4% (periksa kemungkinan salah input).")
        gaps = s.index.to_series().diff().dt.days.dropna()
        if (gaps > 7).any():
            rep.warnings.append(f"{name}: ada jeda > 7 hari antar observasi.")

    if (fedfunds < 0).any() or (fedfunds > 25).any():
        rep.warnings.append("fedfunds: nilai di luar rentang wajar 0–25%.")
    if not fedfunds.index.is_monotonic_increasing:
        rep.warnings.append("fedfunds: tanggal tidak berurutan.")
    expected = pd.date_range(fedfunds.index.min(), fedfunds.index.max(), freq="MS")
    missing = expected.difference(fedfunds.index)
    if len(missing):
        rep.warnings.append(f"fedfunds: {len(missing)} bulan hilang (mis. {missing[0]:%b %Y}).")

    if bi["bi_rate"].isna().any():
        rep.warnings.append("bi_rate: ada nilai kosong.")
    if usdidr.index.min() < bi.index.min():
        n = int((usdidr.index < bi.index.min()).sum())
        rep.warnings.append(
            f"bi_rate: data RDG pertama {bi.index.min():%d %b %Y}; {n} hari kurs sebelum itu tidak punya BI-Rate."
        )
    return rep
