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
    is_leader_stock,
    calculate_trend_strength_score,
    calculate_volatility_contraction,
    is_stage2_trend,
    calculate_avg_dollar_volume,
    calculate_atr_pct,
    calculate_price_52w_distance,
)
from rs_system.rs_history import calculate_rs_1w_ago
from rs_system.data_fetcher import DataFetcher
from rs_system.config import MARKET_BENCHMARK
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
    
    # 过滤器
    st.markdown("#### 🔍 过滤器")
    show_only_leaders = st.checkbox(
        "仅显示领导者股票",
        value=False,
        help="筛选条件：\n• Price > 50-day SMA\n• 50-day SMA > 200-day SMA\n• RS Rating > 80"
    )
    show_only_stage2 = st.checkbox(
        "仅显示第二阶段趋势（强化版）",
        value=False,
        help="筛选条件：\n• Price > SMA50 > SMA150 > SMA200\n• SMA50 至少高于 SMA200 约 15%\n• 最近约 6 个月最大回撤不超过约 30%"
    )
    
    st.markdown("---")
    
    st.markdown("#### 📊 流动性与风险过滤")
    min_dollar_volume_m = st.slider(
        "最小日均成交额（最近 50 日，单位：百万美元）",
        min_value=0.0,
        max_value=50.0,
        value=2.0,
        step=0.5,
        help="按最近 50 日平均成交额过滤，建议 ≥ 2M，保证流动性。"
    )
    max_atr_pct = st.slider(
        "最大日波动率 ATR%（14 日）",
        min_value=0.0,
        max_value=20.0,
        value=10.0,
        step=0.5,
        help="ATR(14) / Close * 100，过滤日内波动过大的标的，便于持仓。0 表示不过滤。"
    )
    
    only_near_52w_high = st.checkbox(
        "仅显示价格接近 52 周新高且 RS 线创新高的股票",
        value=False,
        help="筛选条件：\n• 当前价格距离 52 周高点不超过约 5%\n• RS Line 为 52 周新高（🔥）"
    )
    
    st.markdown("---")
    
    # 说明
    st.markdown("#### ℹ️ 系统说明")
    st.markdown("""
    **自动分析：**
    - 系统自动获取市场基准股票（S&P 500 + NASDAQ 100 + Russell 1000）
    - 计算所有股票的 IBD 风格 RS Rating（1-99分）
    - 基于市场分布进行百分位排名
    
    **计算方法：**
    - IBD 风格加权 RS
    - Adjusted Close 价格
    - 权重：3个月40%，6/9/12个月各20%
    
    **RS线创新高：**
    - 🔥 表示 RS Line 达到 252 日高点
    """)
    
    # 执行按钮
    run_button = st.button("🚀 开始分析", type="primary", use_container_width=True)

