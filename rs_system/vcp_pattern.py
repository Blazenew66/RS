"""
VCP（波动率收缩模式）识别模块
基于马克·米勒维尼的《超级绩效》方法
识别多级波动率收缩模式
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def identify_vcp_pattern(
    price_data: pd.DataFrame,
    min_contractions: int = 2,
    max_contractions: int = 3
) -> Optional[Dict]:
    """
    识别VCP（波动率收缩模式）
    
    VCP特征：
    1. 价格在上升趋势中
    2. 出现2-3次波动率收缩
    3. 每次收缩后价格回调幅度递减
    4. 成交量在收缩期间递减
    
    Args:
        price_data: 价格数据
        min_contractions: 最小收缩次数（默认2）
        max_contractions: 最大收缩次数（默认3）
        
    Returns:
        VCP模式信息
        {
            'has_vcp': bool,
            'contraction_count': int,  # 收缩次数
            'contractions': List[Dict],  # 每次收缩的详细信息
            'pattern_strength': str,  # 'Strong', 'Moderate', 'Weak'
            'breakout_ready': bool  # 是否准备突破
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
        
        if len(prices) < 200:  # 需要足够的历史数据
            return None
        
        # 1. 检查是否在上升趋势中（价格在SMA200上方）
        sma200 = prices.rolling(window=200).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        if pd.isna(sma200) or current_price < sma200:
            return {
                'has_vcp': False,
                'reason': '不在上升趋势中'
            }
        
        # 2. 识别波动率收缩
        contractions = []
        
        # 分析最近6个月的数据（约126个交易日）
        lookback_days = min(126, len(prices))
        recent_prices = prices.tail(lookback_days)
        recent_volumes = volumes.tail(lookback_days)
        
        # 寻找价格高点和低点
        window_size = 20  # 20天窗口
        
        for i in range(lookback_days - window_size * 3, lookback_days - window_size, window_size):
            if i < 0:
                continue
            
            window_prices = recent_prices.iloc[i:i+window_size]
            window_volumes = recent_volumes.iloc[i:i+window_size]
            
            if len(window_prices) < window_size:
                continue
            
            # 计算波动率（最高价与最低价的百分比差）
            high = window_prices.max()
            low = window_prices.min()
            volatility = ((high - low) / low) * 100
            
            # 计算平均成交量
            avg_volume = window_volumes.mean()
            
            # 计算价格变化
            price_change = (window_prices.iloc[-1] - window_prices.iloc[0]) / window_prices.iloc[0] * 100
            
            contractions.append({
                'period': i,
                'volatility': round(volatility, 2),
                'avg_volume': avg_volume,
                'price_change': round(price_change, 2),
                'high': high,
                'low': low
            })
        
        # 3. 分析收缩模式
        if len(contractions) < min_contractions:
            return {
                'has_vcp': False,
                'reason': f'收缩次数不足（需要至少{min_contractions}次）'
            }
        
        # 检查波动率是否递减
        volatility_trend = []
        volume_trend = []
        
        for i in range(len(contractions) - 1):
            vol_ratio = contractions[i+1]['volatility'] / contractions[i]['volatility'] if contractions[i]['volatility'] > 0 else 1
            volatility_trend.append(vol_ratio < 1.0)  # 波动率递减
            
            vol_vol_ratio = contractions[i+1]['avg_volume'] / contractions[i]['avg_volume'] if contractions[i]['avg_volume'] > 0 else 1
            volume_trend.append(vol_vol_ratio < 1.0)  # 成交量递减
        
        # 判断VCP模式
        volatility_decreasing = sum(volatility_trend) >= len(volatility_trend) * 0.6  # 至少60%的收缩是递减的
        volume_decreasing = sum(volume_trend) >= len(volume_trend) * 0.6
        
        has_vcp = volatility_decreasing and len(contractions) >= min_contractions
        
        if not has_vcp:
            return {
                'has_vcp': False,
                'reason': '波动率收缩模式不明显'
            }
        
        # 4. 评估模式强度
        pattern_strength = 'Weak'
        if len(contractions) >= 3 and volatility_decreasing and volume_decreasing:
            pattern_strength = 'Strong'
        elif len(contractions) >= 2 and volatility_decreasing:
            pattern_strength = 'Moderate'
        
        # 5. 检查是否准备突破
        # 如果最近一次收缩的波动率很小，且价格接近高点，可能准备突破
        last_contraction = contractions[-1]
        recent_volatility = last_contraction['volatility']
        price_near_high = (current_price - last_contraction['low']) / (last_contraction['high'] - last_contraction['low']) > 0.7
        
        breakout_ready = recent_volatility < 5.0 and price_near_high  # 波动率<5%且价格在区间上部70%
        
        return {
            'has_vcp': True,
            'contraction_count': len(contractions),
            'contractions': contractions,
            'pattern_strength': pattern_strength,
            'breakout_ready': breakout_ready,
            'current_volatility': round(recent_volatility, 2)
        }
        
    except Exception as e:
        logger.error(f"识别VCP模式失败: {e}")
        return None


def check_vcp_breakout(
    price_data: pd.DataFrame,
    volume_threshold: float = 1.5
) -> Optional[Dict]:
    """
    检查VCP模式后的突破
    
    Args:
        price_data: 价格数据
        volume_threshold: 成交量放大倍数阈值
        
    Returns:
        突破信息
        {
            'has_breakout': bool,
            'breakout_price': float,
            'volume_ratio': float,
            'breakout_strength': str
        }
    """
    try:
        vcp_info = identify_vcp_pattern(price_data)
        if not vcp_info or not vcp_info.get('has_vcp'):
            return None
        
        # 检查是否突破
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if 'Date' in price_data.columns:
            price_data = price_data.set_index('Date').sort_index()
        
        prices = price_data[price_col].dropna()
        volumes = price_data['Volume'].dropna()
        
        if len(prices) < 20 or len(volumes) < 20:
            return None
        
        # 获取最近的高点（阻力位）
        recent_high = prices.tail(60).max()
        current_price = prices.iloc[-1]
        current_volume = volumes.iloc[-1]
        avg_volume = volumes.tail(50).mean()
        
        # 判断是否突破
        price_breakout = current_price > recent_high * 0.98  # 接近或突破高点（2%容差）
        volume_surge = current_volume / avg_volume >= volume_threshold if avg_volume > 0 else False
        
        has_breakout = price_breakout and volume_surge
        
        if not has_breakout:
            return {
                'has_breakout': False,
                'vcp_info': vcp_info
            }
        
        # 评估突破强度
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        if volume_ratio >= 2.0:
            breakout_strength = 'Strong'
        elif volume_ratio >= 1.5:
            breakout_strength = 'Moderate'
        else:
            breakout_strength = 'Weak'
        
        return {
            'has_breakout': True,
            'breakout_price': round(current_price, 2),
            'volume_ratio': round(volume_ratio, 2),
            'breakout_strength': breakout_strength,
            'vcp_info': vcp_info
        }
        
    except Exception as e:
        logger.error(f"检查VCP突破失败: {e}")
        return None

