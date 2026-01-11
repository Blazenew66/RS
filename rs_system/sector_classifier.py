"""
板块分类模块
基于TradingView的板块分类标准，将股票分类到中文板块
"""
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# TradingView板块分类（中文）
SECTOR_MAPPING = {
    # 科技
    'Technology': '科技',
    'Information Technology': '科技',
    'Software': '科技',
    'Semiconductors': '科技',
    'Internet Content & Information': '科技',
    'Electronic Components': '科技',
    'Computer Hardware': '科技',
    
    # 金融
    'Financial Services': '金融',
    'Financial': '金融',
    'Banks': '金融',
    'Capital Markets': '金融',
    'Insurance': '金融',
    'Credit Services': '金融',
    'Mortgage Finance': '金融',
    
    # 医疗保健
    'Healthcare': '医疗保健',
    'Health Care': '医疗保健',
    'Biotechnology': '医疗保健',
    'Pharmaceuticals': '医疗保健',
    'Medical Devices': '医疗保健',
    'Medical Care': '医疗保健',
    'Diagnostics & Research': '医疗保健',
    
    # 能源
    'Energy': '能源',
    'Oil & Gas': '能源',
    'Oil & Gas E&P': '能源',
    'Oil & Gas Refining & Marketing': '能源',
    'Oil & Gas Drilling': '能源',
    'Oil & Gas Equipment & Services': '能源',
    
    # 工业
    'Industrial': '工业',
    'Industrials': '工业',
    'Aerospace & Defense': '工业',
    'Airlines': '工业',
    'Railroads': '工业',
    'Machinery': '工业',
    'Industrial Products': '工业',
    'Specialty Industrial Machinery': '工业',
    
    # 消费必需品
    'Consumer Staples': '消费必需品',
    'Consumer Defensive': '消费必需品',
    'Food & Beverages': '消费必需品',
    'Packaged Foods': '消费必需品',
    'Beverages': '消费必需品',
    'Tobacco': '消费必需品',
    'Household & Personal Products': '消费必需品',
    
    # 非必需消费品
    'Consumer Discretionary': '非必需消费品',
    'Consumer Cyclical': '非必需消费品',
    'Retail': '非必需消费品',
    'Specialty Retail': '非必需消费品',
    'Department Stores': '非必需消费品',
    'Apparel Retail': '非必需消费品',
    'Auto & Truck Dealers': '非必需消费品',
    'Restaurants': '非必需消费品',
    'Hotels & Motels': '非必需消费品',
    'Leisure': '非必需消费品',
    'Entertainment': '非必需消费品',
    'Gambling': '非必需消费品',
    
    # 公用事业
    'Utilities': '公用事业',
    'Electric Utilities': '公用事业',
    'Gas Utilities': '公用事业',
    'Water Utilities': '公用事业',
    'Renewable Energy': '公用事业',
    
    # 材料
    'Materials': '材料',
    'Basic Materials': '材料',
    'Chemicals': '材料',
    'Steel': '材料',
    'Gold': '材料',
    'Copper': '材料',
    'Aluminum': '材料',
    'Agricultural Inputs': '材料',
    'Building Materials': '材料',
    
    # 房地产
    'Real Estate': '房地产',
    'REIT': '房地产',
    'REIT - Diversified': '房地产',
    'REIT - Residential': '房地产',
    'REIT - Office': '房地产',
    'REIT - Retail': '房地产',
    'REIT - Industrial': '房地产',
    'Real Estate Services': '房地产',
    
    # 通信服务
    'Communication Services': '通信服务',
    'Telecom Services': '通信服务',
    'Telecommunications': '通信服务',
    'Media': '通信服务',
    'Broadcasting': '通信服务',
    'Publishing': '通信服务',
    'Entertainment': '通信服务',
    
    # 其他
    'Conglomerates': '综合企业',
    'Other': '其他',
    'Unknown': '未知',
}

