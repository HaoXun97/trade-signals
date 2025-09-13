# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import pyodbc
import os
from dotenv import load_dotenv

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


# 從 MSSQL 讀取資料（優化版）
def read_ohlcv_from_mssql(
    server, database, table, user, password, chunk_size=50000
):
    """
    優化的資料讀取函數，使用分塊讀取以減少記憶體使用並提升效能
    還加入了更好的連線選項和查詢最佳化
    """
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={user};PWD={password};"
        f"Trusted_Connection=no;Connection Timeout=30;"
        f"Application Name=TechnicalAnalysis"
    )

    try:
        # 使用上下文管理器自動處理連線關閉
        with pyodbc.connect(conn_str) as conn:
            # 設置連線選項
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')

            # 檢查資料量
            count_query = f"SELECT COUNT(*) FROM {table}"
            cursor = conn.cursor()
            row_count = cursor.execute(count_query).fetchval()
            print(f"資料表 {table} 共有 {row_count:,} 筆資料")

            # 如果資料量不大，直接讀取全部
            if row_count <= chunk_size:
                query = f"""
                SELECT * FROM {table}
                ORDER BY datetime
                """
                df = pd.read_sql(query, conn)
                print(f"已一次讀取全部 {len(df):,} 筆資料")
            else:
                # 使用分塊讀取大型資料集
                print("資料量較大，使用分塊讀取...")

                # 獲取日期範圍
                date_range_query = f"""
                SELECT MIN(datetime) as min_date, MAX(datetime) as max_date
                FROM {table}
                """
                date_range = pd.read_sql(date_range_query, conn)
                min_date = date_range['min_date'].iloc[0]
                max_date = date_range['max_date'].iloc[0]

                # 分批讀取資料
                chunks = []
                current_date = min_date
                end_date = max_date

                # 使用日期範圍分批讀取
                while current_date <= end_date:
                    next_date = pd.to_datetime(
                        current_date) + pd.DateOffset(months=3)
                    chunk_query = (
                        f"""
                        SELECT * FROM {table}
                        WHERE datetime >= '{current_date}'
                        AND datetime < '{next_date}'
                        ORDER BY datetime
                        """
                    )
                    chunk = pd.read_sql(chunk_query, conn)
                    chunks.append(chunk)
                    print(
                        f"已讀取 {current_date} 至 {next_date} 期間的 "
                        f"{len(chunk):,} 筆資料"
                    )
                    current_date = next_date

                # 合併所有分塊
                df = pd.concat(chunks, ignore_index=True)
                print(f"共讀取 {len(df):,} 筆資料")

        # 確保 datetime 欄位為 datetime 型態
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')

        # 排序資料並重置索引
        df = df.sort_values('datetime').reset_index(drop=True)

        return df

    except Exception as e:
        print(f"讀取資料時發生錯誤: {str(e)}")
        return pd.DataFrame()

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
    # 向量化：比較當前價格/ dif 與前 lookback 期間的 min/max（不包含當前）
    df = df.copy()
    df['MACD_Div'] = ''
    # 使用 shift(1) 讓滾動區間不包含當前列
    price_shift = df['close_price'].shift(1)
    dif_shift = df['dif'].shift(1)
    price_min = price_shift.rolling(
        window=lookback, min_periods=lookback
    ).min()
    price_max = price_shift.rolling(
        window=lookback, min_periods=lookback
    ).max()
    macd_min = dif_shift.rolling(
        window=lookback, min_periods=lookback
    ).min()
    macd_max = dif_shift.rolling(
        window=lookback, min_periods=lookback
    ).max()

    cond_bottom = (df['close_price'] < price_min) & (df['dif'] > macd_min)
    cond_top = (df['close_price'] > price_max) & (df['dif'] < macd_max)

    df.loc[cond_bottom, 'MACD_Div'] = '底背離'
    df.loc[cond_top, 'MACD_Div'] = '頂背離'
    return df

# 異常偵測（K線異常波動）


