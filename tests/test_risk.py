import numpy as np
import pandas as pd
import pytest

from fedbi import risk


@pytest.fixture(scope="module")
def parts(bundle):
    raw = risk.raw_components(bundle.daily)
    return raw, risk.component_scores(raw)


def test_scores_in_range(parts):
    _, sc = parts
    assert sc.min().min() >= 0 and sc.max().max() <= 100


def test_index_in_range_and_centered(parts):
    _, sc = parts
    idx = risk.composite_index(sc, risk.DEFAULT_WEIGHTS).dropna()
    assert idx.between(0, 100).all()
    assert 40 < idx.mean() < 60  # percentile rank → rata-rata ≈ 50


def test_spread_direction_inverted(parts):
    raw, sc = parts
    hi, lo = raw["spread"].idxmax(), raw["spread"].idxmin()
    assert sc.loc[hi, "spread"] < sc.loc[lo, "spread"]
    assert sc.loc[raw["fx_vol"].idxmax(), "fx_vol"] > 95  # vol tertinggi → tekanan tertinggi


def test_pct_rank_properties():
    s = pd.Series([3.0, 1.0, 2.0, 2.0, np.nan])
    r = risk._pct_rank_full(s)
    assert np.isnan(r.iloc[4])
    assert r.iloc[1] < r.iloc[2] == r.iloc[3] < r.iloc[0]
    assert r.dropna().between(0, 100).all()


def test_weights_normalization():
    w = risk.normalize_weights({"spread": 50, "fx_vol": 50, "dxy_chg": 0, "fx_dep": 0})
    assert w["spread"] == 0.5 and w["dxy_chg"] == 0 and sum(w.values()) == pytest.approx(1)
    zero = risk.normalize_weights({c: 0 for c in risk.COMPONENTS})
    assert all(v == pytest.approx(0.25) for v in zero.values())
    neg = risk.normalize_weights({"spread": -10, "fx_vol": 10, "dxy_chg": 0, "fx_dep": 0})
    assert neg["spread"] == 0 and neg["fx_vol"] == 1


def test_contributions_sum_to_index(parts):
    _, sc = parts
    w = {"spread": 40, "fx_vol": 10, "dxy_chg": 30, "fx_dep": 20}
    c = risk.contributions(sc, w)
    idx = risk.composite_index(sc, w)
    assert np.allclose(c.sum(axis=1, min_count=1).dropna(), idx.dropna())


def test_single_weight_equals_component(parts):
    _, sc = parts
    only = risk.composite_index(sc, {"spread": 0, "fx_vol": 0, "dxy_chg": 100, "fx_dep": 0})
    assert np.allclose(only.dropna(), sc["dxy_chg"].dropna())


def test_missing_component_renormalized():
    sc = pd.DataFrame({"spread": [np.nan, 80.0], "fx_vol": [60.0, 40.0], "dxy_chg": [60.0, 40.0], "fx_dep": [60.0, 40.0]})
    idx = risk.composite_index(sc, risk.DEFAULT_WEIGHTS)
    assert idx.iloc[0] == pytest.approx(60.0)  # 3 komponen tersedia, bobot dinormalisasi ulang
    assert idx.iloc[1] == pytest.approx(50.0)


def test_expanding_has_no_lookahead(bundle):
    d = bundle.daily
    p = risk.RiskParams(method="expanding")
    full = risk.component_scores(risk.raw_components(d, p), p)
    cut = d.iloc[:600]
    part = risk.component_scores(risk.raw_components(cut, p), p)
    a, b = full.iloc[:600].dropna(), part.dropna()
    assert len(b) > 100
    assert np.allclose(a.loc[b.index], b)  # menambah data masa depan tidak mengubah skor masa lalu


def test_expanding_starts_after_min_history(bundle):
    p = risk.RiskParams(method="expanding", min_history=126)
    sc = risk.component_scores(risk.raw_components(bundle.daily, p), p)
    first_valid = sc["fx_dep"].first_valid_index()
    assert bundle.daily.index.get_loc(first_valid) >= 126


def test_zone():
    assert risk.zone(10) == "Hijau" and risk.zone(40) == "Kuning" and risk.zone(69.9) == "Kuning"
    assert risk.zone(70) == "Merah" and risk.zone(float("nan")) == "n/a"
    assert risk.zone(55, 50, 60) == "Kuning" and risk.zone(61, 50, 60) == "Merah"


def test_snapshot_table(parts):
    raw, sc = parts
    w = risk.DEFAULT_WEIGHTS
    t = risk.snapshot_table(raw, sc, w, raw.index[-1])
    idx = risk.composite_index(sc, w)
    assert list(t["Komponen"]) == [risk.LABELS[c] for c in risk.COMPONENTS]
    assert t["Kontribusi (poin)"].sum() == pytest.approx(idx.iloc[-1])
    assert t["Porsi indeks (%)"].sum() == pytest.approx(100)
    assert t["Bobot (%)"].sum() == pytest.approx(100)


def test_invalid_method(parts):
    raw, _ = parts
    with pytest.raises(ValueError):
        risk.component_scores(raw, risk.RiskParams(method="lainnya"))
