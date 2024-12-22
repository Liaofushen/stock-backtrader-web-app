import backtrader as bt
from .base import BaseStrategy

class FibonacciStrategy(BaseStrategy):
    params = (
        ('period', 20),       # 用于寻找高点低点的周期
        ('fib1', 0.236),     # 第一个斐波那契回调位
        ('fib2', 0.382),     # 第二个斐波那契回调位
        ('fib3', 0.618),     # 第三个斐波那契回调位
        ('atr_period', 14),   # ATR周期
        ('atr_stop', 2),      # ATR止损倍数
        ('printlog', True)
    )

    def __init__(self):
        # 价格数据
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low

        # 订单和位置跟踪
        self.order = None
        self.buyprice = None
        self.stoplose = None

        # 计算高点和低点
        self.highest = bt.indicators.Highest(self.datahigh, period=self.params.period)
        self.lowest = bt.indicators.Lowest(self.datalow, period=self.params.period)

        # ATR指标用于止损
        self.atr = bt.indicators.ATR(period=self.params.atr_period)

        # 计算斐波那契回调位
        self.fib_levels = []

    def next(self):
        if self.order:
            return

        # 计算当前的斐波那契回调位
        swing_high = self.highest[0]
        swing_low = self.lowest[0]
        price_range = swing_high - swing_low

        fib_236 = swing_high - price_range * self.params.fib1
        fib_382 = swing_high - price_range * self.params.fib2
        fib_618 = swing_high - price_range * self.params.fib3

        # 更新跟踪止损
        if self.position:
            if self.dataclose[0] > self.buyprice:
                new_stop = self.dataclose[0] - self.atr[0] * self.params.atr_stop
                if self.stoplose is None or new_stop > self.stoplose:
                    self.stoplose = new_stop

            # 检查止损
            if self.dataclose[0] < self.stoplose:
                self.log(f'止损: Close={self.dataclose[0]:.2f}, Stop={self.stoplose:.2f}')
                self.order = self.close()
                self.stoplose = None
                return

        # 入场逻辑
        if not self.position:
            # 价格在0.618回调位附近，且出现反弹
            if self.dataclose[0] >= fib_618 * 0.99 and self.dataclose[0] <= fib_618 * 1.01:
                if self.dataclose[0] > self.dataclose[-1]:  # 价格开始反弹
                    self.log(f'买入信号 (0.618回调): Close={self.dataclose[0]:.2f}')
                    self.order = self.buy()
                    self.buyprice = self.dataclose[0]
                    self.stoplose = self.buyprice - self.atr[0] * self.params.atr_stop

            # 价格在0.382回调位附近，且出现反弹
            elif self.dataclose[0] >= fib_382 * 0.99 and self.dataclose[0] <= fib_382 * 1.01:
                if self.dataclose[0] > self.dataclose[-1]:  # 价格开始反弹
                    self.log(f'买入信号 (0.382回调): Close={self.dataclose[0]:.2f}')
                    self.order = self.buy()
                    self.buyprice = self.dataclose[0]
                    self.stoplose = self.buyprice - self.atr[0] * self.params.atr_stop

        # 出场逻辑
        else:
            # 当价格达到0.236回调位时获利了结
            if self.dataclose[0] >= fib_236:
                self.log(f'卖出信号 (0.236目标): Close={self.dataclose[0]:.2f}')
                self.order = self.close()
                self.stoplose = None 