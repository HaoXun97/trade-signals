# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from scipy.stats import zscore

# 訊號權重配置
SIGNAL_WEIGHTS = {
    'MACD_Div': 2.0,        # 背離信號 - 最高權重（強力反轉訊號）
    'MA_Cross': 1.5,        # 均線交叉 - 高權重（趨勢確認）
    'MACD_Cross': 1.4,      # MACD交叉 - 高權重（動量確認）
    'EMA_Cross': 1.3,       # EMA交叉 - 高權重（短期趨勢）
    'RSI_Oversold': 1.2,    # RSI超買超賣 - 較高權重（反轉訊號）
    'BB_Break': 1.0,        # 布林通道突破 - 中等權重
    'KD_Cross': 1.0,        # KD交叉 - 中等權重
    'CCI': 0.9,             # CCI - 中低權重
    'WILLR': 0.8,           # 威廉指標 - 中低權重
    'Volume': 0.7,          # 成交量異常 - 輔助權重
    'MOM': 0.6,             # 動量指標 - 輔助權重
    'Trend': 0.5,           # 趨勢判斷 - 輔助權重
    'RSI_Near': 0.4,        # RSI接近 - 較低權重（預警性質）
}


def read_ohlcv(csv_path):
    df = pd.read_csv(csv_path, encoding='utf-8')
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    return df

# 均線突破訊號（ma5/ma20）


def ma_cross_signal(df):
    signal = (df['ma5'] > df['ma20']) & (
        df['ma5'].shift(1) <= df['ma20'].shift(1))
    df['MA_Cross'] = np.where(signal, '突破MA20', '')
    signal = (df['ma5'] < df['ma20']) & (
        df['ma5'].shift(1) >= df['ma20'].shift(1))
    df['MA_Cross'] = np.where(signal, '跌破MA20', df['MA_Cross'])
    return df

# 布林通道突破


def bollinger_signal(df):
    df['BB_Signal'] = ''
    df.loc[df['close_price'] > df['bb_upper'], 'BB_Signal'] = '突破上軌'
    df.loc[df['close_price'] < df['bb_lower'], 'BB_Signal'] = '突破下軌'
    return df

# MACD 黃金/死亡交叉（dif/macd）


def macd_signal(df):
    df['MACD_Cross'] = ''
    cross_up = (df['dif'] > df['macd']) & (
        df['dif'].shift(1) <= df['macd'].shift(1))
    cross_down = (df['dif'] < df['macd']) & (
        df['dif'].shift(1) >= df['macd'].shift(1))
    df.loc[cross_up, 'MACD_Cross'] = '黃金交叉'
    df.loc[cross_down, 'MACD_Cross'] = '死亡交叉'
    return df

# 多空趨勢判斷（ma20）


def trend_signal(df):
    df['Trend'] = np.where(df['close_price'] > df['ma20'], '偏多', '偏空')
    return df

# MACD 與價格背離（簡單判斷）


def macd_divergence(df, lookback=10):
    df['MACD_Div'] = ''
    for i in range(lookback, len(df)):
        price_min = df['close_price'][i-lookback:i].min()
        price_max = df['close_price'][i-lookback:i].max()
        macd_min = df['dif'][i-lookback:i].min()
        macd_max = df['dif'][i-lookback:i].max()
        # 底背離
        if df['close_price'][i] < price_min and df['dif'][i] > macd_min:
            df.at[i, 'MACD_Div'] = '底背離'
        # 頂背離
        if df['close_price'][i] > price_max and df['dif'][i] < macd_max:
            df.at[i, 'MACD_Div'] = '頂背離'
    return df

# 異常偵測（K線異常波動）


def anomaly_detection(df, window=20, threshold=3):
    df['Return'] = df['close_price'].pct_change()
    df['ZScore'] = zscore(df['Return'].fillna(
        0).rolling(window).mean().fillna(0))
    df['Anomaly'] = np.where(abs(df['ZScore']) > threshold, 'Anomaly', '')
    return df

# RSI 訊號


