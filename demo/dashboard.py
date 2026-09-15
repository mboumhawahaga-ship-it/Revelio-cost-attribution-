import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).parent.parent
OUTPUT_PATH = BASE_DIR / "output" / "enriched_costs.json"
sys.path.insert(0, str(BASE_DIR / "lambda"))

from kpi import compute_kpis

st.set_page_config(page_title="Revelio — Cost Attribution", layout="wide")
st.title("Revelio — FinOps Cost Attribution")
st.caption("Who created what, and what did it cost?")


@st.cache_data(ttl=0)
def load_data() -> pd.DataFrame:
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        return pd.DataFrame(json.load(f))


df = load_data()
kpis = compute_kpis(str(OUTPUT_PATH))

# ── KPI Cards ──────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("💰 Total Cost", f"${kpis['total_cost_usd']:.2f}")
c2.metric("✅ Attribution Rate", f"{kpis['attribution_rate_pct']}%")
c3.metric(
    "❓ Unknown Cost",
    f"${kpis['unknown_cost_usd']:.2f}",
    f"{kpis['unknown_cost_pct']}% of total",
    delta_color="inverse",
)

st.divider()

# ── BEFORE / AFTER ─────────────────────────────────────────────────────────
col_b, col_a = st.columns(2)

with col_b:
    st.subheader("🔴 Before — Unattributed Costs")
    st.caption("Resources with no owner found in CloudTrail")
    before = df[df["initiated_by"] == "not-found-in-cloudtrail"][
        ["resource_id", "service", "operation", "cost_usd"]
    ].copy()
    before["cost_usd"] = before["cost_usd"].map("${:.4f}".format)
    before.columns = ["Resource ID", "Service", "Operation", "Cost"]
    st.dataframe(before, use_container_width=True, hide_index=True)

with col_a:
    st.subheader("🟢 After — Attributed Costs")
    st.caption("Resources with owner resolved from CloudTrail")
    after = df[df["initiated_by"] != "not-found-in-cloudtrail"][
        ["resource_id", "service", "initiated_by", "cost_usd"]
    ].copy()
    after["cost_usd"] = after["cost_usd"].map("${:.4f}".format)
    after.columns = ["Resource ID", "Service", "Created By", "Cost"]
    st.dataframe(after, use_container_width=True, hide_index=True)

st.divider()

# ── Charts ─────────────────────────────────────────────────────────────────
col_c1, col_c2 = st.columns(2)

with col_c1:
    st.subheader("Cost by Creator (Top 10)")
    creator_df = (
        df[df["initiated_by"] != "not-found-in-cloudtrail"]
        .groupby("initiated_by")["cost_usd"]
        .sum()
        .sort_values(ascending=True)
        .tail(10)
        .reset_index()
    )
    fig1 = px.bar(
        creator_df,
        x="cost_usd",
        y="initiated_by",
        orientation="h",
        labels={"cost_usd": "Cost (USD)", "initiated_by": "Creator"},
        color="cost_usd",
        color_continuous_scale="Blues",
    )
    fig1.update_layout(coloraxis_showscale=False, height=350, margin=dict(l=0))
    st.plotly_chart(fig1, use_container_width=True)

with col_c2:
    st.subheader("Attributed vs Unattributed by Service")
    service_df = df.copy()
    service_df["status"] = service_df["initiated_by"].apply(
        lambda x: "Unattributed" if x == "not-found-in-cloudtrail" else "Attributed"
    )
    service_grouped = (
        service_df.groupby(["service", "status"])["cost_usd"].sum().reset_index()
    )
    fig2 = px.bar(
        service_grouped,
        x="service",
        y="cost_usd",
        color="status",
        barmode="group",
        labels={"cost_usd": "Cost (USD)", "service": "Service"},
        color_discrete_map={"Attributed": "#2ecc71", "Unattributed": "#e74c3c"},
    )
    fig2.update_layout(height=350, legend_title_text="")
    st.plotly_chart(fig2, use_container_width=True)
