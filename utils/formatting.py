# utils/formatting.py

def fmt_currency(value, decimals=0):
    """Format a number as currency string."""
    if value is None:
        return "N/A"
    try:
        if decimals == 0:
            return f"${value:,.0f}"
        return f"${value:,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"

def fmt_pct(value, decimals=2):
    """Format a decimal as percentage string."""
    if value is None:
        return "N/A"
    try:
        return f"{value:.{decimals}%}"
    except (TypeError, ValueError):
        return "N/A"

def fmt_number(value, decimals=2):
    """Format a plain number."""
    if value is None:
        return "N/A"
    try:
        return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"

def fmt_ratio(value, decimals=2):
    """Format a ratio/multiplier."""
    if value is None:
        return "N/A"
    try:
        return f"{value:.{decimals}f}x"
    except (TypeError, ValueError):
        return "N/A"
