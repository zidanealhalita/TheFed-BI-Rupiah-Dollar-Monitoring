"""Pembuat grafik Plotly. Fungsi murni: DataFrame/array masuk, ``go.Figure`` keluar."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config
from .risk import COMPONENTS, LABELS

C = config.COLORS
_COMP_COLORS = {"spread": C["spread"], "fx_vol": C["bi"], "dxy_chg": C["dxy"], "fx_dep": C["fed"]}


def _base(fig: go.Figure, height: int = 420, hover: str = "x unified") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode=hover,
        separators=config.PLOTLY_SEPARATORS,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def _vline(fig: go.Figure, x, label: str | None = None, color: str = C["event"]) -> None:
    """Garis vertikal aman untuk sumbu tanggal (menghindari bug add_vline + Timestamp)."""
    x = pd.Timestamp(x).strftime("%Y-%m-%d")
    fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, yref="y domain", line=dict(color=color, width=1.5, dash="dash"))
    if label:
        fig.add_annotation(
            x=x, y=1, yref="y domain", text=label, showarrow=False, xanchor="left", yanchor="top", font=dict(color=color, size=11)
        )


# --------------------------------------------------------------------------
# Halaman 1 — Monitor
# --------------------------------------------------------------------------
def fig_rates_spread(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.66, 0.34])
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["bi_rate"],
            name="BI-Rate",
            line=dict(color=C["bi"], width=2.4, shape="hv"),
            hovertemplate="%{y:.2f}%",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["fedfunds"],
            name="Fed Funds (rata² bulanan)",
            line=dict(color=C["fed"], width=2.4, shape="hv"),
            hovertemplate="%{y:.2f}%",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["spread"],
            name="Spread BI−Fed",
            fill="tozeroy",
            line=dict(color=C["spread"], width=1.6, shape="hv"),
            fillcolor="rgba(42,157,143,0.25)",
            hovertemplate="%{y:.2f} pp",
        ),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="% p.a.", row=1, col=1, ticksuffix="%")
    fig.update_yaxes(title_text="pp", row=2, col=1)
    return _base(fig, 520)


def fig_usdidr_rdg(df: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=df.index, y=df["usdidr"], name="USD/IDR", line=dict(color=C["idr"], width=1.8), hovertemplate="Rp %{y:,.0f}")
    )
    ev = events[(events.index >= df.index.min()) & (events.index <= df.index.max())]
    spec = {"Naik": ("triangle-up", C["naik"]), "Turun": ("triangle-down", C["turun"]), "Tetap": ("circle", C["tetap"])}
    for name, (symbol, color) in spec.items():
        sub = ev[ev["keputusan"] == name]  # RDG pertama dalam data ('Awal') tidak punya keputusan pembanding
        if sub.empty:
            continue
        y = df["usdidr"].reindex(sub.index, method="ffill")
        text = [
            f"RDG {d:%d %b %Y}: {r.keputusan}"
            + (f" {abs(r.delta_bps):.0f} bps" if r.delta_bps != 0 else "")
            + f" → {r.bi_rate:.2f}%"
            for d, r in sub.iterrows()
        ]
        fig.add_trace(
            go.Scatter(
                x=sub.index,
                y=y,
                mode="markers",
                name=f"RDG {name}",
                text=text,
                marker=dict(symbol=symbol, color=color, size=11 if name != "Tetap" else 7, line=dict(width=1, color="white")),
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.update_yaxes(title_text="Rp per USD", tickformat=",.0f")
    return _base(fig, 440, hover="closest")


def fig_inflasi_real(monthly: pd.DataFrame) -> go.Figure:
    """monthly: kolom inflasi, bi_rate (akhir bulan)."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=monthly.index, y=monthly["bi_rate"], name="BI-Rate", line=dict(color=C["bi"], width=2, shape="hv"))
    )
    fig.add_trace(go.Scatter(x=monthly.index, y=monthly["inflasi"], name="Inflasi YoY", line=dict(color=C["inflasi"], width=2)))
    fig.add_trace(
        go.Scatter(
            x=monthly.index,
            y=monthly["bi_rate"] - monthly["inflasi"],
            name="BI-Rate riil (BI − inflasi)",
            fill="tozeroy",
            line=dict(color=C["spread"], width=1.5),
            fillcolor="rgba(42,157,143,0.18)",
        )
    )
    fig.update_yaxes(ticksuffix="%")
    return _base(fig, 340)


