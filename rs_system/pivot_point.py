"""
精确买入点（Pivot Point）识别模块
基于马克·米勒维尼的《超级绩效》方法
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


def identify_pivot_point(
    price_data: pd.DataFrame,
    lookback_days: int = 20,
    volume_threshold: float = 1.5
) -> Optional[Dict]:
    """
    识别精确买入点（Pivot Point）
    
    买入点特征：
    1. 价格突破近期高点（20-30天）
    2. 成交量放大（至少1.5倍平均成交量）
    3. 价格在关键阻力位附近或突破
    4. RS Line 处于上升趋势
    
    Args:
        price_data: 包含价格和成交量数据的 DataFrame
        lookback_days: 回看天数（默认20天）
        volume_threshold: 成交量放大倍数阈值（默认1.5倍）
        
    Returns:
        包含买入点信息的字典，如果没有买入点则返回 None
        {
            'has_pivot': bool,
            'pivot_price': float,  # 买入点价格
            'breakout_date': datetime,  # 突破日期
            'volume_ratio': float,  # 成交量比率
            'resistance_level': float,  # 阻力位
            'distance_from_resistance': float,  # 距离阻力位的百分比
            'signal_strength': str  # 'Strong', 'Moderate', 'Weak'
        }
    """
    try:
        # 检查必要列
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns or 'Volume' not in price_data.columns:
            return None
        
        # 确保数据按日期排序
        if 'Date' in price_data.columns:
            price_data = price_data.set_index('Date').sort_index()
        else:
            price_data = price_data.sort_index()
        
        prices = price_data[price_col].dropna()
        volumes = price_data['Volume'].dropna()
        
        if len(prices) < lookback_days + 5:
            return None
        
        # 获取最近的数据
        recent_prices = prices.tail(lookback_days + 5)
        recent_volumes = volumes.tail(lookback_days + 5)
        
        # 1. 识别近期高点（阻力位）
        lookback_prices = recent_prices.tail(lookback_days)
        resistance_level = lookback_prices.max()
        resistance_date = lookback_prices.idxmax()
        
        # 2. 当前价格和成交量
        current_price = prices.iloc[-1]
        current_volume = volumes.iloc[-1]
        current_date = prices.index[-1]
        
        # 3. 计算平均成交量
        avg_volume = recent_volumes.tail(50).mean() if len(recent_volumes) >= 50 else recent_volumes.mean()
        
        if pd.isna(avg_volume) or avg_volume == 0:
            return None
        
        # 4. 成交量比率
        volume_ratio = current_volume / avg_volume
        
        # 5. 判断是否突破阻力位
        price_above_resistance = current_price > resistance_level
        distance_from_resistance = ((current_price - resistance_level) / resistance_level) * 100
        
        # 6. 判断成交量是否放大
        volume_surge = volume_ratio >= volume_threshold
        
        # 7. 判断是否在阻力位附近（±2%范围内）
        near_resistance = abs(distance_from_resistance) <= 2.0
        
        # 8. 计算信号强度
        signal_strength = 'Weak'
        if price_above_resistance and volume_surge:
            if volume_ratio >= 2.0 and distance_from_resistance > 1.0:
                signal_strength = 'Strong'
            elif volume_ratio >= 1.5:
                signal_strength = 'Moderate'
        elif near_resistance and volume_surge:
            signal_strength = 'Moderate'
        
        # 9. 判断是否有买入点
        has_pivot = (price_above_resistance or near_resistance) and volume_surge
        
        if not has_pivot:
            return {
                'has_pivot': False,
                'pivot_price': None,
                'breakout_date': None,
                'volume_ratio': round(volume_ratio, 2),
                'resistance_level': round(resistance_level, 2),
                'distance_from_resistance': round(distance_from_resistance, 2),
                'signal_strength': signal_strength
            }
        
        return {
            'has_pivot': True,
            'pivot_price': round(current_price, 2),
            'breakout_date': current_date,
            'volume_ratio': round(volume_ratio, 2),
            'resistance_level': round(resistance_level, 2),
            'distance_from_resistance': round(distance_from_resistance, 2),
            'signal_strength': signal_strength
        }
        
    except Exception as e:
        logger.error(f"识别买入点失败: {e}")
        return None


def check_pivot_breakout(
    price_data: pd.DataFrame,
    rs_line_series: Optional[pd.Series] = None,
    market_price_data: Optional[pd.DataFrame] = None
) -> Optional[Dict]:
    """
    检查买入点突破（结合RS Line确认）
    
    Args:
        price_data: 股票价格数据
        rs_line_series: RS Line 时间序列（可选）
        market_price_data: 市场基准数据（如果 rs_line_series 为 None 则需要）
        
    Returns:
        突破信息字典
    """
    try:
        # 基本买入点识别
        pivot_info = identify_pivot_point(price_data)
        if not pivot_info or not pivot_info.get('has_pivot'):
            return pivot_info
        
        # 如果提供了 RS Line，检查 RS Line 趋势
        if rs_line_series is not None and len(rs_line_series) > 0:
            rs_line = rs_line_series.sort_index()
            if len(rs_line) >= 20:
                # 检查 RS Line 是否上升
                recent_rs = rs_line.tail(20)
                rs_trend = (recent_rs.iloc[-1] - recent_rs.iloc[0]) / recent_rs.iloc[0] * 100
                pivot_info['rs_trend_pct'] = round(rs_trend, 2)
                pivot_info['rs_confirming'] = rs_trend > 0
            else:
                pivot_info['rs_confirming'] = None
        elif market_price_data is not None:
            # 从市场数据计算 RS Line
            from rs_system.indicators import calculate_rs_trend
            rs_slope, rs_arrow = calculate_rs_trend(price_data, market_price_data)
            pivot_info['rs_trend_pct'] = round(rs_slope, 2) if rs_slope else None
            pivot_info['rs_confirming'] = rs_arrow == "⬆️" if rs_arrow else None
        else:
            pivot_info['rs_confirming'] = None
        
        # 如果 RS Line 确认，提升信号强度
        if pivot_info.get('rs_confirming') and pivot_info['signal_strength'] == 'Moderate':
            pivot_info['signal_strength'] = 'Strong'
        
        return pivot_info
        
    except Exception as e:
        logger.error(f"检查买入点突破失败: {e}")
        return None

