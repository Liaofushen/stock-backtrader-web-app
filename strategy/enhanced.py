import backtrader as bt
from .base import BaseStrategy

class EnhancedStrategy(BaseStrategy):
    params = (
        ('fast_ma', 5),      # 快速MA
        ('slow_ma', 20),     # 慢速MA
        ('signal_ma', 9),    # MACD信号线
        ('macd1', 12),       # MACD快线
        ('macd2', 26),       # MACD慢线
        ('rsi_period', 14),  # RSI周期
        ('rsi_upper', 70),   # RSI超买
        ('rsi_lower', 30),   # RSI超卖
        ('atr_period', 14),  # ATR周期
        ('atr_multiplier', 2),  # ATR倍数(用于止损)
        ('volume_factor', 2), # 成交量放大倍数
        ('printlog', True)
    )

    def __init__(self):
        # 价格数据
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.datavolume = self.datas[0].volume

        # 订单相关
        self.order = None
        self.buyprice = None
        self.stoplose = None

        # 技术指标
        # 双均线系统
        self.ma_fast = bt.indicators.SMA(period=self.params.fast_ma)
        self.ma_slow = bt.indicators.SMA(period=self.params.slow_ma)
        self.crossover = bt.indicators.CrossOver(self.ma_fast, self.ma_slow)

        # MACD
        self.macd = bt.indicators.MACD(
            period_me1=self.params.macd1,
            period_me2=self.params.macd2,
            period_signal=self.params.signal_ma
        )

        # RSI
        self.rsi = bt.indicators.RSI(period=self.params.rsi_period)

        # ATR
        self.atr = bt.indicators.ATR(period=self.params.atr_period)

        # 成交量MA
        self.volume_ma = bt.indicators.SMA(self.datavolume, period=20)

    def next(self):
        # 如果有待执行订单，不操作
        if self.order:
            return

        # 更新止损价
        if self.position:
            if self.dataclose[0] > self.buyprice:
                new_stop = self.dataclose[0] - self.atr[0] * self.params.atr_multiplier
                if self.stoplose is None or new_stop > self.stoplose:
                    self.stoplose = new_stop

        # 检查止损
        if self.position and self.dataclose[0] < self.stoplose:
            self.log(f'触发止损: Close={self.dataclose[0]:.2f}, Stop={self.stoplose:.2f}')
            self.order = self.close()
            self.stoplose = None
            return

        # 入场逻辑
        if not self.position:
            # 1. 均线金叉
            if self.crossover > 0:
                # 2. MACD柱状图为正
                if self.macd.macd[0] > 0 and self.macd.signal[0] > 0:
                    # 3. RSI不在超买区
                    if self.rsi[0] < self.params.rsi_upper:
                        # 4. 成交量放大
                        if self.datavolume[0] > self.volume_ma[0] * self.params.volume_factor:
                            self.log(f'买入信号: Close={self.dataclose[0]:.2f}')
                            self.order = self.buy()
                            self.buyprice = self.dataclose[0]
                            # 设置初始止损
                            self.stoplose = self.buyprice - self.atr[0] * self.params.atr_multiplier

        # 出场逻辑
        else:
            # 1. 均线死叉
            if self.crossover < 0:
                # 2. MACD柱状图为负
                if self.macd.macd[0] < 0:
                    # 3. RSI不在超卖区
                    if self.rsi[0] > self.params.rsi_lower:
                        self.log(f'卖出信号: Close={self.dataclose[0]:.2f}')
                        self.order = self.close()
                        self.stoplose = None 