# --------------------------------------------------------------------------
# Halaman 2 — Transmisi
# --------------------------------------------------------------------------
def fig_rolling_corr(corr: pd.Series, title: str) -> go.Figure:
    fig = go.Figure(
        go.Scatter(x=corr.index, y=corr, name="Korelasi", line=dict(color=C["fed"], width=2), hovertemplate="ρ = %{y:.2f}")
    )
    fig.add_hline(y=0, line=dict(color=C["tetap"], width=1, dash="dot"))
    fig.update_yaxes(range=[-1.05, 1.05], title_text="ρ")
    fig.update_layout(title=dict(text=title, font=dict(size=14)))
    return _base(fig, 340)


def fig_rolling_vol(vol: pd.Series, full_median: float) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=vol.index,
            y=vol,
            name="Volatilitas",
            line=dict(color=C["idr"], width=2),
            fill="tozeroy",
            fillcolor="rgba(38,70,83,0.12)",
            hovertemplate="%{y:.1f}%",
        )
    )
    fig.add_hline(
        y=full_median,
        line=dict(color=C["event"], width=1, dash="dash"),
        annotation_text=f"median riwayat {full_median:.1f}%".replace(".", ","),
        annotation_position="top left",
    )
    fig.update_yaxes(ticksuffix="%", title_text="% p.a.", rangemode="tozero")
    return _base(fig, 340)