def rsi_signal(df, rsi_col='rsi_14', overbought=70, oversold=30, near=5):
    df['RSI_Signal'] = ''
    df.loc[df[rsi_col] >= overbought, 'RSI_Signal'] = '超買'
    df.loc[df[rsi_col] <= oversold, 'RSI_Signal'] = '超賣'
    df.loc[(df[rsi_col] < overbought) & (
        df[rsi_col] >= overbought - near), 'RSI_Signal'] = '接近超買'
    df.loc[(df[rsi_col] > oversold) & (
        df[rsi_col] <= oversold + near), 'RSI_Signal'] = '接近超賣'
    return df

# KD訊號


def kd_signal(df, k_col='k_value', d_col='d_value'):
    df['KD_Signal'] = ''
    # K上穿D
    cross_up = (df[k_col] > df[d_col]) & (
        df[k_col].shift(1) <= df[d_col].shift(1))
    cross_down = (df[k_col] < df[d_col]) & (
        df[k_col].shift(1) >= df[d_col].shift(1))
    df.loc[cross_up, 'KD_Signal'] = 'K上穿D'
    df.loc[cross_down, 'KD_Signal'] = 'K下穿D'
    # 超買/超賣
    df.loc[(df[k_col] > 80) & (df[d_col] > 80), 'KD_Signal'] = 'KD超買'
    df.loc[(df[k_col] < 20) & (df[d_col] < 20), 'KD_Signal'] = 'KD超賣'
    return df

# 壓力位/支撐位（以bb_upper/bb_lower為例）


def support_resistance_signal(df):
    df['SR_Signal'] = ''
    df.loc[(df['close_price'] >= df['bb_upper'] * 0.98), 'SR_Signal'] = '接近壓力位'
    df.loc[(df['close_price'] <= df['bb_lower'] * 1.02), 'SR_Signal'] = '接近支撐位'
    return df

# 成交量異常（大於均量1.5倍）


def volume_anomaly_signal(df, window=20, threshold=1.5):
    df['vol_ma'] = df['volume'].rolling(window).mean()
    df['Volume_Anomaly'] = np.where(
        df['volume'] > df['vol_ma'] * threshold, '量能異常', '')
    return df

# EMA訊號（ema12/ema26交叉）


def ema_cross_signal(df):
    df['EMA_Cross'] = ''
    cross_up = (df['ema12'] > df['ema26']) & (
        df['ema12'].shift(1) <= df['ema26'].shift(1))
    cross_down = (df['ema12'] < df['ema26']) & (
        df['ema12'].shift(1) >= df['ema26'].shift(1))
    df.loc[cross_up, 'EMA_Cross'] = 'EMA黃金交叉'
    df.loc[cross_down, 'EMA_Cross'] = 'EMA死亡交叉'
    return df


# CCI 訊號
def cci_signal(df, cci_col='cci', overbought=100, oversold=-100):
    df['CCI_Signal'] = ''
    df.loc[df[cci_col] >= overbought, 'CCI_Signal'] = 'CCI超買'
    df.loc[df[cci_col] <= oversold, 'CCI_Signal'] = 'CCI超賣'
    # CCI 穿越零軸
    cross_up = (df[cci_col] > 0) & (df[cci_col].shift(1) <= 0)
    cross_down = (df[cci_col] < 0) & (df[cci_col].shift(1) >= 0)
    df.loc[cross_up, 'CCI_Signal'] = 'CCI上穿零軸'
    df.loc[cross_down, 'CCI_Signal'] = 'CCI下穿零軸'
    return df


# 威廉指標訊號
def willr_signal(df, willr_col='willr', overbought=-20, oversold=-80):
    df['WILLR_Signal'] = ''
    df.loc[df[willr_col] >= overbought, 'WILLR_Signal'] = 'WILLR超買'
    df.loc[df[willr_col] <= oversold, 'WILLR_Signal'] = 'WILLR超賣'
    return df


# 動量指標訊號
def momentum_signal(df, mom_col='mom'):
    df['MOM_Signal'] = ''
    # 動量穿越零軸
    cross_up = (df[mom_col] > 0) & (df[mom_col].shift(1) <= 0)
    cross_down = (df[mom_col] < 0) & (df[mom_col].shift(1) >= 0)
    df.loc[cross_up, 'MOM_Signal'] = '動量轉正'
    df.loc[cross_down, 'MOM_Signal'] = '動量轉負'
    return df


