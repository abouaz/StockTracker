import os
import pandas as pd
import yfinance as yf

class Stock:
    """
    A class to represent a stock and handle its historical data extraction and processing.

    Parameters
    ----------
    ticker : str
        The stock ticker symbol (e.g., 'AAPL', 'MSFT').
    cache_dir : str
        Directory path to cache downloaded stock data in parquet format.
    """

    def __init__(self, ticker, cache_dir="data/ohlcv"):
        self.ticker = ticker
        self.cache_dir = cache_dir
        self.data = None

    def load_data(self, years=5, start=None, end=None):
        """
        Load historical stock data from cache or download from Yahoo Finance.

        Parameters
        ----------
        years : int, optional
            Number of years of data to download if start and end are not specified (default is 5).
        start : str or pandas.Timestamp, optional
            Start date for data download in 'YYYY-MM-DD' format or Timestamp. If None, calculated from years.
        end : str or pandas.Timestamp, optional
            End date for data download in 'YYYY-MM-DD' format or Timestamp. If None, defaults to today.
        """
        os.makedirs(self.cache_dir, exist_ok=True)
        if start is None and end is None:
            end = pd.Timestamp.today()
            start_year = (end - pd.DateOffset(years=years)).year # how many years ago
            start = pd.Timestamp(year=start_year, month=1, day=1) # 1st of Jan
        cache_path = os.path.join(self.cache_dir, f"{self.ticker}.parquet")
        if os.path.exists(cache_path):
            self.data = pd.read_parquet(cache_path)
        else:
            df = yf.download(self.ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
            df.rename(columns={'Adj Close': 'adj_close'}, inplace=True)
            df.to_parquet(cache_path)
            self.data = df

    def rebase(self, column="Close", base=100.0):
        """
        Rebase the specified column of stock data to a base value.

        Parameters
        ----------
        column : str, optional
            The column name to rebase (default is 'adj_close').
        base : float, optional
            The base value to rebase to (default is 100.0).

        Returns
        -------
        pandas.Series
            The rebased series with the same index as the original data.
        """
        if self.data is None or column not in self.data.columns:
            raise ValueError(f"Data not loaded or column '{column}' not found.")
        series = self.data[column].dropna()
        return series / series.iloc[0] * base # movement from the first value (1st of jan)

    def split_by_year(self, column="Close"):
        """
        Split the rebased stock data by year.

        Parameters
        ----------
        column : str, optional
            The column name to use for splitting (default is 'adj_close').

        Returns
        -------
        dict of int to pandas.Series
            Dictionary mapping year to the rebased data series for that year.
        """
        if self.data is None or column not in self.data.columns:
            raise ValueError(f"Data not loaded or column '{column}' not found.")
        rebased = self.rebase(column=column)
        rebased.index = pd.to_datetime(rebased.index) # ensure index is datetime
        grouped = rebased.groupby(rebased.index.year) # group by year
        return {year: group for year, group in grouped} # that will look like {2020: Series, 2021: Series, ...}

    def normalize(self, column):
        """
        Normalize the specified column of stock data to a 0–100 range.

        Parameters
        ----------
        column : str
            The column name to normalize.

        Returns
        -------
        pandas.Series
            The normalized series with the same index as the original data.
        """
        if self.data is None or column not in self.data.columns:
            raise ValueError(f"Data not loaded or column '{column}' not found.")
        series = self.data[column].dropna()
        return (series - series.min()) / (series.max() - series.min())*100 # scale to 0-100

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        for ticker in ["AAPL", "MSFT", "AMZN"]:
            stock = Stock(ticker, tmpdir)
            stock.load_data()
            print(f"{ticker} data summary:")
            print(stock.data.head())
            print(f"Rebased {ticker} close:")
            print(stock.rebase().head())
            print(f"{ticker} data split by year keys:")
            print(list(stock.split_by_year().keys()))
            print("-" * 40)
