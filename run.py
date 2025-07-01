import pandas as pd
import talib

# 所有K線型態函數與中文註解對應表
candle_patterns = [
    ('CDL2CROWS', '兩隻烏鴉'),
    ('CDL3BLACKCROWS', '三隻烏鴉'),
    ('CDL3INSIDE', '三內部漲跌'),
    ('CDL3LINESTRIKE', '三線打擊'),
    ('CDL3OUTSIDE', '三外部漲跌'),
    ('CDL3STARSINSOUTH', '三南方之星'),
    ('CDL3WHITESOLDIERS', '三白兵'),
    ('CDLABANDONEDBABY', '棄嬰'),
    ('CDLADVANCEBLOCK', '上升區塊'),
    ('CDLBELTHOLD', '捉腰帶線'),
    ('CDLBREAKAWAY', '脫離'),
    ('CDLCLOSINGMARUBOZU', '光頭光腳(單頭腳判定)'),
    ('CDLCONCEALBABYSWALL', '藏嬰吞沒'),
    ('CDLCOUNTERATTACK', '反擊線'),
    ('CDLDARKCLOUDCOVER', '烏雲蓋頂'),
    ('CDLDOJI', '十字'),
    ('CDLDOJISTAR', '十字星'),
    ('CDLDRAGONFLYDOJI', '蜻蜓十字'),
    ('CDLENGULFING', '吞沒形態'),
    ('CDLEVENINGDOJISTAR', '十字暮星'),
    ('CDLEVENINGSTAR', '暮星'),
    ('CDLGAPSIDESIDEWHITE', '缺口上漲'),
    ('CDLGRAVESTONEDOJI', '墓碑十字'),
    ('CDLHAMMER', '錘頭'),
    ('CDLHANGINGMAN', '上吊線'),
    ('CDLHARAMI', '孕線'),
    ('CDLHARAMICROSS', '十字孕線'),
    ('CDLHIGHWAVE', '風高浪大線'),
    ('CDLHIKKAKE', 'Hikkake 陷阱'),
    ('CDLHIKKAKEMOD', 'Hikkake Modified'),
    ('CDLHOMINGPIGEON', '家鴿'),
    ('CDLIDENTICAL3CROWS', '三胞胎烏鴉'),
    ('CDLINNECK', '頸內線'),
    ('CDLINVERTEDHAMMER', '倒錘頭'),
    ('CDLKICKING', '反沖形態'),
    ('CDLKICKINGBYLENGTH', '反沖-長短判斷'),
    ('CDLLADDERBOTTOM', '梯形底部'),
    ('CDLLONGLEGGEDDOJI', '長腿十字'),
    ('CDLLONGLINE', '長蠟燭'),
    ('CDLMARUBOZU', '光頭光腳'),
    ('CDLMATCHINGLOW', '匹配低點'),
    ('CDLMATHOLD', '鋪墊'),
    ('CDLMORNINGDOJISTAR', '十字晨星'),
    ('CDLMORNINGSTAR', '晨星'),
    ('CDLONNECK', '頸上線'),
    ('CDLPIERCING', '刺穿形態'),
    ('CDLRICKSHAWMAN', '黃包車夫'),
    ('CDLRISEFALL3METHODS', '上升/下降三法'),
    ('CDLSEPARATINGLINES', '分離線'),
    ('CDLSHOOTINGSTAR', '射擊星'),
    ('CDLSHORTLINE', '短蠟燭'),
    ('CDLSPINNINGTOP', '紡錘線'),
    ('CDLSTALLEDPATTERN', '停滯形態'),
    ('CDLSTICKSANDWICH', '三明治'),
    ('CDLTAKURI', '探水竿'),
    ('CDLTASUKIGAP', '跳空並列(月缺)'),
    ('CDLTHRUSTING', '向上突破'),
    ('CDLTRISTAR', '三星'),
    ('CDLUNIQUE3RIVER', '奇特三河床'),
    ('CDLUPSIDEGAP2CROWS', '向上跳空兩隻烏鴉'),
    ('CDLXSIDEGAP3METHODS', '跳空三法'),
]


def main():
    df = pd.read_csv('2330.csv')
    df = df.rename(columns={
        'open_price': 'open',
        'high_price': 'high',
        'low_price': 'low',
        'close_price': 'close',
        'volume': 'volume'
    })
    open_ = df['open'].values
    high_ = df['high'].values
    low_ = df['low'].values
    close_ = df['close'].values

    # 自動呼叫所有型態函數
    for func_name, _ in candle_patterns:
        func = getattr(talib, func_name)
        # 部分型態需要 penetration 參數
        if func_name in ['CDLDARKCLOUDCOVER',
                         'CDLEVENINGDOJISTAR',
                         'CDLEVENINGSTAR',
                         'CDLMATHOLD',
                         'CDLMORNINGDOJISTAR',
                         'CDLMORNINGSTAR']:
            df[func_name[3:]] = func(open_, high_, low_, close_, penetration=0)
        else:
            df[func_name[3:]] = func(open_, high_, low_, close_)

    # 合併所有非0訊號為一個欄位
    def combine_patterns(row):
        signals = []
        for func_name, zh in candle_patterns:
            val = row[func_name[3:]]
            if val != 0:
                signals.append(f"{zh}({val})")
        return ','.join(signals) if signals else ''

    df['PatternSignals'] = df.apply(combine_patterns, axis=1)

    # 只顯示有訊號的資料
    result = df[df['PatternSignals'] != '']
    print(result[['symbol', 'datetime', 'open', 'high',
          'low', 'close', 'PatternSignals']].head(10))
    df.to_csv('output.csv', index=False, encoding='utf-8-sig')


if __name__ == "__main__":
    main()
