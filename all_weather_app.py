import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_datareader.data as web
from datetime import date
import os

# -----------------------------
# APP CONFIG
# -----------------------------
st.set_page_config(
    page_title="All-Weather Portfolio (Azure)",
    layout="wide"
)

st.write("App loaded successfully.")  # Azure health check helper

# -----------------------------
# SESSION STATE
# -----------------------------
if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

# -----------------------------
# FRED API KEY
# -----------------------------
FRED_API_KEY = os.environ.get("FRED_API_KEY")
if FRED_API_KEY:
    os.environ["FRED_API_KEY"] = FRED_API_KEY

# ------------------------------
# Calculate macro cycle probabilities
# ------------------------------
def calculate_cycle_probabilities(cpi, spread, returns):
    """
    Simple rule-based macro regime probabilities
    """
    probs = pd.DataFrame(index=cpi.index)

    # Normalize inputs
    cpi_z = (cpi - cpi.mean()) / cpi.std()
    spread_z = (spread - spread.mean()) / spread.std()
    ret_z = (returns - returns.mean()) / returns.std()

    probs["Inflation"] = (0.6 * cpi_z + 0.2 * -spread_z + 0.2 * ret_z).clip(0, 1)
    probs["Recession"] = (0.6 * -spread_z + 0.3 * -ret_z + 0.1 * cpi_z).clip(0, 1)
    probs["Growth"] = (0.5 * ret_z + 0.3 * spread_z + 0.2 * -cpi_z).clip(0, 1)
    probs["Slowdown"] = 1 - probs.max(axis=1)

    # Normalize to sum to 1
    probs = probs.div(probs.sum(axis=1), axis=0)

    return probs



# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.header("Date Range")

    start_date = st.date_input(
        "Start Date",
        value=pd.to_datetime("2005-01-01")
    )

    end_date = st.date_input(
        "End Date",
        value=date.today()
    )

    st.markdown("---")
    st.header("Main Portfolio Weights (%)")

    main_tickers = ["VTI", "TLT", "IEF", "GLD", "DBC"]
    main_weights = {}

    for t in main_tickers:
        main_weights[t] = st.number_input(
            t,
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=1.0
        )

    st.markdown("---")
    st.header("Second Portfolio (Optional)")

    second_tickers = st.text_input(
        "Tickers (comma-separated, max 10)",
        value=""
    )

    second_weights_input = st.text_input(
        "Weights (%) (comma-separated, same order)",
        value=""
    )

    st.markdown("---")

    if st.button("Run Analysis"):
        st.session_state.run_analysis = True

st.markdown("---")
st.subheader("Model Info")
st.caption("Probabilities derived from CPI momentum, yield curve, and portfolio returns.")


# -----------------------------
# MAIN BODY
# -----------------------------
if not st.session_state.run_analysis:
    st.info("Set parameters in the sidebar and click **Run Analysis**.")
    st.stop()

# -----------------------------
# VALIDATION
# -----------------------------
if sum(main_weights.values()) != 100:
    st.error("Main portfolio weights must sum to 100%.")
    st.stop()

# -----------------------------
# DATA FETCH — MAIN PORTFOLIO
# -----------------------------
@st.cache_data(show_spinner=False)
def load_prices(tickers, start, end):
    data = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False
    )
    return data["Close"]

prices_main = load_prices(
    main_tickers,
    start_date,
    end_date
)

returns_main = prices_main.pct_change().dropna()

weights_main_series = pd.Series(main_weights) / 100
main_portfolio_returns = returns_main.dot(weights_main_series)

main_performance = (1 + main_portfolio_returns).cumprod() - 1
main_performance.name = "Main Portfolio"

# -----------------------------
# DATA FETCH — SECOND PORTFOLIO
# -----------------------------
second_performance = None

if second_tickers and second_weights_input:
    tickers_2 = [t.strip().upper() for t in second_tickers.split(",")]
    weights_2 = [float(w) for w in second_weights_input.split(",")]

    if len(tickers_2) <= 10 and sum(weights_2) == 100:
        prices_2 = load_prices(
            tickers_2,
            start_date,
            end_date
        )

        returns_2 = prices_2.pct_change().dropna()
        weights_2_series = pd.Series(weights_2, index=tickers_2) / 100

        second_returns = returns_2.dot(weights_2_series)
        second_performance = (1 + second_returns).cumprod() - 1
        second_performance.name = "Second Portfolio"

# -----------------------------
# PORTFOLIO PERFORMANCE CHART
# -----------------------------
st.subheader("Portfolio Performance (Daily % Change, Starting at 0)")

plot_df = pd.concat(
    [main_performance, second_performance],
    axis=1
)

st.line_chart(plot_df)

# -----------------------------
# CPI (FRED)
# -----------------------------
if FRED_API_KEY:
    st.subheader("Consumer Price Index (CPI)")

    cpi = web.DataReader(
        "CPIAUCSL",
        "fred",
        start_date,
        end_date
    )

    st.line_chart(cpi)

# -----------------------------
# 2Y–10Y TREASURY SPREAD (FRED)
# -----------------------------
if FRED_API_KEY:
    st.subheader("2Y–10Y Treasury Yield Spread")

    spread = web.DataReader(
        "T10Y2Y",
        "fred",
        start_date,
        end_date
    )

    st.line_chart(spread)

# ----- CYCLE PROBABILITY MODEL -----
try:
    cpi = macro_data["CPIAUCSL"].pct_change(12).dropna()
    spread = macro_data["T10Y2Y"].dropna()

    common = cpi.index.intersection(spread.index)
    cpi = cpi.loc[common]
    spread = spread.loc[common]

    probs = calculate_cycle_probabilities(
        cpi,
        spread,
        portfolio_return.reindex(common).fillna(0)
    )

    st.subheader("Macro Regime Probabilities")

    st.area_chart(probs)

    st.write("### Current Regime Snapshot")
    st.table(probs.tail(1).T)

except Exception as e:
    st.warning(f"Cycle model unavailable: {e}")
