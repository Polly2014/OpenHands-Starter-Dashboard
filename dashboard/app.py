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
    page_title="OpenHands-Starter Telemetry Dashboard",
    page_icon="📊",
    layout="wide"
)

# 配置
API_URL = os.getenv("API_URL", "http://localhost:9999")

# 页面标题
st.title("OpenHands-Starter Telemetry Dashboard")
st.subheader("整体安装情况")

# 在仪表板中添加日期选择器
st.sidebar.header("筛选器")
date_options = ["最近7天", "最近30天", "最近90天", "全部"]
date_filter = st.sidebar.selectbox("时间范围", date_options)

# 添加会话状态筛选器
session_status_filter = st.sidebar.multiselect(
    "安装状态过滤", 
    options=["全部", "成功", "失败"], 
    default=["全部"]
)

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
@st.cache_data(ttl=300)
def get_telemetry_stats(start_date=None):
    try:
        url = f"{API_URL}/api/telemetry/stats"
        if start_date:
            url += f"?start_date={start_date}"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"无法连接到API服务器 ({API_URL})。请检查连接或服务器状态。")
        if st.button("重试连接"):
            st.experimental_rerun()
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP错误: {e.response.status_code} - {e.response.reason}")
        return None
    except Exception as e:
        st.error(f"获取统计数据时出错: {str(e)}")
        st.info("请检查API服务器日志获取更多信息。")
        return None

# 获取安装趋势数据
@st.cache_data(ttl=300)
def get_installation_trend(start_date=None):
    try:
        url = f"{API_URL}/api/telemetry/trends"
        if start_date:
            url += f"?start_date={start_date}"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"无法连接到API服务器 ({API_URL})。请检查连接或服务器状态。")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"获取趋势数据HTTP错误: {e.response.status_code} - {e.response.reason}")
        return None
    except Exception as e:
        st.error(f"获取趋势数据时出错: {str(e)}")
        return None

# 获取安装用户统计
@st.cache_data(ttl=300)
def get_unique_users(start_date=None):
    try:
        url = f"{API_URL}/api/telemetry/users"
        if start_date:
            url += f"?start_date={start_date}"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        # 错误已经在其他函数中显示，这里不重复显示
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"获取用户数据HTTP错误: {e.response.status_code} - {e.response.reason}")
        return None
    except Exception as e:
        st.error(f"获取用户数据时出错: {str(e)}")
        return None

# 获取最近会话
@st.cache_data(ttl=300)
def get_recent_sessions(limit=10, start_date=None, status_filter=None):
    try:
        url = f"{API_URL}/api/telemetry/recent?limit={limit}"
        
        # 添加日期筛选
        if start_date:
            url += f"&start_date={start_date}"
            
        # 添加状态筛选
        if status_filter and status_filter != "全部":
            success_value = "true" if status_filter == "成功" else "false"
            url += f"&success={success_value}"
            
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"无法连接到API服务器 ({API_URL})。请检查连接或服务器状态。")
        return []
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP错误: {e.response.status_code} - {e.response.reason}")
        return []
    except Exception as e:
        st.error(f"获取会话数据时出错: {str(e)}")
        return []

# 获取会话详情
def get_session_events(session_id):
    try:
        response = requests.get(f"{API_URL}/api/telemetry/sessions/{session_id}/events")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"无法连接到API服务器 ({API_URL})。请检查连接或服务器状态。")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP错误: {e.response.status_code} - {e.response.reason}")
        return None
    except Exception as e:
        st.error(f"获取会话事件时出错: {str(e)}")
        return None

# dashboard/app.py 添加导出功能
def export_to_csv(df, filename):
    return df.to_csv().encode('utf-8')

# 刷新按钮
col1, col2 = st.columns([1, 15])
with col1:
    if st.button("🔄 刷新"):
        st.cache_data.clear()
        st.success("数据已刷新!")

# 获取筛选过的日期
start_date = filter_by_date(date_filter)

# 获取各种数据
stats = get_telemetry_stats(start_date)
trend_data = get_installation_trend(start_date)
users_data = get_unique_users(start_date)

# 确定状态筛选器
active_status_filter = None
if session_status_filter and "全部" not in session_status_filter:
    if len(session_status_filter) == 1:
        active_status_filter = session_status_filter[0]

