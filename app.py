import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pymongo

def wide_space_default():
    st.set_page_config(layout="wide")

wide_space_default()

# MongoDB connection
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(st.secrets['MONGO_DB_URL'])
client = init_connection()
db = client["AI_Chat"]
collection = db["consumption_log"]
page_account_collection = db["page_account"]

# Function to fetch data from MongoDB
@st.cache_data
def get_data(start_date, end_date):
    db = client["AI_Chat"]
    collection = db["consumption_log"]

    query = {
        "time": {
            "$gte": start_date,
            "$lte": end_date
        }
    }
    
    data = list(collection.find(query))
    return pd.DataFrame(data)

# Streamlit app
st.title("ainbox LLMOps Dashboard")

# Date range selection
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", datetime.now() - timedelta(days=7))
with col2:
    end_date = st.date_input("End Date", datetime.now())

# Convert dates to datetime
start_datetime = datetime.combine(start_date, datetime.min.time())
end_datetime = datetime.combine(end_date, datetime.max.time())

# Fetch data button
if st.button("Fetch Data"):
    df = get_data(start_datetime, end_datetime)

    # Map page IDs to page names
    page_ids = df["page_id"].unique()
    page_names = {
        page_id: page_account_collection.find_one({"page_id": page_id})["page_name"]
        for page_id in page_ids
    }

    # Update DataFrame with page names
    df["page_name"] = df["page_id"].map(page_names)

    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Summary", "Model Performance", "Page Usage", "Model Distribution", "Usage Over Time"])

    with tab1:
        # Summary Statistics
        st.subheader("Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Cost", f"${df['cost'].sum():.6f}")
        col2.metric("Total Prompts", df["total_prompt"].sum())
        col3.metric("Unique Models", df["model"].nunique())
        col4.metric("Unique Page Name", df["page_name"].nunique())

    with tab2:
        # Metrics selection
        metrics = ["prompt_input", "prompt_output", "total_prompt", "cost", "prompt_token_per_price"]  # Add new metric
        selected_metric = st.selectbox("Select Metric", metrics)

        # Calculate prompt token per price
        df['prompt_token_per_price'] = df['total_prompt'] / df['cost']

        # Model Performance Chart
        st.subheader("Model Performance Metrics")
        
        fig = px.bar(df, x="model", y=selected_metric, color="model",
                        labels={selected_metric: "Prompt Tokens per Price"},
                        title=f"Prompt Tokens per Price by Model")
        
        figg = px.scatter_3d(df, x="model", y=selected_metric, color="model",
                        labels={selected_metric: selected_metric.replace("_", " ").title()},
                        title=f"{selected_metric.replace('_', ' ').title()} by Model")
        st.plotly_chart(fig)
        st.plotly_chart(figg)

    with tab3:
        # Page ID Usage Token
        st.subheader("Page ID Usage Token")
        page_id_usage = df.groupby("page_name").agg({
            "prompt_input": "sum",
            "prompt_output": "sum",
            "total_prompt": "sum",
            "cost": "sum"
        }).reset_index()

        fig_page_id = px.bar(page_id_usage, x="page_name", y="total_prompt",
                             color="page_name",  # Add color="page_name" here
                             labels={"total_prompt": "Total Tokens", "page_name": "Page Name"},
                             title="Total Token Usage by Page Name")
        st.plotly_chart(fig_page_id)

    with tab4:
        # Model Distribution Pie Chart
        st.subheader("Model Usage Distribution")
        model_distribution = df["model"].value_counts().reset_index()
        model_distribution.columns = ["model", "count"]
        fig_pie = px.pie(model_distribution, values="count", names="model", title="Model Usage Distribution")
        st.plotly_chart(fig_pie)

    with tab5:
        # Usage Over Time (All Pages)
        st.subheader("Usage Over Time (All Pages)")
        df["time"] = pd.to_datetime(df["time"])
        df["minute"] = df["time"].dt.floor('Min')
        time_series = df.groupby(["minute", "page_name"]).agg({"total_prompt": "sum", "cost": "sum"}).reset_index()

        fig_time = px.scatter(time_series, x="minute", y="total_prompt", color="page_name",
                           labels={"value": "Total Prompts", "variable": "Metric", "page_name": "Page Name"},
                           title="Total Prompt Usage Over Time (All Pages)")
        st.plotly_chart(fig_time)

        fig_cost = px.scatter(time_series, x="minute", y="cost", color="page_name",
                           labels={"value": "Cost", "variable": "Metric", "page_name": "Page Name"},
                           title="Cost Over Time (All Pages)")
        st.plotly_chart(fig_cost)

        # Usage Over Time (All Models)
        st.subheader("Usage Over Time (All Models)")
        df["time"] = pd.to_datetime(df["time"])
        df["minute"] = df["time"].dt.floor('Min')
        time_series = df.groupby(["minute", "page_name", "model"]).agg({"total_prompt": "sum", "cost": "sum"}).reset_index()

        fig_mtime = px.scatter(time_series, x="minute", y="total_prompt", color="model",
                           labels={"value": "Total Prompts", "variable": "Metric", "page_name": "Page Name", "model": "Model"},
                           title="Total Prompt Usage Over Time (All Model)")
        st.plotly_chart(fig_mtime)

        fig_mcost = px.scatter(time_series, x="minute", y="cost", color="model",
                           labels={"value": "Cost", "variable": "Metric", "page_name": "Page Name", "model": "Model"},
                           title="Cost Over Time (All Model)")
        st.plotly_chart(fig_mcost)

    # Usage Details Table
    st.subheader("Usage Details")
    st.dataframe(df[["time", "page_name", "prompt_input", "prompt_output", "total_prompt", "cost","model"]])
