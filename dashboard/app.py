"""Proxene Dashboard - Real-time monitoring and analytics"""

import streamlit as st
import redis.asyncio as redis
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import asyncio
import json
import os
from typing import Dict, List, Any

# Page config
st.set_page_config(
    page_title="Proxene Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    
    .cost-card {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    
    .pii-card {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    
    .stMetric > label {
        font-size: 14px !important;
    }
</style>
""", unsafe_allow_html=True)


class DashboardData:
    """Data access layer for dashboard"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            return True
        except Exception as e:
            st.error(f"Failed to connect to Redis: {e}")
            return False
    
    async def get_daily_costs(self, days: int = 7) -> Dict[str, float]:
        """Get daily costs for the last N days"""
        if not self.client:
            return {}
        
        costs = {}
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"proxene:cost:daily:{date}"
            cost = await self.client.get(key)
            costs[date] = float(cost) if cost else 0.0
        
        return costs
    
    async def get_model_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get model usage statistics"""
        if not self.client:
            return []
        
        stats = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            
            # Get all model keys for this date
            pattern = f"proxene:cost:model:*:{date}"
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            for key in keys:
                model_data = await self.client.hgetall(key)
                if model_data:
                    model_name = key.split(':')[3]  # Extract model name
                    stats.append({
                        'date': date,
                        'model': model_name,
                        'requests': int(model_data.get('requests', 0)),
                        'input_tokens': int(float(model_data.get('input_tokens', 0))),
                        'output_tokens': int(float(model_data.get('output_tokens', 0))),
                        'cost': float(model_data.get('cost', 0))
                    })
        
        return stats
    
    async def get_request_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent request logs (mock implementation)"""
        # In a real implementation, this would fetch from a proper log storage
        # For now, we'll generate some mock data
        logs = []
        base_time = datetime.now()
        
        models = ['gpt-3.5-turbo', 'gpt-4', 'gpt-4o-mini', 'claude-3-haiku']
        statuses = [200, 200, 200, 200, 429, 400]  # Mostly successful
        
        for i in range(limit):
            log = {
                'timestamp': (base_time - timedelta(minutes=i * 2)).isoformat(),
                'model': models[i % len(models)],
                'status': statuses[i % len(statuses)],
                'cost': round(0.001 + (i % 10) * 0.001, 6),
                'input_tokens': 50 + (i % 200),
                'output_tokens': 20 + (i % 100),
                'pii_findings': 1 if i % 15 == 0 else 0,  # PII every 15th request
                'cached': i % 8 == 0  # Cache hit every 8th request
            }
            logs.append(log)
        
        return logs


@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_dashboard_data():
    """Load data for dashboard (cached)"""
    dashboard = DashboardData()
    
    # Run async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        connected = loop.run_until_complete(dashboard.connect())
        if not connected:
            return None, None, None
            
        daily_costs = loop.run_until_complete(dashboard.get_daily_costs())
        model_stats = loop.run_until_complete(dashboard.get_model_stats())
        request_logs = loop.run_until_complete(dashboard.get_request_logs())
        
        return daily_costs, model_stats, request_logs
    
    finally:
        loop.close()


def render_header():
    """Render dashboard header"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h1>🛡️ Proxene Dashboard</h1>
            <p style="color: #666;">AI Governance & Cost Monitoring</p>
        </div>
        """, unsafe_allow_html=True)


def render_metrics_overview(daily_costs: Dict[str, float], model_stats: List[Dict[str, Any]], request_logs: List[Dict[str, Any]]):
    """Render key metrics overview"""
    
    # Calculate totals
    total_cost = sum(daily_costs.values())
    today_cost = daily_costs.get(datetime.now().strftime("%Y-%m-%d"), 0.0)
    total_requests = sum(stat['requests'] for stat in model_stats)
    pii_count = sum(1 for log in request_logs if log['pii_findings'] > 0)
    
    st.markdown("### 📊 Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="cost-card">
            <h3>${:.2f}</h3>
            <p>Total Cost (7d)</p>
        </div>
        """.format(total_cost), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="cost-card">
            <h3>${:.2f}</h3>
            <p>Today's Cost</p>
        </div>
        """.format(today_cost), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h3>{:,}</h3>
            <p>Total Requests</p>
        </div>
        """.format(total_requests), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="pii-card">
            <h3>{}</h3>
            <p>PII Detections</p>
        </div>
        """.format(pii_count), unsafe_allow_html=True)


def render_cost_trends(daily_costs: Dict[str, float]):
    """Render cost trends chart"""
    st.markdown("### 💰 Cost Trends")
    
    if not daily_costs:
        st.info("No cost data available. Make sure Redis is running and Proxene has processed some requests.")
        return
    
    # Prepare data
    df = pd.DataFrame(list(daily_costs.items()), columns=['Date', 'Cost'])
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    
    # Create chart
    fig = px.line(
        df, 
        x='Date', 
        y='Cost',
        title='Daily Cost Trends',
        labels={'Cost': 'Cost ($)', 'Date': 'Date'},
        line_shape='spline'
    )
    
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Cost ($)",
        showlegend=False,
        height=400
    )
    
    fig.update_traces(
        line=dict(color='#667eea', width=3),
        marker=dict(size=8, color='#764ba2')
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_model_usage(model_stats: List[Dict[str, Any]]):
    """Render model usage statistics"""
    st.markdown("### 🤖 Model Usage")
    
    if not model_stats:
        st.info("No model statistics available.")
        return
    
    # Aggregate by model
    model_totals = {}
    for stat in model_stats:
        model = stat['model']
        if model not in model_totals:
            model_totals[model] = {'requests': 0, 'cost': 0, 'tokens': 0}
        
        model_totals[model]['requests'] += stat['requests']
        model_totals[model]['cost'] += stat['cost']
        model_totals[model]['tokens'] += stat['input_tokens'] + stat['output_tokens']
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Requests by model
        if model_totals:
            models = list(model_totals.keys())
            requests = [model_totals[m]['requests'] for m in models]
            
            fig = px.pie(
                values=requests,
                names=models,
                title="Requests by Model"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Cost by model
        if model_totals:
            costs = [model_totals[m]['cost'] for m in models]
            
            fig = px.bar(
                x=models,
                y=costs,
                title="Cost by Model",
                labels={'x': 'Model', 'y': 'Cost ($)'}
            )
            fig.update_traces(marker_color='#f093fb')
            st.plotly_chart(fig, use_container_width=True)


def render_request_logs(request_logs: List[Dict[str, Any]]):
    """Render recent request logs"""
    st.markdown("### 📋 Recent Requests")
    
    if not request_logs:
        st.info("No request logs available.")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(request_logs)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Add status icons
    def status_icon(status):
        if status == 200:
            return "✅"
        elif status == 429:
            return "⚠️"
        else:
            return "❌"
    
    df['Status'] = df['status'].apply(lambda x: f"{status_icon(x)} {x}")
    df['Cost'] = df['cost'].apply(lambda x: f"${x:.4f}")
    df['Tokens'] = df['input_tokens'] + df['output_tokens']
    df['PII'] = df['pii_findings'].apply(lambda x: "🔒" if x > 0 else "")
    df['Cache'] = df['cached'].apply(lambda x: "💾" if x else "")
    
    # Display table
    display_df = df[['timestamp', 'model', 'Status', 'Cost', 'Tokens', 'PII', 'Cache']].copy()
    display_df.columns = ['Time', 'Model', 'Status', 'Cost', 'Tokens', 'PII', 'Cache']
    display_df['Time'] = display_df['Time'].dt.strftime('%H:%M:%S')
    
    st.dataframe(display_df.head(20), use_container_width=True)


def render_pii_analysis(request_logs: List[Dict[str, Any]]):
    """Render PII analysis"""
    st.markdown("### 🔒 PII Detection Analysis")
    
    pii_logs = [log for log in request_logs if log['pii_findings'] > 0]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "PII Detections",
            len(pii_logs),
            f"{len(pii_logs)/len(request_logs)*100:.1f}% of requests" if request_logs else "0%"
        )
    
    with col2:
        if pii_logs:
            # PII by model
            pii_by_model = {}
            for log in pii_logs:
                model = log['model']
                pii_by_model[model] = pii_by_model.get(model, 0) + 1
            
            fig = px.bar(
                x=list(pii_by_model.keys()),
                y=list(pii_by_model.values()),
                title="PII Detections by Model",
                labels={'x': 'Model', 'y': 'PII Detections'}
            )
            fig.update_traces(marker_color='#4facfe')
            st.plotly_chart(fig, use_container_width=True)


def main():
    """Main dashboard application"""
    render_header()
    
    # Load data
    with st.spinner("Loading dashboard data..."):
        daily_costs, model_stats, request_logs = load_dashboard_data()
    
    if daily_costs is None:
        st.error("Failed to connect to Redis. Please ensure Redis is running and accessible.")
        st.info("Default Redis URL: redis://localhost:6379")
        return
    
    # Auto-refresh toggle
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=True)
        show_debug = st.checkbox("Show Debug Info", value=False)
        
        if auto_refresh:
            st.rerun()
    
    # Render dashboard sections
    render_metrics_overview(daily_costs, model_stats, request_logs)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        render_cost_trends(daily_costs)
    with col2:
        render_pii_analysis(request_logs)
    
    st.markdown("---")
    
    render_model_usage(model_stats)
    
    st.markdown("---")
    
    render_request_logs(request_logs)
    
    # Debug info
    if show_debug:
        st.markdown("### 🐛 Debug Information")
        st.json({
            "daily_costs": daily_costs,
            "model_stats_count": len(model_stats),
            "request_logs_count": len(request_logs),
            "redis_url": "redis://localhost:6379"
        })


if __name__ == "__main__":
    main()