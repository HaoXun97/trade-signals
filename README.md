# 技術分析交易訊號系統

## 專案簡介

本專案為一套技術分析交易訊號判斷系統，從 MSSQL 資料庫讀取股票/期貨等金融商品的 OHLCV 及技術指標數據，並根據多重交易訊號自動產生買賣建議，最終將分析結果寫回 MSSQL 資料庫，方便後續查詢與應用。

## 主要功能

- 從 MSSQL 資料庫讀取 OHLCV 及技術指標數據（MA、MACD、RSI、KD、布林通道、CCI、WILLR、MOM 等）
- 多重訊號加權自動產生買賣建議
- 分析結果自動寫入 MSSQL `trade_signals` 資料表（支援多 symbol 並保留歷史資料）
- 支援以 symbol 為單位進行分析，不會覆蓋其他商品資料
- 執行效能優化，適合大數據量批次運算

## 使用說明

### 1. 環境準備

- Python 3.8 以上
- 需安裝套件：`pandas`, `numpy`, `pyodbc`, `python-dotenv`
- 需安裝 SQL Server ODBC Driver（建議 17 版以上）

安裝 Python 套件：

```bash
pip install pandas numpy pyodbc python-dotenv
```

### 2. 設定資料庫連線

請於專案根目錄建立 `.env` 或 `.env.local` 檔案，內容範例如下：

```
MSSQL_SERVER=your_server
MSSQL_DATABASE=your_db
MSSQL_TABLE=your_ohlcv_table
MSSQL_USER=your_user
MSSQL_PASSWORD=your_password
```

### 3. 執行分析

直接執行主程式：

```bash
python analyze_signals.py
```

可於程式內修改 `symbol` 變數，指定要分析的商品代碼。

### 4. 分析結果

- 分析結果會自動寫入 MSSQL `trade_signals` 資料表。
- 每次僅會更新該 symbol、該日期區間的資料，不影響其他商品。
- 欄位包含所有技術指標、買賣訊號、強度分數等。

## 資料表結構（trade_signals）

| 欄位名稱        | 型態         | 說明           |
| --------------- | ------------ | -------------- |
| id              | int          | 主鍵，自動編號 |
| datetime        | datetime     | 時間           |
| symbol          | nvarchar(20) | 商品代碼       |
| close_price     | float        | 收盤價         |
| Trade_Signal    | nvarchar(50) | 買賣訊號       |
| Signal_Strength | nvarchar(50) | 訊號強度       |
| Buy_Signals     | float        | 多頭分數       |
| Sell_Signals    | float        | 空頭分數       |
| ...             | ...          | 其他指標欄位   |

## 常見問題

- 若出現 ODBC 連線錯誤，請確認 SQL Server ODBC Driver 已安裝，且帳號密碼正確。
- 若需同時分析多個 symbol，請多次執行主程式並修改 symbol 變數。
- 若需批次分析多商品，可自行撰寫迴圈呼叫分析主流程。