def fig_event_paths(paths: pd.DataFrame, window: int) -> go.Figure:
    groups = [g for g in ("Naik", "Tetap", "Turun") if g in set(paths["keputusan"])]
    fig = make_subplots(
        rows=1, cols=max(len(groups), 1), shared_yaxes=True, horizontal_spacing=0.03, subplot_titles=[f"RDG {g}" for g in groups]
    )
    gc = {"Naik": C["naik"], "Tetap": C["tetap"], "Turun": C["turun"]}
    for j, g in enumerate(groups, start=1):
        sub = paths[paths["keputusan"] == g]
        for _, e in sub.groupby("event_date"):
            fig.add_trace(
                go.Scatter(
                    x=e["k"],
                    y=e["cum_ret"],
                    mode="lines",
                    showlegend=False,
                    line=dict(color=gc[g], width=0.8),
                    opacity=0.28,
                    hoverinfo="skip",
                ),
                row=1,
                col=j,
            )
        mean = sub.groupby("k")["cum_ret"].mean()
        fig.add_trace(
            go.Scatter(
                x=mean.index,
                y=mean.values,
                mode="lines+markers",
                name=f"Rata-rata {g}",
                line=dict(color=gc[g], width=3),
                marker=dict(size=6),
                hovertemplate="hari %{x}: %{y:.2f}%",
            ),
            row=1,
            col=j,
        )
        fig.add_hline(y=0, line=dict(color=C["tetap"], width=1, dash="dot"), row=1, col=j)
        fig.add_vline(x=0, line=dict(color=C["event"], width=1, dash="dash"), row=1, col=j)
        fig.update_xaxes(title_text="hari bursa relatif RDG", dtick=max(window // 5, 1), row=1, col=j)
    fig.update_yaxes(title_text="Δ USD/IDR kumulatif (%)", ticksuffix="%", row=1, col=1)
    return _base(fig, 400, hover="closest")


def fig_dxy_context(df: pd.DataFrame) -> go.Figure:
    d = df[["usdidr", "dxy"]].dropna()
    fig = go.Figure()
    if d.empty:
        return _base(fig, 340)
    fig.add_trace(
        go.Scatter(
            x=d.index,
            y=d["usdidr"] / d["usdidr"].iloc[0] * 100,
            name="USD/IDR",
            line=dict(color=C["idr"], width=2),
            hovertemplate="%{y:.1f}",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d.index,
            y=d["dxy"] / d["dxy"].iloc[0] * 100,
            name="DXY",
            line=dict(color=C["dxy"], width=2),
            hovertemplate="%{y:.1f}",
        )
    )
    fig.add_hline(y=100, line=dict(color=C["tetap"], width=1, dash="dot"))
    fig.update_yaxes(title_text="indeks (awal rentang = 100)")
    return _base(fig, 340)


def fig_dxy_level(dxy: pd.Series) -> go.Figure:
    fig = go.Figure(go.Scatter(x=dxy.index, y=dxy, name="DXY", line=dict(color=C["dxy"], width=2), hovertemplate="%{y:.2f}"))
    fig.update_yaxes(title_text="level DXY")
    return _base(fig, 300)


# --------------------------------------------------------------------------
# Halaman 3 — Simulator
# --------------------------------------------------------------------------
def _fan_traces(fig: go.Figure, x, q: pd.DataFrame, color_rgb: str, name_prefix: str = "") -> None:
    def rgba(a):
        return f"rgba({color_rgb},{a})"

    fig.add_trace(go.Scatter(x=x, y=q["p5"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=x,
            y=q["p95"],
            fill="tonexty",
            fillcolor=rgba(0.14),
            line=dict(width=0),
            name=f"{name_prefix}5–95%",
            hovertemplate="p95: %{y:.2f}",
        )
    )
    fig.add_trace(go.Scatter(x=x, y=q["p25"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=x,
            y=q["p75"],
            fill="tonexty",
            fillcolor=rgba(0.28),
            line=dict(width=0),
            name=f"{name_prefix}25–75%",
            hovertemplate="p75: %{y:.2f}",
        )
    )


def fig_fan(
    hist: pd.Series,
    grid: pd.DatetimeIndex,
    q: pd.DataFrame,
    sample_paths: np.ndarray | None,
    threshold: float | None,
    expected: np.ndarray | None,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist.index,
            y=hist,
            name="Fed Funds (aktual)",
            line=dict(color=C["fed"], width=2.4, shape="hv"),
            hovertemplate="%{y:.2f}%",
        )
    )
    if sample_paths is not None:
        for i, p in enumerate(sample_paths):
            fig.add_trace(
                go.Scatter(
                    x=grid,
                    y=p,
                    mode="lines",
                    line=dict(color="rgba(224,123,0,0.25)", width=0.7),
                    showlegend=i == 0,
                    name="Contoh lintasan",
                    hoverinfo="skip",
                )
            )
    _fan_traces(fig, grid, q, "224,123,0")
    fig.add_trace(
        go.Scatter(x=grid, y=q["p50"], name="Median", line=dict(color=C["fed"], width=2.4), hovertemplate="median: %{y:.2f}%")
    )
    fig.add_trace(
        go.Scatter(
            x=grid,
            y=q["mean"],
            name="Rata-rata",
            line=dict(color=C["idr"], width=1.6, dash="dot"),
            hovertemplate="mean: %{y:.2f}%",
        )
    )
    if expected is not None:
        fig.add_trace(
            go.Scatter(
                x=grid,
                y=expected,
                name="Jalur ekspektasi m(t)",
                line=dict(color=C["tetap"], width=1.2, dash="dash"),
                hovertemplate="m(t): %{y:.2f}%",
            )
        )
    if threshold is not None:
        fig.add_hline(
            y=threshold,
            line=dict(color=C["event"], width=1.2, dash="dash"),
            annotation_text=f"X = {threshold:.2f}%".replace(".", ","),
            annotation_position="bottom right",
        )
    _vline(fig, grid[0], None, color=C["tetap"])
    fig.update_yaxes(ticksuffix="%", title_text="Fed Funds")
    return _base(fig, 470)


def fig_terminal_hist(rT: np.ndarray, threshold: float) -> go.Figure:
    fig = go.Figure(
        go.Histogram(x=rT, nbinsx=50, marker=dict(color=C["fed"]), opacity=0.8, hovertemplate="%{x:.2f}%: %{y} lintasan")
    )
    fig.add_vline(x=threshold, line=dict(color=C["event"], width=1.5, dash="dash"))
    fig.update_xaxes(ticksuffix="%", title_text="Fed Funds di akhir horizon")
    fig.update_yaxes(title_text="jumlah lintasan")
    return _base(fig, 280, hover="closest")


def fig_spread_fan(hist: pd.Series, grid: pd.DatetimeIndex, q: pd.DataFrame, threshold: float | None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist.index,
            y=hist,
            name="Spread aktual",
            line=dict(color=C["spread"], width=2.4, shape="hv"),
            hovertemplate="%{y:.2f} pp",
        )
    )
    _fan_traces(fig, grid, q, "42,157,143")
    fig.add_trace(
        go.Scatter(
            x=grid, y=q["p50"], name="Median", line=dict(color=C["spread"], width=2.4), hovertemplate="median: %{y:.2f} pp"
        )
    )
    if threshold is not None:
        fig.add_hline(
            y=threshold,
            line=dict(color=C["event"], width=1.2, dash="dash"),
            annotation_text=f"ambang {threshold:.2f} pp".replace(".", ","),
            annotation_position="bottom right",
        )
    _vline(fig, grid[0], None, color=C["tetap"])
    fig.update_yaxes(title_text="BI-Rate − Fed Funds (pp)")
    return _base(fig, 400)


# --------------------------------------------------------------------------
# Halaman 4 — Risk Signal
# --------------------------------------------------------------------------
def fig_gauge(value: float, ref: float | None, green_max: float, yellow_max: float) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number" + ("+delta" if ref is not None and not np.isnan(ref) else ""),
            value=float(value),
            number=dict(valueformat=".1f"),
            delta=dict(
                reference=float(ref) if ref is not None and not np.isnan(ref) else 0,
                valueformat=".1f",
                increasing=dict(color=C["merah"]),
                decreasing=dict(color=C["hijau"]),
            ),
            gauge=dict(
                axis=dict(range=[0, 100], tickvals=[0, green_max, yellow_max, 100]),
                bar=dict(color="#2b2b2b", thickness=0.28),
                steps=[
                    dict(range=[0, green_max], color=C["hijau"]),
                    dict(range=[green_max, yellow_max], color=C["kuning"]),
                    dict(range=[yellow_max, 100], color=C["merah"]),
                ],
                threshold=dict(line=dict(color="#2b2b2b", width=4), thickness=0.8, value=float(value)),
            ),
        )
    )
    fig.update_layout(height=300, margin=dict(l=30, r=30, t=30, b=10), separators=config.PLOTLY_SEPARATORS)
    return fig


