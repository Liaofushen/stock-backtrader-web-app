import backtrader as bt
from .base import BaseStrategy

class BreakoutStrategy(BaseStrategy):
    params = (
        ('limit_up_pct', 9.8),      # 涨停判定（考虑误差）
        ('volume_ratio', 2.0),       # 放量倍数
        ('price_up_pct', 5.0),       # 价格突破幅度
        ('max_hold_days', 3),        # 最大持仓天数
        ('stop_loss_pct', 5.0),      # 止损比例
        ('take_profit_pct', 7.0),    # 止盈比例
        ('printlog', True)
    )

    def __init__(self):
        # 基础数据
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.dataopen = self.datas[0].open
        self.datavolume = self.datas[0].volume

        # 订单和持仓管理
        self.order = None
        self.buyprice = None
        self.hold_days = 0
        
        # 计算技术指标
        # 成交量移动平均
        self.volume_ma = bt.indicators.SMA(self.datavolume, period=5)
        # 价格移动平均
        self.price_ma = bt.indicators.SMA(self.dataclose, period=5)
        
    def next(self):
        # 如果有待执行订单，不操作
        if self.order:
            return

        # 如果持仓中，检查止损、止盈或持仓天数
        if self.position:
            self.hold_days += 1
            
            # 计算当前收益率（避免除零）
            if self.buyprice and self.buyprice > 0:
                current_profit = (self.dataclose[0] - self.buyprice) / self.buyprice * 100
            else:
                current_profit = 0
            
            # 1. 止损检查
            if current_profit <= -self.params.stop_loss_pct:
                self.log(f'止损: Close={self.dataclose[0]:.2f}, Profit={current_profit:.2f}%')
                self.order = self.close()
                self.hold_days = 0
                return
                
            # 2. 止盈检查
            if current_profit >= self.params.take_profit_pct:
                self.log(f'止盈: Close={self.dataclose[0]:.2f}, Profit={current_profit:.2f}%')
                self.order = self.close()
                self.hold_days = 0
                return
                
            # 3. 最大持仓天数检查
            if self.hold_days >= self.params.max_hold_days:
                self.log(f'超过最大持仓天数: Close={self.dataclose[0]:.2f}, Days={self.hold_days}')
                self.order = self.close()
                self.hold_days = 0
                return

        # 入场逻辑
        if not self.position:
            try:
                # 条件1: 当日涨幅接近涨停（避免除零）
                if self.dataopen[0] > 0:
                    daily_rise = (self.dataclose[0] - self.dataopen[0]) / self.dataopen[0] * 100
                    is_limit_up = daily_rise >= self.params.limit_up_pct
                else:
                    is_limit_up = False
                
                # 条件2: 放量（避免除零）
                if self.volume_ma[0] > 0:
                    volume_surge = self.datavolume[0] > self.volume_ma[0] * self.params.volume_ratio
                else:
                    volume_surge = False
                
                # 条件3: 价格突破（避免除零）
                if self.dataclose[-1] > 0:
                    price_break = (self.dataclose[0] - self.dataclose[-1]) / self.dataclose[-1] * 100 >= self.params.price_up_pct
                else:
                    price_break = False
                
                # 条件4: 五日均线向上（避免无效值）
                if self.price_ma[-1] is not None and self.price_ma[0] is not None:
                    ma_trend_up = self.price_ma[0] > self.price_ma[-1]
                else:
                    ma_trend_up = False
                
                # 满足所有条件则买入
                if is_limit_up and volume_surge and price_break and ma_trend_up:
                    self.log(f'买入信号: Close={self.dataclose[0]:.2f}, Volume={self.datavolume[0]}')
                    self.order = self.buy()
                    self.buyprice = self.dataclose[0]
                    self.hold_days = 0
                    
            except Exception as e:
                self.log(f'计算错误: {str(e)}')
                return