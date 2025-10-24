import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from typing import List

# ---------------- Page ----------------
st.set_page_config(page_title="Google Top Search Terms", layout="wide")

# ---------------- Auth / Client ----------------
# Expect st.secrets["google_service_account"] to contain a full SA JSON mapping
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google_service_account"]
)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)


# location MUST be set on the client (or passed to client.query), not in QueryJobConfig
client = bigquery.Client(
    credentials=credentials,
    project=credentials.project_id,
    location="US",  # <-- moved here
)

# ---------------- SQL (weekly, parametrized) ----------------
TOP_TERMS_SQL = """
WITH weekly_terms AS (
  SELECT
    term,
    DATE(week) AS week_date,
    score,
    rank,
    ROW_NUMBER() OVER (
      PARTITION BY country_name, DATE(week)
      ORDER BY score DESC
    ) AS rnk
  FROM `bigquery-public-data.google_trends.international_top_terms`
  WHERE DATE(week) BETWEEN @start_date AND @end_date
    AND country_name = @country
)
SELECT term, week_date AS date, score, rank
FROM weekly_terms
WHERE rnk <= 5
ORDER BY date, rank
"""

# ---------------- Data helpers ----------------
@st.cache_data(ttl=3600)
def get_countries() -> List[str]:
    q = """
      SELECT DISTINCT country_name
      FROM `bigquery-public-data.google_trends.international_top_terms`
      WHERE country_name IS NOT NULL
      ORDER BY country_name
    """

    # removed location="US" here
    job_cfg = bigquery.QueryJobConfig(
        use_query_cache=True,
        maximum_bytes_billed=1_000_000_000,  # 1 GB safety cap
    )

    df = client.query(q, job_config=job_cfg).to_dataframe()
    countries = df["country_name"].dropna().tolist()
    return countries


@st.cache_data(ttl=600)
def execute_query(country_name: str, start: date, end: date) -> pd.DataFrame:
    # removed location="US" here too
    job_cfg = bigquery.QueryJobConfig(
        use_query_cache=True,
        maximum_bytes_billed=1_000_000_000,  # 1 GB guard
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start),
            bigquery.ScalarQueryParameter("end_date", "DATE", end),
            bigquery.ScalarQueryParameter("country", "STRING", country_name),
        ],
    )

    return client.query(TOP_TERMS_SQL, job_config=job_cfg).to_dataframe()


def pick_default_country(countries: List[str]) -> str:
    for pref in ("Philippines", "United States"):
        if pref in countries:
            return pref
    return countries[0]


# ---------------- UI ----------------
st.title("Google Top Search Terms")

with st.sidebar:
    st.header("Filters")
    countries = get_countries()
    if not countries:
        st.warning("No countries available from the dataset.")
        st.stop()

    default_country = pick_default_country(countries)
    try:
        default_idx = countries.index(default_country)
    except ValueError:
        default_idx = 0

    selected_country = st.selectbox("Country", countries, index=default_idx)

    calendar_min_date = date(2025, 1, 1)   # adjust if you want earlier data
    calendar_max_date = min(datetime.now().date(), date.today())

    raw_range = st.date_input(
        "Date Range",
        value=(calendar_min_date, calendar_max_date),
        min_value=calendar_min_date,
        max_value=calendar_max_date,
    )

    st.caption("Created by Rhanny Urbis")

# Normalize date range (support single date selection)
if isinstance(raw_range, tuple) and len(raw_range) == 2:
    start_date, end_date = raw_range
else:
    start_date = end_date = raw_range

# Ensure start <= end
if start_date > end_date:
    start_date, end_date = end_date, start_date

st.markdown(f"Showing top 5 weekly search terms from **{start_date}** to **{end_date}**")

# ---------------- Query + Output ----------------
df = execute_query(selected_country, start_date, end_date)

if not df.empty:
    st.subheader(f"Top 5 Weekly Search Terms in {selected_country}")
    fig_bar = px.bar(
        df,
        x="date",
        y="score",
        color="term",
        title=f"Top 5 Weekly Search Terms — {selected_country}",
        barmode="group",
    )
    fig_bar.update_layout(
        xaxis_title="Week",
        yaxis_title="Score",
        legend_title_text="Term",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    with st.expander("See raw data"):
        st.dataframe(df, use_container_width=True)
else:
    st.warning("No data found for the selected filters.")
