import numpy as np
import pandas as pd
import pytest

from fedbi import loaders


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("18.125,0", 18125.0),
        ("103,80", 103.80),
        ("-0,03%", -0.03),
        ("3,28 %", 3.28),
        ("-0,09 %", -0.09),
        ("1.234.567,5", 1234567.5),
        (5.75, 5.75),
        ("", np.nan),
        ("-", np.nan),
        (None, np.nan),
        ("abc", np.nan),
    ],
)
def test_parse_id_number(raw, expected):
    out = loaders.parse_id_number(raw)
    assert (np.isnan(out) and np.isnan(expected)) or out == pytest.approx(expected)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("21 Oktober 2026", "2026-10-21"),
        ("9 Juni 2026", "2026-06-09"),
        ("20 Mei 2026", "2026-05-20"),
        ("Agustus 2025", "2025-08-01"),
        ("17 Desember 2025", "2025-12-17"),
        ("3 Agu 2024", "2024-08-03"),
    ],
)
def test_parse_id_date(raw, expected):
    assert loaders.parse_id_date(raw) == pd.Timestamp(expected)


def test_parse_id_date_invalid():
    assert pd.isna(loaders.parse_id_date("bukan tanggal"))
    assert pd.isna(loaders.parse_id_date("12 Foo 2024"))


def test_price_csv_parsing(tmp_path):
    f = tmp_path / "fx.csv"
    f.write_text(
        '\ufeff"Tanggal","Terakhir","Pembukaan","Tertinggi","Terendah","Vol.","Perubahan%"\n'
        '"03/01/2023","15.595,0","15.595,0","15.612,5","15.550,0","0,17K","0,16%"\n'
        '"02/01/2023","15.570,0","15.490,0","15.583,5","15.490,0","0,12K","0,03%"\n'
        '"04/01/2023","15.585,0","15.612,5","15.633,0","15.580,0","0,19K","-0,06%"\n',
        encoding="utf-8",
    )
    s = loaders.load_usdidr(f)
    assert list(s.index) == list(pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04"]))
    assert s.tolist() == [15570.0, 15595.0, 15585.0]


def test_dxy_drops_weekend(tmp_path):
    f = tmp_path / "dxy.csv"
    f.write_text(
        '"Tanggal","Terakhir"\n"22/11/2026","103,85"\n"20/11/2026","103,81"\n',  # 22 Nov 2026 = Minggu
        encoding="utf-8",
    )
    s = loaders.load_dxy(f)
    assert list(s.index) == [pd.Timestamp("2026-11-20")]


def test_excel_parsers(tmp_path):
    rows = [
        [None] * 4,
        [None] * 4,
        ["BI-7Day-RR"] * 4,
        [None] * 4,
        ["NO", "Tanggal", "BI-7Day-RR", None],
        [1, "21 Oktober 2026", "5,75 %", None],
        [2, "9 Juni 2026", "5,50 %", None],
        [3, "20 Mei 2026", "5,25 %", None],
        [4, "22 April 2026", "4,75 %", None],
    ]
    f = tmp_path / "bi.xlsx"
    pd.DataFrame(rows).to_excel(f, header=False, index=False)
    bi = loaders.load_bi_rate(f)
    assert bi.index.is_monotonic_increasing
    assert bi["bi_rate"].tolist() == [4.75, 5.25, 5.50, 5.75]
    assert bi["delta_bps"].tolist()[1:] == [50, 25, 25]
    assert bi["keputusan"].tolist() == ["Awal", "Naik", "Naik", "Naik"]

    rows = [
        [None] * 4,
        ["Data Inflasi"] * 4,
        ["No", "Periode", "Data Inflasi", None],
        [1, "Februari 2025", "-0,09 %", None],
        [2, "Januari 2025", "0,76 %", None],
    ]
    f = tmp_path / "inf.xlsx"
    pd.DataFrame(rows).to_excel(f, header=False, index=False)
    inf = loaders.load_inflasi(f)
    assert inf.index.tolist() == [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")]
    assert inf.tolist() == [0.76, -0.09]


def test_real_files_sane(bundle):
    d = bundle.daily
    assert d.index.is_monotonic_increasing and not d.index.has_duplicates
    assert (d["usdidr"] > 10_000).all() and (d["usdidr"] < 30_000).all()
    assert d["dxy"].dropna().between(80, 130).all()
    assert d["fedfunds"].between(0, 10).all()
    assert d["bi_rate"].dropna().between(2, 10).all()
    assert (d["spread"].dropna() == (d["bi_rate"] - d["fedfunds"]).dropna()).all()
    assert (bundle.inflasi.between(-2, 15)).all()
    assert (bundle.dxy_full.index.dayofweek < 5).all()


def test_bi_decision_labels_consistent(bundle):
    bi = bundle.bi_events
    diff = (bi["bi_rate"].diff() * 100).round(0)
    for dt, r in bi.iloc[1:].iterrows():
        exp = "Naik" if diff[dt] > 0 else "Turun" if diff[dt] < 0 else "Tetap"
        assert r["keputusan"] == exp
    assert bi["keputusan"].iloc[0] == "Awal"
