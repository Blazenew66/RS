"""
基本面筛选模块
基于马克·米勒维尼的《超级绩效》方法
筛选条件：营收增长、盈利增长、ROE等
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def fetch_fundamental_data(ticker: str) -> Optional[Dict]:
    """
    获取股票的基本面数据
    
    Args:
        ticker: 股票代码
        
    Returns:
        包含基本面数据的字典，如果获取失败返回 None
        {
            'revenue_growth_qoq': float,  # 季度营收增长率
            'revenue_growth_yoy': float,  # 年度营收增长率
            'earnings_growth_qoq': float,  # 季度盈利增长率
            'earnings_growth_yoy': float,  # 年度盈利增长率
            'roe': float,  # 净资产收益率
            'profit_margin': float,  # 利润率
            'pe_ratio': float,  # 市盈率
            'data_available': bool  # 数据是否可用
        }
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        
        # 获取财务数据
        info = stock.info
        
        if not info or len(info) == 0:
            return None
        
        result = {
            'data_available': False,
            'revenue_growth_qoq': None,
            'revenue_growth_yoy': None,
            'earnings_growth_qoq': None,
            'earnings_growth_yoy': None,
            'roe': None,
            'profit_margin': None,
            'pe_ratio': None
        }
        
        # 营收增长率（季度）
        if 'quarterlyRevenueGrowth' in info and info['quarterlyRevenueGrowth'] is not None:
            result['revenue_growth_qoq'] = round(info['quarterlyRevenueGrowth'] * 100, 2)
        
        # 营收增长率（年度）
        if 'revenueGrowth' in info and info['revenueGrowth'] is not None:
            result['revenue_growth_yoy'] = round(info['revenueGrowth'] * 100, 2)
        
        # 盈利增长率（季度）
        if 'earningsQuarterlyGrowth' in info and info['earningsQuarterlyGrowth'] is not None:
            result['earnings_growth_qoq'] = round(info['earningsQuarterlyGrowth'] * 100, 2)
        
        # 盈利增长率（年度）
        if 'earningsGrowth' in info and info['earningsGrowth'] is not None:
            result['earnings_growth_yoy'] = round(info['earningsGrowth'] * 100, 2)
        
        # ROE（净资产收益率）
        if 'returnOnEquity' in info and info['returnOnEquity'] is not None:
            result['roe'] = round(info['returnOnEquity'] * 100, 2)
        
        # 利润率
        if 'profitMargins' in info and info['profitMargins'] is not None:
            result['profit_margin'] = round(info['profitMargins'] * 100, 2)
        
        # 市盈率
        if 'trailingPE' in info and info['trailingPE'] is not None:
            result['pe_ratio'] = round(info['trailingPE'], 2)
        elif 'forwardPE' in info and info['forwardPE'] is not None:
            result['pe_ratio'] = round(info['forwardPE'], 2)
        
        # 检查是否有任何数据
        result['data_available'] = any([
            result['revenue_growth_qoq'] is not None,
            result['revenue_growth_yoy'] is not None,
            result['earnings_growth_qoq'] is not None,
            result['earnings_growth_yoy'] is not None,
            result['roe'] is not None,
            result['profit_margin'] is not None
        ])
        
        return result
        
    except Exception as e:
        logger.warning(f"获取 {ticker} 基本面数据失败: {e}")
        return None