# 買賣訊號統計與判斷（優化版）
def generate_trade_signals(df, min_signals=3):
    """
    根據多個技術指標訊號產生買賣建議
    當達到最低訊號數量時發出買賣訊號
    """
    # 初始化買賣訊號計數（使用浮點數型態）
    df['Buy_Signals'] = 0.0
    df['Sell_Signals'] = 0.0

    # 多頭訊號統計（使用配置權重）
    buy_conditions = [
        (df['MA_Cross'] == '突破MA20', SIGNAL_WEIGHTS['MA_Cross']),
        (df['MACD_Cross'] == '黃金交叉', SIGNAL_WEIGHTS['MACD_Cross']),
        (df['EMA_Cross'] == 'EMA黃金交叉', SIGNAL_WEIGHTS['EMA_Cross']),
        (df['KD_Signal'] == 'K上穿D', SIGNAL_WEIGHTS['KD_Cross']),
        (df['RSI_Signal'] == '超賣', SIGNAL_WEIGHTS['RSI_Oversold']),
        (df['RSI_Signal'] == '接近超賣', SIGNAL_WEIGHTS['RSI_Near']),
        (df['BB_Signal'] == '突破下軌', SIGNAL_WEIGHTS['BB_Break']),
        (df['MACD_Div'] == '底背離', SIGNAL_WEIGHTS['MACD_Div']),
        (df['Trend'] == '偏多', SIGNAL_WEIGHTS['Trend']),
        (df['Volume_Anomaly'] == '量能異常', SIGNAL_WEIGHTS['Volume']),
        (df['CCI_Signal'] == 'CCI超賣', SIGNAL_WEIGHTS['CCI']),
        (df['CCI_Signal'] == 'CCI上穿零軸', SIGNAL_WEIGHTS['CCI']),
        (df['WILLR_Signal'] == 'WILLR超賣', SIGNAL_WEIGHTS['WILLR']),
        (df['MOM_Signal'] == '動量轉正', SIGNAL_WEIGHTS['MOM']),
        (df['KD_Signal'] == 'KD超賣', SIGNAL_WEIGHTS['KD_Cross'])
    ]

    for condition, weight in buy_conditions:
        df.loc[condition, 'Buy_Signals'] += weight

    # 空頭訊號統計（使用配置權重）
    sell_conditions = [
        (df['MA_Cross'] == '跌破MA20', SIGNAL_WEIGHTS['MA_Cross']),
        (df['MACD_Cross'] == '死亡交叉', SIGNAL_WEIGHTS['MACD_Cross']),
        (df['EMA_Cross'] == 'EMA死亡交叉', SIGNAL_WEIGHTS['EMA_Cross']),
        (df['KD_Signal'] == 'K下穿D', SIGNAL_WEIGHTS['KD_Cross']),
        (df['RSI_Signal'] == '超買', SIGNAL_WEIGHTS['RSI_Oversold']),
        (df['RSI_Signal'] == '接近超買', SIGNAL_WEIGHTS['RSI_Near']),
        (df['BB_Signal'] == '突破上軌', SIGNAL_WEIGHTS['BB_Break']),
        (df['MACD_Div'] == '頂背離', SIGNAL_WEIGHTS['MACD_Div']),
        (df['Trend'] == '偏空', SIGNAL_WEIGHTS['Trend']),
        (df['KD_Signal'] == 'KD超買', SIGNAL_WEIGHTS['KD_Cross']),
        (df['CCI_Signal'] == 'CCI超買', SIGNAL_WEIGHTS['CCI']),
        (df['CCI_Signal'] == 'CCI下穿零軸', SIGNAL_WEIGHTS['CCI']),
        (df['WILLR_Signal'] == 'WILLR超買', SIGNAL_WEIGHTS['WILLR']),
        (df['MOM_Signal'] == '動量轉負', SIGNAL_WEIGHTS['MOM'])
    ]

    for condition, weight in sell_conditions:
        df.loc[condition, 'Sell_Signals'] += weight

    # 產生最終買賣訊號
    df['Trade_Signal'] = ''
    df['Signal_Strength'] = ''

    # 買入訊號
    strong_buy = df['Buy_Signals'] >= min_signals + 1
    buy = (df['Buy_Signals'] >= min_signals) & (~strong_buy)

    # 賣出訊號
    strong_sell = df['Sell_Signals'] >= min_signals + 1
    sell = (df['Sell_Signals'] >= min_signals) & (~strong_sell)

    # 設定訊號
    df.loc[strong_buy, 'Trade_Signal'] = '強烈買入'
    df.loc[buy, 'Trade_Signal'] = '買入'
    df.loc[strong_sell, 'Trade_Signal'] = '強烈賣出'
    df.loc[sell, 'Trade_Signal'] = '賣出'

    # 修正訊號強度計算
    for idx in df[strong_buy].index:
        df.at[idx, 'Signal_Strength'] = f'多頭{df.at[idx, "Buy_Signals"]:.1f}分'
    for idx in df[buy].index:
        df.at[idx, 'Signal_Strength'] = f'多頭{df.at[idx, "Buy_Signals"]:.1f}分'
    for idx in df[strong_sell].index:
        df.at[idx, 'Signal_Strength'] = f'空頭{df.at[idx, "Sell_Signals"]:.1f}分'
    for idx in df[sell].index:
        df.at[idx, 'Signal_Strength'] = f'空頭{df.at[idx, "Sell_Signals"]:.1f}分'

    return df

