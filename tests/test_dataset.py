import numpy as np
import pandas as pd

from fedbi import dataset


def _toy():
    idx = pd.bdate_range("2024-01-29", "2024-03-05")
    fx = pd.Series(np.linspace(15500, 15800, len(idx)), index=idx, name="usdidr")
    dxy = pd.Series(np.linspace(103, 104, len(idx)), index=idx).drop(pd.Timestamp("2024-02-14"))
    bi = pd.DataFrame({"bi_rate": [6.00, 6.25]}, index=pd.to_datetime(["2024-02-07", "2024-02-21"]))
    ff = pd.Series([5.33, 5.30, 5.25], index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    return fx, dxy, bi, ff


def test_bi_rate_asof_no_lookahead():
    fx, dxy, bi, ff = _toy()
    d = dataset.build_daily(fx, dxy, bi, ff)
    assert np.isnan(d.loc["2024-02-06", "bi_rate"])  # sebelum RDG pertama: tidak dikarang
    assert d.loc["2024-02-07", "bi_rate"] == 6.00  # berlaku pada tanggal RDG
    assert d.loc["2024-02-20", "bi_rate"] == 6.00
    assert d.loc["2024-02-21", "bi_rate"] == 6.25
    assert d.loc["2024-03-05", "bi_rate"] == 6.25


def test_fedfunds_month_mapping_and_spread():
    fx, dxy, bi, ff = _toy()
    d = dataset.build_daily(fx, dxy, bi, ff)
    assert d.loc["2024-01-31", "fedfunds"] == 5.33
    assert d.loc["2024-02-01", "fedfunds"] == 5.30
    assert d.loc["2024-02-29", "fedfunds"] == 5.30
    assert d.loc["2024-03-04", "fedfunds"] == 5.25
    assert np.isclose(d.loc["2024-02-21", "spread"], 6.25 - 5.30)


def test_dxy_missing_day_forward_filled():
    fx, dxy, bi, ff = _toy()
    d = dataset.build_daily(fx, dxy, bi, ff)
    assert d.loc["2024-02-14", "dxy"] == d.loc["2024-02-13", "dxy"]


def test_asof():
    s = pd.Series([1.0, 2.0, np.nan], index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    assert dataset.asof(s, pd.Timestamp("2024-02-15")) == (2.0, pd.Timestamp("2024-02-01"))
    assert dataset.asof(s, pd.Timestamp("2024-03-15")) == (2.0, pd.Timestamp("2024-02-01"))
    assert dataset.asof(s, pd.Timestamp("2023-12-01")) == (None, None)
