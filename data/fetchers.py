# data/fetchers.py
import streamlit as st
import pandas as pd
import yfinance as yf
from config import IEMG_WEIGHTS, SPY_WEIGHTS


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_iemg_weights():
    """Fetch IEMG constituent weights from the iShares holdings CSV endpoint.

    Cached for 24 hours (ttl=86400).  Falls back to the hardcoded IEMG_WEIGHTS
    dict if the request fails or the response cannot be parsed.

    Returns
    -------
    dict[str, float]
        Mapping of ticker -> weight (%) for all IEMG constituents.
    """
    import urllib.request
    import io as _io

    url = (
        "https://www.ishares.com/us/products/244050/"
        "ishares-core-msci-emerging-markets-etf/"
        "1467271812596.ajax?tab=holdings&fileType=csv"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.ishares.com/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        lines = raw.splitlines()
        # Locate the header row (the one containing "Ticker")
        header_idx = next(
            (i for i, l in enumerate(lines) if "Ticker" in l),
            None
        )
        if header_idx is None:
            return IEMG_WEIGHTS  # fallback

        df = pd.read_csv(
            _io.StringIO("\n".join(lines[header_idx:])),
            on_bad_lines="skip"
        )
        df.columns = df.columns.str.strip()
        weight_col = next((c for c in df.columns if "Weight" in c), None)
        if "Ticker" not in df.columns or weight_col is None:
            return IEMG_WEIGHTS  # fallback

        weights = dict(zip(
            df["Ticker"].astype(str).str.strip(),
            pd.to_numeric(df[weight_col], errors="coerce").fillna(0.0)
        ))
        # Remove cash / non-equity rows that have blank tickers
        weights = {k: v for k, v in weights.items() if k and k != "nan"}
        return weights if weights else IEMG_WEIGHTS

    except Exception:
        return IEMG_WEIGHTS  # fallback to hardcoded values


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_spy_weights():
    """Fetch S&P 500 constituent weights via IVV's iShares holdings CSV endpoint.

    IVV (iShares Core S&P 500 ETF) tracks the same index as SPY and uses the
    same iShares CSV format, making it a convenient live source for SPY weights.
    Cached for 24 hours.  Falls back to SPY_WEIGHTS if the request fails.

    Returns
    -------
    dict[str, float]
        Mapping of ticker -> weight (%) for S&P 500 constituents.
    """
    import urllib.request
    import io as _io

    url = (
        "https://www.ishares.com/us/products/239726/"
        "ishares-core-sp-500-etf/"
        "1467271812596.ajax?tab=holdings&fileType=csv"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.ishares.com/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        lines = raw.splitlines()
        header_idx = next(
            (i for i, l in enumerate(lines) if "Ticker" in l),
            None
        )
        if header_idx is None:
            return SPY_WEIGHTS  # fallback

        df = pd.read_csv(
            _io.StringIO("\n".join(lines[header_idx:])),
            on_bad_lines="skip"
        )
        df.columns = df.columns.str.strip()
        weight_col = next((c for c in df.columns if "Weight" in c), None)
        if "Ticker" not in df.columns or weight_col is None:
            return SPY_WEIGHTS  # fallback

        weights = dict(zip(
            df["Ticker"].astype(str).str.strip(),
            pd.to_numeric(df[weight_col], errors="coerce").fillna(0.0)
        ))
        weights = {k: v for k, v in weights.items() if k and k != "nan"}
        return weights if weights else SPY_WEIGHTS

    except Exception:
        return SPY_WEIGHTS  # fallback to hardcoded values


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_risk_free_rate():
    """Fetch the current 13-week T-bill rate (^IRX) as a proxy for the risk-free rate."""
    try:
        data = yf.download('^IRX', period='5d', progress=False)
        if not data.empty:
            # ^IRX returns the rate as a percentage (e.g. 4.2 means 4.2%)
            latest_rate = float(data['Close'].dropna().iloc[-1])
            return round(latest_rate, 2)
    except Exception:
        pass
    return 5.0  # Fallback default


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_data(symbols, start_date, end_date):
    """Fetch historical price data from Yahoo Finance."""
    try:
        if isinstance(symbols, str):
            symbols = [symbols]

        # Filter out empty symbols
        symbols = [s for s in symbols if s and isinstance(s, str) and s.strip()]

        if not symbols:
            return pd.DataFrame()

        data = yf.download(
            symbols,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=True,
            threads=True
        )

        if data.empty:
            return pd.DataFrame()

        # Handle single vs multiple symbols
        if len(symbols) == 1:
            if 'Close' in data.columns:
                result = pd.DataFrame({symbols[0]: data['Close']})
            else:
                result = pd.DataFrame({symbols[0]: data.iloc[:, 0]})
        else:
            if 'Close' in data.columns:
                result = data['Close']
            elif isinstance(data.columns, pd.MultiIndex):
                result = data.xs('Close', axis=1, level=0) if 'Close' in data.columns.get_level_values(0) else data
            else:
                result = data

        # Flatten MultiIndex columns if present
        if isinstance(result.columns, pd.MultiIndex):
            result.columns = result.columns.get_level_values(-1)

        return result

    except Exception as e:
        st.error(f"Error fetching price data: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sector_info(symbols) -> dict:
    """Fetch sector classification for each symbol using yfinance.

    Returns
    -------
    dict[str, str]
        Mapping of ticker -> GICS sector name.
        CASH is mapped to 'Cash'. Unknown tickers default to 'Unknown'.
    """
    _SECTOR_NORMALIZE = {
        'Technology': 'Technology',
        'Financial Services': 'Financials',
        'Healthcare': 'Health Care',
        'Consumer Cyclical': 'Consumer Discretionary',
        'Communication Services': 'Communication Services',
        'Industrials': 'Industrials',
        'Consumer Defensive': 'Consumer Staples',
        'Energy': 'Energy',
        'Basic Materials': 'Materials',
        'Real Estate': 'Real Estate',
        'Utilities': 'Utilities',
    }
    sector_map = {}
    for symbol in symbols:
        if not symbol or not isinstance(symbol, str):
            continue
        if symbol.upper() == 'CASH':
            sector_map[symbol] = 'Cash'
            continue
        try:
            info = yf.Ticker(symbol).info
            raw = info.get('sector', '') or ''
            sector_map[symbol] = _SECTOR_NORMALIZE.get(raw, raw or 'Unknown')
        except Exception:
            sector_map[symbol] = 'Unknown'
    return sector_map


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_volume_data(symbols, period: str = '3mo') -> pd.DataFrame:
    """Fetch daily trading volume for the given symbols.

    Parameters
    ----------
    symbols : list[str]
        Ticker list. CASH is excluded (no exchange volume).
    period : str
        yfinance period string, e.g. '3mo'.

    Returns
    -------
    pd.DataFrame
        DataFrame with tickers as columns and dates as index,
        containing daily share volume.
    """
    tradeable = [s for s in symbols if s and isinstance(s, str) and s.upper() != 'CASH']
    if not tradeable:
        return pd.DataFrame()
    try:
        data = yf.download(
            tradeable, period=period,
            progress=False, auto_adjust=True, threads=True
        )
        if data.empty:
            return pd.DataFrame()
        if len(tradeable) == 1:
            if 'Volume' in data.columns:
                return pd.DataFrame({tradeable[0]: data['Volume']})
            return pd.DataFrame()
        if isinstance(data.columns, pd.MultiIndex):
            lvl0 = data.columns.get_level_values(0)
            if 'Volume' in lvl0:
                vol = data['Volume']
                if isinstance(vol.columns, pd.MultiIndex):
                    vol.columns = vol.columns.get_level_values(-1)
                return vol
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fx_rates(currencies, start_date, end_date):
    """Fetch FX rates for currency conversion (vs USD)."""
    fx_tickers = {
        'EUR': 'EURUSD=X',
        'GBP': 'GBPUSD=X',
        'JPY': 'JPYUSD=X',
        'CNY': 'CNYUSD=X',
        'CHF': 'CHFUSD=X',
        'AUD': 'AUDUSD=X',
        'CAD': 'CADUSD=X',
    }

    rates = {}
    for curr in currencies:
        if curr in fx_tickers:
            try:
                data = yf.download(fx_tickers[curr], start=start_date, end=end_date, progress=False)
                rates[curr] = data['Close']
            except:
                import pandas as pd
                rates[curr] = pd.Series(1.0, index=pd.date_range(start_date, end_date))

    return pd.DataFrame(rates)
