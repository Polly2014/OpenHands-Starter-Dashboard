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

# 修改前端代码以使用新的API
def display_user_analysis(start_date=None):
    st.subheader("用户分析")
    
    # 获取用户概览数据
    @st.cache_data(ttl=300)
    def get_user_overview(start_date=None):
        url = f"{API_URL}/api/telemetry/users/overview"
        if start_date:
            url += f"?start_date={start_date}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"获取用户概览失败: {str(e)}")
            return None
    
    # 获取特定用户详情
    @st.cache_data(ttl=300)
    def get_user_details(username, start_date=None):
        url = f"{API_URL}/api/telemetry/users/{username}"
        if start_date:
            url += f"?start_date={start_date}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                st.warning(f"未找到用户: {username}")
            else:
                st.error(f"获取用户详情失败: {str(e)}")
            return None
        except Exception as e:
            st.error(f"获取用户详情失败: {str(e)}")
            return None
    
    # 使用筛选过的日期
    overview_data = get_user_overview(start_date)
    
    if overview_data:
        # 显示用户总体统计，包括匿名用户
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("总用户数", overview_data.get("total_users", 0))
        with col2:
            st.metric("实名用户", overview_data.get("named_users", 0))
        with col3:
            st.metric("匿名用户", overview_data.get("anonymous_users", 0))
        with col4:
            st.metric("活跃用户", overview_data.get("active_users", 0))
        with col5:
            st.metric("新用户(30天)", overview_data.get("new_users_30d", 0))

        # 处理顶级用户表格 - 添加兼容性检查
        if "top_users" in overview_data and overview_data["top_users"]:
            # 创建 DataFrame
            users_df = pd.DataFrame(overview_data["top_users"])
            
            # 添加列存在性检查
            if "lastSeen" in users_df.columns:
                users_df["lastSeen"] = pd.to_datetime(users_df["lastSeen"])
                users_df["上次活动"] = users_df["lastSeen"].dt.strftime("%Y-%m-%d %H:%M")
                
            if "isAnonymous" in users_df.columns:
                # 创建样式指示匿名/实名用户
                users_df["用户类型"] = users_df["isAnonymous"].apply(
                    lambda x: "匿名" if x else "实名")
        
        # 版本分布
        st.subheader("版本分布")
        if overview_data["version_distribution"]:
            version_df = pd.DataFrame(overview_data["version_distribution"])
            
            # 创建一个切换，允许用户选择查看全部用户或仅实名用户
            user_view = st.radio(
                "用户视图:", 
                ["所有用户", "仅实名用户", "仅匿名用户"],
                horizontal=True
            )
            
            if user_view == "仅实名用户" and "namedCount" in version_df.columns:
                # 只显示实名用户版本分布
                fig = px.pie(
                    version_df, 
                    values="namedCount", 
                    names="version",
                    title="实名用户版本分布",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
            elif user_view == "仅匿名用户" and "anonymousCount" in version_df.columns:
                # 只显示匿名用户版本分布
                fig = px.pie(
                    version_df, 
                    values="anonymousCount", 
                    names="version",
                    title="匿名用户版本分布",
                    color_discrete_sequence=px.colors.qualitative.Dark24
                )
            else:
                # 显示所有用户版本分布
                fig = px.pie(
                    version_df, 
                    values="userCount", 
                    names="version",
                    title="所有用户版本分布",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
            
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hole=0.4,
                pull=[0.05 if x == version_df['userCount'].max() else 0 for x in version_df['userCount']]
            )
            
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)
            
            # 显示版本数据表格
            st.caption("版本用户数据详情")
            version_df_display = version_df.rename(columns={
                "version": "版本",
                "userCount": "总用户数",
                "anonymousCount": "匿名用户",
                "namedCount": "实名用户",
                "activeUsers": "活跃用户",
                "activePercentage": "活跃率(%)"
            })
            st.dataframe(version_df_display, use_container_width=True)
            
            # 添加CSV导出功能
            csv = export_to_csv(version_df_display, "version_distribution.csv")
            st.download_button(
                label="导出版本分布数据",
                data=csv,
                file_name="version_distribution.csv",
                mime="text/csv"
            )
        else:
            st.info("暂无版本分布数据")
        
        # 版本采用趋势
        if overview_data.get("version_adoption_trend"):
            st.subheader("版本采用趋势")
            trend_df = pd.DataFrame(overview_data["version_adoption_trend"])
            trend_df["date"] = pd.to_datetime(trend_df["date"])
            
            fig = px.line(
                trend_df,
                x="date",
                y="count",
                color="version",
                title="版本采用趋势",
                labels={"date": "月份", "count": "用户数", "version": "版本"}
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # 最活跃用户列表
        if overview_data.get("top_users"):
            st.subheader("最活跃用户")
            users_df = pd.DataFrame(overview_data["top_users"])
            users_df["lastSeen"] = pd.to_datetime(users_df["lastSeen"])
            users_df["上次活动"] = users_df["lastSeen"].dt.strftime("%Y-%m-%d %H:%M")
            
            # 添加用户详情链接功能
            users_df["状态"] = users_df["isActive"].apply(lambda x: "活跃" if x else "非活跃")
            
            # 检查并处理列名，确保安全访问
            # 修复: 添加检查和默认值，使代码更健壮
            columns_to_display = []
            rename_map = {}
            
            # 检查并添加每一列
            if "username" in users_df.columns:
                columns_to_display.append("username")
                rename_map["username"] = "用户名"
            
            # 检查 installCount 列，如果不存在但有 deployCount 列，则使用它
            if "installCount" in users_df.columns:
                columns_to_display.append("installCount")
                rename_map["installCount"] = "安装次数"
            
            # 检查 successCount 列
            if "successCount" in users_df.columns:
                columns_to_display.append("successCount") 
                rename_map["successCount"] = "成功安装"
            
            # 添加剩余列
            columns_to_display.extend(["上次活动"])
            
            if "latestVersion" in users_df.columns:
                columns_to_display.append("latestVersion")
                rename_map["latestVersion"] = "当前版本"
            
            columns_to_display.append("状态")
            
            # 选择可用列并重命名
            users_display = users_df[columns_to_display].rename(columns=rename_map)
            
            st.dataframe(users_display, use_container_width=True)
            
            # 添加用户详情查看功能
            selected_user = st.selectbox("选择用户查看详情:", [""] + users_df["username"].tolist())
            
            if selected_user:
                user_details = get_user_details(selected_user, start_date)
                if user_details:
                    st.subheader(f"用户详情: {selected_user}")
                    
                    # 用户基本信息
                    details = user_details["stats"]
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("安装次数", details.get("installCount", 0))
                    with col2:
                        st.metric("部署次数", details.get("deployCount", 0))
                    with col3:
                        st.metric("成功次数", details.get("successCount", 0))
                    with col4:
                        st.metric("成功率", f"{details.get('successRate', 0):.1f}%")
                    
                    # 用户版本历史
                    st.subheader("版本使用历史")
                    if user_details.get("version_history"):
                        history_df = pd.DataFrame(user_details["version_history"])
                        history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
                        history_df["时间"] = history_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
                        
                        history_display = history_df[["时间", "version", "sessionId", "status"]]
                        history_display.columns = ["时间", "版本", "会话ID", "状态"]
                        
                        st.dataframe(history_display, use_container_width=True)
                    else:
                        st.info("无版本历史数据")
                    
                    # 最近会话
                    st.subheader("最近会话")
                    if user_details.get("recent_sessions"):
                        sessions_df = pd.DataFrame(user_details["recent_sessions"])
                        sessions_df["startTime"] = pd.to_datetime(sessions_df["startTime"])
                        sessions_df["endTime"] = pd.to_datetime(sessions_df["endTime"])
                        sessions_df["开始时间"] = sessions_df["startTime"].dt.strftime("%Y-%m-%d %H:%M")
                        sessions_df["结束时间"] = sessions_df["endTime"].dt.strftime("%Y-%m-%d %H:%M")
                        sessions_df["持续时间"] = sessions_df["duration_seconds"].apply(lambda x: f"{x:.1f}秒")
                        sessions_df["状态"] = sessions_df["success"].apply(lambda x: "成功" if x else "失败")
                        
                        sessions_display = sessions_df[["sessionId", "开始时间", "结束时间", "持续时间", "version", "状态"]]
                        sessions_display.columns = ["会话ID", "开始时间", "结束时间", "持续时间", "版本", "状态"]
                        
                        st.dataframe(sessions_display, use_container_width=True)
                    else:
                        st.info("无会话数据")
                        
    else:
        st.info("暂无用户数据")


# 主页面布局
tab_installation, tab_user = st.tabs(["安装统计", "用户分析"])

# 在仪表板中添加日期选择器
st.sidebar.header("筛选器")
date_options = ["最近7天", "最近30天", "最近90天", "全部"]
date_filter = st.sidebar.selectbox("时间范围", date_options)


with tab_installation:

    st.subheader("整体安装情况")

    # 刷新按钮
    col1, col2 = st.columns([1, 15])
    with col1:
        if st.button("🔄 刷新"):
            st.cache_data.clear()
            st.success("数据已刷新!")

    # 获取筛选过的日期
    start_date = filter_by_date(date_filter)
    
    # 获取所有数据
    stats = get_telemetry_stats(start_date)
    trend_data = get_installation_trend(start_date)
    users_data = get_unique_users(start_date)

    # 显示KPI卡片
    if stats:
        # 第一行KPI卡片 - 主要指标
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("总安装次数", stats['total_sessions'])
        with col2:
            st.metric("成功安装", stats['successful_installs'])
        with col3:
            st.metric("成功率", f"{stats['success_rate']:.1f}%")
        with col4:
            st.metric("平均安装时间", f"{stats['avg_install_time']:.1f} 秒")
        with col5:
            if users_data and 'avg_sessions_per_user' in users_data:
                st.metric("平均每用户安装次数", f"{users_data['avg_sessions_per_user']:.1f}")
            else:
                st.metric("独立安装用户", users_data.get('unique_users', 0) if users_data else 0)
                
        # 第二行KPI卡片 - 时间段指标
        if trend_data and 'summary' in trend_data:
            summary = trend_data['summary']
            st.subheader("时段安装情况")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                today = summary.get('today', {})
                st.metric(
                    "今日安装", 
                    f"{today.get('successful', 0)}/{today.get('total', 0)}",
                    help="格式：成功安装/总安装"
                )
            with col2:
                this_week = summary.get('this_week', {})
                st.metric(
                    "本周安装", 
                    f"{this_week.get('successful', 0)}/{this_week.get('total', 0)}",
                    help="格式：成功安装/总安装"
                )
            with col3:
                this_month = summary.get('this_month', {})
                st.metric(
                    "本月安装", 
                    f"{this_month.get('successful', 0)}/{this_month.get('total', 0)}",
                    help="格式：成功安装/总安装"
                )

        # 显示安装趋势图
        if trend_data:
            st.subheader("安装趋势分析")
            
            # 创建tab布局用于切换不同周期的图表
            trend_tab1, trend_tab2, trend_tab3 = st.tabs(["日趋势", "周趋势", "月趋势"])
            
            # 处理日趋势数据
            with trend_tab1:
                if 'daily_installs' in trend_data and trend_data['daily_installs']:
                    trend_df = pd.DataFrame(trend_data['daily_installs'])
                    trend_df['date'] = pd.to_datetime(trend_df['date'])
                    
                    # 创建每日趋势图 - 显示总安装量和成功安装量
                    fig_daily = go.Figure()
                    
                    # 添加总安装量线条 - 带填充区域
                    fig_daily.add_trace(
                        go.Scatter(
                            x=trend_df['date'],
                            y=trend_df['total'],
                            name='总安装量',
                            line=dict(width=3, color='#1E88E5'),
                            mode='lines+markers',
                            marker=dict(size=6, color='#1E88E5', line=dict(width=1, color='white')),
                            fill='tozeroy',
                            fillcolor='rgba(30, 136, 229, 0.2)'
                        )
                    )
                    
                    # 添加成功安装量线条 - 带填充区域
                    fig_daily.add_trace(
                        go.Scatter(
                            x=trend_df['date'],
                            y=trend_df['successful'],
                            name='成功安装',
                            line=dict(width=3, color='#4CAF50'),
                            mode='lines+markers',
                            marker=dict(size=6, color='#4CAF50', line=dict(width=1, color='white')),
                            fill='tozeroy',
                            fillcolor='rgba(76, 175, 80, 0.2)'
                        )
                    )
                    
                    # 添加成功率线条，仿照月趋势图
                    fig_daily.add_trace(
                        go.Scatter(
                            x=trend_df['date'],
                            y=trend_df['success_rate'],
                            name='成功率 (%)',
                            line=dict(width=3, color='#FF9800', dash='dot'),
                            mode='lines+markers',
                            marker=dict(size=6, color='#FF9800'),
                            yaxis='y2'
                        )
                    )
                    
                    # 美化图表，添加双Y轴
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
                            zeroline=False,
                            title='安装数量'
                        ),
                        yaxis2=dict(
                            title='成功率 (%)',
                            overlaying='y',
                            side='right',
                            range=[0, 100],
                            ticksuffix='%'
                        ),
                        margin=dict(l=10, r=50, b=10, t=50),
                        legend=dict(
                            orientation="h",
                            xanchor="right",
                            x=1.0,
                            yanchor="top",
                            y=1.0
                        ),
                        title_text='每日安装量与成功率',
                        title_y=0.95,
                        title_x=0.5,
                        title_xanchor='center',
                        title_yanchor='top'
                    )
                    
                    st.plotly_chart(fig_daily, use_container_width=True)
                else:
                    st.info("暂无每日安装数据")
            
            # 处理周趋势数据
            with trend_tab2:
                if 'weekly_installs' in trend_data and trend_data['weekly_installs']:
                    weekly_df = pd.DataFrame(trend_data['weekly_installs'])
                    weekly_df['week'] = pd.to_datetime(weekly_df['week_start'])
                    
                    # 创建周趋势图 - 改为折线图带填充
                    fig_weekly = go.Figure()
                    
                    # 添加总安装量线条 - 带填充区域
                    fig_weekly.add_trace(
                        go.Scatter(
                            x=weekly_df['week'],
                            y=weekly_df['total'],
                            name='总安装量',
                            line=dict(width=3, color='#1E88E5'),
                            mode='lines+markers',
                            marker=dict(size=8, color='#1E88E5', line=dict(width=1, color='white')),
                            fill='tozeroy',
                            fillcolor='rgba(30, 136, 229, 0.2)'
                        )
                    )
                    
                    # 添加成功安装线条 - 带填充区域
                    fig_weekly.add_trace(
                        go.Scatter(
                            x=weekly_df['week'],
                            y=weekly_df['successful'],
                            name='成功安装',
                            line=dict(width=3, color='#4CAF50'),
                            mode='lines+markers',
                            marker=dict(size=8, color='#4CAF50', line=dict(width=1, color='white')),
                            fill='tozeroy',
                            fillcolor='rgba(76, 175, 80, 0.2)'
                        )
                    )
                    
                    # 添加成功率线条，仿照月趋势图
                    fig_weekly.add_trace(
                        go.Scatter(
                            x=weekly_df['week'],
                            y=weekly_df['success_rate'],
                            name='成功率 (%)',
                            line=dict(width=3, color='#FF9800', dash='dot'),
                            mode='lines+markers',
                            marker=dict(size=7, color='#FF9800'),
                            yaxis='y2'
                        )
                    )
                    
                    # 美化图表，添加双Y轴
                    fig_weekly.update_layout(
                        xaxis_title='周起始日期',
                        yaxis_title='安装数量',
                        height=450,
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis=dict(
                            showgrid=True,
                            gridcolor='rgba(211, 211, 211, 0.5)',
                            zeroline=False,
                            tickangle=45
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridcolor='rgba(211, 211, 211, 0.5)',
                            zeroline=False,
                            title='安装数量'
                        ),
                        yaxis2=dict(
                            title='成功率 (%)',
                            overlaying='y',
                            side='right',
                            range=[0, 100],
                            ticksuffix='%'
                        ),
                        margin=dict(l=10, r=50, b=10, t=50),
                        legend=dict(
                            orientation="h",
                            xanchor="right",
                            x=1.0,
                            yanchor="top",
                            y=1.0
                        ),
                        title_text='每周安装量与成功率',
                        title_y=0.95,
                        title_x=0.5,
                        title_xanchor='center',
                        title_yanchor='top'
                    )
                    
                    st.plotly_chart(fig_weekly, use_container_width=True)
                else:
                    st.info("暂无每周安装数据")
            
            # 处理月趋势数据
            with trend_tab3:
                if 'monthly_installs' in trend_data and trend_data['monthly_installs']:
                    monthly_df = pd.DataFrame(trend_data['monthly_installs'])
                    monthly_df['month'] = pd.to_datetime(monthly_df['month'])
                    
                    # 创建月趋势图 - 改为折线图带填充
                    fig_monthly = go.Figure()
                    
                    # 添加总安装量线条 - 带填充区域
                    fig_monthly.add_trace(
                        go.Scatter(
                            x=monthly_df['month'],
                            y=monthly_df['total'],
                            name='总安装量',
                            line=dict(width=3, color='#1E88E5'),
                            mode='lines+markers+text',
                            marker=dict(size=10, color='#1E88E5', line=dict(width=1, color='white')),
                            text=monthly_df['total'],
                            textposition='top center',
                            fill='tozeroy',
                            fillcolor='rgba(30, 136, 229, 0.2)'
                        )
                    )
                    
                    # 添加成功安装线条 - 带填充区域
                    fig_monthly.add_trace(
                        go.Scatter(
                            x=monthly_df['month'],
                            y=monthly_df['successful'],
                            name='成功安装',
                            line=dict(width=3, color='#4CAF50'),
                            mode='lines+markers+text',
                            marker=dict(size=10, color='#4CAF50', line=dict(width=1, color='white')),
                            text=monthly_df['successful'],
                            textposition='bottom center',
                            fill='tozeroy',
                            fillcolor='rgba(76, 175, 80, 0.2)'
                        )
                    )
                    
                    # 添加成功率线条
                    fig_monthly.add_trace(
                        go.Scatter(
                            x=monthly_df['month'],
                            y=monthly_df['success_rate'],
                            name='成功率 (%)',
                            line=dict(width=3, color='#FF9800', dash='dot'),
                            mode='lines+markers',
                            marker=dict(size=8, color='#FF9800'),
                            yaxis='y2'
                        )
                    )
                    
                    # 美化图表 - 添加双Y轴
                    fig_monthly.update_layout(
                        xaxis_title='月份',
                        yaxis_title='安装数量',
                        height=450,
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis=dict(
                            showgrid=True,
                            gridcolor='rgba(211, 211, 211, 0.5)',
                            zeroline=False,
                            tickangle=45,
                            tickformat="%Y-%m"
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridcolor='rgba(211, 211, 211, 0.5)',
                            zeroline=False,
                            title='安装数量'
                        ),
                        yaxis2=dict(
                            title='成功率 (%)',
                            overlaying='y',
                            side='right',
                            range=[0, 100],
                            ticksuffix='%'
                        ),
                        margin=dict(l=10, r=50, b=10, t=50),
                        legend=dict(
                            orientation="h",
                            xanchor="right",
                            x=1.0,
                            yanchor="top",
                            y=1.0
                        ),
                        title_text='每月安装量与成功率',
                        title_y=0.95,
                        title_x=0.5,
                        title_xanchor='center',
                        title_yanchor='top'
                    )
                    
                    st.plotly_chart(fig_monthly, use_container_width=True)
                else:
                    st.info("暂无每月安装数据")
    else:
        st.warning("无法获取统计数据。请确保后端API正在运行。")
        if st.button("尝试重新连接"):
            st.experimental_rerun()

    # 显示最近会话
    st.subheader("最近安装会话")

    # 更新会话状态筛选器 - 使用水平单选按钮替代多选框
    status_options = ["全部", "成功", "失败"]
    session_status_filter = st.radio(
        "会话状态筛选:",
        options=status_options,
        index=0,
        horizontal=True,
        help="选择需要查看的会话状态类型"
    )
    
    # 简化状态筛选逻辑
    active_status_filter = None
    if session_status_filter != "全部":
        active_status_filter = session_status_filter
    
    # 获取筛选后的会话数据
    recent_sessions = get_recent_sessions(20, start_date, active_status_filter)

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

with tab_user:

    start_date = filter_by_date(date_filter)

    # 显示当前筛选器状态
    if date_filter != "全部":
        st.info(f"当前显示: {date_filter}的数据")

    display_user_analysis(start_date)

# 页脚
st.markdown("---")
st.markdown("OpenHands-Starter Telemetry Dashboard -- Designed By Polly | © 2025")