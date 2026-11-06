"""Chart Library for Automated Manufacturing MIS & Rejection Reports.

Provides pure visualizer functions using both Matplotlib (for static PDF/Excel embeds)
and Plotly (for interactive Dashboard & Streamlit explorer), styled strictly
to the calm, minimal-contrast Dribbble aesthetic (Section 5.2/5.6).
"""

import io
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Visual Styling Tokens (Plan Section 5.2 & 5.6)
# ---------------------------------------------------------------------------
COLORS = {
    "accent": "#8E9BFF",       # Lavender Blue
    "accent_soft": "#E6E9FF",  # Soft Lavender
    "mint": "#A8DCC4",         # Good
    "butter": "#F6DDA8",       # Warn
    "rose": "#F4B9C0",         # Bad
    "sky": "#B7D8F5",          # Sky
    "lilac": "#D4C2F0",        # Lilac
    "text": "#3F4558",         # Slate Text
    "text_muted": "#8A90A6",   # Faint Text
    "surface": "#FBFBFD",      # Soft Surface
    "surface_alt": "#EEF0F6",  # Input/Border surface
    "grid": "#EDF0F7",         # Subtle horizontal grid line
}

PALETTE_CYCLE = [
    COLORS["accent"],
    COLORS["mint"],
    COLORS["butter"],
    COLORS["rose"],
    COLORS["sky"],
    COLORS["lilac"],
]

# Set global Matplotlib styling defaults
plt.rcParams.update({
    "font.sans-serif": ["Inter", "Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.family": "sans-serif",
    "text.color": COLORS["text"],
    "axes.labelcolor": COLORS["text_muted"],
    "xtick.color": COLORS["text_muted"],
    "ytick.color": COLORS["text_muted"],
    "axes.edgecolor": "none",
    "figure.facecolor": "none",
    "axes.facecolor": "none",
})


# ---------------------------------------------------------------------------
# Utility Conversion Helpers
# ---------------------------------------------------------------------------
def matplotlib_to_base64_png(fig: plt.Figure, dpi: int = 200) -> str:
    """Encodes a Matplotlib Figure as a base64 Data URI string for HTML/PDF reports."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True, dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def save_matplotlib_png(fig: plt.Figure, output_path: Union[str, Path], dpi: int = 200) -> Path:
    """Saves a Matplotlib Figure as a high-resolution transparent PNG."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="png", bbox_inches="tight", transparent=True, dpi=dpi)
    plt.close(fig)
    return path


# ===========================================================================
# 1. MATPLOTLIB STATIC CHARTS (For PDF & Excel Workbooks)
# ===========================================================================

def chart_production_vs_target_mpl(df: pd.DataFrame, title: str = "Daily Production vs Target") -> plt.Figure:
    """Generates a soft dual-line / bar + line chart of Target vs Produced Quantity.

    Pure function: (dataframe) -> plt.Figure
    Expects columns: date_key or day_name, target_qty, produced_qty
    """
    fig, ax = plt.subplots(figsize=(8, 3.8))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")

    dates = df["day_name"].tolist() if "day_name" in df.columns else df["date_key"].astype(str).tolist()
    x = np.arange(len(dates))

    # Production Area / Line
    ax.plot(x, df["produced_qty"], color=COLORS["accent"], linewidth=2.5, marker="o", markersize=6, label="Actual Produced")
    ax.fill_between(x, df["produced_qty"], alpha=0.12, color=COLORS["accent"])

    # Target Dotted Line
    ax.plot(x, df["target_qty"], color=COLORS["text_muted"], linewidth=1.8, linestyle="--", marker="s", markersize=4, label="Target Qty")

    # Clean axes
    ax.set_title(title, fontsize=13, weight=600, pad=14, color=COLORS["text"], loc="left")
    ax.set_xticks(x)
    ax.set_xticklabels(dates, fontsize=10)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{int(y):,}"))
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=1.0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.legend(frameon=False, loc="upper right", fontsize=9)
    plt.tight_layout()
    return fig


def chart_rejection_trend_mpl(df: pd.DataFrame, threshold_pct: float = 3.5, title: str = "Daily Rejection % Trend") -> plt.Figure:
    """Generates a clean trend line of rejection % with a soft threshold guideline.

    Pure function: (dataframe) -> plt.Figure
    Expects columns: date_key or day_name, rejection_pct
    """
    fig, ax = plt.subplots(figsize=(8, 3.8))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")

    dates = df["day_name"].tolist() if "day_name" in df.columns else df["date_key"].astype(str).tolist()
    x = np.arange(len(dates))
    rates = df["rejection_pct"].tolist()

    # Trend line with soft nodes
    ax.plot(x, rates, color=COLORS["rose"], linewidth=2.5, marker="o", markersize=6, label="Rejection %")
    ax.fill_between(x, rates, alpha=0.10, color=COLORS["rose"])

    # Threshold control line
    ax.axhline(threshold_pct, color=COLORS["butter"], linestyle=":", linewidth=1.5, label=f"Threshold ({threshold_pct}%)")

    # Value callout chips on points
    for i, txt in enumerate(rates):
        ax.annotate(f"{txt:.2f}%", (x[i], rates[i] + 0.08), ha="center", fontsize=8.5, color=COLORS["text"])

    ax.set_title(title, fontsize=13, weight=600, pad=14, color=COLORS["text"], loc="left")
    ax.set_xticks(x)
    ax.set_xticklabels(dates, fontsize=10)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=100.0, decimals=1))
    ax.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=1.0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.legend(frameon=False, loc="upper right", fontsize=9)
    plt.tight_layout()
    return fig


