"""Titik masuk dashboard — jalankan dengan:  streamlit run app.py"""

import streamlit as st

from fedbi import __version__, ui
from fedbi.ui import fmt_date, fmt_month
from views import monitor, risk_signal, simulator, transmisi

st.set_page_config(
    page_title="Fed → BI-Rate → Rupiah",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

bundle = ui.load_or_stop()

pages = [
    st.Page(monitor.render, title="Monitor", icon=":material/monitoring:", url_path="monitor", default=True),
    st.Page(transmisi.render, title="Transmisi", icon=":material/swap_horiz:", url_path="transmisi"),
    st.Page(simulator.render, title="Simulator", icon=":material/casino:", url_path="simulator"),
    st.Page(risk_signal.render, title="Risk Signal", icon=":material/speed:", url_path="risk-signal"),
]
page = st.navigation(pages)

with st.sidebar:
    st.markdown("### Fed → BI-Rate → Rupiah")
    st.caption("Pemantauan transmisi kebijakan moneter AS ke Indonesia")

# Filter tanggal berlaku global, kecuali di Simulator (yang bekerja ke depan, bukan ke belakang)
if page.title == "Simulator":
    ui.keep_date_filter_alive()
else:
    ui.render_date_filter(bundle)

with st.sidebar:
    with st.expander("Sumber & kualitas data"):
        labels = {
            "usdidr": "USD/IDR (harian)",
            "dxy": "DXY (harian)",
            "fedfunds": "Fed Funds (bulanan)",
            "bi_rate": "BI-Rate (per RDG)",
            "inflasi": "Inflasi YoY (bulanan)",
        }
        for key, label in labels.items():
            last = bundle.report.last_obs[key]
            when = fmt_month(last) if key in {"fedfunds", "inflasi"} else fmt_date(last)
            st.markdown(f"- **{label}**: s.d. {when}")
        for w in bundle.report.warnings:
            st.warning(w, icon=":material/warning:")
    st.caption(f"v{__version__}")

page.run()