def anomaly_detection(df, window=20, threshold=3):
    # 使用滾動平均與標準差計算 z-score，避免對整個序列套用 scipy.zscore
    df = df.copy()
    df['Return'] = df['close_price'].pct_change()
    roll_mean = df['Return'].rolling(window=window, min_periods=window).mean()
    roll_std = df['Return'].rolling(window=window, min_periods=window).std()
    df['ZScore'] = (df['Return'] - roll_mean) / roll_std
    df['ZScore'] = df['ZScore'].replace([np.inf, -np.inf], np.nan).fillna(0)
    df['Anomaly'] = np.where(abs(df['ZScore']) > threshold, 'Anomaly', '')
    # 移除臨時欄位以保持輸出乾淨
    df.drop(columns=['Return', 'ZScore'], inplace=True, errors='ignore')
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
    df = df.copy()
    vol_ma = df['volume'].rolling(window=window, min_periods=1).mean()
    cond = df['volume'] > vol_ma * threshold
    df['Volume_Anomaly'] = np.where(cond, '量能異常', '')
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

    # 向量化設定訊號強度字串，避免逐筆迴圈
    df.loc[df['Trade_Signal'].isin(['買入', '強烈買入']), 'Signal_Strength'] = (
        '多頭' + df.loc[df['Trade_Signal'].isin(['買入', '強烈買入']), 'Buy_Signals']
        .map(lambda v: f'{v:.1f}分')
    )
    df.loc[df['Trade_Signal'].isin(['賣出', '強烈賣出']), 'Signal_Strength'] = (
        '空頭' + df.loc[df['Trade_Signal'].isin(['賣出', '強烈賣出']), 'Sell_Signals']
        .map(lambda v: f'{v:.1f}分')
    )

    return df

# 定義儲存至MSSQL的函數


