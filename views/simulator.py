"""Halaman 3 — Simulator: proyeksi Fed Funds (Hull-White + Monte Carlo) dan risiko spread."""

from __future__ import annotations

import numpy as np
import streamlit as st

from fedbi import charts, config
from fedbi import hullwhite as hw
from fedbi.dataset import asof
from fedbi.ui import fmt_month, fmt_num, load_or_stop, to_month_end_series

DEFAULTS = {
    "sim_a": 0.20,
    "sim_sigma": 0.40,
    "sim_paths": 5000,
    "sim_shock": 0,
    "sim_kind": "mean_reverting",
    "sim_theta": 3.50,
    "sim_seed": config.SIM_SEED_DEFAULT,
    "sim_floor": True,
    "sim_anti": True,
    "sim_samples": False,
    "sim_x": 4.00,
    "sim_bi_mode": "hold",
    "sim_bi_target": 5.75,
    "sim_beta": 0.5,
    "sim_spread_thr": 1.00,
}
KIND_LABELS = {
    "mean_reverting": "Mean-reverting ke θ∞ (Vasicek)",
    "flat": "Datar di level terakhir",
    "linear": "Linier ke target di akhir horizon",
}
BI_LABELS = {
    "hold": "BI-Rate tetap",
    "linear": "BI-Rate linier ke target",
    "passthrough": "BI-Rate mengikuti Fed (β)",
}


@st.cache_data(show_spinner="Menjalankan simulasi…")
def _simulate(p: hw.HWParams) -> np.ndarray:
    return hw.simulate(p)


def _apply_calibration(a: float, sigma: float) -> None:
    st.session_state["sim_a"] = float(np.clip(round(a, 2), 0.01, 2.0))
    st.session_state["sim_sigma"] = float(np.clip(round(sigma, 2), 0.05, 3.0))


