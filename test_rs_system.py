"""
快速测试脚本：验证 RS 排名系统是否正常工作
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rs_system.main import run_rs_ranking
from rs_system.config import DEFAULT_TICKERS

if __name__ == "__main__":
    print("=" * 80)
    print("RS 排名系统 - 快速测试")
    print("=" * 80)
    print("\n使用少量股票进行测试（5只）...")
    
    # 使用前5只股票进行快速测试
    test_tickers = DEFAULT_TICKERS[:5]
    print(f"测试股票: {', '.join(test_tickers)}")
    print("\n开始测试...\n")
    
    try:
        result = run_rs_ranking(
            tickers=test_tickers,
            save_csv=True,
            print_report=True
        )
        
        if result is not None and not result.empty:
            print("\n" + "=" * 80)
            print("✅ 测试成功！系统运行正常。")
            print("=" * 80)
            print(f"\n生成了 {len(result)} 只股票的排名结果")
            print(f"结果已保存到: output/rs_rankings.csv")
        else:
            print("\n❌ 测试失败：未能生成排名结果")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 测试失败：{str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