def save_signals_to_mssql(df, server, database,
                          user, password, table_name='trade_signals'):
    """
    將分析結果儲存至MSSQL資料庫 (優化版)
    使用批量插入而非逐行插入，大幅提升效能
    """
    import time
    start_time = time.time()

    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};UID={user};PWD={password};"
        f"Trusted_Connection=no"
    )

    # 設置連接超時和快速失敗選項
    conn = pyodbc.connect(conn_str, timeout=30)
    cursor = conn.cursor()

    # 確認資料表是否存在，若不存在則建立
    try:
        # 檢查資料表是否存在
        check_table_query = f"""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{table_name}')
        BEGIN
            CREATE TABLE {table_name} (
                id INT IDENTITY(1,1) PRIMARY KEY,
                datetime DATETIME,
                symbol NVARCHAR(20),
                close_price FLOAT,
                Trade_Signal NVARCHAR(50),
                Signal_Strength NVARCHAR(50),
                Buy_Signals FLOAT,
                Sell_Signals FLOAT,
                MA_Cross NVARCHAR(50),
                BB_Signal NVARCHAR(50),
                MACD_Cross NVARCHAR(50),
                Trend NVARCHAR(50),
                MACD_Div NVARCHAR(50),
                RSI_Signal NVARCHAR(50),
                KD_Signal NVARCHAR(50),
                SR_Signal NVARCHAR(50),
                Volume_Anomaly NVARCHAR(50),
                EMA_Cross NVARCHAR(50),
                CCI_Signal NVARCHAR(50),
                WILLR_Signal NVARCHAR(50),
                MOM_Signal NVARCHAR(50),
                Anomaly NVARCHAR(50),
                INDEX idx_datetime (datetime),
                INDEX idx_symbol (symbol)
            )
        END
        """
        cursor.execute(check_table_query)
        conn.commit()

        # 準備要寫入的資料欄位
        required_columns = ['datetime', 'symbol', 'close_price',
                            'Trade_Signal',
                            'Signal_Strength', 'Buy_Signals', 'Sell_Signals',
                            'MA_Cross', 'BB_Signal', 'MACD_Cross', 'Trend',
                            'MACD_Div', 'RSI_Signal', 'KD_Signal', 'SR_Signal',
                            'Volume_Anomaly', 'EMA_Cross', 'CCI_Signal',
                            'WILLR_Signal', 'MOM_Signal', 'Anomaly']

        # 確保DataFrame包含所有需要的欄位
        for col in required_columns:
            if col not in df.columns:
                if col == 'symbol' and 'symbol' not in df.columns:
                    # 如果缺少symbol欄位，新增一個預設值
                    df['symbol'] = 'Unknown'
                else:
                    df[col] = ''

        # 準備批量插入，採用智能更新而非全部清空
        # 1. 只更新當前分析的symbol資料，不影響其他symbol
        if 'symbol' in df.columns and len(df) > 0:
            symbols = list(df['symbol'].unique())
            if symbols and symbols[0] != 'Unknown':
                # 獲取資料的日期範圍，只刪除這個範圍內的資料
                min_date = df['datetime'].min()
                max_date = df['datetime'].max()

                for symbol in symbols:
                    # 對每個symbol，只刪除相同日期範圍的資料
                    delete_query = f"""
                    DELETE FROM {table_name}
                    WHERE symbol = '{symbol}'
                    AND datetime >= '{min_date}' AND datetime <= '{max_date}'
                    """
                    cursor.execute(delete_query)

                conn.commit()
                print(f"已更新 {symbols} 在 {min_date} 到 {max_date} 期間的資料")

        # 2. 使用快速插入方法
        # 設定每批次處理的資料量
        batch_size = 1000
        total_rows = len(df)

        # 構建參數化查詢
        insert_query = f"""
        INSERT INTO {table_name} (datetime, symbol, close_price, Trade_Signal,
                                Signal_Strength, Buy_Signals, Sell_Signals,
                                MA_Cross, BB_Signal, MACD_Cross,
                                Trend, MACD_Div,
                                RSI_Signal, KD_Signal, SR_Signal,
                                Volume_Anomaly,
                                EMA_Cross, CCI_Signal, WILLR_Signal,
                                MOM_Signal, Anomaly)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # 批次處理資料
        for i in range(0, total_rows, batch_size):
            batch_df = df.iloc[i:i+batch_size]
            batch_data = []

            for _, row in batch_df.iterrows():
                record = (
                    row['datetime'],
                    row.get('symbol', 'Unknown'),
                    row['close_price'],
                    row['Trade_Signal'],
                    row['Signal_Strength'],
                    row['Buy_Signals'],
                    row['Sell_Signals'],
                    row['MA_Cross'],
                    row['BB_Signal'],
                    row['MACD_Cross'],
                    row['Trend'],
                    row['MACD_Div'],
                    row['RSI_Signal'],
                    row['KD_Signal'],
                    row['SR_Signal'],
                    row['Volume_Anomaly'],
                    row['EMA_Cross'],
                    row['CCI_Signal'],
                    row['WILLR_Signal'],
                    row['MOM_Signal'],
                    row.get('Anomaly', '')
                )
                batch_data.append(record)

            # 批次執行
            cursor.fast_executemany = True
            cursor.executemany(insert_query, batch_data)
            conn.commit()

            # 顯示進度
            progress = min(i + batch_size, total_rows)
            print(
                f"已處理 {progress}/{total_rows} 筆資料 "
                f"({progress/total_rows*100:.1f}%)")

        # 記錄執行時間
        elapsed_time = time.time() - start_time
        print(f"成功將 {total_rows} 筆資料儲存至 {table_name} 資料表，"
              f"耗時 {elapsed_time:.2f} 秒")

    except Exception as e:
        conn.rollback()
        print(f"儲存資料至MSSQL時發生錯誤: {str(e)}")
    finally:
        cursor.close()
        conn.close()  # 主流程


def analyze_signals_from_db(
        server, database, table, user, password, output_path=None):
    """優化版分析流程，包括效能監控"""
    import time
    total_start_time = time.time()

    print("開始從資料庫讀取資料...")
    read_start = time.time()
    df = read_ohlcv_from_mssql(server, database, table, user, password)
    read_time = time.time() - read_start
    print(f"讀取完成，共 {len(df)} 筆資料，耗時 {read_time:.2f} 秒")

    # 應用所有技術指標計算（加入計時）
    print("開始計算技術指標...")
    calc_start = time.time()

    # 優化：避免重複計算，增加資料預處理
    # 首先對資料進行排序和索引優化
    df = df.sort_values('datetime').reset_index(drop=True)

    # 應用各種技術指標計算
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
    df = cci_signal(df)
    df = willr_signal(df)
    df = momentum_signal(df)

    calc_time = time.time() - calc_start
    print(f"指標計算完成，耗時 {calc_time:.2f} 秒")

    # 產生買賣訊號
    signal_start = time.time()
    df = generate_trade_signals(df)
    signal_time = time.time() - signal_start
    print(f"訊號生成完成，耗時 {signal_time:.2f} 秒")

    # 儲存至MSSQL
    print("開始儲存結果到資料庫...")
    save_start = time.time()
    save_signals_to_mssql(df, server, database, user, password)
    save_time = time.time() - save_start
    print(f"資料庫儲存完成，耗時 {save_time:.2f} 秒")

    # 如果有提供輸出路徑，也同時儲存為CSV
    if output_path:
        csv_start = time.time()
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        csv_time = time.time() - csv_start
        print(f"CSV檔案儲存完成，耗時 {csv_time:.2f} 秒，路徑: {output_path}")

    # 計算總執行時間
    total_time = time.time() - total_start_time
    print(f"\n總執行時間: {total_time:.2f} 秒")
    print(f"- 資料讀取: {read_time:.2f}秒 ({read_time/total_time*100:.1f}%)")
    print(f"- 指標計算: {calc_time:.2f}秒 ({calc_time/total_time*100:.1f}%)")
    print(f"- 訊號生成: {signal_time:.2f}秒 ({signal_time/total_time*100:.1f}%)")
    print(f"- 資料儲存: {save_time:.2f}秒 ({save_time/total_time*100:.1f}%)")

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


def analyze_signals_from_db_with_symbol(
    server, database, table, user, password, output_path=None, symbol=None
):
    """優化版的含symbol分析流程"""
    import time
    total_start_time = time.time()

    print(f"開始分析 symbol={symbol}" if symbol else "開始分析全部資料")

    # 優化：在SQL查詢時就過濾symbol
    if symbol and symbol != 'Unknown':
        # 建立直接過濾symbol的查詢
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};DATABASE={database};UID={user};PWD={password}"
        )
        with pyodbc.connect(conn_str) as conn:
            # 先檢查symbol是否存在
            check_query = f"SELECT COUNT(*) FROM {table} WHERE symbol = ?"
            cursor = conn.cursor()
            count = cursor.execute(check_query, symbol).fetchval()

            if count == 0:
                print(f"找不到 symbol={symbol} 的資料，程式結束。")
                return

            print(f"找到 {count} 筆 {symbol} 的資料，開始讀取...")
            query = f"SELECT * FROM {table} WHERE symbol = ? ORDER BY datetime"
            read_start = time.time()
            df = pd.read_sql(query, conn, params=[symbol])
            read_time = time.time() - read_start
            print(f"讀取完成，耗時 {read_time:.2f} 秒")
    else:
        # 讀取全部資料
        read_start = time.time()
        df = read_ohlcv_from_mssql(server, database, table, user, password)
        read_time = time.time() - read_start

    if df.empty:
        print("沒有資料可分析，程式結束。")
        return

    # 應用各種技術指標計算
    print("開始計算技術指標...")
    calc_start = time.time()

    # 對性能影響較大的指標進行批次計算
    signals = []

    # 計算各類指標訊號
    df = ma_cross_signal(df)
    signals.append("MA交叉")

    df = bollinger_signal(df)
    signals.append("布林通道")

    df = macd_signal(df)
    signals.append("MACD交叉")

    df = trend_signal(df)
    signals.append("趨勢判斷")

    df = macd_divergence(df)
    signals.append("MACD背離")

    df = anomaly_detection(df)
    signals.append("異常偵測")

    df = rsi_signal(df)
    signals.append("RSI訊號")

    df = kd_signal(df)
    signals.append("KD訊號")

    df = support_resistance_signal(df)
    signals.append("壓力支撐位")

    df = volume_anomaly_signal(df)
    signals.append("成交量異常")

    df = ema_cross_signal(df)
    signals.append("EMA交叉")

    df = cci_signal(df)
    signals.append("CCI訊號")

    df = willr_signal(df)
    signals.append("威廉指標")

    df = momentum_signal(df)
    signals.append("動量指標")

    calc_time = time.time() - calc_start
    print(f"指標計算完成，耗時 {calc_time:.2f} 秒，共計算 {len(signals)} 個指標")

    # 生成買賣訊號
    signal_start = time.time()
    df = generate_trade_signals(df)
    signal_time = time.time() - signal_start
    print(f"訊號生成完成，耗時 {signal_time:.2f} 秒")

    # 儲存至MSSQL
    save_start = time.time()
    save_signals_to_mssql(df, server, database, user, password)
    save_time = time.time() - save_start

    # 如果有提供輸出路徑，也同時儲存為CSV
    if output_path:
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f'分析結果已儲存至 {output_path}')

    # 計算總執行時間
    total_time = time.time() - total_start_time
    print(f"\n總執行時間: {total_time:.2f} 秒")
    print(f"- 資料讀取: {read_time:.2f}秒 ({read_time/total_time*100:.1f}%)")
    print(f"- 指標計算: {calc_time:.2f}秒 ({calc_time/total_time*100:.1f}%)")
    print(f"- 訊號生成: {signal_time:.2f}秒 ({signal_time/total_time*100:.1f}%)")
    print(f"- 資料儲存: {save_time:.2f}秒 ({save_time/total_time*100:.1f}%)")

    print_analysis_summary(df)


if __name__ == '__main__':
    import sys
    # 優先讀取 .env.local，若不存在再讀取 .env
    env_local = '.env.local'
    if os.path.exists(env_local):
        load_dotenv(env_local, override=True)
    else:
        load_dotenv()
    # 從環境變數取得 MSSQL 連線參數
    server = os.getenv('MSSQL_SERVER')
    database = os.getenv('MSSQL_DATABASE')
    table = os.getenv('MSSQL_TABLE')
    user = os.getenv('MSSQL_USER')
    password = os.getenv('MSSQL_PASSWORD')
    output_csv = os.getenv('OUTPUT_CSV', '')  # 預設不輸出到CSV

    # 預設 symbol
    default_symbol = '2317'
    # 若有命令列參數則用該 symbol，否則用預設值
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
        print(f"使用命令列參數 symbol: {symbol}")
    else:
        symbol = default_symbol
        print(f"未指定 symbol，使用預設值: {symbol}")

    analyze_signals_from_db_with_symbol(
        server, database, table, user, password, output_csv, symbol)