def _reset() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def render() -> None:
    bundle = load_or_stop()
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)

    ff_last_dt = bundle.fedfunds.index.max()
    r0 = float(bundle.fedfunds.iloc[-1])
    grid = hw.month_grid(ff_last_dt, config.HORIZON_END)
    n_steps = len(grid) - 1
    bi0, _ = asof(bundle.daily["bi_rate"], bundle.end)

    st.title("Simulator")
    st.caption(
        f"Hull-White satu faktor + Monte Carlo · titik awal Fed Funds **{fmt_month(ff_last_dt)} = {fmt_num(r0, 2, '%')}** "
        f"· horizon s.d. **{fmt_month(grid[-1])}** ({n_steps} bulan)"
    )

    # ------------------------------------------------------------ kontrol
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.slider(
            "Mean reversion a (per tahun)",
            0.01,
            2.00,
            step=0.01,
            key="sim_a",
            help="Kecepatan penyimpangan kembali ke jalur ekspektasi. a=0,2 → waktu paruh ≈ 3,5 tahun; a=1 → ≈ 8 bulan.",
        )
        c2.slider(
            "Volatilitas σ (pp/√tahun)",
            0.05,
            3.00,
            step=0.05,
            key="sim_sigma",
            help="Simpangan baku perubahan suku bunga per √tahun, dalam poin persentase.",
        )
        c3.select_slider("Jumlah lintasan", options=[500, 1000, 2000, 5000, 10000, 20000], key="sim_paths")
        c4.slider(
            "Shock awal (bps)",
            -200,
            200,
            step=5,
            key="sim_shock",
            help="Lonjakan sesaat pada Fed Funds di t₀ (mis. +50 = kejutan pengetatan), lalu meluruh dengan kecepatan a.",
        )

        try:
            cal = hw.calibrate_ar1(bundle.fedfunds)
            hint = f"Estimasi kasar dari data bulanan ({cal['n']} obs): a ≈ {cal['a']:.2f}, σ ≈ {cal['sigma']:.2f}. Presisinya rendah (lihat docs/METODOLOGI.md)."
            cc1, cc2 = st.columns([4, 1])
            cc1.caption(hint)
            cc2.button("Pakai estimasi data", on_click=_apply_calibration, args=(cal["a"], cal["sigma"]), width="stretch")
        except ValueError:
            pass

        with st.expander("Opsi lanjutan"):
            o1, o2, o3 = st.columns(3)
            o1.selectbox(
                "Jalur ekspektasi m(t)",
                list(KIND_LABELS),
                format_func=KIND_LABELS.get,
                key="sim_kind",
                help="Ke mana rata-rata Fed Funds diarahkan sebelum ada shock/ketidakpastian.",
            )
            o2.slider(
                "θ∞ / target akhir (%)",
                0.0,
                8.0,
                step=0.05,
                key="sim_theta",
                help="Level jangka panjang (mean-reverting) atau target di akhir horizon (linier). Diabaikan pada jalur datar.",
            )
            o3.number_input("Seed acak", min_value=0, step=1, key="sim_seed")
            f1, f2, f3, f4 = st.columns(4)
            f1.checkbox("Batas bawah 0%", key="sim_floor")
            f2.checkbox("Antithetic variates", key="sim_anti", help="Pasangan lintasan Z dan −Z: mengurangi galat Monte Carlo.")
            f3.checkbox("Tampilkan contoh lintasan", key="sim_samples")
            f4.button("Reset parameter", on_click=_reset, width="stretch")

        p1, p2 = st.columns(2)
        p1.slider("Ambang X untuk P(Fed Funds > X) (%)", 0.0, 8.0, step=0.05, key="sim_x")
        eval_options = list(grid[1:])
        if st.session_state.get("sim_eval") not in eval_options:
            st.session_state["sim_eval"] = eval_options[-1]
        p2.select_slider(
            "Tanggal evaluasi",
            options=eval_options,
            format_func=fmt_month,
            key="sim_eval",
            help="Bulan di mana probabilitas, ekspektasi, dan persentil dihitung.",
        )

    ss = st.session_state
    params = hw.HWParams(
        r0=r0,
        a=float(ss.sim_a),
        sigma=float(ss.sim_sigma),
        n_steps=n_steps,
        n_paths=int(ss.sim_paths),
        shock_bps=float(ss.sim_shock),
        path_kind=ss.sim_kind,
        theta=float(ss.sim_theta),
        floor=0.0 if ss.sim_floor else None,
        seed=int(ss.sim_seed),
        antithetic=bool(ss.sim_anti),
    )
    paths = _simulate(params)
    q = hw.fan_quantiles(paths)
    step = int(list(grid).index(ss.sim_eval))
    stats = hw.terminal_stats(paths, float(ss.sim_x), step=step)

    # ------------------------------------------------------------ fan chart
    st.subheader("Fan chart Fed Funds")
    hist = bundle.fedfunds.tail(36)
    sample = None
    if ss.sim_samples:
        stride = max(len(paths) // 40, 1)
        sample = paths[::stride][:40]
    st.plotly_chart(charts.fig_fan(hist, grid, q, sample, float(ss.sim_x), hw.expected_path(params)), width="stretch")
    st.caption(
        "Pita gelap = persentil 25–75, pita terang = 5–95. Garis putus-putus abu-abu = jalur ekspektasi m(t) sebelum shock."
    )

    # ------------------------------------------------------------ kotak probabilitas
    st.subheader(f"Kotak probabilitas · {fmt_month(grid[step])}")
    left, right = st.columns([3, 2])
    with left:
        a1, a2 = st.columns(2)
        a1.metric(
            f"P(Fed Funds > {fmt_num(ss.sim_x, 2, '%')})",
            fmt_num(stats["prob_above"] * 100, 1, "%"),
            border=True,
            help=f"Pada {fmt_month(grid[step])}. Galat baku Monte Carlo ≈ ±{fmt_num(stats['se_prob'] * 100, 1)} pp.",
        )
        a2.metric(
            "P(pernah > X dalam horizon)",
            fmt_num(stats["prob_ever_above"] * 100, 1, "%"),
            border=True,
            help="Peluang lintasan menembus X setidaknya sekali di antara bulan pertama s.d. akhir horizon.",
        )
        b1, b2 = st.columns(2)
        b1.metric(
            "Ekspektasi (rata-rata)",
            fmt_num(stats["mean"], 2, "%"),
            fmt_num(stats["mean"] - r0, 2, " pp vs sekarang", signed=True),
            delta_color="off",
            border=True,
        )
        b2.metric(
            "Persentil 95",
            fmt_num(stats["p95"], 2, "%"),
            border=True,
            help=f"Median {fmt_num(stats['median'], 2, '%')} · persentil 5 {fmt_num(stats['p5'], 2, '%')}",
        )
        st.caption(
            f"Median {fmt_num(stats['median'], 2, '%')} · persentil 5 {fmt_num(stats['p5'], 2, '%')} · {fmt_num(ss.sim_paths, 0)} lintasan."
        )
    with right:
        st.plotly_chart(charts.fig_terminal_hist(paths[:, step], float(ss.sim_x)), width="stretch")

    # ------------------------------------------------------------ spread
    st.subheader("Proyeksi spread BI-Rate vs jalur simulasi Fed")
    s1, s2, s3 = st.columns([2, 2, 2])
    s1.radio("Asumsi BI-Rate", list(BI_LABELS), format_func=BI_LABELS.get, key="sim_bi_mode")
    if ss.sim_bi_mode == "linear":
        s2.slider("Target BI-Rate di akhir horizon (%)", 2.0, 9.0, step=0.05, key="sim_bi_target")
    elif ss.sim_bi_mode == "passthrough":
        s2.slider(
            "β (pass-through dari Fed)",
            0.0,
            1.5,
            step=0.05,
            key="sim_beta",
            help="ΔBI = β × ΔFed relatif titik awal. β=0 setara BI-Rate tetap; β=1 menjaga spread tetap.",
        )
    else:
        s2.caption(f"BI-Rate dipatok di {fmt_num(bi0, 2, '%')} (level terakhir).")
    s3.slider(
        "Ambang spread kritis (pp)",
        -1.0,
        4.0,
        step=0.05,
        key="sim_spread_thr",
        help="Spread di bawah ambang ini dianggap mulai menekan rupiah (asumsi Anda sendiri, bukan standar baku).",
    )

    bi_paths = hw.bi_rate_paths(
        ss.sim_bi_mode, bi0, paths, r0, params.dt, target=float(ss.sim_bi_target), beta=float(ss.sim_beta)
    )
    spread_paths = bi_paths - paths
    qs = hw.fan_quantiles(spread_paths)
    spread_hist = to_month_end_series(bundle.daily["spread"]).dropna().tail(36)
    st.plotly_chart(charts.fig_spread_fan(spread_hist, grid, qs, float(ss.sim_spread_thr)), width="stretch")

    sp_T = spread_paths[:, step]
    m1, m2, m3 = st.columns(3)
    m1.metric(
        f"Spread median · {fmt_month(grid[step])}",
        fmt_num(float(np.median(sp_T)), 2, " pp"),
        border=True,
        help=f"Spread terakhir aktual: {fmt_num(bi0 - r0, 2, ' pp')}",
    )
    m2.metric("P(spread < ambang)", fmt_num(float((sp_T < ss.sim_spread_thr).mean() * 100), 1, "%"), border=True)
    m3.metric(
        "Rentang 5–95%",
        f"{fmt_num(float(np.percentile(sp_T, 5)), 2)} s.d. {fmt_num(float(np.percentile(sp_T, 95)), 2)} pp",
        border=True,
    )

    with st.expander("Cara kerja & asumsi"):
        st.latex(r"dr_t = \left[\theta(t) - a\,r_t\right]dt + \sigma\,dW_t \qquad \theta(t) = m'(t) + a\,m(t)")
        st.markdown(
            """
- Disimulasikan sebagai **r(t) = m(t) + x(t)** dengan `x` proses Ornstein–Uhlenbeck bermean nol dan transisi **eksak** (tanpa bias diskretisasi).
- **m(t)** = jalur ekspektasi pilihan Anda. Tanpa kurva yield/forward, θ(t) tidak bisa dikalibrasi ke pasar, jadi m(t) adalah *asumsi*, bukan prakiraan.
- **Shock awal** memindahkan r(0) sebesar x₀, lalu meluruh dengan kecepatan a.
- Fed Funds di data = rata-rata bulanan efektif (FRED), bukan batas target FOMC.
- Model Gaussian: suku bunga bisa turun tajam/ negatif tanpa batas bawah; opsi *Batas bawah 0%* hanya memotong hasil, tidak mengubah dinamika.
- Distribusi ini **tidak mencerminkan reaksi kebijakan The Fed** (diskret, bergantung data), sehingga ekor distribusinya perlu dibaca sebagai skenario, bukan peluang riil.
- Detail & validasi: `docs/METODOLOGI.md`.
"""
        )
