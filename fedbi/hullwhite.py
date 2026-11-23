"""Model Hull-White satu faktor + simulasi Monte Carlo untuk Fed Funds.

Model:   dr(t) = [θ(t) − a·r(t)] dt + σ dW(t)

Implementasi memakai dekomposisi eksak ``r(t) = m(t) + x(t)`` dengan

    dx = −a·x dt + σ dW,   x(0) = shock awal,
    m(t) = jalur ekspektasi deterministik,   θ(t) = m'(t) + a·m(t).

Artinya θ(t) dikalibrasi agar *rata-rata* proses mengikuti m(t) (di praktik,
m(t) diambil dari kurva forward pasar; di sini dipilih pengguna karena data
kurva yield tidak tersedia). x(t) disimulasikan dengan transisi OU **eksak**,
jadi tidak ada bias diskretisasi walau langkahnya bulanan.

Satuan: suku bunga dalam persen (%), σ dalam pp/√tahun, a per tahun.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PATH_KINDS = ("mean_reverting", "flat", "linear")


@dataclass(frozen=True)
class HWParams:
    r0: float  # suku bunga terakhir yang diamati (%)
    a: float = 0.20  # kecepatan mean reversion (per tahun)
    sigma: float = 0.40  # volatilitas (pp / √tahun)
    n_steps: int = 26  # jumlah langkah (bulan)
    dt: float = 1 / 12  # panjang langkah (tahun)
    n_paths: int = 5000
    shock_bps: float = 0.0  # shock awal pada r(0), dalam bps
    path_kind: str = "mean_reverting"
    theta: float = 3.50  # level jangka panjang (mean_reverting) / target akhir (linear), %
    floor: float | None = 0.0  # batas bawah hasil simulasi (%); None = tanpa batas
    seed: int = 42
    antithetic: bool = True

    def __post_init__(self):
        if self.a < 0 or self.sigma < 0:
            raise ValueError("a dan sigma harus ≥ 0")
        if self.n_steps < 1 or self.n_paths < 1:
            raise ValueError("n_steps dan n_paths harus ≥ 1")
        if self.path_kind not in PATH_KINDS:
            raise ValueError(f"path_kind harus salah satu dari {PATH_KINDS}")


def expected_path(p: HWParams) -> np.ndarray:
    """Jalur ekspektasi deterministik m(t), t = 0..n_steps·dt (tanpa shock)."""
    t = np.arange(p.n_steps + 1) * p.dt
    if p.path_kind == "mean_reverting":
        return p.theta + (p.r0 - p.theta) * np.exp(-p.a * t)
    if p.path_kind == "flat":
        return np.full_like(t, p.r0)
    T = p.n_steps * p.dt
    return p.r0 + (p.theta - p.r0) * t / T


def theta_t(p: HWParams) -> np.ndarray:
    """θ(t) = m'(t) + a·m(t) pada grid waktu (untuk dokumentasi/ diagnostik)."""
    m = expected_path(p)
    dm = np.gradient(m, p.dt)
    return dm + p.a * m


def _ou_coefficients(a: float, sigma: float, dt: float) -> tuple[float, float]:
    """Koefisien transisi OU eksak: x_{t+dt} = decay·x_t + sd·Z."""
    if a < 1e-10:
        return 1.0, sigma * np.sqrt(dt)
    decay = np.exp(-a * dt)
    sd = sigma * np.sqrt((1 - np.exp(-2 * a * dt)) / (2 * a))
    return float(decay), float(sd)


def simulate(p: HWParams) -> np.ndarray:
    """Simulasikan lintasan Fed Funds. Return array (n_paths, n_steps + 1), kolom 0 = t0."""
    rng = np.random.default_rng(p.seed)
    decay, sd = _ou_coefficients(p.a, p.sigma, p.dt)

    if p.antithetic:
        half = (p.n_paths + 1) // 2
        z = rng.standard_normal((half, p.n_steps))
        z = np.concatenate([z, -z], axis=0)[: p.n_paths]
    else:
        z = rng.standard_normal((p.n_paths, p.n_steps))

    x = np.empty((p.n_paths, p.n_steps + 1))
    x[:, 0] = p.shock_bps / 100.0
    for i in range(p.n_steps):
        x[:, i + 1] = decay * x[:, i] + sd * z[:, i]

    r = expected_path(p)[None, :] + x
    if p.floor is not None:
        r = np.maximum(r, p.floor)
    return r


def analytic_moments(p: HWParams) -> pd.DataFrame:
    """Mean & std teoretis r(t) (tanpa floor) — dipakai untuk validasi simulasi."""
    t = np.arange(p.n_steps + 1) * p.dt
    mean = expected_path(p) + (p.shock_bps / 100.0) * np.exp(-p.a * t)
    if p.a < 1e-10:
        var = p.sigma**2 * t
    else:
        var = p.sigma**2 / (2 * p.a) * (1 - np.exp(-2 * p.a * t))
    return pd.DataFrame({"mean": mean, "std": np.sqrt(var)}, index=t)