# 获取筛选后的会话数据
recent_sessions = get_recent_sessions(20, start_date, active_status_filter)

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
        # 如果有独立用户数据，则显示独立用户数
        if users_data and 'unique_users' in users_data:
            st.metric("独立安装用户", users_data['unique_users'])
        else:
            st.metric("平均安装时间", f"{stats['avg_install_time']:.1f} 秒")
            
    # 如果有用户数据且包含活跃用户指标，则添加额外的KPI行
    if users_data and 'active_users' in users_data:
        st.subheader("用户活跃度")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("活跃用户数", users_data['active_users'])
        with col2:
            st.metric("平均安装时间", f"{stats['avg_install_time']:.1f} 秒")
        with col3:
            if 'returning_users' in users_data:
                st.metric("重复安装用户", users_data['returning_users'])
        with col4:
            if 'avg_sessions_per_user' in users_data:
                st.metric("每用户平均安装次数", f"{users_data['avg_sessions_per_user']:.1f}")

    # 显示安装趋势图
    if trend_data:
        st.subheader("安装数量趋势分析")
        
        # 创建三列布局
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
        
        # 添加当日和前一日安装数据比较
        with metrics_col1:
            # 计算当日和前一日的安装数
            if 'daily_installs' in trend_data and len(trend_data['daily_installs']) > 1:
                today_data = trend_data['daily_installs'][-1]
                yesterday_data = trend_data['daily_installs'][-2]
                today_count = today_data.get('count', 0)
                yesterday_count = yesterday_data.get('count', 0)
                delta = today_count - yesterday_count
                delta_percent = f"{delta/yesterday_count*100:.1f}%" if yesterday_count > 0 else "N/A"
                
                st.metric(
                    "今日安装", 
                    today_count,
                    delta=delta_percent,
                    delta_color="normal"
                )
            else:
                st.metric("今日安装", "无数据")
        
        # 添加本周和上周安装数据比较
        with metrics_col2:
            if 'weekly_installs' in trend_data and len(trend_data['weekly_installs']) > 1:
                this_week = trend_data['weekly_installs'][-1]
                last_week = trend_data['weekly_installs'][-2]
                this_week_count = this_week.get('count', 0)
                last_week_count = last_week.get('count', 0)
                delta = this_week_count - last_week_count
                delta_percent = f"{delta/last_week_count*100:.1f}%" if last_week_count > 0 else "N/A"
                
                st.metric(
                    "本周安装", 
                    this_week_count,
                    delta=delta_percent,
                    delta_color="normal"
                )
            else:
                st.metric("本周安装", "无数据")
        
        # 添加平均每日安装数
        with metrics_col3:
            if 'daily_installs' in trend_data and trend_data['daily_installs']:
                daily_counts = [day.get('count', 0) for day in trend_data['daily_installs']]
                if daily_counts:
                    avg_daily = sum(daily_counts) / len(daily_counts)
                    st.metric("平均每日安装", f"{avg_daily:.1f}")
                else:
                    st.metric("平均每日安装", "无数据")
            else:
                st.metric("平均每日安装", "无数据")
        
        # 创建tab布局用于切换不同周期的图表
        trend_tab1, trend_tab2, trend_tab3 = st.tabs(["日趋势", "周趋势", "月趋势"])
        
        # 处理趋势数据
        with trend_tab1:
            if 'daily_installs' in trend_data and trend_data['daily_installs']:
                trend_df = pd.DataFrame(trend_data['daily_installs'])
                trend_df['date'] = pd.to_datetime(trend_df['date'])
                
                # 创建每日趋势图 - 优化样式
                fig_daily = px.line(
                    trend_df,
                    x='date',
                    y='count',
                    title='每日安装数量',
                    labels={'date': '日期', 'count': '安装数量'},
                    line_shape='spline',  # 使线条更平滑
                    markers=True  # 显示数据点
                )
                
                # 自定义线条样式
                fig_daily.update_traces(
                    line=dict(width=3, color='#1E88E5'),  # 蓝色粗线
                    marker=dict(size=6, color='#1E88E5', line=dict(width=1, color='white'))  # 数据点样式
                )
                
                # 添加成功率曲线（如果存在）
                if 'success_rate' in trend_df.columns:
                    fig_daily.add_trace(
                        go.Scatter(
                            x=trend_df['date'],
                            y=trend_df['success_rate'],
                            mode='lines+markers',
                            name='成功率',
                            yaxis='y2',
                            line=dict(color='#43A047', width=2, shape='spline', dash='dot'),  # 绿色虚线
                            marker=dict(size=5, color='#43A047', symbol='diamond')  # 菱形标记
                        )
                    )
                    
                    # 添加第二个Y轴 - 更好的样式
                    fig_daily.update_layout(
                        yaxis2=dict(
                            title='成功率 (%)',
                            overlaying='y',
                            side='right',
                            range=[0, 100],
                            showgrid=False
                        )
                    )
                
                # 添加区域填充，使图表更具视觉效果
                fig_daily.add_trace(
                    go.Scatter(
                        x=trend_df['date'],
                        y=trend_df['count'],
                        mode='none',
                        fill='tozeroy',
                        fillcolor='rgba(30, 136, 229, 0.1)',  # 半透明蓝色
                        name='安装总量',
                        showlegend=False
                    )
                )
                
                # 美化图表 - 修复布局参数
                fig_daily.update_layout(
                    xaxis_title='日期',
                    yaxis_title='安装数量',
                    height=450,
                    hovermode='x unified',
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    xaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(211, 211, 211, 0.5)',
                        zeroline=False
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(211, 211, 211, 0.5)',
                        zeroline=False
                    ),
                    margin=dict(l=10, r=10, b=10, t=50),
                    legend=dict(
                        orientation="v",  # 垂直方向排列
                        xanchor="right",  # 右对齐
                        x=0.99,  # 靠右边缘
                        yanchor="top",    # 顶部对齐
                        y=0.99,  # 靠顶部边缘
                        bgcolor="rgba(255,255,255,0.8)",  # 半透明白色背景
                        bordercolor="rgba(211,211,211,0.5)",  # 浅灰色边框
                        borderwidth=1
                    ),
                    title_text='每日安装数量',  # 使用title_text代替嵌套字典
                    title_y=0.95,
                    title_x=0.5,
                    title_xanchor='center',
                    title_yanchor='top',
                )
                
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                st.info("暂无每日安装数据")
        
        # 周趋势图 - 优化样式
        with trend_tab2:
            if 'weekly_installs' in trend_data and trend_data['weekly_installs']:
                weekly_df = pd.DataFrame(trend_data['weekly_installs'])
                weekly_df['week'] = pd.to_datetime(weekly_df['week_start'])
                
                # 创建周趋势图
                fig_weekly = px.bar(
                    weekly_df,
                    x='week',
                    y='count',
                    title='每周安装总量',
                    labels={'week': '周开始日期', 'count': '安装数量'},
                    text='count'  # 在柱状图上显示数值
                )
                
                # 设置柱状图样式
                fig_weekly.update_traces(
                    marker_color='rgba(76, 175, 80, 0.7)',  # 半透明绿色
                    marker_line_color='#2E7D32',  # 深绿色轮廓
                    marker_line_width=1.5,
                    textposition='outside',  # 文本位置
                    texttemplate='%{text}',  # 文本显示格式
                )
                
                # 添加更好看的趋势线
                fig_weekly.add_trace(
                    go.Scatter(
                        x=weekly_df['week'],
                        y=weekly_df['count'],
                        mode='lines+markers',
                        line=dict(color='#FF5722', width=2, shape='spline'),  # 橙色曲线
                        marker=dict(
                            size=8,
                            symbol='circle',
                            color='#FF5722',
                            line=dict(color='white', width=1)
                        ),
                        name='周趋势'
                    )
                )
                
                # 增强图表样式 - 使用与日趋势图相同的参数格式
                fig_weekly.update_layout(
                    height=450,
                    xaxis_title='周起始日期',
                    yaxis_title='安装数量',
                    bargap=0.4,  # 调整柱间距
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    xaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(211, 211, 211, 0.5)',
                        zeroline=False,
                        tickangle=45  # 倾斜日期标签
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(211, 211, 211, 0.5)',
                        zeroline=False
                    ),
                    margin=dict(l=10, r=10, b=10, t=50),
                    legend=dict(
                        orientation="v",
                        xanchor="right",
                        x=0.99,
                        yanchor="top",
                        y=0.99,
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="rgba(211,211,211,0.5)",
                        borderwidth=1
                    ),
                    title_text='每周安装总量',  # 使用title_text代替嵌套字典
                    title_y=0.95,
                    title_x=0.5,
                    title_xanchor='center',
                    title_yanchor='top',
                )
                
                st.plotly_chart(fig_weekly, use_container_width=True)
            else:
                st.info("暂无每周安装数据")
        
        # 月趋势图 - 优化样式
        with trend_tab3:
            if 'daily_installs' in trend_data and trend_data['daily_installs']:
                # 按月聚合数据
                trend_df = pd.DataFrame(trend_data['daily_installs'])
                trend_df['date'] = pd.to_datetime(trend_df['date'])
                trend_df['month'] = trend_df['date'].dt.to_period('M')
                
                # 按月分组
                monthly_data = trend_df.groupby('month')['count'].sum().reset_index()
                monthly_data['month_date'] = monthly_data['month'].dt.to_timestamp()
                
                # 创建月趋势图 - 更吸引人的渐变色柱状图
                fig_monthly = px.bar(
                    monthly_data,
                    x='month_date',
                    y='count',
                    title='每月安装总量',
                    labels={'month_date': '月份', 'count': '安装数量'},
                    text='count',  # 显示数值
                    color='count',  # 根据值设置颜色
                    color_continuous_scale='Viridis',  # 使用渐变色
                )
                
                # 美化图表
                fig_monthly.update_traces(
                    texttemplate='%{text}',
                    textposition='outside',
                    marker_line_width=1,
                    marker_line_color='white',  # 白色柱状图边框
                    hovertemplate='<b>月份</b>: %{x|%Y-%m}<br><b>安装数量</b>: %{y}<extra></extra>'
                )
                
                # 添加均值基准线
                mean_value = monthly_data['count'].mean()
                fig_monthly.add_shape(
                    type="line",
                    x0=monthly_data['month_date'].min(),
                    y0=mean_value,
                    x1=monthly_data['month_date'].max(),
                    y1=mean_value,
                    line=dict(
                        color="rgba(255, 0, 0, 0.5)",
                        width=2,
                        dash="dash",
                    ),
                )
                
                # 标记均值
                fig_monthly.add_annotation(
                    x=monthly_data['month_date'].max(),
                    y=mean_value,
                    text=f"平均: {mean_value:.1f}",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor="rgba(255, 0, 0, 0.5)",
                    ax=50,
                    ay=-30
                )
                
                # 增强布局样式 - 使用与日趋势图相同的参数格式
                fig_monthly.update_layout(
                    height=450,
                    xaxis_title='月份',
                    yaxis_title='安装数量',
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    xaxis=dict(
                        tickformat="%Y-%m",
                        tickangle=45,
                        showgrid=True,
                        gridcolor='rgba(211, 211, 211, 0.5)',
                        zeroline=False,
                        tickmode='auto',
                        nticks=len(monthly_data)
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(211, 211, 211, 0.5)',
                        zeroline=False
                    ),
                    margin=dict(l=10, r=10, b=10, t=50),
                    coloraxis_showscale=False,  # 隐藏颜色刻度
                    legend=dict(
                        orientation="v",
                        xanchor="right",
                        x=0.99,
                        yanchor="top",
                        y=0.99,
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="rgba(211,211,211,0.5)",
                        borderwidth=1
                    ),
                    title_text='每月安装总量',  # 使用title_text代替嵌套字典
                    title_y=0.95,
                    title_x=0.5,
                    title_xanchor='center',
                    title_yanchor='top',
                )
                
                st.plotly_chart(fig_monthly, use_container_width=True)
            else:
                st.info("暂无每月安装数据")

   

    # 创建步骤成功率图表
    st.subheader("安装步骤状态分布")
    
    steps_data = []
    available_steps = []
    
    for step, statuses in stats["steps_status"].items():
        available_steps.append(step)
        total = sum(statuses.values())
        for status, count in statuses.items():
            steps_data.append({
                "步骤": step,
                "状态": status,
                "数量": count,
                "百分比": (count / total * 100) if total > 0 else 0
            })
    
    # 添加步骤筛选到侧边栏
    step_filter = st.sidebar.multiselect(
        "安装步骤过滤",
        options=["全部"] + available_steps,
        default=["全部"]
    )
    
    steps_df = pd.DataFrame(steps_data)
    
    # 应用步骤筛选
    if step_filter and "全部" not in step_filter:
        steps_df = steps_df[steps_df["步骤"].isin(step_filter)]
    
    if not steps_df.empty:
        fig = px.bar(
            steps_df,
            x="步骤",
            y="数量",
            color="状态",
            barmode="stack",
            text="百分比",
            hover_data=["步骤", "状态", "数量", "百分比"],
            labels={"百分比": "%"}
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无步骤数据")
else:
    st.warning("无法获取统计数据。请确保后端API正在运行。")
    if st.button("尝试重新连接"):
        st.experimental_rerun()

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
    
    # 显示过滤后的结果
    st.dataframe(sessions_display, use_container_width=True)
    
    # 显示筛选结果统计
    st.caption(f"显示 {len(sessions_df)} 条会话记录 {('(' + date_filter + ')') if date_filter != '全部' else ''}")

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
st.markdown("OpenHands-Starter Telemetry Dashboard -- Designed By Polly | © 2025")