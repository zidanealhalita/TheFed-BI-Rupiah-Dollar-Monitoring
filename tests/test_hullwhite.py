import numpy as np
import pandas as pd
import pytest

from fedbi import hullwhite as hw


def P(**kw):
    base = dict(r0=3.88, a=0.5, sigma=0.8, n_steps=26, n_paths=40_000, floor=None, seed=1)
    base.update(kw)
    return hw.HWParams(**base)


@pytest.mark.parametrize("kind", hw.PATH_KINDS)
def test_moments_match_analytic(kind):
    p = P(path_kind=kind, theta=3.0, shock_bps=50)
    paths = hw.simulate(p)
    am = hw.analytic_moments(p)
    assert np.abs(paths.mean(0) - am["mean"].to_numpy()).max() < 0.01
    assert np.abs(paths.std(0) - am["std"].to_numpy()).max() < 0.02


def test_initial_value_and_shock():
    p = P(shock_bps=75)
    paths = hw.simulate(p)
    assert np.allclose(paths[:, 0], 3.88 + 0.75)
    assert hw.simulate(P(shock_bps=0))[:, 0].tolist() == pytest.approx([3.88] * 40_000)


def test_shock_decays_toward_expected_path():
    p = P(shock_bps=100, sigma=0.0, a=1.0, path_kind="flat")
    paths = hw.simulate(p)
    expected = 3.88 + 1.0 * np.exp(-1.0 * np.arange(27) / 12)
    assert np.allclose(paths[0], expected)


def test_reproducible_seed_and_different_seed():
    a = hw.simulate(P(n_paths=500, seed=7))
    b = hw.simulate(P(n_paths=500, seed=7))
    c = hw.simulate(P(n_paths=500, seed=8))
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_antithetic_pairs_and_odd_paths():
    paths = hw.simulate(P(n_paths=1001, antithetic=True, floor=None))
    assert paths.shape == (1001, 27)
    m = hw.expected_path(P())
    dev = paths - m
    half = (1001 + 1) // 2  # 501 pasangan: lintasan i dan i+501 saling berlawanan
    assert np.allclose(dev[:500], -dev[half : half + 500])


def test_zero_mean_reversion_is_random_walk():
    p = P(a=0.0, sigma=1.0, path_kind="flat")
    paths = hw.simulate(p)
    t = 26 / 12
    assert paths[:, -1].std() == pytest.approx(np.sqrt(t), rel=0.03)


def test_floor_applied():
    paths = hw.simulate(P(r0=0.3, sigma=2.0, floor=0.0, path_kind="flat"))
    assert paths.min() >= 0.0
    assert hw.simulate(P(r0=0.3, sigma=2.0, floor=None, path_kind="flat")).min() < 0.0


def test_theta_t_reproduces_expected_path():
    """Integrasi ODE dm/dt = θ(t) − a·m harus menghasilkan kembali m(t)."""
    p = P(path_kind="linear", theta=2.0, n_steps=240, dt=1 / 120)
    m = hw.expected_path(p)
    th = hw.theta_t(p)
    dm = np.gradient(m, p.dt)
    assert np.allclose(dm, th - p.a * m, atol=1e-9)


def test_invalid_params():
    with pytest.raises(ValueError):
        hw.HWParams(r0=3, a=-1)
    with pytest.raises(ValueError):
        hw.HWParams(r0=3, path_kind="zigzag")
    with pytest.raises(ValueError):
        hw.HWParams(r0=3, n_paths=0)


def test_terminal_stats_probabilities():
    paths = np.array([[1.0, 2.0, 3.0], [1.0, 5.0, 2.0], [1.0, 1.0, 4.0], [1.0, 1.0, 1.0]])
    s = hw.terminal_stats(paths, threshold=2.5)
    assert s["prob_above"] == 0.5  # 3.0 dan 4.0 pada akhir
    assert s["prob_ever_above"] == 0.75  # baris 1,2,3 pernah > 2.5
    assert s["mean"] == pytest.approx(2.5)
    s1 = hw.terminal_stats(paths, threshold=2.5, step=1)
    assert s1["prob_above"] == 0.25


def test_fan_quantiles_ordered():
    q = hw.fan_quantiles(hw.simulate(P(n_paths=2000)))
    assert (q["p5"] <= q["p25"]).all() and (q["p25"] <= q["p50"]).all()
    assert (q["p50"] <= q["p75"]).all() and (q["p75"] <= q["p95"]).all()


def test_bi_rate_modes():
    fed = np.array([[3.0, 3.5, 4.0], [3.0, 2.5, 2.0]])
    assert np.all(hw.bi_rate_paths("hold", 5.75, fed, 3.0, 1 / 12) == 5.75)
    lin = hw.bi_rate_paths("linear", 5.0, fed, 3.0, 1 / 12, target=6.0)
    assert np.allclose(lin[0], [5.0, 5.5, 6.0])
    pt = hw.bi_rate_paths("passthrough", 5.75, fed, 3.0, 1 / 12, beta=0.5)
    assert np.allclose(pt[0], [5.75, 6.0, 6.25]) and np.allclose(pt[1], [5.75, 5.5, 5.25])
    # β=1 → spread konstan
    pt1 = hw.bi_rate_paths("passthrough", 5.75, fed, 3.0, 1 / 12, beta=1.0)
    assert np.allclose(pt1 - fed, 2.75)
    with pytest.raises(ValueError):
        hw.bi_rate_paths("linear", 5.0, fed, 3.0, 1 / 12)
    with pytest.raises(ValueError):
        hw.bi_rate_paths("aneh", 5.0, fed, 3.0, 1 / 12)


def test_calibrate_recovers_ou_parameters():
    rng = np.random.default_rng(0)
    a, theta, sigma, dt, n = 1.2, 3.0, 0.7, 1 / 12, 6000
    decay = np.exp(-a * dt)
    sd = sigma * np.sqrt((1 - decay**2) / (2 * a))
    x = np.empty(n)
    x[0] = theta
    for i in range(n - 1):
        x[i + 1] = theta + (x[i] - theta) * decay + sd * rng.standard_normal()
    cal = hw.calibrate_ar1(pd.Series(x))
    assert cal["a"] == pytest.approx(a, rel=0.15)
    assert cal["theta"] == pytest.approx(theta, abs=0.15)
    assert cal["sigma"] == pytest.approx(sigma, rel=0.1)


def test_calibrate_requires_enough_data():
    with pytest.raises(ValueError):
        hw.calibrate_ar1(pd.Series(np.arange(5.0)))


def test_month_grid():
    g = hw.month_grid(pd.Timestamp("2026-10-01"), "2028-12-01")
    assert g[0] == pd.Timestamp("2026-10-01") and g[-1] == pd.Timestamp("2028-12-01")
    assert len(g) == 27