def fig_risk_timeline(idx: pd.Series, green_max: float, yellow_max: float, event_date=None, event_label=None) -> go.Figure:
    fig = go.Figure()
    for lo, hi, col in ((0, green_max, C["hijau"]), (green_max, yellow_max, C["kuning"]), (yellow_max, 100, C["merah"])):
        fig.add_hrect(y0=lo, y1=hi, fillcolor=col, opacity=0.10, line_width=0)
    fig.add_trace(
        go.Scatter(x=idx.index, y=idx, name="Indeks tekanan", line=dict(color="#2b2b2b", width=2), hovertemplate="%{y:.1f}")
    )
    if event_date is not None and idx.index.min() <= pd.Timestamp(event_date) <= idx.index.max():
        _vline(fig, event_date, event_label)
    fig.update_yaxes(range=[0, 100], title_text="indeks (0–100)")
    return _base(fig, 400)


def fig_contrib_area(contrib: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for c in COMPONENTS:
        fig.add_trace(
            go.Scatter(
                x=contrib.index,
                y=contrib[c],
                name=LABELS[c],
                stackgroup="one",
                mode="lines",
                line=dict(width=0.5, color=_COMP_COLORS[c]),
                hovertemplate="%{y:.1f} poin",
            )
        )
    fig.update_yaxes(range=[0, 100], title_text="kontribusi (poin)")
    return _base(fig, 340)
