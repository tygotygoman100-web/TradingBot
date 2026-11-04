import yfinance as yf
import pandas as pd

class TradingBot:
    def __init__(self, ticker="BTC-USD", fast_window=3, slow_window=10):
        self.ticker = ticker
        self.fast_window = fast_window
        self.slow_window = slow_window

    def fetch_data(self):
        df = yf.download(self.ticker, period="1d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    def calculate_indicators(self, df):
        df['Fast_MA'] = df['Close'].rolling(window=self.fast_window).mean()
        df['Slow_MA'] = df['Close'].rolling(window=self.slow_window).mean()
        return df