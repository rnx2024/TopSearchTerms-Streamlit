import streamlit as st
from google.cloud import bigquery
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

# Set page config
st.set_page_config(page_title="Google Top Search Terms", layout="wide")

# Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "googlecloud.json"  

# Initialize BigQuery client
client = bigquery.Client(project="chatbot-446403")

# Default date range
end_date = datetime.now().date()
start_date = datetime(2025, 1, 1).date()


# Build query
def get_query(country_name, start_date, end_date):
    
    return f"""
    WITH daily_terms AS (
        SELECT 
            term, 
            DATE(week) AS date, 
            score, 
            rank,
            ROW_NUMBER() OVER (PARTITION BY DATE(week), country_name ORDER BY score DESC) AS daily_rank
        FROM `bigquery-public-data.google_trends.international_top_terms`
        WHERE DATE(week) BETWEEN '{start_date}' AND '{end_date}'
        AND country_name = '{country_name}'
        
    )
    SELECT term, date, score, rank
    FROM daily_terms
    WHERE daily_rank <= 5
    ORDER BY date, rank
    """

# Get valid countries
@st.cache_data
def get_countries():
    query = """
    SELECT DISTINCT country_name
    FROM `bigquery-public-data.google_trends.international_top_terms`
    ORDER BY country_name
    """
    query_job = client.query(query)
    df = query_job.to_dataframe()
    return df['country_name'].dropna().unique().tolist()

# Default fallback
def get_default_country(available_countries, preferred="United States"):
    return preferred if preferred in available_countries else available_countries[0]

# Run query
def execute_query(country_name, start_date, end_date):
    query = get_query(country_name, start_date, end_date)
    job_config = bigquery.QueryJobConfig(use_query_cache=False)
    query_job = client.query(query, job_config=job_config)
    return query_job.to_dataframe()

# UI starts
st.title("🔍 Google Top Search Terms")



# Sidebar filters
with st.sidebar:
    st.header("Filters")
    countries = get_countries()
    default_country = get_default_country(countries)
    selected_country = st.selectbox("Country", countries, index=countries.index(default_country))
    
   
    # Fixed start and end range for calendar
    calendar_min_date = datetime(2025, 1, 1).date()
    calendar_max_date = datetime.now().date()

# Date input with constraints
    date_range = st.date_input(
    "Date Range",
    value=(calendar_min_date, calendar_max_date),
    min_value=calendar_min_date,
    max_value=calendar_max_date

   
) 
with st.sidebar:
    
    st.markdown("📌 **Created by Rhanny Urbis**")

st.markdown(f"Showing top 5 search terms from **{date_range[0]}** to **{date_range[1]}**")

# Query results
df = execute_query(selected_country, date_range[0], date_range[1])

# Output
if not df.empty:
    st.subheader(f"📊 Top 5 Search Terms in {selected_country}")
    
    # Bar chart only
    fig_bar = px.bar(df, x='date', y='score', color='term', title='Top Search Terms by Day')
    st.plotly_chart(fig_bar, use_container_width=True)

    # Raw data
    with st.expander("📋 See raw data"):
        st.dataframe(df)
else:
    st.warning("No data found for the selected filters.")