def chart_defect_pareto_mpl(df: pd.DataFrame, title: str = "Defect Pareto Distribution") -> plt.Figure:
    """Generates a standardized Defect Pareto chart (bars + cumulative % curve).

    Pure function: (dataframe) -> plt.Figure
    Expects columns: defect_code, rejected_qty, cumulative_pct
    """
    fig, ax1 = plt.subplots(figsize=(8.5, 4.0))
    fig.patch.set_facecolor("none")
    ax1.set_facecolor("none")

    top_df = df.head(7)  # Focus on vital few
    defects = top_df["defect_code"].tolist()
    counts = top_df["rejected_qty"].tolist()
    cum_pct = top_df["cumulative_pct"].tolist()
    x = np.arange(len(defects))

    # Defect Volume Bars (Soft rounded pastel bars)
    bars = ax1.bar(x, counts, color=COLORS["accent"], width=0.55, label="Defect Count", alpha=0.90)
    ax1.set_ylabel("Quantity Rejected", color=COLORS["text_muted"], fontsize=9.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(defects, rotation=25, ha="right", fontsize=9)
    ax1.grid(axis="y", color=COLORS["grid"], linestyle="-", linewidth=1.0)
    ax1.set_axisbelow(True)
    for spine in ax1.spines.values():
        spine.set_visible(False)

    # Cumulative % Curve on Secondary Axis
    ax2 = ax1.twinx()
    ax2.set_facecolor("none")
    ax2.plot(x, cum_pct, color=COLORS["rose"], linewidth=2.2, marker="D", markersize=5, label="Cumulative %")
    ax2.axhline(80.0, color=COLORS["butter"], linestyle="--", linewidth=1.2, label="80% Cutoff")
    ax2.set_ylabel("Cumulative %", color=COLORS["text_muted"], fontsize=9.5)
    ax2.set_ylim(0, 110)
    ax2.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=100.0, decimals=0))
    for spine in ax2.spines.values():
        spine.set_visible(False)

    ax1.set_title(title, fontsize=13, weight=600, pad=14, color=COLORS["text"], loc="left")
    plt.tight_layout()
    return fig


def chart_rejection_split_donut_mpl(df: pd.DataFrame, title: str = "Rejection Disposition (Scrap vs Rework)") -> plt.Figure:
    """Generates a calm Dribbble-style donut chart of rejection breakdown.

    Pure function: (dataframe) -> plt.Figure
    Expects dataframe or dict with categories and values
    """
    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")

    labels = df["category"].tolist() if "category" in df.columns else ["Scrap", "Reworkable"]
    values = df["quantity"].tolist() if "quantity" in df.columns else [df["scrap_qty"].sum(), df["reworkable_qty"].sum()]
    colors = [COLORS["rose"], COLORS["sky"]][:len(labels)]

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(width=0.40, edgecolor="white", linewidth=2.5),
    )

    for at in autotexts:
        at.set_color(COLORS["text"])
        at.set_fontsize(9.5)
        at.set_weight(600)
    for t in texts:
        t.set_color(COLORS["text"])
        t.set_fontsize(10)

    ax.set_title(title, fontsize=12, weight=600, pad=12, color=COLORS["text"], loc="center")
    plt.tight_layout()
    return fig


