"""
市场环境判断模块
基于马克·米勒维尼的《超级绩效》方法
判断市场整体趋势和阶段
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def analyze_market_direction(
    market_data: pd.DataFrame,
    market_tickers: List[str],
    price_data_dict: Dict[str, pd.DataFrame] = None
) -> Dict:
    """
    分析市场整体方向和阶段
    
    Args:
        market_data: 市场基准数据（如SPY）
        market_tickers: 市场股票列表
        price_data_dict: 股票价格数据字典（可选，用于计算市场分布）
        
    Returns:
        市场环境分析结果
        {
            'market_stage': str,  # 'Bull Market', 'Bear Market', 'Correction', 'Uncertain'
            'market_trend': str,  # 'Up', 'Down', 'Sideways'
            'distribution_ratio': float,  # 上涨股票比例
            'spy_trend': str,  # SPY趋势
            'spy_above_sma200': bool,
            'spy_above_sma50': bool,
            'advance_decline_ratio': float,
            'recommendation': str  # 交易建议
        }
    """
    try:
        result = {
            'market_stage': 'Uncertain',
            'market_trend': 'Sideways',
            'distribution_ratio': 0.5,
            'spy_trend': 'Sideways',
            'spy_above_sma200': False,
            'spy_above_sma50': False,
            'advance_decline_ratio': 1.0,
            'recommendation': '谨慎交易'
        }
        
        # 1. 分析SPY趋势
        if market_data is not None and not market_data.empty:
            spy_analysis = analyze_spy_trend(market_data)
            result.update(spy_analysis)
        
        # 2. 分析市场分布（如果提供了股票数据）
        if price_data_dict and len(price_data_dict) > 0:
            distribution = calculate_market_distribution(price_data_dict)
            result['distribution_ratio'] = distribution.get('advance_ratio', 0.5)
            result['advance_decline_ratio'] = distribution.get('advance_decline_ratio', 1.0)
        
        # 3. 综合判断市场阶段
        market_stage = determine_market_stage(result)
        result['market_stage'] = market_stage
        
        # 4. 生成交易建议
        result['recommendation'] = generate_trading_recommendation(result)
        
        return result
        
    except Exception as e:
        logger.error(f"分析市场方向失败: {e}")
        return {
            'market_stage': 'Uncertain',
            'market_trend': 'Sideways',
            'recommendation': '数据不足，无法判断'
        }


def analyze_spy_trend(spy_data: pd.DataFrame) -> Dict:
    """
    分析SPY（市场基准）的趋势
    
    Args:
        spy_data: SPY价格数据
        
    Returns:
        SPY趋势分析结果
    """
    try:
        # 确保数据按日期排序
        if 'Date' in spy_data.columns:
            spy_data = spy_data.set_index('Date').sort_index()
        else:
            spy_data = spy_data.sort_index()
        
        price_col = 'Adj Close' if 'Adj Close' in spy_data.columns else 'Close'
        if price_col not in spy_data.columns:
            return {'spy_trend': 'Unknown', 'spy_above_sma200': False, 'spy_above_sma50': False}
        
        prices = spy_data[price_col].dropna()
        
        if len(prices) < 200:
            return {'spy_trend': 'Unknown', 'spy_above_sma200': False, 'spy_above_sma50': False}
        
        # 计算移动平均线
        sma50 = prices.rolling(window=50).mean().iloc[-1]
        sma200 = prices.rolling(window=200).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        # 计算趋势（最近20天）
        if len(prices) >= 20:
            recent_prices = prices.tail(20)
            price_change = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0] * 100
            
            if price_change > 2:
                spy_trend = 'Up'
            elif price_change < -2:
                spy_trend = 'Down'
            else:
                spy_trend = 'Sideways'
        else:
            spy_trend = 'Sideways'
        
        # 判断价格与均线关系
        spy_above_sma200 = current_price > sma200 if not pd.isna(sma200) else False
        spy_above_sma50 = current_price > sma50 if not pd.isna(sma50) else False
        
        return {
            'spy_trend': spy_trend,
            'spy_above_sma200': spy_above_sma200,
            'spy_above_sma50': spy_above_sma50,
            'spy_price_vs_sma200': round((current_price - sma200) / sma200 * 100, 2) if not pd.isna(sma200) else None
        }
        
    except Exception as e:
        logger.error(f"分析SPY趋势失败: {e}")
        return {'spy_trend': 'Unknown', 'spy_above_sma200': False, 'spy_above_sma50': False}


def calculate_market_distribution(price_data_dict: Dict[str, pd.DataFrame]) -> Dict:
    """
    计算市场分布（上涨/下跌股票比例）
    
    Args:
        price_data_dict: 股票价格数据字典 {ticker: price_data}
        
    Returns:
        市场分布统计
    """
    try:
        if not price_data_dict or len(price_data_dict) == 0:
            return {'advance_ratio': 0.5, 'advance_decline_ratio': 1.0}
        
        advances = 0
        declines = 0
        unchanged = 0
        
        for ticker, price_data in price_data_dict.items():
            try:
                # 确保数据按日期排序
                if 'Date' in price_data.columns:
                    price_data = price_data.set_index('Date').sort_index()
                else:
                    price_data = price_data.sort_index()
                
                price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
                if price_col not in price_data.columns:
                    continue
                
                prices = price_data[price_col].dropna()
                if len(prices) < 2:
                    continue
                
                # 计算最近5天的变化
                if len(prices) >= 5:
                    price_change = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5] * 100
                else:
                    price_change = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0] * 100
                
                if price_change > 0.5:
                    advances += 1
                elif price_change < -0.5:
                    declines += 1
                else:
                    unchanged += 1
                    
            except Exception as e:
                logger.debug(f"计算 {ticker} 市场分布失败: {e}")
                continue
        
        total = advances + declines + unchanged
        if total == 0:
            return {'advance_ratio': 0.5, 'advance_decline_ratio': 1.0}
        
        advance_ratio = advances / total
        advance_decline_ratio = advances / declines if declines > 0 else (advances + 1) / 1
        
        return {
            'advance_ratio': round(advance_ratio, 3),
            'advance_decline_ratio': round(advance_decline_ratio, 2),
            'advances': advances,
            'declines': declines,
            'unchanged': unchanged
        }
        
    except Exception as e:
        logger.error(f"计算市场分布失败: {e}")
        return {'advance_ratio': 0.5, 'advance_decline_ratio': 1.0}


def determine_market_stage(market_analysis: Dict) -> str:
    """
    判断市场阶段
    
    市场阶段：
    - Bull Market: 牛市（SPY在SMA200上方，上涨股票>60%）
    - Bear Market: 熊市（SPY在SMA200下方，下跌股票>60%）
    - Correction: 调整（SPY在SMA200上方但短期下跌）
    - Uncertain: 不确定
    """
    spy_above_sma200 = market_analysis.get('spy_above_sma200', False)
    spy_trend = market_analysis.get('spy_trend', 'Sideways')
    distribution_ratio = market_analysis.get('distribution_ratio', 0.5)
    
    # 牛市判断
    if spy_above_sma200 and spy_trend == 'Up' and distribution_ratio > 0.6:
        return 'Bull Market'
    
    # 熊市判断
    if not spy_above_sma200 and spy_trend == 'Down' and distribution_ratio < 0.4:
        return 'Bear Market'
    
    # 调整判断
    if spy_above_sma200 and spy_trend == 'Down' and distribution_ratio < 0.5:
        return 'Correction'
    
    # 不确定
    return 'Uncertain'


def generate_trading_recommendation(market_analysis: Dict) -> str:
    """
    根据市场分析生成交易建议
    
    Args:
        market_analysis: 市场分析结果
        
    Returns:
        交易建议文本
    """
    market_stage = market_analysis.get('market_stage', 'Uncertain')
    spy_above_sma200 = market_analysis.get('spy_above_sma200', False)
    distribution_ratio = market_analysis.get('distribution_ratio', 0.5)
    
    if market_stage == 'Bull Market':
        if distribution_ratio > 0.7:
            return '✅ 强势牛市，积极买入'
        else:
            return '✅ 牛市环境，可以买入'
    
    elif market_stage == 'Bear Market':
        return '⚠️ 熊市环境，建议空仓或做空'
    
    elif market_stage == 'Correction':
        return '⚠️ 市场调整，谨慎买入，等待确认'
    
    else:
        if spy_above_sma200 and distribution_ratio > 0.5:
            return '⚠️ 市场方向不明，选择性买入'
        else:
            return '⚠️ 市场方向不明，建议观望'

