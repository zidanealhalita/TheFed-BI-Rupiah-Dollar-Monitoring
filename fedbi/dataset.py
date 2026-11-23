"""Menyatukan semua sumber ke satu tabel harian (indeks = hari bursa valas USD/IDR)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import loaders


@dataclass
class Bundle:
    """Seluruh data yang dipakai dashboard."""

    daily: pd.DataFrame  # usdidr, dxy, bi_rate, fedfunds, spread (harian)
    dxy_full: pd.Series  # DXY pada kalender aslinya (bisa lebih panjang dari kurs)
    bi_events: pd.DataFrame  # keputusan RDG (bi_rate, delta_bps, keputusan)
    fedfunds: pd.Series  # bulanan
    inflasi: pd.Series  # bulanan
    report: loaders.DataReport

    @property
    def start(self) -> pd.Timestamp:
        return self.daily.index.min()

    @property
    def end(self) -> pd.Timestamp:
        return self.daily.index.max()


def build_daily(usdidr: pd.Series, dxy: pd.Series, bi_events: pd.DataFrame, fedfunds: pd.Series) -> pd.DataFrame:
    """Gabungkan seri pada kalender USD/IDR.

    * DXY, BI-Rate: *as-of* (nilai terakhir yang sudah diketahui pada tanggal itu).
    * Fed Funds: rata-rata bulanan FRED dipetakan ke seluruh hari pada bulan tersebut
      (lihat docs/METODOLOGI.md untuk implikasinya).
    * BI-Rate sebelum RDG pertama dalam data = NaN (tidak dikarang).
    """
    idx = usdidr.index
    month_start = idx.to_period("M").to_timestamp()
    out = pd.DataFrame(index=idx)
    out.index.name = "date"
    out["usdidr"] = usdidr
    out["dxy"] = dxy.reindex(idx, method="ffill")
    out["bi_rate"] = bi_events["bi_rate"].reindex(idx, method="ffill")
    out["fedfunds"] = fedfunds.reindex(month_start, method="ffill").to_numpy()
    out["spread"] = out["bi_rate"] - out["fedfunds"]
    return out


def load_bundle() -> Bundle:
    usdidr = loaders.load_usdidr()
    dxy = loaders.load_dxy()
    fedfunds = loaders.load_fedfunds()
    bi = loaders.load_bi_rate()
    inflasi = loaders.load_inflasi()
    report = loaders.validate(usdidr, dxy, fedfunds, bi, inflasi)
    daily = build_daily(usdidr, dxy, bi, fedfunds)
    return Bundle(daily=daily, dxy_full=dxy, bi_events=bi, fedfunds=fedfunds, inflasi=inflasi, report=report)


def asof(series: pd.Series, date: pd.Timestamp) -> tuple[float, pd.Timestamp] | tuple[None, None]:
    """Nilai valid terakhir pada/ sebelum ``date`` beserta tanggal observasinya."""
    s = series.dropna()
    s = s[s.index <= pd.Timestamp(date)]
    if s.empty:
        return None, None
    return float(s.iloc[-1]), s.index[-1]