def chart_shop_comparison_bar_mpl(df: pd.DataFrame, title: str = "Shop Rejection Rate Comparison") -> plt.Figure:
    """Generates a horizontal comparison bar chart of shop rejection percentages.

    Pure function: (dataframe) -> plt.Figure
    Expects columns: shop_code, rejection_pct
    """
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")

    shops = df["shop_code"].tolist()
    rates = df["rejection_pct"].tolist()
    y = np.arange(len(shops))

    colors = [COLORS["accent"] if "FOUNDRY" in s else COLORS["sky"] for s in shops]
    bars = ax.barh(y, rates, color=colors, height=0.45, align="center")

    for i, v in enumerate(rates):
        ax.text(v + 0.1, i, f"{v:.2f}%", va="center", fontsize=9.5, weight=600, color=COLORS["text"])

    ax.set_yticks(y)
    ax.set_yticklabels(shops, fontsize=10, weight=500)
    ax.set_xlim(0, max(rates) * 1.35)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=100.0, decimals=1))
    ax.grid(axis="x", color=COLORS["grid"], linestyle="-", linewidth=1.0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(title, fontsize=12.5, weight=600, pad=12, color=COLORS["text"], loc="left")
    plt.tight_layout()
    return fig


# ===========================================================================
# 2. PLOTLY INTERACTIVE CHARTS (For Dashboard & Streamlit Explorer)
# ===========================================================================

def chart_production_vs_target_plotly(df: pd.DataFrame, title: str = "Daily Production vs Target") -> go.Figure:
    """Generates an interactive Plotly dual-line chart with muted surfaces and tooltips."""
    dates = df["day_name"].tolist() if "day_name" in df.columns else df["date_key"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=df["produced_qty"],
        name="Actual Produced",
        mode="lines+markers",
        line=dict(color=COLORS["accent"], width=3, shape="spline"),
        marker=dict(size=7, color=COLORS["accent"]),
        fill="tozeroy",
        fillcolor="rgba(142, 155, 255, 0.12)",
    ))

    fig.add_trace(go.Scatter(
        x=dates,
        y=df["target_qty"],
        name="Planned Target",
        mode="lines+markers",
        line=dict(color=COLORS["text_muted"], width=2, dash="dash"),
        marker=dict(size=5, color=COLORS["text_muted"]),
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(color=COLORS["text"], size=15)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=30, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, color=COLORS["text_muted"]),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], color=COLORS["text_muted"]),
        hovermode="x unified",
    )
    return fig


def chart_rejection_trend_plotly(df: pd.DataFrame, threshold_pct: float = 3.5, title: str = "Daily Rejection Rate %") -> go.Figure:
    """Generates an interactive Plotly trend curve with threshold guidance."""
    dates = df["day_name"].tolist() if "day_name" in df.columns else df["date_key"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=df["rejection_pct"],
        name="Rejection %",
        mode="lines+markers+text",
        text=[f"{v:.2f}%" for v in df["rejection_pct"]],
        textposition="top center",
        line=dict(color=COLORS["rose"], width=3, shape="spline"),
        marker=dict(size=8, color=COLORS["rose"]),
    ))

    fig.add_hline(
        y=threshold_pct,
        line_dash="dot",
        line_color=COLORS["butter"],
        annotation_text=f"Threshold ({threshold_pct}%)",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(color=COLORS["text"], size=15)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=30, t=50, b=40),
        xaxis=dict(showgrid=False, color=COLORS["text_muted"]),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], color=COLORS["text_muted"], ticksuffix="%"),
    )
    return fig


def chart_defect_pareto_plotly(df: pd.DataFrame, title: str = "Defect Pareto (80/20 Analysis)") -> go.Figure:
    """Generates an interactive Plotly Pareto chart with primary bars and secondary cumulative %."""
    top_df = df.head(7)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=top_df["defect_code"],
            y=top_df["rejected_qty"],
            name="Rejected Qty",
            marker=dict(color=COLORS["accent"], cornerradius=6),
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=top_df["defect_code"],
            y=top_df["cumulative_pct"],
            name="Cumulative %",
            mode="lines+markers",
            line=dict(color=COLORS["rose"], width=2.5),
            marker=dict(size=6, color=COLORS["rose"]),
        ),
        secondary_y=True,
    )

    fig.add_hline(
        y=80.0,
        line_dash="dash",
        line_color=COLORS["butter"],
        secondary_y=True,
    )

    fig.update_layout(
        title=dict(text=title, font=dict(color=COLORS["text"], size=15)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=50, b=40),
        xaxis=dict(showgrid=False, color=COLORS["text_muted"]),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], color=COLORS["text_muted"], title="Quantity"),
        yaxis2=dict(showgrid=False, color=COLORS["text_muted"], range=[0, 110], ticksuffix="%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def chart_rejection_split_donut_plotly(df: pd.DataFrame, title: str = "Scrap vs Rework Distribution") -> go.Figure:
    """Generates an interactive Plotly donut chart with hover callouts."""
    labels = df["category"].tolist() if "category" in df.columns else ["Scrap", "Reworkable"]
    values = df["quantity"].tolist() if "quantity" in df.columns else [df["scrap_qty"].sum(), df["reworkable_qty"].sum()]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=[COLORS["rose"], COLORS["sky"]], line=dict(color="#ffffff", width=2)),
        textinfo="label+percent",
        hoverinfo="label+value+percent",
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(color=COLORS["text"], size=15)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
    )
    return fig

