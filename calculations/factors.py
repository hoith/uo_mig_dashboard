# calculations/factors.py
"""
Fama-French factor exposure analysis.

Downloads daily FF3/FF5 factors from Ken French's data library and
runs OLS regression of portfolio excess returns on those factors.
"""

import io
import zipfile
import urllib.request

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats


# ---------------------------------------------------------------------------
# Data download
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_ff_factors(start_date_str: str, end_date_str: str) -> pd.DataFrame:
    """Download Fama-French 5-factor daily data from Ken French's website.

    Parameters
    ----------
    start_date_str, end_date_str : str
        ISO date strings ('YYYY-MM-DD') used to filter the downloaded data.

    Returns
    -------
    pd.DataFrame
        DatetimeIndex, columns: Mkt-RF, SMB, HML, RMW, CMA, RF
        All values are in decimal form (i.e. 0.01 = 1 %).
        Returns an empty DataFrame if the download fails.
    """
    url = (
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
        "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_bytes = resp.read()

        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            fname = z.namelist()[0]
            with z.open(fname) as f:
                content = f.read().decode("utf-8", errors="replace")

        lines = content.splitlines()

        # Locate the header row that contains 'Mkt-RF'
        header_idx = next(
            (i for i, line in enumerate(lines) if "Mkt-RF" in line), None
        )
        if header_idx is None:
            return pd.DataFrame()

        # The daily section ends at the first blank line after the header
        end_idx = None
        for i in range(header_idx + 2, len(lines)):
            if lines[i].strip() == "":
                end_idx = i
                break

        data_lines = lines[header_idx:end_idx] if end_idx else lines[header_idx:]
        df = pd.read_csv(io.StringIO("\n".join(data_lines)), skipinitialspace=True)
        df.columns = df.columns.str.strip()

        # First column is YYYYMMDD date
        date_col = df.columns[0]
        df.index = pd.to_datetime(
            df[date_col].astype(str).str.strip(), format="%Y%m%d", errors="coerce"
        )
        df = df.drop(columns=[date_col]).dropna(how="all")

        # Convert from percentage to decimal
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0
        df = df.dropna()

        # Filter to requested window
        start = pd.to_datetime(start_date_str)
        end = pd.to_datetime(end_date_str)
        return df.loc[(df.index >= start) & (df.index <= end)]

    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

def run_factor_regression(
    portfolio_returns: pd.Series,
    factors_df: pd.DataFrame,
    model: str = "FF5",
) -> dict:
    """OLS regression of portfolio excess returns on Fama-French factors.

    Parameters
    ----------
    portfolio_returns : pd.Series
        Daily portfolio returns (TWR-adjusted).
    factors_df : pd.DataFrame
        Output of ``fetch_ff_factors`` — must contain 'RF' column plus factor columns.
    model : {'FF3', 'FF5'}
        Which factor model to use.

    Returns
    -------
    dict with keys:
        alpha             – annualised intercept
        alpha_daily       – daily intercept
        alpha_tstat       – t-statistic for alpha
        alpha_pvalue      – p-value for alpha
        betas             – {factor: loading}
        t_stats           – {factor: t-stat}
        p_values          – {factor: p-value}
        se                – {factor: std error of loading}
        r_squared         – float
        adj_r_squared     – float
        factor_contributions – {factor: annualised contribution}
        factor_annual_means  – {factor: annualised mean return}
        n_obs             – number of observations
        aligned_returns   – aligned DataFrame used in regression (for charts)
    Returns empty dict if data are insufficient.
    """
    if factors_df.empty or portfolio_returns.empty:
        return {}

    if model == "FF3":
        factor_cols = ["Mkt-RF", "SMB", "HML"]
    else:
        factor_cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]

    factor_cols = [c for c in factor_cols if c in factors_df.columns]
    if not factor_cols:
        return {}

    rf = factors_df["RF"] if "RF" in factors_df.columns else pd.Series(
        0.0, index=factors_df.index
    )

    aligned = pd.concat(
        [portfolio_returns, factors_df[factor_cols], rf], axis=1, join="inner"
    )
    aligned.columns = ["portfolio"] + factor_cols + ["RF"]
    aligned = aligned.dropna()

    n = len(aligned)
    if n < 30:
        return {}

    k = len(factor_cols) + 1  # +1 for alpha/intercept

    y = (aligned["portfolio"] - aligned["RF"]).values
    X_factors = aligned[factor_cols].values
    X = np.column_stack([np.ones(n), X_factors])

    # OLS
    betas, _, _, _ = np.linalg.lstsq(X, y, rcond=None)

    # Residual variance and standard errors
    y_hat = X @ betas
    residuals = y - y_hat
    s2 = np.dot(residuals, residuals) / max(n - k, 1)
    XtX_inv = np.linalg.pinv(X.T @ X)
    se_vec = np.sqrt(np.maximum(s2 * np.diag(XtX_inv), 0))

    t_vec = betas / np.where(se_vec > 0, se_vec, np.nan)
    p_vec = 2.0 * (1.0 - stats.t.cdf(np.abs(t_vec), df=max(n - k, 1)))

    ss_res = float(np.dot(residuals, residuals))
    ss_tot = float(np.dot(y - y.mean(), y - y.mean()))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - k, 1)

    factor_annual_means = (aligned[factor_cols].mean() * 252).to_dict()
    factor_contributions = {
        factor_cols[i]: float(betas[i + 1]) * factor_annual_means[factor_cols[i]]
        for i in range(len(factor_cols))
    }

    return {
        "alpha": float(betas[0]) * 252,
        "alpha_daily": float(betas[0]),
        "alpha_tstat": float(t_vec[0]),
        "alpha_pvalue": float(p_vec[0]),
        "betas": {factor_cols[i]: float(betas[i + 1]) for i in range(len(factor_cols))},
        "t_stats": {factor_cols[i]: float(t_vec[i + 1]) for i in range(len(factor_cols))},
        "p_values": {factor_cols[i]: float(p_vec[i + 1]) for i in range(len(factor_cols))},
        "se": {factor_cols[i]: float(se_vec[i + 1]) for i in range(len(factor_cols))},
        "r_squared": float(r2),
        "adj_r_squared": float(adj_r2),
        "factor_contributions": factor_contributions,
        "factor_annual_means": factor_annual_means,
        "n_obs": n,
        "aligned_returns": aligned,
    }
