"""
Streamlit Web 应用：美股 RS 排名系统
"""
import streamlit as st
import pandas as pd
from rs_system.main import run_rs_ranking, load_ticker_list
from rs_system.config import DEFAULT_TICKERS, TOP_N_DISPLAY
import time
import logging

# 配置日志（Streamlit 中简化日志输出）
logging.basicConfig(level=logging.WARNING)

# 页面配置
st.set_page_config(
    page_title="美股 RS 排名系统",
    page_icon="📈",
    layout="wide"
)

st.title("📈 美股 RS 相对强度排名系统")
st.markdown("基于 IBD 风格的相对强度排名")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置选项")
    
    # 股票列表选择
    use_default = st.checkbox("使用默认股票列表", value=True)
    
    if not use_default:
        ticker_input = st.text_input(
            "输入股票代码（用空格分隔）",
            value="AAPL MSFT GOOGL AMZN TSLA",
            help="例如: AAPL MSFT GOOGL"
        )
        if ticker_input and ticker_input.strip():
            tickers = [t.strip().upper() for t in ticker_input.split() if t.strip()]
            if not tickers:
                st.warning("⚠️ 请输入至少一个股票代码")
        else:
            tickers = []
    else:
        tickers = None
    
    st.markdown("---")
    st.markdown("### 📊 说明")
    st.markdown("""
    - **RS 计算方法**: IBD 风格，相对于市场基准（SPY）的加权相对强度
    - **计算周期**: 过去 12 个月，近期权重更高（最近 3 个月权重 40%）
    - **排名分数**: 1-99 分（百分位排名）
    - **数据来源**: Yahoo Finance
    """)
    
    # 执行按钮
    run_button = st.button("🚀 开始计算", type="primary", use_container_width=True)

# 主内容区
if run_button:
    # 验证输入
    if not use_default and (not tickers or len(tickers) == 0):
        st.error("❌ 请至少输入一个股票代码")
    else:
        # 显示进度
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            with st.spinner("正在计算 RS 排名..."):
                status_text.text("正在获取股票数据...")
                progress_bar.progress(25)

                rankings_df = run_rs_ranking(
                    tickers=tickers,
                    save_csv=False,
                    print_report=False
                )

                if rankings_df is not None and not rankings_df.empty:
                    progress_bar.progress(100)
                    status_text.text("✅ 计算完成！")
                    time.sleep(0.5)

                    progress_bar.empty()
                    status_text.empty()

                    st.success(f"✅ 成功计算 {len(rankings_df)} 只股票的 RS 排名")

                    # 统计信息卡片
                    st.subheader("📈 统计信息")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("总股票数", len(rankings_df))
                    with col2:
                        st.metric("最高 RS 分数", f"{rankings_df['rs_score'].max():.1f}")
                    with col3:
                        st.metric("最低 RS 分数", f"{rankings_df['rs_score'].min():.1f}")
                    with col4:
                        st.metric("平均 RS 分数", f"{rankings_df['rs_score'].mean():.1f}")

                    # 显示 Top N
                    st.subheader(f"🏆 RS Top {TOP_N_DISPLAY}")
                    top_df = rankings_df.head(TOP_N_DISPLAY).copy()
                    # 格式化显示
                    top_df['rs_raw'] = top_df['rs_raw'].apply(lambda x: f"{x:.2f}")
                    top_df['rs_score'] = top_df['rs_score'].apply(lambda x: f"{x:.1f}")
                    if 'rs_line' in top_df.columns:
                        top_df['rs_line'] = top_df['rs_line'].apply(lambda x: f"{x:.4f}")
                    
                    display_cols = ['ticker', 'rs_raw', 'rs_score', 'rank']
                    if 'rs_line' in top_df.columns:
                        display_cols.insert(-1, 'rs_line')
                    
                    column_config = {
                        "ticker": "股票代码",
                        "rs_raw": "加权 RS",
                        "rs_score": "RS 分数",
                        "rank": "排名"
                    }
                    if 'rs_line' in top_df.columns:
                        column_config["rs_line"] = "RS Line"
                    
                    st.dataframe(
                        top_df[display_cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config=column_config
                    )

                    # 显示完整排名
                    with st.expander("📊 查看完整排名", expanded=False):
                        full_df = rankings_df.copy()
                        full_df['rs_raw'] = full_df['rs_raw'].apply(lambda x: f"{x:.2f}")
                        full_df['rs_score'] = full_df['rs_score'].apply(lambda x: f"{x:.1f}")
                        if 'rs_line' in full_df.columns:
                            full_df['rs_line'] = full_df['rs_line'].apply(lambda x: f"{x:.4f}")
                        
                        display_cols = ['ticker', 'rs_raw', 'rs_score', 'rank']
                        if 'rs_line' in full_df.columns:
                            display_cols.insert(-1, 'rs_line')
                        
                        column_config = {
                            "ticker": "股票代码",
                            "rs_raw": "加权 RS",
                            "rs_score": "RS 分数",
                            "rank": "排名"
                        }
                        if 'rs_line' in full_df.columns:
                            column_config["rs_line"] = "RS Line"
                        
                        st.dataframe(
                            full_df[display_cols],
                            use_container_width=True,
                            hide_index=True,
                            column_config=column_config
                        )

                    # 下载 CSV
                    csv = rankings_df.to_csv(index=False)
                    st.download_button(
                        label="📥 下载 CSV 文件",
                        data=csv,
                        file_name="rs_rankings.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    progress_bar.empty()
                    status_text.empty()
                    st.error("❌ 未能获取股票数据，请检查网络连接或稍后重试")
                    st.info("💡 提示：可能是网络问题或 Yahoo Finance 暂时不可用")
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ 发生错误: {str(e)}")
            with st.expander("查看详细错误信息"):
                st.exception(e)

else:
    # 初始状态显示说明
    st.info("👈 请在左侧配置选项，然后点击「开始计算」按钮")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📋 功能说明
        
        - **RS 计算**: IBD 风格，相对于市场基准（SPY）的加权相对强度
        - **加权机制**: 过去 12 个月，近期权重更高（最近 3 个月权重 40%）
        - **排名分数**: 1-99 分（百分位排名），分数越高表示相对强度越强
        - **RS Line**: 股价/市场基准比率，用于识别领先股票
        - **数据来源**: Yahoo Finance (yfinance)
        - **自动处理**: 缺失数据、异常值自动处理
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 使用步骤
        
        1. 选择股票列表（默认或自定义）
        2. 点击「开始计算」按钮
        3. 查看排名结果和统计信息
        4. 下载 CSV 文件（可选）
        
        ### ⚠️ 注意事项
        
        - 首次运行可能需要较长时间（获取数据）
        - 确保网络连接正常
        - 某些股票可能暂时无法获取数据
        """)
    
    # 显示默认股票列表
    with st.expander("📝 默认股票列表", expanded=False):
        st.write(f"共 {len(DEFAULT_TICKERS)} 只股票")
        cols = st.columns(5)
        for i, ticker in enumerate(DEFAULT_TICKERS):
            with cols[i % 5]:
                st.text(ticker)

