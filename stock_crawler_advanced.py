#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台灣股票爬蟲助手 (進階版)
功能: 支援上市、上櫃、ETF - 從官方API獲取股票一個月資料並繪製圖表
使用方式: python stock_crawler_advanced.py
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import sys

# 設定中文字體
rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial']
rcParams['axes.unicode_minus'] = False

class TaiwanStockCrawlerAdvanced:
    """支援上市、上櫃、ETF的台灣股票爬蟲"""
    
    def __init__(self):
        # 證交所 API (上市)
        self.tse_base_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY"
        self.tse_stock_info = "https://openapi.twse.com.tw/v1/reference/stockInfo"
        
        # 櫃檯買賣中心 API (上櫃)
        self.otc_base_url = "https://www.tpex.org.tw/openapi/v1/DAILY_CANDLE"
        self.otc_stock_info = "https://www.tpex.org.tw/openapi/v1/SECURITY_INFO"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # 禁用 SSL 驗證以解決櫃買中心 API 的證書問題
        self.session.verify = False
    
    def validate_stock_code(self, stock_code):
        """驗證股票代號格式
        
        台股代號規則:
        - 上市/上櫃: 4位數字 (例: 2303, 6488)
        - ETF: 5-6位 (純數字 或 數字+字母) (例: 00940, 00403A, 00687B)
        - 都必須以數字開頭
        """
        if not isinstance(stock_code, str):
            return False
        stock_code = stock_code.strip()
        
        # 移除 .TW 尾碼
        if stock_code.endswith('.TW'):
            stock_code = stock_code[:-3]
        
        # 驗證: 長度 4-6位 且首字為數字 (支援含字母的ETF)
        # ❌ 不用 stock_code.isdigit() 因為會拒絕 00403A、00687B 等含字母的ETF
        # ✓ 用 stock_code[0].isdigit() 只檢查首位是數字即可
        return 4 <= len(stock_code) <= 6 and stock_code[0].isdigit()
    

    def get_tse_stock_info(self, stock_code):
        """從證交所取得股票資訊 (上市)"""
        try:
            params = {"response": "json"}
            response = self.session.get(self.tse_stock_info, params=params, timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                    for item in data.get('data', []):
                        if item[0] == stock_code:
                            return {
                                'name': item[1],
                                'market': 'tse',  # 上市
                                'code': stock_code
                            }
                except Exception as json_err:
                    print(f"⚠️  證交所 JSON 解析失敗: {str(json_err)[:50]}")
        except Exception as e:
            print(f"⚠️  查詢上市股票失敗: {str(e)[:50]}")
        return None
    
    def get_otc_stock_info(self, stock_code):
        """從櫃買中心取得股票資訊 (上櫃)"""
        try:
            params = {"response": "json"}
            response = self.session.get(self.otc_stock_info, params=params, timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                    for item in data.get('data', []):
                        if item[0] == stock_code:
                            return {
                                'name': item[1],
                                'market': 'otc',  # 上櫃
                                'code': stock_code
                            }
                except Exception as json_err:
                    print(f"⚠️  櫃買中心 JSON 解析失敗: {str(json_err)[:50]}")
        except Exception as e:
            print(f"⚠️  查詢上櫃股票失敗: {str(e)[:50]}")
        return None
    
    def get_stock_info(self, stock_code):
        """自動判斷並取得股票資訊"""
        stock_code = stock_code.strip()
        
        # 優先查詢上市
        info = self.get_tse_stock_info(stock_code)
        if info:
            return info
        
        # 再查詢上櫃
        info = self.get_otc_stock_info(stock_code)
        if info:
            return info
        
        return None
    
    def fetch_tse_data(self, stock_code, days=30):
        """從證交所取得上市股票資料"""
        all_data = []
        current_date = datetime.now()
        
        print(f"正在從證交所 API 取得 {stock_code} 的資料...")
        
        for i in range(min(120, days * 4)):
            date = current_date - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            
            try:
                params = {
                    "response": "json",
                    "date": date_str,
                    "stockNo": stock_code
                }
                
                response = self.session.get(self.tse_base_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('stat') == 'ok' and data.get('data'):
                        all_data.extend(data['data'])
                        print(f"  ✓ {date_str}: 取得 {len(data['data'])} 筆資料")
                        
                        if len(all_data) >= days:
                            break
                            
            except Exception as e:
                continue
        
        return all_data if all_data else None
    
    def fetch_otc_data(self, stock_code, days=30):
        """從櫃買中心取得上櫃股票資料"""
        all_data = []
        current_date = datetime.now()
        
        print(f"正在從櫃買中心 API 取得 {stock_code} 的資料...")
        
        for i in range(min(120, days * 4)):
            date = current_date - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            
            try:
                params = {
                    "response": "json",
                    "date": date_str,
                    "symbol": stock_code
                }
                
                response = self.session.get(self.otc_base_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('stat') == 'ok' and data.get('data'):
                        all_data.extend(data['data'])
                        print(f"  ✓ {date_str}: 取得 {len(data['data'])} 筆資料")
                        
                        if len(all_data) >= days:
                            break
                            
            except Exception as e:
                continue
        
        return all_data if all_data else None
    
    def fetch_stock_data(self, stock_code, stock_info, days=30):
        """根據市場類型取得股票資料"""
        raw_data = None
        
        if stock_info['market'] == 'tse':
            raw_data = self.fetch_tse_data(stock_code, days)
        elif stock_info['market'] == 'otc':
            raw_data = self.fetch_otc_data(stock_code, days)
        
        if not raw_data:
            print(f"❌ 無法取得代號 {stock_code} 的資料")
            return None
        
        # 轉換為 DataFrame
        df = pd.DataFrame(raw_data)
        
        # 統一欄位名稱
        column_mapping = {
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }
        
        # 重新命名欄位
        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume'] + list(df.columns[6:])
        
        # 數據清理
        try:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        except Exception as e:
            print(f"⚠️  數據轉換錯誤: {e}")
            return None
        
        # 排序並取最近的 days 筆資料
        df = df.dropna(subset=['date']).sort_values('date').tail(days).reset_index(drop=True)
        
        return df
    
    def plot_stock_chart(self, df, stock_code, stock_name, market_type, save_path='stock_chart.png'):
        """繪製股票圖表"""
        if df is None or df.empty:
            print("❌ 無資料可繪圖")
            return
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 繪製線圖
        ax.plot(df['date'], df['close'], label='收盤價', color='#1f77b4', linewidth=2.5, marker='o', markersize=4)
        ax.plot(df['date'], df['high'], label='最高價', color='#2ca02c', linewidth=1, linestyle='--', alpha=0.7)
        ax.plot(df['date'], df['low'], label='最低價', color='#d62728', linewidth=1, linestyle='--', alpha=0.7)
        ax.fill_between(df['date'], df['low'], df['high'], alpha=0.1, color='gray')
        
        # 設定標題
        market_label = {
            'tse': '(上市)',
            'otc': '(上櫃)',
            'etf': '(ETF)'
        }.get(market_type, '')
        
        title = f"股票 {stock_code} {market_label} {stock_name}" if stock_name else f"股票 {stock_code} {market_label}"
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('股價 (台幣)', fontsize=12)
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # 格式化日期
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate(rotation=45, ha='right')
        
        # 添加統計資訊
        if not df.empty:
            current_price = df['close'].iloc[-1]
            first_price = df['close'].iloc[0]
            highest = df['high'].max()
            lowest = df['low'].min()
            change = current_price - first_price
            change_pct = (change / first_price) * 100
            
            info_text = (
                f"現價: {current_price:.2f} | "
                f"最高: {highest:.2f} | "
                f"最低: {lowest:.2f} | "
                f"漲跌: {change:+.2f} ({change_pct:+.2f}%)"
            )
            ax.text(0.5, -0.15, info_text, transform=ax.transAxes, 
                   ha='center', fontsize=11, 
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ 圖表已保存: {save_path}")
        plt.show()
    
    def print_stock_info(self, df, stock_code, stock_name, market_type):
        """列印股票資訊"""
        if df is None or df.empty:
            print(f"❌ 代號: {stock_code} - 無資料")
            return
        
        market_label = {
            'tse': '上市',
            'otc': '上櫃',
            'etf': 'ETF'
        }.get(market_type, '未知')
        
        print(f"\n{'='*70}")
        print(f"  股票代號: {stock_code}")
        print(f"  市場類型: {market_label}")
        if stock_name:
            print(f"  股票名稱: {stock_name}")
        print(f"{'='*70}")
        
        # 統計資訊
        current_price = df['close'].iloc[-1]
        first_price = df['close'].iloc[0]
        highest = df['high'].max()
        lowest = df['low'].min()
        avg_price = df['close'].mean()
        change = current_price - first_price
        change_pct = (change / first_price) * 100
        volume = df['volume'].sum()
        
        print(f"\n  現價:     {current_price:>10.2f} 元")
        print(f"  最高:     {highest:>10.2f} 元")
        print(f"  最低:     {lowest:>10.2f} 元")
        print(f"  平均:     {avg_price:>10.2f} 元")
        print(f"  漲跌:     {change:>+10.2f} 元 ({change_pct:>+7.2f}%)")
        print(f"  總成交量: {volume:>10.0f} 張")
        print(f"  交易天數: {len(df):>10} 天")
        print(f"{'='*70}\n")
        
        # 詳細資料表
        print("  詳細資料 (最近20個交易日):")
        print(f"  {'日期':<12} {'開盤':>8} {'最高':>8} {'最低':>8} {'收盤':>8} {'成交量(張)':>12}")
        print(f"  {'-'*60}")
        
        for idx, row in df.tail(20).iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            print(f"  {date_str}  {row['open']:>8.2f} {row['high']:>8.2f} {row['low']:>8.2f} {row['close']:>8.2f} {row['volume']:>12.0f}")
        
        print()


def main():
    """主程式"""
    print("\n" + "="*70)
    print("  台灣股票爬蟲助手 v2.0 (進階版)")
    print("  支援: 上市股票、上櫃股票、ETF")
    print("="*70)
    
    # 輸入股票代號
    while True:
        stock_input = input("\n請輸入股票代號 (例如: 2303, 00940): ").strip()
        
        if not stock_input:
            print("❌ 請輸入股票代號")
            continue
        
        break
    
    # 建立爬蟲
    crawler = TaiwanStockCrawlerAdvanced()
    
    # 驗證代號
    if not crawler.validate_stock_code(stock_input):
        print("❌ 股票代號格式不正確")
        return
    
    # 取得股票資訊
    print(f"\n正在查詢股票 {stock_input}...")
    stock_info = crawler.get_stock_info(stock_input)
    
    if not stock_info:
        print(f"❌ 無法找到代號 {stock_input} 的股票")
        print("\n可能的原因:")
        print("   1. 股票代號格式不正確")
        print("   2. 該股票尚未上市或已下市")
        print("   3. 新上市 ETF - API 資料更新延遲（通常 1-3 天）")
        print("   4. 網路連線問題或 API 服務中斷")
        print("\n建議:")
        print("   • 確認代號是否正確 (例如: 2303, 00940, 00403A)")
        print("   • 造訪 https://tw.stock.yahoo.com 確認代號有效")
        print("   • 如為新上市商品，請稍後重試")
        return
    
    print(f"✓ 找到: {stock_info['name']} ({['上市', '上櫃', 'ETF'][['tse', 'otc', 'etf'].index(stock_info['market'])]})")
    
    # 取得股票資料
    df = crawler.fetch_stock_data(stock_input, stock_info, days=30)
    
    if df is None or df.empty:
        print(f"\n❌ 無法取得 {stock_input} 的資料")
        return
    
    # 列印資訊
    crawler.print_stock_info(df, stock_input, stock_info['name'], stock_info['market'])
    
    # 繪製圖表
    crawler.plot_stock_chart(df, stock_input, stock_info['name'], stock_info['market'])
    
    print("\n✓ 處理完成！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中止程式")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
