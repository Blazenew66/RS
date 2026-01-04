"""
Streamlit Web 应用：美股 RS 排名系统（专业版）
"""
import sys
import os

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from rs_system.market_ranking import get_combined_index_tickers, calculate_market_wide_rs_ranking
from rs_system.rs_calculator import RSCalculator
from rs_system.indicators import (
    calculate_sma50_distance, 
    calculate_rs_trend, 
    calculate_volume_surge,
    check_rs_line_52w_high,
    is_leader_stock
)
from rs_system.rs_history import calculate_rs_1w_ago
from rs_system.data_fetcher import DataFetcher
from rs_system.config import MARKET_BENCHMARK, DEFAULT_TICKERS
import time
import logging

# 配置日志
logging.basicConfig(level=logging.WARNING)

# 页面配置（必须在所有 Streamlit 命令之前）
st.set_page_config(
    page_title="RS Ranking Pro | 美股相对强度排名系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 样式（美化界面）
st.markdown("""
<style>
    /* 主标题样式 */
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    /* 卡片样式 */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
    }
    
    /* 表格样式 */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        font-size: 1.1rem !important;
    }
    
    /* 表格单元格内容居中 */
    .dataframe td, .dataframe th {
        text-align: center !important;
        vertical-align: middle !important;
        font-size: 1.1rem !important;
        padding: 0.75rem !important;
    }
    
    /* 表格数字样式 */
    .dataframe tbody td {
        font-size: 1.15rem !important;
        font-weight: 500 !important;
    }
    
    /* RS Rating 高亮样式 */
    .rs-high {
        background-color: #10b981;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
    }
    
    .rs-medium {
        background-color: #f59e0b;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
    }
    
    .rs-low {
        background-color: #ef4444;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
    }
    
    .rs-new-high {
        border: 3px solid #3b82f6 !important;
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5) !important;
    }
    
    /* 侧边栏样式 */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    /* 按钮样式 */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* 统计卡片 */
    [data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
    }
    
    /* 整体字体增大 */
    .stMarkdown, .stText, .stDataFrame {
        font-size: 1.1rem !important;
    }
    
    /* 标题字体 */
    h1, h2, h3 {
        font-size: 2.5rem !important;
    }
    
    h2 {
        font-size: 2rem !important;
    }
    
    h3 {
        font-size: 1.5rem !important;
    }
    
    /* 表格行悬停效果 */
    .dataframe tbody tr:hover {
        background-color: #f3f4f6;
    }
</style>
""", unsafe_allow_html=True)

# 主标题
st.markdown('<h1 class="main-title">📈 RS Ranking Pro</h1>', unsafe_allow_html=True)
st.markdown("**专业级 IBD 风格相对强度排名系统 | 基于 S&P 500 + NASDAQ 100 + Russell 1000 市场范围分析**")

# 缓存装饰器
@st.cache_data(ttl=3600)
def get_cached_combined_tickers():
    """获取并缓存整合指数股票列表（S&P 500 + NASDAQ 100 + Russell 1000）"""
    return get_combined_index_tickers()

# 侧边栏配置
with st.sidebar:
    st.markdown("### ⚙️ 配置面板")
    
    # 市场数据更新
    st.markdown("#### 📊 市场数据")
    update_market_data = st.button("🔄 更新市场数据", use_container_width=True)
    if update_market_data:
        st.cache_data.clear()
        st.success("✅ 缓存已清除")
    
    st.markdown("---")
    
    # 股票列表选择
    st.markdown("#### 📋 股票列表")
    use_default = st.checkbox("使用默认股票列表", value=True)
    
    if not use_default:
        ticker_input = st.text_input(
            "输入股票代码（空格分隔）",
            value="AAPL MSFT GOOGL AMZN TSLA",
            help="例如: AAPL MSFT GOOGL"
        )
        if ticker_input and ticker_input.strip():
            tickers = [t.strip().upper() for t in ticker_input.split() if t.strip()]
        else:
            tickers = []
    else:
        tickers = DEFAULT_TICKERS.copy()
    
    st.markdown("---")
    
    # 过滤器
    st.markdown("#### 🔍 过滤器")
    show_only_leaders = st.checkbox(
        "仅显示领导者股票",
        value=False,
        help="筛选条件：\n• Price > 50-day SMA\n• 50-day SMA > 200-day SMA\n• RS Rating > 80"
    )
    
    st.markdown("---")
    
    # 说明
    st.markdown("#### ℹ️ 系统说明")
    st.markdown("""
    **计算方法：**
    - 市场范围排名（S&P 500 + NASDAQ 100 + Russell 1000）
    - IBD 风格加权 RS
    - Adjusted Close 价格
    
    **权重配置：**
    - 3个月：40%
    - 6/9/12个月：各20%
    
    **RS线创新高：**
    - 🔥 表示 RS Line 达到 252 日高点
    """)
    
    # 执行按钮
    run_button = st.button("🚀 开始分析", type="primary", use_container_width=True)

# 主内容区
if run_button:
    if not use_default and (not tickers or len(tickers) == 0):
        st.error("❌ 请至少输入一个股票代码")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            with st.spinner("正在计算市场范围 RS 排名..."):
                # 步骤1: 获取整合指数列表（S&P 500 + NASDAQ 100 + Russell 1000）
                status_text.text("📥 获取市场股票列表（S&P 500 + NASDAQ 100 + Russell 1000）...")
                progress_bar.progress(10)
                market_tickers = get_cached_combined_tickers()
                
                if not market_tickers or len(market_tickers) < 100:
                    st.error(f"❌ 无法获取足够的市场股票列表（当前：{len(market_tickers) if market_tickers else 0} 只）")
                    st.stop()
                
                # 步骤2: 计算市场范围排名
                status_text.text(f"📊 计算市场范围排名（基于 {len(market_tickers)} 只市场股票）...")
                progress_bar.progress(30)
                
                result = calculate_market_wide_rs_ranking(
                    user_tickers=tickers,
                    market_tickers=market_tickers,  # 使用全量股票（无限制）
                    use_cache=True,
                    max_workers=10  # 并行计算线程数
                )
                
                if isinstance(result, tuple):
                    rankings_df, market_rs_distribution = result
                else:
                    rankings_df = result
                    market_rs_distribution = []
                
                if rankings_df is None or rankings_df.empty:
                    st.error("❌ 未能计算出排名结果")
                    st.stop()
                
                # 步骤3: 计算额外指标
                status_text.text("🔧 计算技术指标（SMA50、RS Trend、Volume、RS Line 52W High、RS 1W Change）...")
                progress_bar.progress(50)
                
                fetcher = DataFetcher()
                market_benchmark = fetcher.fetch_single_ticker(MARKET_BENCHMARK)
                
                indicators_data = []
                for idx, row in rankings_df.iterrows():
                    ticker = row['ticker']
                    price_data = row.get('price_data')
                    rs_score = row['rs_score']
                    
                    if price_data is None:
                        continue
                    
                    # 计算所有指标
                    sma50_dist = calculate_sma50_distance(price_data)
                    
                    # 获取已计算的 rs_line_series（如果存在）
                    rs_line_series = row.get('rs_line')
                    
                    if market_benchmark is not None and not market_benchmark.empty:
                        rs_trend_slope, rs_trend_arrow = calculate_rs_trend(price_data, market_benchmark)
                        # 使用已计算的 rs_line_series（如果存在），否则从价格数据计算
                        rs_line_52w_high = check_rs_line_52w_high(
                            stock_price_data=price_data,
                            market_price_data=market_benchmark,
                            rs_line_series=rs_line_series if isinstance(rs_line_series, pd.Series) else None
                        )
                    else:
                        rs_trend_slope, rs_trend_arrow = None, "→"
                        rs_line_52w_high = False
                    
                    volume_surge = calculate_volume_surge(price_data)
                    is_leader = is_leader_stock(price_data, rs_score)
                    
                    # 计算1周前 RS Rating
                    rs_1w_ago = None
                    if market_benchmark is not None and len(market_rs_distribution) > 0:
                        try:
                            rs_1w_ago = calculate_rs_1w_ago(
                                ticker, price_data, market_rs_distribution, market_benchmark
                            )
                        except:
                            pass
                    
                    indicators_data.append({
                        'ticker': ticker,
                        'sma50_dist': sma50_dist,
                        'rs_trend_arrow': rs_trend_arrow,
                        'volume_surge': volume_surge,
                        'rs_line_52w_high': rs_line_52w_high,
                        'is_leader': is_leader,
                        'rs_1w_ago': rs_1w_ago,
                        'price_data': price_data
                    })
                
                # 合并指标数据
                indicators_df = pd.DataFrame(indicators_data)
                if not indicators_df.empty:
                    rankings_df = rankings_df.merge(
                        indicators_df[['ticker', 'sma50_dist', 'rs_trend_arrow', 'volume_surge', 
                                      'rs_line_52w_high', 'is_leader', 'rs_1w_ago']],
                        on='ticker',
                        how='left'
                    )
                    price_data_dict = dict(zip(indicators_df['ticker'], indicators_df['price_data']))
                    rankings_df['price_data'] = rankings_df['ticker'].map(price_data_dict)
                
                # 应用过滤器
                if show_only_leaders:
                    rankings_df = rankings_df[rankings_df['is_leader'] == True].copy()
                    if rankings_df.empty:
                        st.warning("⚠️ 没有股票符合领导者条件")
                        st.stop()
            
            # with st.spinner 块结束，开始显示结果
            progress_bar.progress(100)
            status_text.text("✅ 计算完成！")
            time.sleep(0.5)

            progress_bar.empty()
            status_text.empty()

            # 成功提示
            st.success(f"✅ 成功分析 {len(rankings_df)} 只股票（基于 S&P 500 + NASDAQ 100 + Russell 1000 市场分布）")
            
            # 统计信息卡片（美化）
            st.markdown("---")
            st.markdown("### 📊 市场概览")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("总股票数", len(rankings_df), delta=None)
            with col2:
                st.metric("最高 RS", f"{rankings_df['rs_score'].max():.0f}", delta=None)
            with col3:
                st.metric("平均 RS", f"{rankings_df['rs_score'].mean():.1f}", delta=None)
            with col4:
                rs_80_plus = len(rankings_df[rankings_df['rs_score'] >= 80])
                st.metric("RS 80+", rs_80_plus, delta=None)
            with col5:
                leaders_count = len(rankings_df[rankings_df.get('is_leader', False) == True])
                st.metric("领导者", leaders_count, delta=None)
            
            # 准备显示数据
            display_df = rankings_df.copy()
            
            # RS Rating 显示（带颜色和252日新高标记🔥）
            def format_rs_rating(score, is_52w_high):
                if score >= 80:
                    color_class = "rs-high"
                    emoji = "🟢"
                elif score >= 70:
                    color_class = "rs-medium"
                    emoji = "🟡"
                else:
                    color_class = "rs-low"
                    emoji = "🔴"
                
                # 使用🔥标记252日新高
                high_mark = " 🔥" if is_52w_high else ""
                return f"{emoji} {score:.0f}{high_mark}"
            
            display_df['rs_rating_display'] = display_df.apply(
                lambda row: format_rs_rating(
                    row['rs_score'], 
                    row.get('rs_line_52w_high', False)
                ), axis=1
            )
            
            # RS 1周变化
            def format_rs_1w_change(rs_current, rs_1w_ago):
                if pd.isna(rs_1w_ago) or rs_1w_ago is None:
                    return "N/A"
                change = rs_current - rs_1w_ago
                if change > 0:
                    return f"⬆️ +{change:.0f}"
                elif change < 0:
                    return f"⬇️ {change:.0f}"
                else:
                    return "→ 0"
            
            display_df['rs_1w_change'] = display_df.apply(
                lambda row: format_rs_1w_change(
                    row['rs_score'],
                    row.get('rs_1w_ago')
                ), axis=1
            )
            
            # 格式化其他列
            display_df['sma50_display'] = display_df['sma50_dist'].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A"
            )
            display_df['rs_trend_display'] = display_df['rs_trend_arrow'].fillna("→")
            display_df['volume_display'] = display_df['volume_surge'].apply(
                lambda x: f"{x:.2f}x" if pd.notna(x) else "N/A"
            )
            
            # 按 RS Rating 降序排列
            display_df = display_df.sort_values('rs_score', ascending=False).reset_index(drop=True)
            
            # 显示数据表格
            st.markdown("---")
            st.markdown("### 📈 RS 排名表格（按 RS Rating 降序排列）")
            
            # 表格列
            table_cols = ['ticker', 'rs_rating_display', 'rs_1w_change', 'sma50_display', 
                         'rs_trend_display', 'volume_display']
            table_cols = [col for col in table_cols if col in display_df.columns]
            
            st_df = display_df[table_cols].copy()
            st_df.columns = ['股票代码', 'RS Rating', 'RS 1W Change', 'Price vs SMA50', 
                            'RS Trend', 'Volume Surge']
            
            # 使用 st.dataframe 显示（带样式）
            st.dataframe(
                st_df,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # 说明：252日新高标记
            if display_df['rs_line_52w_high'].any():
                st.info("🔥 标记表示 RS Line 达到 252 日高点（创新高）")
            
            # 股票图表选择
            st.markdown("---")
            st.markdown("### 📊 股票图表分析")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                selected_ticker = st.selectbox(
                    "选择股票",
                    rankings_df['ticker'].tolist(),
                    index=0,
                    label_visibility="collapsed"
                )
            
            # 显示选中股票的关键指标
            if selected_ticker:
                selected_row = rankings_df[rankings_df['ticker'] == selected_ticker].iloc[0]
                selected_price_data = selected_row.get('price_data')
                
                # 关键指标卡片
                with col2:
                    metric_cols = st.columns(4)
                    with metric_cols[0]:
                        st.metric("RS Rating", f"{selected_row['rs_score']:.0f}")
                    with metric_cols[1]:
                        sma50_val = selected_row.get('sma50_dist', 0)
                        st.metric("vs SMA50", f"{sma50_val:+.1f}%" if pd.notna(sma50_val) else "N/A")
                    with metric_cols[2]:
                        volume_val = selected_row.get('volume_surge', 0)
                        st.metric("Volume", f"{volume_val:.2f}x" if pd.notna(volume_val) else "N/A")
                    with metric_cols[3]:
                        is_52w = selected_row.get('rs_line_52w_high', False)
                        st.metric("52W High", "✅" if is_52w else "❌")
                
                # 图表
                if selected_price_data is not None and market_benchmark is not None:
                    rs_line = None
                    stock_prices = None
                    
                    # 优先使用已计算的 rs_line_series
                    rs_line_series = selected_row.get('rs_line')
                    
                    # 类型检查：处理向后兼容（旧版本可能是单个数值）
                    if isinstance(rs_line_series, pd.Series) and len(rs_line_series) > 0:
                        # 使用已计算的 RS Line 序列（新版本格式）
                        rs_line = rs_line_series.sort_index()
                        
                        # 获取对应的股票价格用于归一化
                        if 'Date' in selected_price_data.columns:
                            stock_df = selected_price_data.set_index('Date')
                        else:
                            stock_df = selected_price_data.copy()
                        
                        stock_col = 'Adj Close' if 'Adj Close' in stock_df.columns else 'Close'
                        stock_prices = stock_df[stock_col].dropna()
                        
                        # 对齐日期
                        common_dates = stock_prices.index.intersection(rs_line.index)
                        if len(common_dates) > 0:
                            stock_prices = stock_prices.loc[common_dates].sort_index()
                            rs_line = rs_line.loc[common_dates].sort_index()
                        else:
                            rs_line = None
                    elif isinstance(rs_line_series, (int, float, np.number)):
                        # 向后兼容：如果是单个数值（旧版本数据），触发重新计算
                        rs_line_series = None  # 触发后续的重新计算
                        rs_line = None
                    else:
                        # 其他情况（None、空等），触发重新计算
                        rs_line = None
                    
                    # 如果没有 rs_line_series 或对齐失败，从价格数据计算
                    if rs_line is None or len(rs_line) == 0:
                        if 'Date' in selected_price_data.columns:
                            stock_df = selected_price_data.set_index('Date')
                        else:
                            stock_df = selected_price_data.copy()
                        
                        if 'Date' in market_benchmark.columns:
                            market_df = market_benchmark.set_index('Date')
                        else:
                            market_df = market_benchmark.copy()
                        
                        stock_col = 'Adj Close' if 'Adj Close' in stock_df.columns else 'Close'
                        market_col = 'Adj Close' if 'Adj Close' in market_df.columns else 'Close'
                        
                        stock_prices = stock_df[stock_col].dropna()
                        market_prices = market_df[market_col].dropna()
                        
                        common_dates = stock_prices.index.intersection(market_prices.index)
                        if len(common_dates) > 0:
                            stock_prices = stock_prices.loc[common_dates].sort_index()
                            market_prices = market_prices.loc[common_dates].sort_index()
                            rs_line = stock_prices / market_prices
                    
                    if rs_line is not None and len(rs_line) > 0 and stock_prices is not None and len(stock_prices) > 0:
                        stock_normalized = (stock_prices / stock_prices.iloc[0]) * 100
                        rs_line_normalized = (rs_line / rs_line.iloc[0]) * 100
                        
                        one_year_ago = rs_line.index[-252] if len(rs_line) > 252 else rs_line.index[0]
                        stock_normalized = stock_normalized.loc[one_year_ago:]
                        rs_line_normalized = rs_line_normalized.loc[one_year_ago:]
                        
                        # 创建图表
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        fig.add_trace(
                            go.Scatter(
                                x=stock_normalized.index,
                                y=stock_normalized.values,
                                name=f"{selected_ticker} 价格",
                                line=dict(color='#667eea', width=2.5),
                                fill='tozeroy',
                                fillcolor='rgba(102, 126, 234, 0.1)'
                            ),
                            secondary_y=False,
                        )
                        
                        fig.add_trace(
                            go.Scatter(
                                x=rs_line_normalized.index,
                                y=rs_line_normalized.values,
                                name="RS Line",
                                line=dict(color='#ef4444', width=2, dash='dash')
                            ),
                            secondary_y=True,
                        )
                        
                        fig.update_xaxes(title_text="日期", showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                        fig.update_yaxes(title_text="价格（归一化 %）", secondary_y=False, showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                        fig.update_yaxes(title_text="RS Line（归一化 %）", secondary_y=True, showgrid=False)
                        
                        fig.update_layout(
                            title=f"{selected_ticker} - 价格与相对强度趋势分析",
                            height=500,
                            hovermode='x unified',
                            template='plotly_white',
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
            
            # 下载 CSV
            st.markdown("---")
            csv_df = rankings_df[['ticker', 'rs_raw', 'rs_score', 'rank']].copy()
            if 'sma50_dist' in rankings_df.columns:
                csv_df['sma50_dist'] = rankings_df['sma50_dist']
            if 'volume_surge' in rankings_df.columns:
                csv_df['volume_surge'] = rankings_df['volume_surge']
            if 'rs_1w_ago' in rankings_df.columns:
                csv_df['rs_1w_change'] = rankings_df['rs_score'] - rankings_df['rs_1w_ago'].fillna(rankings_df['rs_score'])
            
            csv = csv_df.to_csv(index=False)
            st.download_button(
                label="📥 下载完整数据 (CSV)",
                data=csv,
                file_name=f"rs_rankings_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
                
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ 发生错误: {str(e)}")
            with st.expander("查看详细错误信息"):
                st.exception(e)

else:
    # 初始状态 - 美化欢迎页面
    st.markdown("---")
    
    # 欢迎卡片
    welcome_col1, welcome_col2 = st.columns([2, 1])
    
    with welcome_col1:
        st.markdown("""
        ### 🎯 系统简介
        
        **RS Ranking Pro** 是一个专业级的相对强度排名系统，基于 IBD (Investor's Business Daily) 的经典方法。
        
        #### ✨ 核心功能
        
        - **📊 市场范围排名**: 基于 S&P 500 分布计算百分位排名（1-99分），确保评分的市场意义
        - **⚖️ IBD 加权计算**: 3个月40%，6/9/12个月各20%，使用 Adjusted Close 价格
        - **🔍 技术指标分析**: SMA50距离、RS Trend、Volume Surge
        - **📈 52周新高检测**: 自动识别 RS Line 达到52周新高的股票（蓝色标记）
        - **📉 1周变化追踪**: 显示 RS Rating 的周变化，捕捉突破机会
        - **🎯 领导者筛选**: 一键筛选符合所有趋势条件的优质股票
        
        #### 🚀 快速开始
        
        1. 在左侧选择股票列表（默认或自定义）
        2. 可选择启用"仅显示领导者股票"过滤器
        3. 点击"开始分析"按钮
        4. 查看排名结果和技术指标
        5. 选择股票查看详细图表分析
        """)
    
    with welcome_col2:
        st.markdown("""
        ### 📋 默认股票列表
        
        """)
        st.write(f"**共 {len(DEFAULT_TICKERS)} 只股票**")
        cols = st.columns(3)
        for i, ticker in enumerate(DEFAULT_TICKERS):
            with cols[i % 3]:
                st.code(ticker, language=None)
    
    st.markdown("---")
    
    # 功能特点展示
    st.markdown("### 💡 功能特点")
    
    feature_cols = st.columns(3)
    
    with feature_cols[0]:
        st.markdown("""
        #### 🎯 市场范围排名
        - 基于 S&P 500 分布
        - 百分位排名（1-99）
        - 真实市场意义
        """)
    
    with feature_cols[1]:
        st.markdown("""
        #### 📊 技术指标
        - Price vs SMA50
        - RS Trend 趋势
        - Volume Surge
        - 52周新高检测
        """)
    
    with feature_cols[2]:
        st.markdown("""
        #### 🔍 智能筛选
        - 领导者股票筛选
        - RS 1周变化追踪
        - 突破机会识别
        """)
    
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p>💡 <strong>提示</strong>: 首次运行需要获取 S&P 500 数据，可能需要几分钟时间</p>
        <p>数据会自动缓存 1 小时，可手动点击"更新市场数据"刷新</p>
    </div>
    """, unsafe_allow_html=True)
