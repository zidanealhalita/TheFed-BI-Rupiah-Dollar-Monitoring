import numpy as np
import pandas as pd
import pytest

from fedbi import analytics, config


def test_rolling_vol_matches_definition():
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2023-01-02", periods=2000)
    sigma_d = 0.006
    price = pd.Series(15000 * np.exp(np.cumsum(rng.normal(0, sigma_d, len(idx)))), index=idx)
    vol = analytics.rolling_vol(price, 60)
    assert vol.dropna().mean() == pytest.approx(sigma_d * np.sqrt(config.TRADING_DAYS) * 100, rel=0.05)
    last = np.log(price).diff().iloc[-60:].std() * np.sqrt(252) * 100
    assert vol.iloc[-1] == pytest.approx(last)


def test_rolling_vol_zero_for_constant_growth():
    idx = pd.bdate_range("2023-01-02", periods=100)
    price = pd.Series(100 * 1.001 ** np.arange(100), index=idx)
    assert analytics.rolling_vol(price, 20).dropna().max() < 1e-9


def _daily(n=300, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n)
    fx = pd.Series(15000 * np.exp(np.cumsum(rng.normal(0, 0.004, n))), index=idx)
    ff = pd.Series(np.round(np.cumsum(rng.normal(0, 0.05, n)) + 4, 2), index=idx)
    return pd.DataFrame({"usdidr": fx, "dxy": 100 + np.cumsum(rng.normal(0, 0.1, n)), "fedfunds": ff})


def test_corr_level_perfect_relation():
    d = _daily()
    d["fedfunds"] = np.log(d["usdidr"]) * 2 + 1
    c = analytics.rolling_corr_fed_idr(d, window=60, mode="level").dropna()
    assert (c > 0.999).all() and c.max() <= 1.0


def test_corr_constant_window_is_nan_not_inf():
    d = _daily()
    d["fedfunds"] = 5.33
    c = analytics.rolling_corr_fed_idr(d, window=60, mode="level")
    assert c.isna().all() and not np.isinf(c).any()


def test_corr_change_mode_and_invalid_mode():
    d = _daily()
    c = analytics.rolling_corr_fed_idr(d, window=60, mode="change")
    assert c.dropna().between(-1, 1).all()
    with pytest.raises(ValueError):
        analytics.rolling_corr_fed_idr(d, mode="salah")


def test_event_study_recovers_known_jump():
    n = 120
    idx = pd.bdate_range("2024-01-01", periods=n)
    price = pd.Series(15000.0, index=idx)
    ev_date = idx[60]
    price.iloc[60:] *= 1.01  # lonjakan +1% tepat pada hari RDG (hari 0)
    daily = pd.DataFrame({"usdidr": price, "dxy": 100.0, "fedfunds": 5.0})
    events = pd.DataFrame(
        {"bi_rate": [6.0, 6.25], "delta_bps": [np.nan, 25.0], "keputusan": ["Awal", "Naik"]}, index=[idx[10], ev_date]
    )
    paths, summary = analytics.event_study(daily, events, window=5)
    assert paths["event_date"].nunique() == 1  # 'Awal' dikecualikan
    row = paths[paths["k"] == 0].iloc[0]
    assert row["cum_ret"] == pytest.approx(np.log(1.01) * 100)
    assert paths[paths["k"] == -1].iloc[0]["cum_ret"] == 0.0  # basis = penutupan hari −1
    assert paths[paths["k"] == -3].iloc[0]["cum_ret"] == 0.0
    assert summary.loc[summary["keputusan"] == "Naik", "n_event"].iloc[0] == 1
    assert summary.loc[summary["keputusan"] == "Naik", "pct_melemah"].iloc[0] == 100


def test_event_study_net_of_dxy_removes_common_move():
    n = 120
    idx = pd.bdate_range("2024-01-01", periods=n)
    shock = pd.Series(1.0, index=idx)
    shock.iloc[60:] = 1.02
    daily = pd.DataFrame({"usdidr": 15000 * shock, "dxy": 100 * shock, "fedfunds": 5.0})
    events = pd.DataFrame({"bi_rate": [6.0], "delta_bps": [0.0], "keputusan": ["Tetap"]}, index=[idx[60]])
    raw, _ = analytics.event_study(daily, events, window=3, net_of_dxy=False)
    net, _ = analytics.event_study(daily, events, window=3, net_of_dxy=True)
    assert raw["cum_ret"].abs().max() > 1.5
    assert net["cum_ret"].abs().max() < 1e-9


def test_event_study_drops_events_outside_data():
    idx = pd.bdate_range("2024-01-01", periods=30)
    daily = pd.DataFrame({"usdidr": 15000.0, "dxy": 100.0, "fedfunds": 5.0}, index=idx)
    events = pd.DataFrame(
        {"bi_rate": [6.0, 6.0], "delta_bps": [0.0, 0.0], "keputusan": ["Tetap", "Tetap"]}, index=[idx[2], idx[28]]
    )  # keduanya terlalu dekat ujung data untuk window=5
    paths, summary = analytics.event_study(daily, events, window=5)
    assert paths.empty and summary.empty


def test_event_study_real_data(bundle):
    paths, summary = analytics.event_study(bundle.daily, bundle.bi_events, window=5)
    assert paths["event_date"].nunique() >= 40
    assert set(summary["keputusan"]) <= {"Naik", "Tetap", "Turun"}
    assert summary["n_event"].sum() == paths["event_date"].nunique()
