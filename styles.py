# styles.py
CSS = """
<style>
    /* Import terminal monospace font */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');

    /* Global styles — terminal feel */
    html, body, [class*="css"] {
        font-family: 'JetBrains Mono', 'Roboto Mono', 'Courier New', monospace;
        font-size: 13px;
    }

    /* Pure black background */
    .stApp {
        background-color: #000000;
    }

    /* Metric cards — sharp, dense, no shadow */
    div[data-testid="metric-container"] {
        background-color: #111111;
        border: 1px solid #333333;
        border-radius: 2px;
        padding: 8px 12px;
        box-shadow: none;
    }

    div[data-testid="metric-container"] > label {
        color: #FEE123;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    div[data-testid="metric-container"] > div {
        color: #FFFFFF;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Hide delta arrows */
    [data-testid="stMetricDelta"] svg {
        display: none;
    }

    /* Tab styling — angular, orange indicator */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        background-color: #111111;
        border-radius: 0px;
        padding: 0px;
        border-bottom: 1px solid #333333;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 0px;
        color: #999999;
        padding: 8px 16px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-family: 'JetBrains Mono', monospace;
        border-bottom: 2px solid transparent;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1a1a1a;
        color: #FEE123;
        border-bottom: 2px solid #FEE123;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #FEE123;
        background-color: #0a0a0a;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #333333;
    }

    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stSlider label {
        color: #FEE123;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.05em;
    }

    /* Buttons — flat, angular, yellow with black text */
    .stButton > button {
        background-color: #FEE123 !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 2px;
        padding: 6px 16px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.05em;
        transition: background-color 0.2s ease;
    }

    .stButton > button:hover {
        background-color: #154733 !important;
        color: #FEE123 !important;
        transform: none;
        box-shadow: none;
    }

    .stButton > button p,
    .stButton > button span {
        color: #000000 !important;
    }

    .stButton > button:hover p,
    .stButton > button:hover span {
        color: #FEE123 !important;
    }

    /* Data editor / dataframe — sharp edges */
    .stDataFrame {
        border-radius: 0px;
        overflow: hidden;
        border: 1px solid #333333;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background-color: #111111;
        border-radius: 0px;
        border: 1px solid #333333;
        color: #FEE123;
        text-transform: uppercase;
        font-size: 0.7rem;
    }

    /* Headers — orange, uppercase */
    h1, h2, h3, h4, h5, h6 {
        color: #FEE123 !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-family: 'JetBrains Mono', monospace;
    }

    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 0.95rem !important; }
    h4, h5, h6 { font-size: 0.8rem !important; }

    /* Info boxes */
    .stAlert {
        background-color: #111111;
        border: 1px solid #333333;
        border-radius: 0px;
    }

    /* Multiselect tags — black text on yellow background */
    [data-baseweb="tag"] {
        color: #000000 !important;
    }
    [data-baseweb="tag"] span,
    [data-baseweb="tag"] div {
        color: #000000 !important;
    }

    /* KPI card class */
    .kpi-card {
        background-color: #111111;
        border: 1px solid #333333;
        border-radius: 0px;
        padding: 10px 14px;
        text-align: center;
    }

    .kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #FFFFFF;
        font-family: 'JetBrains Mono', monospace;
    }

    .kpi-label {
        font-size: 0.7rem;
        color: #FEE123;
        margin-top: 2px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Horizontal rules */
    hr { border-color: #333333; }

    /* Input overrides */
    .stSelectbox > div > div,
    .stMultiSelect > div > div,
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background-color: #111111 !important;
        border: 1px solid #333333 !important;
        border-radius: 2px !important;
        color: #E0E0E0 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #000000; }
    ::-webkit-scrollbar-thumb { background: #333333; border-radius: 0px; }

    /* Download buttons */
    .stDownloadButton > button {
        background-color: #1a1a1a;
        color: #FEE123;
        border: 1px solid #FEE123;
        border-radius: 2px;
        font-family: 'JetBrains Mono', monospace;
        text-transform: uppercase;
        font-size: 0.7rem;
    }

    .stDownloadButton > button:hover {
        background-color: #FEE123;
        color: #000000;
    }

    /* Text */
    p, li, span { color: #E0E0E0; }

    /* Table font */
    .stDataFrame table {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
    }
</style>
"""
