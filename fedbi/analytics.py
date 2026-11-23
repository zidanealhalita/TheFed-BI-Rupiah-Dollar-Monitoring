"""Analitik deskriptif untuk halaman Transmisi.

Prinsip: semua statistik bergulir dihitung pada *seluruh* riwayat lalu dipotong
untuk tampilan, supaya jendela di awal rentang filter tidak terpotong.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def log_returns(s: pd.Series) -> pd.Series:
    return np.log(s).diff()


def _safe_rolling_corr(x: pd.Series, y: pd.Series, window: int, name: str) -> pd.Series:
    """Korelasi bergulir yang kebal terhadap jendela konstan (varians nol → NaN, bukan ±inf)."""
    mp = int(window * 0.8)
    out = x.rolling(window, min_periods=mp).corr(y)
    flat = (x.rolling(window, min_periods=mp).std() < 1e-9) | (y.rolling(window, min_periods=mp).std() < 1e-9)
    out = out.mask(flat).replace([np.inf, -np.inf], np.nan).clip(-1, 1)
    out.name = name
    return out


# --------------------------------------------------------------------------
# Korelasi bergulir Fed Funds vs USD/IDR
# --------------------------------------------------------------------------
def rolling_corr_fed_idr(daily: pd.DataFrame, window: int = 120, mode: str = "level", change_days: int = 21) -> pd.Series:
    """Korelasi bergulir Fed Funds vs USD/IDR.

    mode="level"  : korelasi level (Fed Funds, ln USD/IDR). Mudah dibaca tetapi rawan
                    spurious karena kedua seri berpola tren (non-stasioner).
    mode="change" : korelasi perubahan ``change_days`` hari (Δ Fed Funds dalam pp vs
                    Δ% USD/IDR). Lebih tahan spurious, tetapi lebih berisik.
    """
    if mode not in {"level", "change"}:
        raise ValueError("mode harus 'level' atau 'change'")
    x = daily["fedfunds"]
    y = np.log(daily["usdidr"])
    if mode == "change":
        x = x.diff(change_days)
        y = y.diff(change_days) * 100
    return _safe_rolling_corr(x, y, window, f"corr_{mode}_{window}")


# --------------------------------------------------------------------------
# Volatilitas bergulir
# --------------------------------------------------------------------------
def rolling_vol(price: pd.Series, window: int = 30) -> pd.Series:
    """Volatilitas tahunan (%) dari log-return harian: std × √252 × 100."""
    r = log_returns(price)
    vol = r.rolling(window, min_periods=int(window * 0.8)).std() * np.sqrt(config.TRADING_DAYS) * 100
    vol.name = f"vol_{window}"
    return vol


def rolling_corr_returns(a: pd.Series, b: pd.Series, window: int = 60) -> pd.Series:
    """Korelasi bergulir antar return harian dua harga."""
    return _safe_rolling_corr(log_returns(a), log_returns(b), window, f"corr_ret_{window}")


# --------------------------------------------------------------------------
# Event study di sekitar RDG
# --------------------------------------------------------------------------
def event_study(
    daily: pd.DataFrame,
    events: pd.DataFrame,
    window: int = 5,
    net_of_dxy: bool = False,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Event study sederhana: jalur kumulatif USD/IDR di sekitar tanggal RDG.

    Hari 0 = tanggal RDG (hari bursa pertama pada/ setelah tanggal). Basis = penutupan
    hari −1, sehingga nilai pada k=0 adalah reaksi hari pengumuman. Nilai dalam persen
    (log-return kumulatif × 100); positif = rupiah melemah.

    net_of_dxy=True mengurangi log-return DXY (return relatif terhadap dolar global).

    Return
    ------
    paths   : long DataFrame [event_date, keputusan, delta_bps, k, cum_ret]
    summary : ringkasan per kelompok keputusan
    """
    logp = np.log(daily["usdidr"])
    if net_of_dxy:
        logp = logp - np.log(daily["dxy"].ffill())
    idx = daily.index

    ev = events[events["keputusan"] != "Awal"]  # RDG pertama tak punya keputusan pembanding
    if start is not None:
        ev = ev[ev.index >= pd.Timestamp(start)]
    if end is not None:
        ev = ev[ev.index <= pd.Timestamp(end)]

    rows = []
    for dt, r in ev.iterrows():
        p0 = int(idx.searchsorted(dt, side="left"))
        if p0 >= len(idx) or p0 - window - 1 < 0 or p0 + window >= len(idx):
            continue  # jendela keluar dari data
        base = logp.iloc[p0 - 1]
        if np.isnan(base):
            continue
        for k in range(-window, window + 1):
            rows.append((dt, r["keputusan"], r["delta_bps"], k, (logp.iloc[p0 + k] - base) * 100))
    paths = pd.DataFrame(rows, columns=["event_date", "keputusan", "delta_bps", "k", "cum_ret"])

    if paths.empty:
        return paths, pd.DataFrame(columns=["keputusan", "n_event", "reaksi_hari0", f"kumulatif_+{window}", "pct_melemah"])

    d0 = paths[paths["k"] == 0].set_index("event_date")["cum_ret"]
    dk = paths[paths["k"] == window].set_index("event_date")["cum_ret"]
    meta = paths.drop_duplicates("event_date").set_index("event_date")["keputusan"]
    tab = pd.DataFrame({"keputusan": meta, "d0": d0, "dk": dk})
    summary = (
        tab.groupby("keputusan")
        .agg(
            n_event=("d0", "size"),
            reaksi_hari0=("d0", "mean"),
            **{f"kumulatif_+{window}": ("dk", "mean")},
            pct_melemah=("dk", lambda s: float((s > 0).mean() * 100)),
        )
        .reindex(["Naik", "Tetap", "Turun"])
        .dropna(how="all")
        .reset_index()
    )
    return paths, summary
