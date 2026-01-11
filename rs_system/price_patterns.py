"""
价格形态识别模块
基于马克·米勒维尼的《超级绩效》方法
识别经典价格形态：杯柄形态、双底、平底、上升三角形等
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def identify_cup_and_handle(
    price_data: pd.DataFrame,
    cup_duration_days: int = 60,
    handle_duration_days: int = 20
) -> Optional[Dict]:
    """
    识别杯柄形态（Cup & Handle）
    
    杯柄形态特征：
    1. 杯部：价格先下跌形成U形底部，然后回升
    2. 柄部：在杯部右侧形成小幅回调（通常10-15%）
    3. 成交量：杯部底部成交量萎缩，柄部成交量进一步萎缩
    4. 突破：价格突破柄部高点，成交量放大
    
    Args:
        price_data: 价格数据
        cup_duration_days: 杯部持续时间（默认60天）
        handle_duration_days: 柄部持续时间（默认20天）
        
    Returns:
        杯柄形态信息
        {
            'has_pattern': bool,
            'pattern_type': str,  # 'Cup & Handle'
            'cup_depth': float,  # 杯部深度（%）
            'handle_depth': float,  # 柄部深度（%）
            'breakout_ready': bool,
            'pattern_strength': str
        }
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns or 'Volume' not in price_data.columns:
            return None
        
        if 'Date' in price_data.columns:
            price_data = price_data.set_index('Date').sort_index()
        
        prices = price_data[price_col].dropna()
        volumes = price_data['Volume'].dropna()
        
        if len(prices) < cup_duration_days + handle_duration_days:
            return None
        
        # 分析最近的数据
        lookback = cup_duration_days + handle_duration_days
        recent_prices = prices.tail(lookback)
        recent_volumes = volumes.tail(lookback)
        
        # 1. 识别杯部
        cup_prices = recent_prices.head(cup_duration_days)
        cup_start_price = cup_prices.iloc[0]
        cup_low = cup_prices.min()
        cup_end_price = cup_prices.iloc[-1]
        
        # 杯部深度（从起点到最低点的跌幅）
        cup_depth = ((cup_start_price - cup_low) / cup_start_price) * 100
        
        # 检查是否形成U形（先跌后涨）
        cup_mid = len(cup_prices) // 2
        cup_first_half_low = cup_prices.iloc[:cup_mid].min()
        cup_second_half_high = cup_prices.iloc[cup_mid:].max()
        
        # U形特征：前半部分下跌，后半部分上涨，且低点在中间
        is_u_shape = (cup_first_half_low < cup_start_price * 0.9 and 
                     cup_second_half_high > cup_low * 1.1 and
                     abs(cup_prices.iloc[cup_mid] - cup_low) / cup_low < 0.05)  # 低点在中间附近
        
        if not is_u_shape or cup_depth < 15 or cup_depth > 50:  # 杯部深度应在15-50%之间
            return {
                'has_pattern': False,
                'reason': '未形成有效的杯部形态'
            }
        
        # 2. 识别柄部
        handle_prices = recent_prices.tail(handle_duration_days)
        handle_start_price = handle_prices.iloc[0]
        handle_low = handle_prices.min()
        handle_end_price = handle_prices.iloc[-1]
        
        # 柄部深度（相对于杯部结束价格）
        handle_depth = ((handle_start_price - handle_low) / handle_start_price) * 100
        
        # 柄部应该在杯部右侧，且深度较小（10-15%）
        if handle_depth < 8 or handle_depth > 20:
            return {
                'has_pattern': False,
                'reason': '柄部深度不符合要求'
            }
        
        # 3. 检查成交量模式
        cup_volumes = recent_volumes.head(cup_duration_days)
        handle_volumes = recent_volumes.tail(handle_duration_days)
        
        # 杯部底部成交量应该萎缩
        cup_bottom_idx = cup_prices.idxmin()
        cup_bottom_vol = volumes.loc[cup_bottom_idx] if cup_bottom_idx in volumes.index else None
        
        # 柄部成交量应该进一步萎缩
        handle_avg_vol = handle_volumes.mean()
        cup_avg_vol = cup_volumes.mean()
        
        volume_contracting = handle_avg_vol < cup_avg_vol * 0.8 if cup_avg_vol > 0 else False
        
        # 4. 检查是否准备突破
        current_price = prices.iloc[-1]
        handle_high = handle_prices.max()
        breakout_ready = (current_price > handle_high * 0.95 and  # 接近或突破柄部高点
                         volume_contracting)
        
        # 5. 评估形态强度
        pattern_strength = 'Weak'
        if (cup_depth >= 20 and cup_depth <= 40 and
            handle_depth >= 10 and handle_depth <= 15 and
            volume_contracting):
            pattern_strength = 'Strong'
        elif cup_depth >= 15 and handle_depth >= 8:
            pattern_strength = 'Moderate'
        
        return {
            'has_pattern': True,
            'pattern_type': 'Cup & Handle',
            'cup_depth': round(cup_depth, 2),
            'handle_depth': round(handle_depth, 2),
            'breakout_ready': breakout_ready,
            'pattern_strength': pattern_strength,
            'volume_contracting': volume_contracting
        }
        
    except Exception as e:
        logger.error(f"识别杯柄形态失败: {e}")
        return None


