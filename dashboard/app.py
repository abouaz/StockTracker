import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from models.stock import Stock

import streamlit as st

st.title("Stock Price Viewer")

ticker = st.selectbox("Select ticker", ["AAPL", "MSFT", "AMZN"])
stock = Stock(ticker)
stock.load_data()
rebased = stock.rebase(column="Close")
split = stock.split_by_year(column="Close")
years = sorted(split.keys())
year = st.selectbox("Select year", years)

st.line_chart(split[year])