def screen_fundamental_criteria(fundamental_data: Optional[Dict]) -> Dict:
    """
    根据基本面标准筛选股票
    
    筛选标准（基于《超级绩效》）：
    1. 季度营收增长率 > 25%（理想）
    2. 年度营收增长率 > 25%
    3. 季度盈利增长率 > 25%
    4. ROE > 15%
    5. 利润率 > 10%
    
    Args:
        fundamental_data: 基本面数据字典
        
    Returns:
        筛选结果字典
        {
            'passes_screen': bool,
            'score': int,  # 0-100分
            'criteria_met': {
                'revenue_growth_qoq': bool,
                'revenue_growth_yoy': bool,
                'earnings_growth_qoq': bool,
                'earnings_growth_yoy': bool,
                'roe': bool,
                'profit_margin': bool
            },
            'details': str  # 详细说明
        }
    """
    if not fundamental_data or not fundamental_data.get('data_available'):
        return {
            'passes_screen': False,
            'score': 0,
            'criteria_met': {},
            'details': '基本面数据不可用'
        }
    
    criteria_met = {
        'revenue_growth_qoq': False,
        'revenue_growth_yoy': False,
        'earnings_growth_qoq': False,
        'earnings_growth_yoy': False,
        'roe': False,
        'profit_margin': False
    }
    
    score = 0
    details = []
    
    # 1. 季度营收增长率 > 25%
    rev_growth_qoq = fundamental_data.get('revenue_growth_qoq')
    if rev_growth_qoq is not None:
        if rev_growth_qoq > 25:
            criteria_met['revenue_growth_qoq'] = True
            score += 20
            details.append(f"季度营收增长 {rev_growth_qoq:.1f}% ✓")
        elif rev_growth_qoq > 0:
            score += 10
            details.append(f"季度营收增长 {rev_growth_qoq:.1f}%")
        else:
            details.append(f"季度营收下降 {abs(rev_growth_qoq):.1f}%")
    
    # 2. 年度营收增长率 > 25%
    rev_growth_yoy = fundamental_data.get('revenue_growth_yoy')
    if rev_growth_yoy is not None:
        if rev_growth_yoy > 25:
            criteria_met['revenue_growth_yoy'] = True
            score += 20
            details.append(f"年度营收增长 {rev_growth_yoy:.1f}% ✓")
        elif rev_growth_yoy > 0:
            score += 10
            details.append(f"年度营收增长 {rev_growth_yoy:.1f}%")
        else:
            details.append(f"年度营收下降 {abs(rev_growth_yoy):.1f}%")
    
    # 3. 季度盈利增长率 > 25%
    earn_growth_qoq = fundamental_data.get('earnings_growth_qoq')
    if earn_growth_qoq is not None:
        if earn_growth_qoq > 25:
            criteria_met['earnings_growth_qoq'] = True
            score += 20
            details.append(f"季度盈利增长 {earn_growth_qoq:.1f}% ✓")
        elif earn_growth_qoq > 0:
            score += 10
            details.append(f"季度盈利增长 {earn_growth_qoq:.1f}%")
        else:
            details.append(f"季度盈利下降 {abs(earn_growth_qoq):.1f}%")
    
    # 4. 年度盈利增长率 > 25%
    earn_growth_yoy = fundamental_data.get('earnings_growth_yoy')
    if earn_growth_yoy is not None:
        if earn_growth_yoy > 25:
            criteria_met['earnings_growth_yoy'] = True
            score += 20
            details.append(f"年度盈利增长 {earnings_growth_yoy:.1f}% ✓")
        elif earn_growth_yoy > 0:
            score += 10
            details.append(f"年度盈利增长 {earnings_growth_yoy:.1f}%")
        else:
            details.append(f"年度盈利下降 {abs(earnings_growth_yoy):.1f}%")
    
    # 5. ROE > 15%
    roe = fundamental_data.get('roe')
    if roe is not None:
        if roe > 15:
            criteria_met['roe'] = True
            score += 10
            details.append(f"ROE {roe:.1f}% ✓")
        elif roe > 0:
            score += 5
            details.append(f"ROE {roe:.1f}%")
        else:
            details.append(f"ROE {roe:.1f}% (负值)")
    
    # 6. 利润率 > 10%
    profit_margin = fundamental_data.get('profit_margin')
    if profit_margin is not None:
        if profit_margin > 10:
            criteria_met['profit_margin'] = True
            score += 10
            details.append(f"利润率 {profit_margin:.1f}% ✓")
        elif profit_margin > 0:
            score += 5
            details.append(f"利润率 {profit_margin:.1f}%")
        else:
            details.append(f"利润率 {profit_margin:.1f}% (负值)")
    
    # 判断是否通过筛选（至少满足3个主要条件）
    passes_screen = sum([
        criteria_met['revenue_growth_qoq'],
        criteria_met['revenue_growth_yoy'],
        criteria_met['earnings_growth_qoq'],
        criteria_met['earnings_growth_yoy']
    ]) >= 2 and (criteria_met['roe'] or criteria_met['profit_margin'])
    
    return {
        'passes_screen': passes_screen,
        'score': min(100, score),
        'criteria_met': criteria_met,
        'details': ' | '.join(details) if details else '无数据'
    }


def get_fundamental_summary(ticker: str) -> Optional[Dict]:
    """
    获取股票的基本面摘要（包含筛选结果）
    
    Args:
        ticker: 股票代码
        
    Returns:
        包含基本面数据和筛选结果的字典
    """
    fundamental_data = fetch_fundamental_data(ticker)
    if not fundamental_data:
        return None
    
    screen_result = screen_fundamental_criteria(fundamental_data)
    
    return {
        'fundamental_data': fundamental_data,
        'screen_result': screen_result
    }

