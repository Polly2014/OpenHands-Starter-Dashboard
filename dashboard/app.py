# dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置页面配置
st.set_page_config(
    page_title="OpenHands Telemetry Dashboard",
    page_icon="📊",
    layout="wide"
)

# 配置
API_URL = os.getenv("API_URL", "http://localhost:9999")

# 页面标题
st.title("OpenHands Telemetry Dashboard")
st.markdown("### Installation Telemetry Analytics")

# 在仪表板中添加日期选择器
st.sidebar.header("筛选器")
date_options = ["最近7天", "最近30天", "最近90天", "全部"]
date_filter = st.sidebar.selectbox("时间范围", date_options)

# # 在 dashboard/app.py 中添加调试输出
# st.sidebar.text(f"API URL: {API_URL}")

# 根据日期筛选修改 API 请求
def filter_by_date(date_filter):
    today = datetime.utcnow()
    if date_filter == "最近7天":
        start_date = today - timedelta(days=7)
    elif date_filter == "最近30天":
        start_date = today - timedelta(days=30)
    elif date_filter == "最近90天":
        start_date = today - timedelta(days=90)
    else:
        return None  # 全部数据
    
    return start_date.isoformat()

# 获取统计数据
@st.cache_data(ttl=300)  # 缓存5分钟
def get_telemetry_stats():
    try:
        response = requests.get(f"{API_URL}/api/telemetry/stats")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching telemetry stats: {str(e)}")
        return None

# 获取最近会话
@st.cache_data(ttl=300)
def get_recent_sessions(limit=10):
    try:
        response = requests.get(f"{API_URL}/api/telemetry/recent?limit={limit}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching recent sessions: {str(e)}")
        return []

# 获取会话详情
def get_session_events(session_id):
    try:
        response = requests.get(f"{API_URL}/api/telemetry/sessions/{session_id}/events")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching session events: {str(e)}")
        return None

# dashboard/app.py 添加导出功能
def export_to_csv(df, filename):
    return df.to_csv().encode('utf-8')

# 刷新按钮
if st.button("刷新数据"):
    st.cache_data.clear()
    st.success("数据已刷新!")

# 获取数据
stats = get_telemetry_stats()
recent_sessions = get_recent_sessions(20)

# 显示KPI卡片
if stats:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总安装次数", stats['total_sessions'])
    with col2:
        st.metric("成功安装", stats['successful_installs'])
    with col3:
        st.metric("成功率", f"{stats['success_rate']:.1f}%")
    with col4:
        st.metric("平均安装时间", f"{stats['avg_install_time']:.1f} 秒")

    # 创建操作系统分布图表
    st.subheader("按操作系统分类的安装数")
    os_data = pd.DataFrame({
        "操作系统": stats["installation_by_os"].keys(),
        "安装数": stats["installation_by_os"].values()
    })
    
    if not os_data.empty:
        fig = px.pie(os_data, names="操作系统", values="安装数", hole=0.4)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无操作系统数据")

    # 创建步骤成功率图表
    st.subheader("安装步骤状态分布")
    
    steps_data = []
    for step, statuses in stats["steps_status"].items():
        total = sum(statuses.values())
        for status, count in statuses.items():
            steps_data.append({
                "步骤": step,
                "状态": status,
                "数量": count,
                "百分比": (count / total * 100) if total > 0 else 0
            })
    
    steps_df = pd.DataFrame(steps_data)
    if not steps_df.empty:
        fig = px.bar(
            steps_df,
            x="步骤",
            y="数量",
            color="状态",
            barmode="stack",
            text="百分比",
            labels={"百分比": "%"}
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无步骤数据")
else:
    st.warning("无法获取统计数据。请确保后端API正在运行。")

# 显示最近会话
st.subheader("最近安装会话")
if recent_sessions:
    # 创建会话表格
    sessions_df = pd.DataFrame(recent_sessions)
    sessions_df["timestamp"] = pd.to_datetime(sessions_df["timestamp"])
    sessions_df["时间"] = sessions_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    sessions_df["状态"] = sessions_df["success"].apply(lambda x: "成功" if x else "失败")
    sessions_df["持续时间"] = sessions_df["duration_seconds"].apply(lambda x: f"{x:.1f} 秒")
    
    # 使用Streamlit的列格式化
    sessions_display = sessions_df[["session_id", "时间", "状态", "持续时间", "os"]]
    sessions_display.columns = ["会话ID", "时间", "状态", "持续时间", "操作系统"]

    # 添加导出功能
    csv = export_to_csv(sessions_df, "sessions.csv")
    st.download_button(
        label="导出会话数据为CSV",
        data=csv,
        file_name="openhands_sessions.csv",
        mime="text/csv",
    )
    
    # 增加会话详情展开功能
    selected_session = st.selectbox("选择会话查看详情:", sessions_df["session_id"].tolist())
    
    if selected_session:
        session_data = get_session_events(selected_session)
        if session_data and session_data["events"]:
            st.subheader(f"会话 {selected_session} 详情")
            
            events = session_data["events"]
            events_df = pd.DataFrame(events)
            
            # 为时间轴创建数据
            events_df["timestamp"] = pd.to_datetime(events_df["timestamp"])
            events_df = events_df.sort_values("timestamp")
            
            # 创建时间轴可视化
            fig = go.Figure()
            
            for i, event in events_df.iterrows():
                # 根据事件状态设置颜色
                color = "green"
                if event["status"] == "failure":
                    color = "red"
                elif event["status"] == "warning" or event["status"] == "partial":
                    color = "orange"
                
                # 添加事件点
                fig.add_trace(go.Scatter(
                    x=[event["timestamp"]],
                    y=[event["step"]],
                    mode="markers+text",
                    marker=dict(color=color, size=15),
                    text=[event["status"]],
                    textposition="top center",
                    name=f"{event['step']} - {event['status']}"
                ))
            
            fig.update_layout(
                title="安装步骤时间轴",
                xaxis_title="时间",
                yaxis_title="安装步骤",
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 显示事件详情
            with st.expander("查看会话事件详情"):
                # 选择要展示的列
                display_cols = ["step", "status", "timestamp"]
                st.dataframe(events_df[display_cols])
                
                # 显示最后一个事件的详细指标
                if "metrics" in events_df.columns:
                    last_event = events_df.iloc[-1]
                    if isinstance(last_event["metrics"], dict) and last_event["metrics"]:
                        st.subheader("最终指标")
                        for key, value in last_event["metrics"].items():
                            st.text(f"{key}: {value}")
else:
    st.info("暂无最近会话数据")

# 页脚
st.markdown("---")
st.markdown("OpenHands Telemetry Dashboard | © 2025")