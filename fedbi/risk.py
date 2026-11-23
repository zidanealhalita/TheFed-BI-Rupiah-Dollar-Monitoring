"""Indeks tekanan komposit 0–100 (Risk Signal).

Empat komponen, masing-masing diubah menjadi skor tekanan 0–100 lewat
*percentile rank* terhadap riwayatnya sendiri (100 = paling menekan):

1. Spread BI−Fed        : makin SEMPIT → makin menekan   (skor dibalik)
2. Volatilitas kurs     : makin tinggi → makin menekan
3. Penguatan DXY        : kenaikan DXY dalam N hari → makin menekan
4. Depresiasi USD/IDR   : kenaikan USD/IDR dalam N hari → makin menekan

Indeks = rata-rata tertimbang skor. Skor bersifat RELATIF terhadap sampel
(bukan batas absolut): 50 berarti "setara median riwayat".
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config

COMPONENTS = ["spread", "fx_vol", "dxy_chg", "fx_dep"]

LABELS = {
    "spread": "Spread BI−Fed",
    "fx_vol": "Volatilitas kurs",
    "dxy_chg": "Penguatan DXY",
    "fx_dep": "Depresiasi USD/IDR",
}

UNITS = {"spread": "pp", "fx_vol": "% p.a.", "dxy_chg": "%", "fx_dep": "%"}

DEFAULT_WEIGHTS = {"spread": 25.0, "fx_vol": 25.0, "dxy_chg": 25.0, "fx_dep": 25.0}


@dataclass(frozen=True)
class RiskParams:
    vol_window: int = 20  # hari bursa untuk volatilitas kurs
    dxy_window: int = 20  # hari bursa untuk perubahan DXY
    fx_window: int = 20  # hari bursa untuk depresiasi USD/IDR
    method: str = "full"  # "full" = percentile terhadap seluruh sampel; "expanding" = tanpa look-ahead
    min_history: int = 126  # observasi minimum untuk mode expanding (~6 bulan)


# --------------------------------------------------------------------------
# Komponen mentah
# --------------------------------------------------------------------------
def raw_components(daily: pd.DataFrame, params: RiskParams = RiskParams()) -> pd.DataFrame:
    """Nilai mentah keempat komponen (satuan pada ``UNITS``)."""
    ret = np.log(daily["usdidr"]).diff()
    out = pd.DataFrame(index=daily.index)
    out["spread"] = daily["bi_rate"] - daily["fedfunds"]
    out["fx_vol"] = (
        ret.rolling(params.vol_window, min_periods=int(params.vol_window * 0.8)).std() * np.sqrt(config.TRADING_DAYS) * 100
    )
    out["dxy_chg"] = (daily["dxy"] / daily["dxy"].shift(params.dxy_window) - 1) * 100
    out["fx_dep"] = (daily["usdidr"] / daily["usdidr"].shift(params.fx_window) - 1) * 100
    return out[COMPONENTS]


# --------------------------------------------------------------------------
# Percentile rank
# --------------------------------------------------------------------------
def _pct_rank_full(s: pd.Series) -> pd.Series:
    """Percentile rank (mid-rank, 0–100) terhadap seluruh nilai valid pada ``s``."""
    valid = np.sort(s.dropna().to_numpy())
    if len(valid) == 0:
        return s * np.nan
    x = s.to_numpy()
    lo = np.searchsorted(valid, x, side="left")
    hi = np.searchsorted(valid, x, side="right")
    pct = (lo + hi) / 2 / len(valid) * 100
    return pd.Series(np.where(np.isnan(x), np.nan, pct), index=s.index)


def _pct_rank_expanding(s: pd.Series, min_history: int) -> pd.Series:
    """Percentile rank terhadap riwayat s/d t (inklusif) — tanpa look-ahead."""
    sorted_vals: list[float] = []
    out = np.full(len(s), np.nan)
    for i, v in enumerate(s.to_numpy()):
        if np.isnan(v):
            continue
        bisect.insort(sorted_vals, v)
        n = len(sorted_vals)
        if n < min_history:
            continue
        lo = bisect.bisect_left(sorted_vals, v)
        hi = bisect.bisect_right(sorted_vals, v)
        out[i] = (lo + hi) / 2 / n * 100
    return pd.Series(out, index=s.index)


def component_scores(raw: pd.DataFrame, params: RiskParams = RiskParams()) -> pd.DataFrame:
    """Skor tekanan 0–100 per komponen (spread dibalik: sempit = tinggi)."""
    if params.method not in {"full", "expanding"}:
        raise ValueError("method harus 'full' atau 'expanding'")
    scores = pd.DataFrame(index=raw.index)
    for c in COMPONENTS:
        pct = _pct_rank_full(raw[c]) if params.method == "full" else _pct_rank_expanding(raw[c], params.min_history)
        scores[c] = 100 - pct if c == "spread" else pct
    return scores


# --------------------------------------------------------------------------
# Pembobotan & indeks
# --------------------------------------------------------------------------
def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Skala bobot agar jumlahnya 1. Semua nol → bobot sama rata."""
    w = {c: max(float(weights.get(c, 0.0)), 0.0) for c in COMPONENTS}
    total = sum(w.values())
    if total <= 0:
        return {c: 1 / len(COMPONENTS) for c in COMPONENTS}
    return {c: v / total for c, v in w.items()}


def contributions(scores: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Kontribusi tiap komponen ke indeks (poin). Jumlah baris = indeks.

    Pada tanggal di mana ada komponen yang NaN, bobot dinormalisasi ulang ke komponen
    yang tersedia, sehingga indeks tetap berskala 0–100.
    """
    w = pd.Series(normalize_weights(weights))
    avail = scores[COMPONENTS].notna()
    eff = avail.mul(w, axis=1)
    eff = eff.div(eff.sum(axis=1).replace(0, np.nan), axis=0)
    out = scores[COMPONENTS].fillna(0).mul(eff)
    return out.where(avail.any(axis=1))  # tanggal tanpa komponen sama sekali → NaN


def composite_index(scores: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    contrib = contributions(scores, weights)
    idx = contrib.sum(axis=1, min_count=1)
    idx[scores[COMPONENTS].notna().sum(axis=1) == 0] = np.nan
    idx.name = "risk_index"
    return idx


def zone(value: float, green_max: float = config.ZONE_GREEN_MAX, yellow_max: float = config.ZONE_YELLOW_MAX) -> str:
    if value is None or np.isnan(value):
        return "n/a"
    if value < green_max:
        return "Hijau"
    if value < yellow_max:
        return "Kuning"
    return "Merah"


def snapshot_table(raw: pd.DataFrame, scores: pd.DataFrame, weights: dict[str, float], date: pd.Timestamp) -> pd.DataFrame:
    """Tabel kontribusi komponen pada ``date`` (atau observasi valid terakhir sebelumnya)."""
    contrib = contributions(scores, weights)
    valid = contrib.index[contrib.index <= pd.Timestamp(date)]
    dt = valid[-1]
    w = normalize_weights(weights)
    total = float(contrib.loc[dt].sum())
    rows = []
    for c in COMPONENTS:
        rows.append(
            {
                "Komponen": LABELS[c],
                "Nilai mentah": raw.loc[dt, c],
                "Satuan": UNITS[c],
                "Skor (0–100)": scores.loc[dt, c],
                "Bobot (%)": w[c] * 100,
                "Kontribusi (poin)": contrib.loc[dt, c],
                "Porsi indeks (%)": (contrib.loc[dt, c] / total * 100) if total > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)
