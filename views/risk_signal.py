"""Halaman 4 — Risk Signal: indeks tekanan komposit 0–100."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fedbi import charts, config, risk
from fedbi.ui import fmt_date, fmt_num, get_date_range, load_or_stop, slice_range

W_KEYS = {c: f"rs_w_{c}" for c in risk.COMPONENTS}
METHOD_LABELS = {"full": "Percentile seluruh sampel", "expanding": "Expanding (tanpa look-ahead)"}


@st.cache_data(show_spinner=False)
def _scores(daily: pd.DataFrame, params: risk.RiskParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = risk.raw_components(daily, params)
    return raw, risk.component_scores(raw, params)


def _reset_weights() -> None:
    for c, k in W_KEYS.items():
        st.session_state[k] = int(risk.DEFAULT_WEIGHTS[c])


def render() -> None:
    bundle = load_or_stop()
    start, end = get_date_range(bundle)
    for c, k in W_KEYS.items():
        st.session_state.setdefault(k, int(risk.DEFAULT_WEIGHTS[c]))
    st.session_state.setdefault("rs_green", config.ZONE_GREEN_MAX)
    st.session_state.setdefault("rs_yellow", config.ZONE_YELLOW_MAX)
    st.session_state.setdefault("rs_method", "full")

    st.title("Risk Signal")
    st.caption(f"Indeks tekanan terhadap rupiah dari empat komponen · per **{fmt_date(end)}**")

    # ------------------------------------------------------------ kontrol bobot
    with st.container(border=True):
        st.markdown("**Bobot komponen**")
        cols = st.columns(4)
        for col, c in zip(cols, risk.COMPONENTS, strict=True):
            col.slider(risk.LABELS[c], 0, 100, step=5, key=W_KEYS[c])
        raw_w = {c: float(st.session_state[W_KEYS[c]]) for c in risk.COMPONENTS}
        if sum(raw_w.values()) <= 0:
            st.warning("Semua bobot 0 — dipakai bobot sama rata.", icon=":material/warning:")
        w = risk.normalize_weights(raw_w)
        r1, r2 = st.columns([5, 1])
        r1.caption("Bobot dinormalisasi otomatis: " + " · ".join(f"{risk.LABELS[c]} {w[c] * 100:.0f}%" for c in risk.COMPONENTS))
        r2.button("Reset bobot", on_click=_reset_weights, width="stretch")

        with st.expander("Parameter lanjutan"):
            a1, a2, a3 = st.columns(3)
            vol_w = a1.select_slider("Jendela volatilitas (hari)", [10, 20, 30, 60], value=20, key="rs_volw")
            dxy_w = a2.select_slider("Jendela perubahan DXY (hari)", [5, 10, 20, 40, 60], value=20, key="rs_dxyw")
            fx_w = a3.select_slider("Jendela depresiasi USD/IDR (hari)", [5, 10, 20, 40, 60], value=20, key="rs_fxw")
            b1, b2, b3 = st.columns(3)
            b1.radio(
                "Normalisasi skor",
                list(METHOD_LABELS),
                format_func=METHOD_LABELS.get,
                key="rs_method",
                help="Seluruh sampel: percentile terhadap seluruh data (mengandung look-ahead). Expanding: hanya data s.d. tanggal itu; indeks baru mulai setelah ±6 bulan.",
            )
            green = b2.slider("Batas hijau → kuning", 10, 60, key="rs_green")
            yellow = b3.slider("Batas kuning → merah", 40, 95, key="rs_yellow")
            if yellow <= green:
                st.warning("Batas merah harus lebih besar dari batas hijau; memakai nilai default.", icon=":material/warning:")
                green, yellow = config.ZONE_GREEN_MAX, config.ZONE_YELLOW_MAX

    params = risk.RiskParams(vol_window=vol_w, dxy_window=dxy_w, fx_window=fx_w, method=st.session_state.rs_method)
    raw, scores = _scores(bundle.daily, params)  # dihitung pada seluruh riwayat, ditampilkan sesuai filter
    contrib = risk.contributions(scores, raw_w)
    index = risk.composite_index(scores, raw_w)

    idx_v = slice_range(index, start, end).dropna()
    if idx_v.empty:
        st.warning("Tidak ada nilai indeks pada rentang ini (mode expanding membutuhkan ±6 bulan riwayat awal).")
        return

    if bundle.dxy_full.index.max() > bundle.end + pd.Timedelta(days=7):
        dxy_now, dxy_then = bundle.dxy_full.iloc[-1], bundle.daily["dxy"].iloc[-1]
        st.info(
            f"Data USD/IDR dan Fed Funds berakhir {fmt_date(bundle.end)}, sedangkan DXY sudah tersedia sampai "
            f"{fmt_date(bundle.dxy_full.index.max())} ({fmt_num((dxy_now / dxy_then - 1) * 100, 1, '%', signed=True)} sejak itu). "
            "Indeks di bawah belum memuat pergerakan tersebut — perbarui file data untuk kondisi terkini.",
            icon=":material/schedule:",
        )

    cur_dt = idx_v.index[-1]
    cur = float(idx_v.iloc[-1])
    ref_dt_pos = index.dropna().index.searchsorted(cur_dt - pd.Timedelta(days=30), side="right") - 1
    ref = float(index.dropna().iloc[ref_dt_pos]) if ref_dt_pos >= 0 else None
    z = risk.zone(cur, green, yellow)

    # ------------------------------------------------------------ gauge + tabel
    g, t = st.columns([2, 3])
    with g:
        st.subheader("Kondisi terakhir")
        st.plotly_chart(charts.fig_gauge(cur, ref, green, yellow), width="stretch")
        badge = {
            "Hijau": ":green-badge[Hijau · tekanan rendah]",
            "Kuning": ":orange-badge[Kuning · waspada]",
            "Merah": ":red-badge[Merah · tekanan tinggi]",
        }[z]
        st.markdown(
            f"{badge}  \nPer {fmt_date(cur_dt)}"
            + (f" · panah = selisih vs 30 hari lalu ({fmt_num(ref, 1)})" if ref is not None else "")
        )
    with t:
        st.subheader("Kontribusi tiap komponen")
        snap = risk.snapshot_table(raw, scores, raw_w, cur_dt)
        snap["Nilai mentah"] = [f"{fmt_num(v, 2)} {u}" for v, u in zip(snap["Nilai mentah"], snap["Satuan"], strict=True)]
        snap = snap.drop(columns="Satuan")
        st.dataframe(
            snap,
            hide_index=True,
            width="stretch",
            column_config={
                "Skor (0–100)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Bobot (%)": st.column_config.NumberColumn(format="%.0f"),
                "Kontribusi (poin)": st.column_config.NumberColumn(format="%.1f"),
                "Porsi indeks (%)": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        st.caption(
            "Skor 100 = komponen paling menekan dalam riwayat; 50 ≈ median. Kontribusi = bobot × skor; jumlahnya = indeks."
        )

    # ------------------------------------------------------------ grafik waktu
    st.subheader("Indeks dari waktu ke waktu")
    st.plotly_chart(
        charts.fig_risk_timeline(idx_v, green, yellow, config.STRESS_EVENT_DATE, config.STRESS_EVENT_LABEL), width="stretch"
    )

    ev = pd.Timestamp(config.STRESS_EVENT_DATE)
    near = index.dropna()
    if len(near) and near.index.min() <= ev <= near.index.max():
        at_ev = float(near[near.index <= ev].iloc[-1])
        before = near[(near.index < ev) & (near.index >= ev - pd.Timedelta(days=30))]
        after = near[(near.index >= ev) & (near.index <= ev + pd.Timedelta(days=30))]
        parts = [f"Pada penanda ({fmt_date(ev)}) indeks **{fmt_num(at_ev, 1)}** ({risk.zone(at_ev, green, yellow).lower()})"]
        if len(before):
            parts.append(f"rata-rata 30 hari sebelumnya {fmt_num(float(before.mean()), 1)}")
        if len(after):
            parts.append(f"puncak 30 hari sesudahnya {fmt_num(float(after.max()), 1)} pada {fmt_date(after.idxmax())}")
        st.caption(" · ".join(parts) + ".")

    with st.expander("Dekomposisi indeks per komponen (area bertumpuk)"):
        st.plotly_chart(charts.fig_contrib_area(slice_range(contrib, start, end).loc[idx_v.index]), width="stretch")

    with st.expander("Cara membaca & keterbatasan"):
        st.markdown(
            """
- Tiap komponen diubah ke **percentile rank** (0–100) terhadap riwayatnya sendiri; spread dibalik karena spread sempit = menekan. Indeks = rata-rata tertimbang.
- Skor bersifat **relatif terhadap sampel (≈3,8 tahun)**: 70 berarti "lebih menekan daripada ±70% hari dalam data", bukan ambang risiko absolut. Sampel tidak memuat krisis besar.
- *Depresiasi USD/IDR* dan *volatilitas kurs* secara alami berkorelasi, jadi efek pergerakan kurs terhitung ganda bila kedua bobot besar.
- Mode *Seluruh sampel* memakai distribusi penuh (ada look-ahead) — cocok untuk membaca; untuk menguji daya peringatan gunakan *Expanding*.
- Zona hijau/kuning/merah hanyalah konvensi tampilan; sesuaikan di *Parameter lanjutan*.
- Detail: `docs/METODOLOGI.md`.
"""
        )