# 主流程


def analyze_signals(csv_path, output_path):
    df = read_ohlcv(csv_path)
    df = ma_cross_signal(df)
    df = bollinger_signal(df)
    df = macd_signal(df)
    df = trend_signal(df)
    df = macd_divergence(df)
    df = anomaly_detection(df)
    df = rsi_signal(df)
    df = kd_signal(df)
    df = support_resistance_signal(df)
    df = volume_anomaly_signal(df)
    df = ema_cross_signal(df)
    df = cci_signal(df)  # 新增CCI訊號
    df = willr_signal(df)  # 新增威廉指標訊號
    df = momentum_signal(df)  # 新增動量指標訊號
    df = generate_trade_signals(df)  # 新增買賣訊號判斷
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f'分析完成，結果已儲存至 {output_path}')

    # 顯示詳細統計資訊
    print_analysis_summary(df)


def print_analysis_summary(df):
    """顯示詳細的分析統計資訊"""
    print("\n=== 交易訊號分析報告 ===")

    # 總體統計
    total_records = len(df)
    signal_records = len(df[df['Trade_Signal'] != ''])

    print(f"總資料筆數: {total_records:,}")
    print(
        f"有訊號筆數: {signal_records:,} ({signal_records/total_records*100:.1f}%)")

    # 交易訊號統計
    trade_counts = df['Trade_Signal'].value_counts()
    print("\n交易訊號統計：")
    for signal, count in trade_counts.items():
        if signal != '':
            percentage = count/total_records*100
            print(f"  {signal}: {count:,} 次 ({percentage:.2f}%)")

    # 訊號強度分布
    buy_signals = df[df['Trade_Signal'].isin(['買入', '強烈買入'])]
    sell_signals = df[df['Trade_Signal'].isin(['賣出', '強烈賣出'])]

    if len(buy_signals) > 0:
        avg_buy_strength = buy_signals['Buy_Signals'].mean()
        max_buy_strength = buy_signals['Buy_Signals'].max()
        print(
            f"\n多頭訊號強度: 平均 {avg_buy_strength:.1f}分, "
            f"最高 {max_buy_strength:.1f}分"
        )

    if len(sell_signals) > 0:
        avg_sell_strength = sell_signals['Sell_Signals'].mean()
        max_sell_strength = sell_signals['Sell_Signals'].max()
        print(
            f"空頭訊號強度: 平均 {avg_sell_strength:.1f}分, "
            f"最高 {max_sell_strength:.1f}分"
        )

    # 最新訊號
    latest_signals = df[df['Trade_Signal'] != ''].tail(3)
    if len(latest_signals) > 0:
        print("\n最近3個交易訊號:")
        for _, row in latest_signals.iterrows():
            print(
                f"  {row['datetime'].strftime('%Y-%m-%d')}: "
                f"{row['Trade_Signal']} ({row['Signal_Strength']})"
            )


if __name__ == '__main__':
    # 請將此路徑改為你的CSV檔案路徑
    input_csv = 'data/2330.csv'
    output_csv = 'data/2330_signals.csv'
    analyze_signals(input_csv, output_csv)
