"""Halaman 2 — Transmisi: hubungan Fed → kurs."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fedbi import analytics, charts
from fedbi.dataset import asof
from fedbi.ui import fmt_date, fmt_num, get_date_range, load_or_stop, slice_range


@st.cache_data(show_spinner=False)
def _corr(daily: pd.DataFrame, window: int, mode: str) -> pd.Series:
    return analytics.rolling_corr_fed_idr(daily, window=window, mode=mode)


@st.cache_data(show_spinner=False)
def _vol(price: pd.Series, window: int) -> pd.Series:
    return analytics.rolling_vol(price, window)


@st.cache_data(show_spinner=False)
def _events(daily: pd.DataFrame, events: pd.DataFrame, window: int, net: bool, start, end):
    return analytics.event_study(daily, events, window=window, net_of_dxy=net, start=start, end=end)


def render() -> None:
    bundle = load_or_stop()
    start, end = get_date_range(bundle)
    d = bundle.daily
    st.title("Transmisi")
    st.caption(f"Bagaimana pergerakan suku bunga AS merambat ke rupiah · rentang {fmt_date(start)} – {fmt_date(end)}")
    if slice_range(d, start, end).empty:
        st.warning("Tidak ada data pada rentang tanggal ini.")
        return

    # ------------------------------------------------------------------ 1
    st.subheader("1 · Korelasi bergulir Fed Funds vs USD/IDR")
    c1, c2 = st.columns([2, 1])
    window = c1.slider("Jendela (hari bursa)", 30, 250, 120, step=10, key="tr_corr_window")
    mode_label = c2.radio(
        "Basis korelasi",
        ["Level", "Perubahan 21 hari"],
        key="tr_corr_mode",
        help="Level: korelasi nilai Fed Funds vs ln(USD/IDR). Perubahan: Δ21 hari Fed Funds (pp) vs Δ21 hari USD/IDR (%).",
    )
    mode = "level" if mode_label == "Level" else "change"
    corr = _corr(d, window, mode)
    corr_v = slice_range(corr, start, end).dropna()
    if corr_v.empty:
        st.info("Rentang terlalu pendek untuk jendela ini — perlebar rentang atau kecilkan jendela.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("ρ terakhir", fmt_num(corr_v.iloc[-1], 2), border=True, help=f"Per {fmt_date(corr_v.index[-1])}")
        m2.metric("ρ rata-rata rentang", fmt_num(corr_v.mean(), 2), border=True)
        m3.metric("Min / maks", f"{fmt_num(corr_v.min(), 2)} / {fmt_num(corr_v.max(), 2)}", border=True)
        title = f"Korelasi bergulir {window} hari — " + ("level" if mode == "level" else "perubahan 21 hari")
        st.plotly_chart(charts.fig_rolling_corr(corr_v, title), width="stretch")
    st.caption("Garis terputus = Fed Funds konstan sepanjang jendela (korelasi tidak terdefinisi).")
    if mode == "level":
        st.warning(
            "Korelasi **level** antar dua seri bertren mudah menyesatkan (spurious): dua seri yang sama-sama "
            "naik/turun akan tampak berkorelasi walau tak ada hubungan sebab-akibat. Bandingkan dengan basis "
            "*Perubahan*, dan ingat Fed Funds di sini bulanan sehingga berbentuk tangga.",
            icon=":material/info:",
        )
    else:
        st.caption(
            "Perubahan 21 hari saling tumpang-tindih, sehingga korelasi antar titik berdekatan tidak independen. Fed Funds sering tidak berubah → banyak nilai nol → korelasi berisik."
        )

    # ------------------------------------------------------------------ 2
    st.subheader("2 · Volatilitas kurs bergulir")
    vwin = st.select_slider("Jendela volatilitas (hari bursa)", options=[10, 20, 30, 60, 90], value=30, key="tr_vol_window")
    vol = _vol(d["usdidr"], vwin)
    vol_v = slice_range(vol, start, end).dropna()
    if vol_v.empty:
        st.info("Rentang terlalu pendek untuk jendela ini.")
    else:
        med = float(vol.median())
        cur = float(vol_v.iloc[-1])
        pct = float((vol.dropna() <= cur).mean() * 100)
        m1, m2, m3 = st.columns(3)
        m1.metric("Volatilitas terakhir", fmt_num(cur, 1, "% p.a."), border=True, help=f"Per {fmt_date(vol_v.index[-1])}")
        m2.metric("Median riwayat", fmt_num(med, 1, "% p.a."), border=True)
        m3.metric(
            "Persentil riwayat", fmt_num(pct, 0, "%"), border=True, help="Posisi nilai terakhir terhadap seluruh riwayat data."
        )
        st.plotly_chart(charts.fig_rolling_vol(vol_v, med), width="stretch")
        st.caption("Volatilitas = simpangan baku log-return harian × √252 (dalam %, tahunan).")

    # ------------------------------------------------------------------ 3
    st.subheader("3 · Event study di sekitar RDG")
    e1, e2 = st.columns([2, 1])
    ewin = e1.slider("Jendela (± hari bursa)", 3, 15, 5, key="tr_event_window")
    net = e2.checkbox(
        "Netralkan pergerakan DXY",
        value=False,
        key="tr_event_net",
        help="Mengurangi log-return DXY dari log-return USD/IDR, sehingga yang tersisa adalah gerak rupiah relatif terhadap dolar global.",
    )
    paths, summary = _events(d, bundle.bi_events, ewin, net, start, end)
    n_all = int((slice_range(bundle.bi_events, start, end)["keputusan"] != "Awal").sum())
    if paths.empty:
        st.info("Tidak ada RDG yang jendelanya lengkap pada rentang ini.")
    else:
        n_used = paths["event_date"].nunique()
        st.caption(
            f"{n_used} dari {n_all} RDG pada rentang dipakai (sisanya jendelanya keluar dari data). "
            "Nilai = perubahan kumulatif USD/IDR dari penutupan hari −1; **positif = rupiah melemah**."
        )
        st.plotly_chart(charts.fig_event_paths(paths, ewin), width="stretch")
        show = summary.rename(
            columns={
                "keputusan": "Keputusan",
                "n_event": "Jumlah RDG",
                "reaksi_hari0": "Reaksi hari-0 (%)",
                f"kumulatif_+{ewin}": f"Kumulatif s.d. +{ewin} hari (%)",
                "pct_melemah": "% RDG rupiah melemah",
            }
        )
        st.dataframe(
            show,
            hide_index=True,
            width="stretch",
            column_config={
                "Reaksi hari-0 (%)": st.column_config.NumberColumn(format="%+.2f"),
                f"Kumulatif s.d. +{ewin} hari (%)": st.column_config.NumberColumn(format="%+.2f"),
                "% RDG rupiah melemah": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        st.warning(
            "Ini studi deskriptif, **bukan uji kausal**. Sampel kelompok *Naik* dan *Turun* sangat kecil, pasar sudah "
            "memperhitungkan keputusan yang diekspektasikan (yang tampak hanya sebagian kejutan), dan jendela RDG yang "
            "berdekatan (mis. Mei–Jun 2026) saling tumpang-tindih.",
            icon=":material/info:",
        )

    # ------------------------------------------------------------------ 4
    st.subheader("4 · Konteks: Dolar AS (DXY)")
    dxy_full = bundle.dxy_full
    dxy_end = dxy_full.index.max() if end >= bundle.end else end  # tampilkan DXY lebih baru dari kurs bila ada
    dxy_v = slice_range(dxy_full, start, dxy_end)
    hist = dxy_full[dxy_full.index <= dxy_end]
    cur, cur_dt = asof(dxy_full, dxy_end)
    prev20 = float(hist.iloc[-21]) if len(hist) > 21 else None
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "DXY",
        fmt_num(cur, 2),
        fmt_num((cur / prev20 - 1) * 100, 2, "% vs 20 hari", signed=True) if prev20 else None,
        delta_color="inverse",
        border=True,
        help=f"Penutupan {fmt_date(cur_dt)}. DXY naik = dolar menguat (tekanan ke rupiah).",
    )
    cr = analytics.rolling_corr_returns(d["usdidr"], d["dxy"], 60)
    cr_v = slice_range(cr, start, end).dropna()
    m2.metric("ρ return harian DXY–USD/IDR (60h)", fmt_num(cr_v.iloc[-1], 2) if len(cr_v) else "—", border=True)
    m3.metric(
        "ρ rata-rata rentang",
        fmt_num(cr_v.mean(), 2) if len(cr_v) else "—",
        border=True,
        help="Rata-rata korelasi bergulir 60 hari.",
    )
    if dxy_full.index.max() > bundle.end + pd.Timedelta(days=7):
        st.info(
            f"Data DXY lebih baru ({fmt_date(dxy_full.index.max())}) daripada data USD/IDR dan Fed Funds ({fmt_date(bundle.end)}). "
            "Analisis gabungan berhenti pada tanggal yang terakhir; grafik level DXY di bawah menampilkan sampai data terbaru.",
            icon=":material/schedule:",
        )
    t1, t2, t3 = st.tabs(["Level DXY", "DXY vs USD/IDR (rebased)", "Korelasi return bergulir"])
    with t1:
        st.plotly_chart(charts.fig_dxy_level(dxy_v), width="stretch")
    with t2:
        st.plotly_chart(charts.fig_dxy_context(slice_range(d, start, end)), width="stretch")
    with t3:
        if cr_v.empty:
            st.info("Rentang terlalu pendek.")
        else:
            st.plotly_chart(
                charts.fig_rolling_corr(cr_v, "Korelasi bergulir 60 hari: return harian DXY vs USD/IDR"), width="stretch"
            )
