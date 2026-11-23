"""Helper UI Streamlit: format angka Indonesia, filter tanggal global, loader ber-cache."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from .dataset import Bundle, load_bundle

DATE_KEY = "global_date_range"
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


# --------------------------------------------------------------------------
# Format angka & tanggal (gaya Indonesia: 1.234,56)
# --------------------------------------------------------------------------
def fmt_num(x: float | None, nd: int = 2, suffix: str = "", signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if signed and round(x, nd) == 0:
        signed = False  # hindari "+0,00"
    s = f"{x:+,.{nd}f}" if signed else f"{x:,.{nd}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


def fmt_date(ts: pd.Timestamp | None) -> str:
    if ts is None or pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    return f"{ts.day} {_MONTH_ABBR[ts.month - 1]} {ts.year}"


def fmt_month(ts: pd.Timestamp | None) -> str:
    if ts is None or pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    return f"{_MONTH_ABBR[ts.month - 1]} {ts.year}"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Memuat data…")
def get_bundle() -> Bundle:
    """Muat & validasi seluruh data (di-cache; restart app atau clear cache untuk memuat ulang)."""
    return load_bundle()


def load_or_stop() -> Bundle:
    """Muat data; bila gagal tampilkan pesan yang bisa ditindaklanjuti, lalu hentikan halaman."""
    try:
        return get_bundle()
    except Exception as exc:  # noqa: BLE001 — tampilkan ke pengguna apa pun penyebabnya
        st.error(
            f"Gagal memuat data: **{exc}**\n\n"
            "Pastikan lima file ada di `data/raw/` dengan format yang sama seperti contoh "
            "(lihat `docs/DATA.md`)."
        )
        st.stop()


# --------------------------------------------------------------------------
# Filter tanggal global (sidebar)
# --------------------------------------------------------------------------
def _set_preset(years: int | None, bundle_start: pd.Timestamp, bundle_end: pd.Timestamp) -> None:
    start = bundle_start if years is None else max(bundle_start, bundle_end - pd.DateOffset(years=years))
    st.session_state[DATE_KEY] = (start.date(), bundle_end.date())


def render_date_filter(bundle: Bundle) -> None:
    """Gambar filter rentang tanggal di sidebar. Dipanggil dari app.py sebelum halaman berjalan."""
    lo, hi = bundle.start.date(), bundle.end.date()
    if DATE_KEY not in st.session_state:
        st.session_state[DATE_KEY] = (lo, hi)
    st.sidebar.markdown("**Rentang tanggal**")
    st.sidebar.slider(
        "Rentang tanggal",
        min_value=lo,
        max_value=hi,
        key=DATE_KEY,
        format="DD MMM YYYY",
        label_visibility="collapsed",
    )
    c1, c2, c3 = st.sidebar.columns(3)
    c1.button("1 th", on_click=_set_preset, args=(1, bundle.start, bundle.end), width="stretch")
    c2.button("2 th", on_click=_set_preset, args=(2, bundle.start, bundle.end), width="stretch")
    c3.button("Semua", on_click=_set_preset, args=(None, bundle.start, bundle.end), width="stretch")


def keep_date_filter_alive() -> None:
    """Streamlit menghapus state widget yang tidak digambar; panggil ini di halaman tanpa filter."""
    if DATE_KEY in st.session_state:
        st.session_state[DATE_KEY] = st.session_state[DATE_KEY]


def get_date_range(bundle: Bundle) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Rentang tanggal terpilih (default: seluruh data)."""
    sel = st.session_state.get(DATE_KEY)
    if not sel or len(sel) != 2:
        return bundle.start, bundle.end
    start, end = pd.Timestamp(sel[0]), pd.Timestamp(sel[1])
    return max(start, bundle.start), min(end, bundle.end)


def slice_range(obj: pd.DataFrame | pd.Series, start: pd.Timestamp, end: pd.Timestamp):
    return obj.loc[(obj.index >= start) & (obj.index <= end)]


def to_month_end_series(daily: pd.Series) -> pd.Series:
    """Nilai terakhir tiap bulan, diindeks ke awal bulan (untuk disejajarkan dengan data bulanan)."""
    m = daily.dropna().groupby(daily.dropna().index.to_period("M")).last()
    m.index = m.index.to_timestamp()
    return m