# 主内容区
if run_button:
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
            
            # 步骤2: 计算市场范围排名（直接使用市场股票列表作为分析目标）
            status_text.text(f"📊 计算市场范围排名（分析 {len(market_tickers)} 只市场股票，使用缓存加速）...")
            progress_bar.progress(30)
            
            # 创建进度回调函数（用于在计算过程中更新进度）
            def update_progress_callback(current, total, stage=""):
                if total > 0:
                    progress = 30 + int((current / total) * 15)  # 30-45% 用于市场RS计算
                    progress_bar.progress(progress)
                    if stage:
                        status_text.text(f"📊 {stage} ({current}/{total})")
            
            result = calculate_market_wide_rs_ranking(
                user_tickers=market_tickers,  # 直接使用市场股票列表作为分析目标
                market_tickers=market_tickers,  # 使用相同的股票列表建立分布
                use_cache=True,
                max_workers=4  # 并行计算线程数（避免对数据源请求过于密集）
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
            status_text.text("🔧 计算技术指标（SMA50、RS Trend、Volume、RS Line 52W High、RS 1W Change、趋势强度、波动率收缩）...")
            progress_bar.progress(50)
            
            fetcher = DataFetcher()
            market_benchmark = fetcher.fetch_single_ticker(MARKET_BENCHMARK)
            
            indicators_data = []
            total_stocks = len(rankings_df)
            
            for idx, row in rankings_df.iterrows():
                # 更新进度
                if (idx + 1) % 50 == 0:
                    progress = 50 + int((idx + 1) / total_stocks * 40)
                    progress_bar.progress(progress)
                    status_text.text(f"🔧 计算技术指标... ({idx + 1}/{total_stocks})")
                
                ticker = row['ticker']
                price_data = row.get('price_data')
                rs_score = row['rs_score']
                
                if price_data is None:
                    continue
                
                # 当前价格（用于展示）
                try:
                    price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
                    last_price = float(price_data[price_col].dropna().iloc[-1])
                except Exception:
                    last_price = None
                
                # 行业 / 板块信息（通过 DataFetcher 获取一次元数据）
                sector = None
                industry = None
                try:
                    meta = fetcher.fetch_metadata(ticker)
                    if isinstance(meta, dict):
                        sector = meta.get("sector")
                        industry = meta.get("industry")
                except Exception:
                    pass
                
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
                
                # 新增指标
                trend_strength = calculate_trend_strength_score(price_data)
                volatility_contraction = calculate_volatility_contraction(price_data, days=10)
                is_stage2 = is_stage2_trend(price_data)
                
                # 流动性与风险指标
                avg_dollar_volume = calculate_avg_dollar_volume(price_data, days=50)
                atr_pct = calculate_atr_pct(price_data, period=14)
                price_52w_distance = calculate_price_52w_distance(price_data)
                
                # 价格是否接近 52 周新高（距离 ≤ 5%）
                near_52w_high = (
                    price_52w_distance is not None 
                    and not pd.isna(price_52w_distance) 
                    and price_52w_distance <= 5.0
                )
                
                # 简单“突破候选”：波动率收缩 + 接近新高 + 放量
                breakout_candidate = (
                    volatility_contraction is not None
                    and volatility_contraction <= 15.0  # 最近 10 日波幅不大
                    and near_52w_high
                    and volume_surge is not None
                    and volume_surge >= 1.5
                )
                
                # 计算1周前 RS Rating
                rs_1w_ago = None
                if market_benchmark is not None and len(market_rs_distribution) > 0:
                    try:
                        rs_1w_ago = calculate_rs_1w_ago(
                            ticker, price_data, market_rs_distribution, market_benchmark
                        )
                    except:
                        pass
                
                # 综合评分（RS + 趋势强度），用于排序和精细筛选
                if trend_strength is not None and not pd.isna(trend_strength):
                    composite_score = 0.6 * rs_score + 0.4 * float(trend_strength)
                else:
                    composite_score = float(rs_score)
                
                indicators_data.append({
                    'ticker': ticker,
                    'last_price': last_price,
                    'sector': sector,
                    'industry': industry,
                    'sma50_dist': sma50_dist,
                    'rs_trend_arrow': rs_trend_arrow,
                    'volume_surge': volume_surge,
                    'rs_line_52w_high': rs_line_52w_high,
                    'is_leader': is_leader,
                    'is_stage2': is_stage2,
                    'trend_strength': trend_strength,
                    'volatility_contraction': volatility_contraction,
                    'avg_dollar_volume': avg_dollar_volume,
                    'atr_pct': atr_pct,
                    'price_52w_distance': price_52w_distance,
                    'near_52w_high': near_52w_high,
                    'breakout_candidate': breakout_candidate,
                    'composite_score': composite_score,
                    'rs_1w_ago': rs_1w_ago,
                    'price_data': price_data
                })
            
            # 合并指标数据
            indicators_df = pd.DataFrame(indicators_data)
            if not indicators_df.empty:
                rankings_df = rankings_df.merge(
                    indicators_df[['ticker', 'last_price', 'sector', 'industry',
                                  'sma50_dist', 'rs_trend_arrow', 'volume_surge', 
                                  'rs_line_52w_high', 'is_leader', 'is_stage2', 
                                  'trend_strength', 'volatility_contraction',
                                  'avg_dollar_volume', 'atr_pct', 'price_52w_distance',
                                  'near_52w_high', 'breakout_candidate',
                                  'composite_score', 'rs_1w_ago']],
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
            
            if show_only_stage2:
                rankings_df = rankings_df[rankings_df['is_stage2'] == True].copy()
                if rankings_df.empty:
                    st.warning("⚠️ 没有股票符合第二阶段趋势条件")
                    st.stop()
            
            # 流动性过滤：日均成交额（美元）
            if 'avg_dollar_volume' in rankings_df.columns and min_dollar_volume_m > 0:
                min_dollar_volume = min_dollar_volume_m * 1_000_000
                rankings_df = rankings_df[
                    (rankings_df['avg_dollar_volume'].notna()) &
                    (rankings_df['avg_dollar_volume'] >= min_dollar_volume)
                ].copy()
                if rankings_df.empty:
                    st.warning("⚠️ 按成交额过滤后，没有符合条件的股票（可以降低“最小日均成交额”阈值重试）")
                    st.stop()
            
            # 波动率过滤：ATR 百分比
            if 'atr_pct' in rankings_df.columns and max_atr_pct > 0:
                rankings_df = rankings_df[
                    (rankings_df['atr_pct'].isna()) |  # 缺数据的保留
                    (rankings_df['atr_pct'] <= max_atr_pct)
                ].copy()
                if rankings_df.empty:
                    st.warning("⚠️ 按 ATR 波动率过滤后，没有符合条件的股票（可以放宽 ATR% 阈值重试）")
                    st.stop()
            
            # 价格 + RS 同步新高过滤
            if only_near_52w_high and 'price_52w_distance' in rankings_df.columns:
                rankings_df = rankings_df[
                    (rankings_df['price_52w_distance'].notna()) &
                    (rankings_df['price_52w_distance'] <= 5.0) &
                    (rankings_df['rs_line_52w_high'] == True)
                ].copy()
                if rankings_df.empty:
                    st.warning("⚠️ 没有股票同时满足“价格接近 52 周新高 + RS 线新高”的条件")
                    st.stop()
        
            # with st.spinner 块结束，开始显示结果
            progress_bar.progress(100)
            status_text.text("✅ 计算完成！")
            time.sleep(0.5)

            progress_bar.empty()
            status_text.empty()

            # 成功提示
            st.success(f"✅ 成功分析 {len(rankings_df)} 只市场基准股票（S&P 500 + NASDAQ 100 + Russell 1000）")
            
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
            # 价格显示
            if 'last_price' in display_df.columns:
                display_df['price_display'] = display_df['last_price'].apply(
                    lambda x: f"${x:.2f}" if pd.notna(x) else "N/A"
                )
            display_df['sma50_display'] = display_df['sma50_dist'].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A"
            )
            display_df['rs_trend_display'] = display_df['rs_trend_arrow'].fillna("→")
            display_df['volume_display'] = display_df['volume_surge'].apply(
                lambda x: f"{x:.2f}x" if pd.notna(x) else "N/A"
            )
            
            # 格式化新指标
            display_df['trend_strength_display'] = display_df['trend_strength'].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
            )
            display_df['volatility_display'] = display_df['volatility_contraction'].apply(
                lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
            )
            # 综合评分显示
            if 'composite_score' in display_df.columns:
                display_df['composite_display'] = display_df['composite_score'].apply(
                    lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
                )
            
            # 按综合评分（或 RS）降序排列
            if 'composite_score' in display_df.columns:
                display_df = display_df.sort_values(
                    ['composite_score', 'rs_score'],
                    ascending=[False, False]
                ).reset_index(drop=True)
            else:
                display_df = display_df.sort_values('rs_score', ascending=False).reset_index(drop=True)
            
            # 显示数据表格
            st.markdown("---")
            st.markdown("### 📈 RS 排名表格（按 RS Rating 降序排列）")
            
            # 表格列（添加新列）
            table_cols = ['ticker', 'price_display', 'sector', 'industry',
                         'rs_rating_display', 'rs_1w_change', 'sma50_display', 
                         'rs_trend_display', 'volume_display', 'trend_strength_display',
                         'volatility_display', 'composite_display']
            table_cols = [col for col in table_cols if col in display_df.columns]
            
            st_df = display_df[table_cols].copy()
            # 更新列名（包含新列）
            column_mapping = {
                'ticker': '股票代码',
                'price_display': '股价',
                'sector': '行业',
                'industry': '细分板块',
                'rs_rating_display': 'RS Rating',
                'rs_1w_change': 'RS 1W Change',
                'sma50_display': 'Price vs SMA50',
                'rs_trend_display': 'RS Trend',
                'volume_display': 'Volume Surge',
                'trend_strength_display': '趋势强度',
                'volatility_display': '波动率收缩',
                'composite_display': '综合评分'
            }
            st_df.columns = [column_mapping.get(col, col) for col in st_df.columns]
            
            # 使用 st.dataframe 显示表格
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
        
        - **📊 自动市场分析**: 自动获取并分析 S&P 500 + NASDAQ 100 + Russell 1000 市场基准股票（800-1000只）
        - **⚖️ IBD 加权计算**: 3个月40%，6/9/12个月各20%，使用 Adjusted Close 价格
        - **🔍 技术指标分析**: SMA50距离、RS Trend、Volume Surge
        - **📈 52周新高检测**: 自动识别 RS Line 达到252日新高的股票（🔥标记）
        - **📉 1周变化追踪**: 显示 RS Rating 的周变化，捕捉突破机会
        - **🎯 领导者筛选**: 一键筛选符合所有趋势条件的优质股票
        
        #### 🚀 快速开始
        
        1. 点击"开始分析"按钮
        2. 系统自动获取市场基准股票列表（S&P 500 + NASDAQ 100 + Russell 1000）
        3. 计算所有股票的 IBD RS Rating（1-99分）
        4. 查看完整排名结果和技术指标
        5. 可选择启用"仅显示领导者股票"过滤器
        6. 选择股票查看详细图表分析
        """)
    
    with welcome_col2:
        st.markdown("""
        ### 📋 市场基准范围
        
        **自动分析股票池：**
        - S&P 500 成分股
        - NASDAQ 100 成分股  
        - Russell 1000 成分股
        
        **总计：800-1000 只股票（至少800只，最多1000只）**
        
        *系统会自动去重并整合这些指数成分股，建立完整的市场分布基准。*
        """)
    
    st.markdown("---")
    
    # 功能特点展示
    st.markdown("### 💡 功能特点")
    
    feature_cols = st.columns(3)
    
    with feature_cols[0]:
        st.markdown("""
        #### 🎯 自动市场分析
        - 自动获取 800-1000 只市场基准股票（至少800只，最多1000只）
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
        <p>💡 <strong>提示</strong>: 首次运行需要获取 800-1000 只市场基准股票数据，可能需要几分钟时间</p>
        <p>数据会自动缓存 24 小时，可手动点击"更新市场数据"刷新</p>
        <p>系统使用并行计算和本地缓存，确保快速响应</p>
    </div>
    """, unsafe_allow_html=True)