def identify_double_bottom(
    price_data: pd.DataFrame,
    lookback_days: int = 100
) -> Optional[Dict]:
    """
    识别双底形态（Double Bottom）
    
    双底特征：
    1. 两个相似的低点（差异<5%）
    2. 两个低点之间有反弹
    3. 第二个低点后价格突破颈线
    
    Args:
        price_data: 价格数据
        lookback_days: 回看天数
        
    Returns:
        双底形态信息
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return None
        
        if 'Date' in price_data.columns:
            price_data = price_data.set_index('Date').sort_index()
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < lookback_days:
            return None
        
        recent_prices = prices.tail(lookback_days)
        
        # 寻找两个低点
        # 使用滚动窗口寻找局部最低点
        window = 20
        local_mins = []
        
        for i in range(window, len(recent_prices) - window):
            window_prices = recent_prices.iloc[i-window:i+window]
            center_price = recent_prices.iloc[i]
            
            if center_price == window_prices.min():
                local_mins.append((i, center_price))
        
        if len(local_mins) < 2:
            return {
                'has_pattern': False,
                'reason': '未找到足够的低点'
            }
        
        # 找到两个最低点
        local_mins.sort(key=lambda x: x[1])  # 按价格排序
        first_bottom = local_mins[0]
        second_bottom = local_mins[1] if len(local_mins) > 1 else None
        
        if not second_bottom:
            return {
                'has_pattern': False,
                'reason': '未找到第二个低点'
            }
        
        # 确保第二个低点在第一个之后
        if second_bottom[0] <= first_bottom[0]:
            if len(local_mins) > 2:
                second_bottom = local_mins[2]
            else:
                return {
                    'has_pattern': False,
                    'reason': '低点顺序不正确'
                }
        
        # 检查两个低点是否相似（差异<5%）
        price_diff = abs(first_bottom[1] - second_bottom[1]) / min(first_bottom[1], second_bottom[1]) * 100
        
        if price_diff > 5:
            return {
                'has_pattern': False,
                'reason': '两个低点差异过大'
            }
        
        # 检查两个低点之间是否有反弹
        between_prices = recent_prices.iloc[first_bottom[0]:second_bottom[0]]
        rebound_high = between_prices.max()
        rebound_pct = ((rebound_high - first_bottom[1]) / first_bottom[1]) * 100
        
        if rebound_pct < 10:  # 反弹至少10%
            return {
                'has_pattern': False,
                'reason': '两个低点之间反弹不足'
            }
        
        # 检查是否突破颈线
        neckline = rebound_high
        current_price = prices.iloc[-1]
        breakout = current_price > neckline * 0.98  # 接近或突破颈线
        
        return {
            'has_pattern': True,
            'pattern_type': 'Double Bottom',
            'first_bottom': round(first_bottom[1], 2),
            'second_bottom': round(second_bottom[1], 2),
            'neckline': round(neckline, 2),
            'breakout': breakout,
            'pattern_strength': 'Strong' if breakout else 'Moderate'
        }
        
    except Exception as e:
        logger.error(f"识别双底形态失败: {e}")
        return None


def identify_all_patterns(price_data: pd.DataFrame) -> Dict:
    """
    识别所有价格形态
    
    Args:
        price_data: 价格数据
        
    Returns:
        所有识别到的形态信息
    """
    patterns = {
        'cup_and_handle': identify_cup_and_handle(price_data),
        'double_bottom': identify_double_bottom(price_data)
    }
    
    # 统计有效形态
    valid_patterns = [p for p in patterns.values() if p and p.get('has_pattern')]
    
    return {
        'patterns': patterns,
        'valid_count': len(valid_patterns),
        'has_any_pattern': len(valid_patterns) > 0
    }