# --------------------------------------------------------------------------
# Ringkasan hasil simulasi
# --------------------------------------------------------------------------
def fan_quantiles(paths: np.ndarray, qs=(5, 25, 50, 75, 95)) -> pd.DataFrame:
    """Persentil lintas-lintasan pada tiap langkah waktu + rata-rata."""
    q = np.percentile(paths, qs, axis=0)
    out = pd.DataFrame({f"p{int(k)}": q[i] for i, k in enumerate(qs)})
    out["mean"] = paths.mean(axis=0)
    return out


def terminal_stats(paths: np.ndarray, threshold: float, step: int = -1) -> dict:
    """Kotak probabilitas pada langkah ``step`` (default: akhir horizon).

    prob_above      : P(r_T > X)
    prob_ever_above : P(max_{t ≥ 1} r_t > X) — pernah menembus X dalam horizon
    se_prob         : galat baku Monte Carlo untuk prob_above
    """
    rT = paths[:, step]
    n = len(rT)
    p_above = float((rT > threshold).mean())
    p_ever = float((paths[:, 1:].max(axis=1) > threshold).mean())
    return {
        "mean": float(rT.mean()),
        "median": float(np.median(rT)),
        "p5": float(np.percentile(rT, 5)),
        "p95": float(np.percentile(rT, 95)),
        "prob_above": p_above,
        "prob_ever_above": p_ever,
        "se_prob": float(np.sqrt(max(p_above * (1 - p_above), 0) / n)),
    }


# --------------------------------------------------------------------------
# Spread BI-Rate vs jalur Fed simulasi
# --------------------------------------------------------------------------
BI_MODES = ("hold", "linear", "passthrough")


def bi_rate_paths(
    mode: str,
    bi0: float,
    fed_paths: np.ndarray,
    fed0: float,
    dt: float,
    target: float | None = None,
    beta: float = 0.5,
) -> np.ndarray:
    """Asumsi jalur BI-Rate terhadap jalur Fed simulasi. Return (n_paths, n_steps+1).

    hold         : BI-Rate tetap di level terakhir.
    linear       : BI-Rate bergerak linear ke ``target`` di akhir horizon.
    passthrough  : BI-Rate = bi0 + β·(Fed_t − fed0): BI mengikuti sebagian pergerakan Fed.
    """
    n_paths, n_cols = fed_paths.shape
    if mode == "hold":
        return np.full((n_paths, n_cols), bi0)
    if mode == "linear":
        if target is None:
            raise ValueError("mode 'linear' butuh target")
        line = bi0 + (target - bi0) * np.arange(n_cols) / (n_cols - 1)
        return np.tile(line, (n_paths, 1))
    if mode == "passthrough":
        return bi0 + beta * (fed_paths - fed0)
    raise ValueError(f"mode harus salah satu dari {BI_MODES}")


# --------------------------------------------------------------------------
# Kalibrasi kasar dari data historis
# --------------------------------------------------------------------------
def calibrate_ar1(series: pd.Series, dt: float = 1 / 12) -> dict:
    """Estimasi (a, θ∞, σ) dari AR(1) OLS pada data bulanan: r_{t+1} = c + φ r_t + ε.

    PERINGATAN: dengan puluhan observasi, estimasi a sangat tidak presisi dan
    cenderung bias ke bawah (kecepatan reversi dianggap lebih lambat dari
    aslinya). Anggap sebagai titik awal, bukan kebenaran.
    """
    x = series.dropna().to_numpy(dtype=float)
    if len(x) < 12:
        raise ValueError("Butuh ≥ 12 observasi untuk kalibrasi")
    X = np.column_stack([np.ones(len(x) - 1), x[:-1]])
    beta, *_ = np.linalg.lstsq(X, x[1:], rcond=None)
    c, phi = beta
    resid = x[1:] - X @ beta
    s_eps = float(resid.std(ddof=2))
    phi_c = float(np.clip(phi, 1e-3, 0.9999))
    a = float(-np.log(phi_c) / dt)
    theta = float(c / (1 - phi)) if abs(1 - phi) > 1e-6 else float(x.mean())
    sigma = float(s_eps * np.sqrt(2 * a / (1 - phi_c**2)))
    return {"a": a, "theta": theta, "sigma": sigma, "phi": float(phi), "n": len(x)}


def month_grid(last_obs: pd.Timestamp, end: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Grid bulanan (awal bulan) dari observasi terakhir sampai ``end`` inklusif."""
    start = pd.Timestamp(last_obs).to_period("M").to_timestamp()
    stop = pd.Timestamp(end).to_period("M").to_timestamp()
    return pd.date_range(start, stop, freq="MS")
