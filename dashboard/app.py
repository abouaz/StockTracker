import sys
import os
from datetime import date, timedelta

# Make sure Python can find our local package (models/stock.py)
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from models.stock import Stock

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ================================
# Stock Viewer — Simple, Clean, Functional
# ================================
# Goals:
# 1) Keep the code easy to read.
# 2) Use small functions for clarity.
# 3) In Compare mode: raw price only, Adjusted Close only, with preset time windows.

st.title("Stock Price Viewer (Simple)")

# --------------------------------
# Small utility functions
# --------------------------------

def period_to_dates(period_label: str) -> tuple[date, date]:
    """Return (start_date, end_date) for a human preset period.

    We map strings to simple date ranges relative to today.
    """
    today = date.today()
    if period_label == "Last week":
        return today - timedelta(days=7), today
    if period_label == "Last month":
        return today - timedelta(days=30), today
    if period_label == "Last year":
        return today - timedelta(days=365), today
    if period_label == "Last 3 years":
        return today - timedelta(days=365 * 3), today
    if period_label == "Last 5 years":
        return today - timedelta(days=365 * 5), today
    # Fallback (should not happen)
    return today - timedelta(days=365), today


def load_adj_close_series(ticker: str, start_d: date, end_d: date) -> pd.Series:
    """Load Adjusted Close for a ticker in [start_d, end_d].

    - Uses Stock.load_data; if it does not accept start/end, we load default and trim.
    - Falls back to Close if Adj Close is not present.
    - Returns a pandas Series indexed by Date (datetime index), named as the ticker.
    """
    s = Stock(ticker)
    # Try to load with explicit dates; if class doesn't support it, load all and trim here.
    try:
        s.load_data(start=str(start_d), end=str(end_d))
    except TypeError:
        s.load_data()
        s.data = s.data.loc[str(start_d):str(end_d)]

    df = s.data.copy()

    # Prefer Adjusted Close; if missing, fallback to Close; otherwise fallback to first numeric column.
    col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
    if col is None:
        # Try best-effort fallback
        if len(df.columns) > 0:
            col = df.columns[0]
        else:
            return pd.Series(dtype=float, name=ticker)

    series = df[col].dropna()
    series.name = ticker
    return series


def merge_on_common_dates(series_dict: dict[str, pd.Series]) -> pd.DataFrame:
    """Inner-join multiple Series on their common dates.

    This ensures a fair comparison starting at the same first mutual trading day.
    """
    if not series_dict:
        return pd.DataFrame()
    merged = pd.concat(series_dict.values(), axis=1, join="inner").sort_index()
    return merged


def plot_line(series: pd.Series, title: str, y_label: str) -> None:
    """Plot a single line series with Plotly."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=series.values, mode='lines', name=series.name))
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=y_label,
        title=title,
        template="plotly_white",
        legend_title_text="Ticker",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_overlay(df: pd.DataFrame, title: str, y_label: str) -> None:
    """Plot multiple columns of a DataFrame as overlayed lines with Plotly."""
    fig = go.Figure()
    for col in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], mode='lines', name=col))
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=y_label,
        title=title,
        template="plotly_white",
        legend_title_text="Ticker",
    )
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------
# Mode selection
# --------------------------------
mode = st.radio("Mode", ["View", "Compare"], horizontal=True)
TICKERS = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "NFLX"]

# --------------------------------
# VIEW MODE (single stock, per-year plot; rebased inside split_by_year)
# --------------------------------
if mode == "View":
    ticker = st.selectbox("Select ticker", TICKERS, index=TICKERS.index("AAPL") if "AAPL" in TICKERS else 0)

    stock = Stock(ticker)
    stock.load_data()  # default behavior from your class (e.g., ~last 5y)

    split = stock.split_by_year(column="Close")  # this function already rebases each year to start at 100
    years = sorted(split.keys())

    if not years:
        st.warning("No data available for the selected ticker.")
    else:
        year = st.selectbox("Select year", years)
        series = split[year]
        plot_line(series, title=f"{ticker} — {year} (rebased at start=100)", y_label="Index (start=100)")

# --------------------------------
# COMPARE MODE (overlay up to 5 stocks, raw Adjusted Close only, preset periods)
# --------------------------------
else:
    st.subheader("Compare up to 5 stocks over a preset period (Adjusted Close)")

    sel = st.multiselect(
        "Select tickers (max 5)",
        TICKERS,
        default=["AAPL", "MSFT", "AMZN"],
        help="Choose up to 5 tickers to compare.",
    )
    if len(sel) > 5:
        st.warning(f"You selected {len(sel)} tickers. Only the first 5 will be used.")
        sel = sel[:5]

    if not sel:
        st.info("Pick at least one ticker to compare.")
        st.stop()

    # Period presets instead of manual date picking
    period_label = st.selectbox(
        "Period",
        ["Last week", "Last month", "Last year", "Last 3 years", "Last 5 years"],
        index=2,  # default: Last year
        help="Use a simple preset to define the date window.",
        key="period_select",
    )
    start_date, end_date = period_to_dates(period_label)
    st.caption(f"Showing data from **{start_date}** to **{end_date}**.")

    # Load Adjusted Close for each ticker in the chosen period
    series_map: dict[str, pd.Series] = {}
    for t in sel:
        series = load_adj_close_series(t, start_date, end_date)
        if not series.empty:
            series_map[t] = series

    if not series_map:
        st.warning("No data found for the selected inputs.")
        st.stop()

    merged = merge_on_common_dates(series_map)
    merged = merged.loc[str(start_date):str(end_date)]
    if merged.shape[0] < 2:
        st.warning("Not enough overlapping dates between tickers in this period.")
        st.stop()

    # Note to the user if the true common start is later than the intended start
    common_start = merged.index.min().date()
    if common_start > start_date:
        st.caption(f"Aligned to first mutual trading day: **{common_start}** (was {start_date}).")

    # Raw price overlay of Adjusted Close only
    plot_overlay(merged, title=f"Comparison — {period_label} (Adjusted Close)", y_label="Adjusted Close")
