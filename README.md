# 技術分析交易訊號系統

## 專案簡介

本專案為一套技術分析交易訊號判斷系統，從 MSSQL 資料庫讀取股票等金融商品的 OHLCV 及技術指標數據，並根據多重交易訊號自動產生買賣建議，最終將分析結果寫回 MSSQL 資料庫，方便後續查詢與應用。

## 專案結構

```
技術分析 Technical-Analysis/
├── signals/                 # 核心分析模組
│   ├── __init__.py
│   ├── analyzer.py          # 主分析流程
│   ├── config.py            # 訊號權重配置
│   ├── db.py                # 資料庫讀寫
│   ├── indicators.py        # 技術指標計算
│   └── trades.py            # 交易訊號生成
├── output/                  # 檔案輸出
├── .env                     # 環境變數配置
├── main.py                  # 主程式入口
├── requirements.txt         # 套件依賴
└── README.md
```

## 主要功能

- **多市場支援**：支援台股、美股、ETF、指數、外匯、加密貨幣、期貨等多種市場
- **多時間週期**：支援日線(1d)、小時線(1h)等不同時間週期
- **豐富技術指標**：MA 交叉、MACD、RSI、KD、布林通道、EMA、CCI、威廉指標、動量指標等
- **智能訊號生成**：多重訊號加權自動產生買賣建議，支援強度評分
- **高效資料處理**：支援大數據量分塊讀取，MERGE upsert 機制保留歷史資料
- **靈活輸出**：可輸出至資料庫或 CSV 檔案

## 使用說明

### 1. 環境準備

- Python 3.8 以上
- 需安裝 SQL Server ODBC Driver（建議 17 版以上）

安裝 Python 套件：

```bash
pip install -r requirements.txt
```

### 2. 設定資料庫連線

請於專案根目錄建立 `.env` 或 `.env.local` 檔案，內容範例如下：

```
MSSQL_SERVER = your_server
MSSQL_DATABASE = market_stock_tw        # 預設資料庫
MSSQL_TABLE = stock_data_1d             # 預設資料表
MSSQL_USER = your_user
MSSQL_PASSWORD = your_password
```

### 3. 執行分析

#### 命令列範例

```bash
# 基本語法
python main.py <symbol1> [<symbol2> ...] [options]

# 查看說明
python main.py -h

# 分析指定商品
python main.py 2330

# 分析美股多個商品小時數據
python main.py AAPL MSFT --us --1h

# 同時輸出 CSV 到 output 目錄
python main.py 2330 --output

# 指定輸出檔名 (輸出至根目錄)
python main.py 2330 --output result.csv
```

### 4. 分析結果

- 分析結果會自動寫入對應的資料庫的 `trade_signals` 資料表（如 `trade_signals_1d`、`trade_signals_1h`）
- 可選擇同時輸出 CSV 檔案至 `output/` 目錄

## 技術指標與訊號

### 支援的技術指標

- **移動平均線**：MA 交叉、EMA 交叉
- **趨勢指標**：MACD 交叉、MACD 背離、趨勢判斷
- **震盪指標**：RSI、KD、CCI、威廉指標
- **通道指標**：布林通道突破
- **成交量**：量能異常偵測
- **動量指標**：動量轉折
- **支撐壓力**：壓力支撐位判斷

### 訊號權重配置

系統根據各指標重要性設定權重（可在 `signals/config.py` 調整）：

- MACD 背離：2.0
- MA 交叉：1.5
- MACD 交叉：1.4
- EMA 交叉：1.3
- RSI 超買超賣：1.2
- 其他指標：0.4-1.0

### 交易訊號生成

- **買入**：多頭訊號分數 ≥ 3 分
- **強烈買入**：多頭訊號分數 ≥ 4 分
- **賣出**：空頭訊號分數 ≥ 3 分
- **強烈賣出**：空頭訊號分數 ≥ 4 分

## 資料表結構

### trade_signals 系列表格

| 欄位名稱        | 型態         | 說明                        |
| --------------- | ------------ | --------------------------- |
| id              | int          | 主鍵，自動編號              |
| datetime        | datetime     | 時間                        |
| symbol          | nvarchar(20) | 商品代碼                    |
| close_price     | float        | 收盤價                      |
| Trade_Signal    | nvarchar(50) | 買賣訊號                    |
| Signal_Strength | nvarchar(50) | 訊號強度（如：多頭 4.2 分） |
| Buy_Signals     | float        | 多頭分數                    |
| Sell_Signals    | float        | 空頭分數                    |
| MA_Cross        | nvarchar(50) | MA 交叉訊號                 |
| MACD_Cross      | nvarchar(50) | MACD 交叉訊號               |
| RSI_Signal      | nvarchar(50) | RSI 訊號                    |
| ...             | ...          | 其他技術指標欄位            |

## 命令列參數說明

### 基本參數

- `-s, --symbol`：指定商品代碼（可多個）
- `-d, --database`：指定資料庫名稱
- `-t, --table`：指定資料表名稱
- `--output`：輸出 CSV 檔案

### 市場選擇

- `--tw`：台股 (market_stock_tw)
- `--us`：美股 (market_stock_us)
- `--etf`：ETF (market_etf)
- `--index`：指數 (market_index)
- `--forex`：外匯 (market_forex)
- `--crypto`：加密貨幣 (market_crypto)
- `--futures`：期貨 (market_futures)

### 時間週期

- `--1d`：日線 (stock_data_1d)
- `--1h`：小時線 (stock_data_1h)

## 常見問題

### 資料庫連線問題

- 確認 SQL Server ODBC Driver 17 已安裝
- 檢查 `.env` 檔案中的連線參數
- 確認資料庫伺服器可連線且帳號密碼正確

### 資料表不存在

- 確認指定的資料表名稱正確
- 系統會自動建立 `trade_signals` 相關表格
- 檢查資料庫權限是否足夠

## 開發說明

### 新增技術指標

1. 在 `signals/indicators.py` 新增指標計算函式
2. 在 `signals/analyzer.py` 中呼叫新指標
3. 在 `signals/trades.py` 中加入買賣條件
4. 在 `signals/config.py` 中設定權重

### 自訂訊號權重

編輯 `signals/config.py` 中的 `SIGNAL_WEIGHTS` 字典，調整各指標權重。

## 授權

本專案僅供學習研究使用，投資有風險，請謹慎評估。
