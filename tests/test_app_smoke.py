"""Smoke test: setiap halaman harus berjalan tanpa exception, termasuk setelah interaksi widget."""

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import ROOT

PAGES = ["monitor", "transmisi", "simulator", "risk_signal"]


def _run(mod: str) -> AppTest:
    code = f"import sys; sys.path.insert(0, {str(ROOT)!r})\nfrom views import {mod}\n{mod}.render()"
    return AppTest.from_string(code, default_timeout=120).run()


def test_entrypoint_runs():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception
    assert at.title[0].value == "Monitor"
    labels = [m.label for m in at.metric]
    assert labels[:5] == ["BI-Rate", "Fed Funds", "Spread BI−Fed", "USD/IDR", "Inflasi YoY"]


def test_date_filter_and_presets():
    import datetime as dt

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.slider[0].set_value((dt.date(2025, 1, 1), dt.date(2026, 6, 30))).run()
    assert not at.exception
    at.button[0].click().run()  # preset 1 th
    assert not at.exception
    lo, hi = at.slider[0].value
    assert (hi - lo).days in range(364, 367)


@pytest.mark.parametrize("mod", PAGES)
def test_page_renders(mod):
    at = _run(mod)
    assert not at.exception, [e.value for e in at.exception]


def test_monitor_kpi_values():
    at = _run("monitor")
    kpi = {m.label: m.value for m in at.metric}
    assert kpi["BI-Rate"].endswith("%") and "," in kpi["BI-Rate"]
    assert kpi["USD/IDR"].replace(".", "").isdigit()


def test_simulator_interactions():
    at = _run("simulator")
    sl = {s.label.split(" (")[0]: s for s in at.slider}
    sl["Mean reversion a"].set_value(1.0).run()
    assert not at.exception
    at.select_slider[0].set_value(500).run()
    assert not at.exception
    next(b for b in at.button if b.label == "Pakai estimasi data").click().run()
    assert not at.exception
    next(b for b in at.button if b.label == "Reset parameter").click().run()
    assert not at.exception
    at.radio[0].set_value("passthrough").run()
    assert not at.exception


def test_risk_weights_all_zero_falls_back():
    at = _run("risk_signal")
    for s in at.slider[:4]:
        s.set_value(0)
    at.run()
    assert not at.exception
    assert any("bobot sama rata" in w.value for w in at.warning)


def test_transmisi_modes():
    at = _run("transmisi")
    at.radio[0].set_value("Perubahan 21 hari").run()
    assert not at.exception
    at.checkbox[0].set_value(True).run()
    assert not at.exception
