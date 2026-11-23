"""Halaman 1 — Monitor: kondisi saat ini."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fedbi import charts
from fedbi.dataset import asof
from fedbi.ui import fmt_date, fmt_month, fmt_num, get_date_range, load_or_stop, slice_range, to_month_end_series


def _spark(s: pd.Series, n: int = 90) -> list[float] | None:
    s = s.dropna().tail(n)
    return s.tolist() if len(s) > 2 else None


def render() -> None:
    bundle = load_or_stop()
    start, end = get_date_range(bundle)
    daily = slice_range(bundle.daily, start, end)

    st.title("Monitor")
    st.caption(f"Kondisi per **{fmt_date(end)}** · rentang tampilan {fmt_date(start)} – {fmt_date(end)}")
    if daily.empty:
        st.warning("Tidak ada data pada rentang tanggal ini.")
        return

    d = bundle.daily  # riwayat penuh (KPI dihitung pada tanggal akhir filter)

    # ---- nilai KPI pada tanggal akhir filter ------------------------------
    bi, _ = asof(d["bi_rate"], end)
    ev = bundle.bi_events[bundle.bi_events.index <= end]
    last_rdg = ev.index[-1] if len(ev) else None
    last_delta = float(ev["delta_bps"].iloc[-1]) if len(ev) and pd.notna(ev["delta_bps"].iloc[-1]) else None

    ff, ff_dt = asof(bundle.fedfunds, end)
    ff_prev, _ = asof(bundle.fedfunds, (ff_dt - pd.DateOffset(months=1)) if ff_dt is not None else end)

    spread, _ = asof(d["spread"], end)
    spread_prev, _ = asof(d["spread"], end - pd.DateOffset(months=1))

    fx, fx_dt = asof(d["usdidr"], end)
    fx_prev, _ = asof(d["usdidr"], end - pd.DateOffset(months=1))

    # inflasi bulan M baru terbit awal bulan M+1 → hindari look-ahead saat filter diputar mundur
    released = bundle.inflasi[(bundle.inflasi.index + pd.DateOffset(months=1)) <= end]
    infl = float(released.iloc[-1]) if len(released) else None
    infl_dt = released.index[-1] if len(released) else None
    infl_prev = float(released.iloc[-2]) if len(released) > 1 else None

    cols = st.columns(5)
    with cols[0]:
        delta = None
        if last_delta is not None:
            delta = "tetap" if last_delta == 0 else f"{fmt_num(last_delta, 0, ' bps', signed=True)} (RDG terakhir)"
        st.metric(
            "BI-Rate",
            fmt_num(bi, 2, "%"),
            delta,
            delta_color="off",
            border=True,
            help=f"BI-7 Day Reverse Repo Rate. RDG terakhir: {fmt_date(last_rdg)}.",
            chart_data=_spark(daily["bi_rate"]),
            chart_type="line",
        )
    with cols[1]:
        delta = fmt_num(ff - ff_prev, 2, " pp vs bln lalu", signed=True) if ff is not None and ff_prev is not None else None
        st.metric(
            "Fed Funds",
            fmt_num(ff, 2, "%"),
            delta,
            delta_color="off",
            border=True,
            help=f"Effective Fed Funds Rate, rata-rata bulanan ({fmt_month(ff_dt)}), sumber FRED.",
            chart_data=_spark(bundle.fedfunds[bundle.fedfunds.index <= end], 24),
            chart_type="line",
        )
    with cols[2]:
        delta = (
            fmt_num(spread - spread_prev, 2, " pp vs 1 bln", signed=True)
            if spread is not None and spread_prev is not None
            else None
        )
        st.metric(
            "Spread BI−Fed",
            fmt_num(spread, 2, " pp"),
            delta,
            border=True,
            help="BI-Rate dikurangi Fed Funds. Naik = selisih imbal hasil makin mendukung rupiah.",
            chart_data=_spark(daily["spread"]),
            chart_type="line",
        )
    with cols[3]:
        delta = fmt_num((fx / fx_prev - 1) * 100, 2, "% vs 1 bln", signed=True) if fx is not None and fx_prev else None
        st.metric(
            "USD/IDR",
            fmt_num(fx, 0),
            delta,
            delta_color="inverse",
            border=True,
            help=f"Penutupan {fmt_date(fx_dt)}. Naik = rupiah melemah (warna merah).",
            chart_data=_spark(daily["usdidr"]),
            chart_type="line",
        )
    with cols[4]:
        delta = (
            fmt_num(infl - infl_prev, 2, " pp vs bln lalu", signed=True) if infl is not None and infl_prev is not None else None
        )
        st.metric(
            "Inflasi YoY",
            fmt_num(infl, 2, "%"),
            delta,
            delta_color="off",
            border=True,
            help=f"Inflasi tahunan (YoY) periode {fmt_month(infl_dt)}.",
            chart_data=_spark(released, 24),
            chart_type="line",
        )

    st.subheader("BI-Rate vs Fed Funds dan spreadnya")
    st.plotly_chart(charts.fig_rates_spread(daily), width="stretch")
    st.caption(
        "Fed Funds = rata-rata bulanan (FRED), sehingga bergerak per bulan. "
        "BI-Rate dianggap berlaku sejak tanggal RDG. Data BI-Rate sebelum RDG pertama (19 Jan 2023) kosong."
    )

    st.subheader("USD/IDR dan keputusan RDG")
    st.plotly_chart(charts.fig_usdidr_rdg(daily, bundle.bi_events), width="stretch")
    st.caption(
        "▲ merah = BI menaikkan suku bunga · ▼ hijau = menurunkan · ● abu-abu = menahan. Arahkan kursor ke penanda untuk detail."
    )

    with st.expander("Tabel keputusan RDG pada rentang ini"):
        t = slice_range(bundle.bi_events, start, end).copy()
        t = t.reset_index().rename(
            columns={"date": "Tanggal RDG", "bi_rate": "BI-Rate (%)", "delta_bps": "Δ (bps)", "keputusan": "Keputusan"}
        )
        st.dataframe(
            t.iloc[::-1],
            hide_index=True,
            width="stretch",
            column_config={
                "Tanggal RDG": st.column_config.DateColumn(format="DD MMM YYYY"),
                "BI-Rate (%)": st.column_config.NumberColumn(format="%.2f"),
                "Δ (bps)": st.column_config.NumberColumn(format="%+d"),
            },
        )

    with st.expander("Inflasi YoY dan BI-Rate riil"):
        m = pd.DataFrame({"inflasi": bundle.inflasi, "bi_rate": to_month_end_series(d["bi_rate"])}).dropna()
        m = m[(m.index >= start.to_period("M").to_timestamp()) & (m.index <= end)]
        if m.empty:
            st.info("Tidak ada data inflasi pada rentang ini.")
        else:
            st.plotly_chart(charts.fig_inflasi_real(m), width="stretch")
            st.caption(
                "BI-Rate riil di sini = BI-Rate akhir bulan − inflasi YoY bulan yang sama (pendekatan sederhana, bukan ekspektasi inflasi)."
            )