# 行业到板块的映射（更细粒度）
INDUSTRY_TO_SECTOR = {
    # 科技相关行业
    'Software—Infrastructure': '科技',
    'Software—Application': '科技',
    'Semiconductors': '科技',
    'Semiconductor Equipment & Materials': '科技',
    'Computer Hardware': '科技',
    'Consumer Electronics': '科技',
    'Electronic Components': '科技',
    'Internet Content & Information': '科技',
    'Internet Retail': '科技',
    'Information Technology Services': '科技',
    'Data Processing & Outsourced Services': '科技',
    
    # 金融相关行业
    'Banks—Diversified': '金融',
    'Banks—Regional': '金融',
    'Capital Markets': '金融',
    'Asset Management': '金融',
    'Insurance—Life': '金融',
    'Insurance—Property & Casualty': '金融',
    'Insurance—Reinsurance': '金融',
    'Mortgage Finance': '金融',
    'Credit Services': '金融',
    'Financial Data & Stock Exchanges': '金融',
    
    # 医疗保健相关行业
    'Biotechnology': '医疗保健',
    'Drug Manufacturers—General': '医疗保健',
    'Drug Manufacturers—Specialty & Generic': '医疗保健',
    'Medical Devices': '医疗保健',
    'Medical Instruments & Supplies': '医疗保健',
    'Medical Care': '医疗保健',
    'Medical Distribution': '医疗保健',
    'Diagnostics & Research': '医疗保健',
    'Health Information Services': '医疗保健',
    
    # 能源相关行业
    'Oil & Gas E&P': '能源',
    'Oil & Gas Refining & Marketing': '能源',
    'Oil & Gas Drilling': '能源',
    'Oil & Gas Equipment & Services': '能源',
    'Oil & Gas Midstream': '能源',
    'Thermal Coal': '能源',
    
    # 工业相关行业
    'Aerospace & Defense': '工业',
    'Airlines': '工业',
    'Railroads': '工业',
    'Trucking': '工业',
    'Marine Shipping': '工业',
    'Industrial Distribution': '工业',
    'Specialty Industrial Machinery': '工业',
    'Farm & Heavy Construction Machinery': '工业',
    'Electrical Equipment & Parts': '工业',
    'Waste Management': '工业',
    'Engineering & Construction': '工业',
    'Building Products & Equipment': '工业',
    
    # 消费必需品相关行业
    'Packaged Foods': '消费必需品',
    'Beverages—Non-Alcoholic': '消费必需品',
    'Beverages—Brewers': '消费必需品',
    'Beverages—Wineries & Distilleries': '消费必需品',
    'Tobacco': '消费必需品',
    'Household & Personal Products': '消费必需品',
    'Personal Care Products': '消费必需品',
    
    # 非必需消费品相关行业
    'Department Stores': '非必需消费品',
    'Specialty Retail': '非必需消费品',
    'Apparel Retail': '非必需消费品',
    'Auto & Truck Dealers': '非必需消费品',
    'Auto Parts': '非必需消费品',
    'Auto Manufacturers': '非必需消费品',
    'Restaurants': '非必需消费品',
    'Hotels & Motels': '非必需消费品',
    'Leisure': '非必需消费品',
    'Entertainment': '非必需消费品',
    'Gambling': '非必需消费品',
    'Textile Manufacturing': '非必需消费品',
    'Footwear & Accessories': '非必需消费品',
    
    # 公用事业相关行业
    'Electric Utilities': '公用事业',
    'Gas Utilities': '公用事业',
    'Water Utilities': '公用事业',
    'Utilities—Renewable': '公用事业',
    'Utilities—Independent Power Producers': '公用事业',
    
    # 材料相关行业
    'Chemicals': '材料',
    'Specialty Chemicals': '材料',
    'Agricultural Inputs': '材料',
    'Steel': '材料',
    'Copper': '材料',
    'Aluminum': '材料',
    'Gold': '材料',
    'Silver': '材料',
    'Other Industrial Metals & Mining': '材料',
    'Building Materials': '材料',
    'Lumber & Wood Production': '材料',
    'Paper & Paper Products': '材料',
    'Packaging & Containers': '材料',
    
    # 房地产相关行业
    'REIT—Diversified': '房地产',
    'REIT—Residential': '房地产',
    'REIT—Office': '房地产',
    'REIT—Retail': '房地产',
    'REIT—Industrial': '房地产',
    'REIT—Healthcare Facilities': '房地产',
    'REIT—Hotel & Motel': '房地产',
    'REIT—Specialty': '房地产',
    'Real Estate Services': '房地产',
    'Real Estate—Development': '房地产',
    
    # 通信服务相关行业
    'Telecom Services': '通信服务',
    'Telecom Services—Domestic': '通信服务',
    'Telecom Services—Foreign': '通信服务',
    'Media—Diversified': '通信服务',
    'Broadcasting': '通信服务',
    'Publishing': '通信服务',
    'Entertainment': '通信服务',
    'Electronic Gaming & Multimedia': '通信服务',
}


def get_sector_chinese(sector: Optional[str], industry: Optional[str] = None) -> str:
    """
    获取股票的中文板块分类（基于TradingView标准）
    
    Args:
        sector: 行业板块（英文，来自yfinance）
        industry: 具体行业（英文，来自yfinance）
        
    Returns:
        中文板块名称
    """
    # 优先使用industry映射（更精确）
    if industry and industry in INDUSTRY_TO_SECTOR:
        return INDUSTRY_TO_SECTOR[industry]
    
    # 其次使用sector映射
    if sector and sector in SECTOR_MAPPING:
        return SECTOR_MAPPING[sector]
    
    # 如果都不匹配，尝试模糊匹配
    if sector:
        sector_upper = sector.upper()
        for key, value in SECTOR_MAPPING.items():
            if key.upper() in sector_upper or sector_upper in key.upper():
                return value
    
    if industry:
        industry_upper = industry.upper()
        for key, value in INDUSTRY_TO_SECTOR.items():
            if key.upper() in industry_upper or industry_upper in key.upper():
                return value
    
    # 默认返回"未知"
    return '未知'


def classify_stock_sector(ticker: str, sector: Optional[str] = None, industry: Optional[str] = None) -> str:
    """
    分类股票到中文板块
    
    Args:
        ticker: 股票代码
        sector: 行业板块（英文）
        industry: 具体行业（英文）
        
    Returns:
        中文板块名称
    """
    return get_sector_chinese(sector, industry)

