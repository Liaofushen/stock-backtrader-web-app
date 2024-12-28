import akshare as ak
import pandas as pd
import talib
import numpy as np
import concurrent.futures
import threading
from concurrent.futures import ThreadPoolExecutor

class StockScreener:
    def __init__(self):
        self.stock_data = None
        self.thread_lock = threading.Lock()
        
    def _process_single_stock(self, stock):
        try:
            stock_code = stock['代码']
            stock_name = stock['名称']
            current_price = float(stock['最新价'])
            change_pct = float(stock['涨跌幅'])
            
            # 获取60分钟K线数据
            hist_data = ak.stock_zh_a_hist_min_em(
                symbol=stock_code,
                period='60',
                adjust='qfq',
                start_date=(pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y%m%d"),
                end_date=pd.Timestamp.now().strftime("%Y%m%d")
            )
            
            if hist_data.empty:
                return None
                
            # 先进行价格预测
            price_prediction = self._predict_next_day_price(hist_data)
            
            # 计算技术指标得分，并传入价格预测结果
            score = self._calculate_score(hist_data, stock_code, stock_name, price_prediction)
            
            if score > 0:
                # 初始化基础结果
                result = [stock_code, stock_name, score, current_price, change_pct]
                
                # 如果有价格预测结果，则添加预测相关信息
                if price_prediction:
                    result.extend([
                        price_prediction['预测最高价'],
                        price_prediction['预测最低价'],
                        price_prediction['预测幅度'],
                        price_prediction['成交量比']
                    ])
                else:
                    # 如果没有预测结果，添加默认值
                    result.extend([0, 0, 0, 0])
                    
                return result
            return None
            
        except Exception as e:
            print(f"处理股票 {stock_code} 时出错: {str(e)}")
            return None

    def screen_stocks(self, progress_callback=None):
        try:
            if progress_callback:
                progress_callback(0, 100, "正在获取市场数据...")
            
            # 获取活跃股票数据
            active_stocks = ak.stock_zh_a_spot_em()
            
            if progress_callback:
                progress_callback(10, 100, "正在筛选活跃股票...")
            
            # 基础过滤条件
            active_stocks = active_stocks[
                (active_stocks['代码'].str.startswith(('00', '60'))) &
                (active_stocks['换手率'].astype(float) >= 3) &
                (~active_stocks['名称'].str.contains('ST')) &
                (active_stocks['涨跌幅'].astype(float) > -5)
            ]
            
            if progress_callback:
                progress_callback(20, 100, "正在排序股票...")
            
            # 将换手率和成交额都转换为百分位数排名
            active_stocks['换手率排名'] = active_stocks['换手率'].astype(float).rank(pct=True)
            active_stocks['成交额排名'] = active_stocks['成交额'].astype(float).rank(pct=True)
            
            # 按照换手率和成交额的排名进行加权排序
            active_stocks['排序得分'] = (
                active_stocks['换手率排名'] * 0.7 +
                active_stocks['成交额排名'] * 0.3
            )
            
            # 按得分降序排序并选取前100只股票
            active_stocks = active_stocks.sort_values(
                by='排序得分',
                ascending=False
            ).head(100)
            
            results = []
            total_stocks = len(active_stocks)
            
            # 使用线程池处理股票分析
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self._process_single_stock, stock): i 
                          for i, (_, stock) in enumerate(active_stocks.iterrows())}
                
                for future in concurrent.futures.as_completed(futures):
                    if progress_callback:
                        current = futures[future] + 1
                        progress = 20 + int(current * 80 / total_stocks)
                        progress_callback(progress, 100, f"正在分析第 {current}/{total_stocks} 支股票...")
                    
                    result = future.result()
                    if result:
                        results.append(result)
            
            # 过滤并排序结果
            valid_results = [r for r in results if r is not None]
            valid_results.sort(key=lambda x: x[2], reverse=True)  # 按推荐指数排序
            
            return valid_results
            
        except Exception as e:
            print(f"获取股票数据时出错: {str(e)}")
            return []

    def _calculate_score(self, df, stock_code=None, stock_name=None, price_prediction=None):
        if len(df) < 30:  # 确保至少有30个小时的数据
            print(f"数据点数不足: {len(df)}")
            return 0
            
        try:
            df = df.copy()
            
            required_columns = ['收盘', '开盘', '最高', '最低', '成交量']
            if not all(col in df.columns for col in required_columns):
                print(f"缺少必要的列: {df.columns}")
                return 0
            
            for col in required_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            close = df['收盘'].values.astype(float)
            open_price = df['开盘'].values.astype(float)
            high = df['最高'].values.astype(float)
            low = df['最低'].values.astype(float)
            volume = df['成交量'].values.astype(float)
            
            score = 0
            
            # 记录正向和负向信号的数量
            positive_signals = []
            negative_signals = []
            
            # 1. 趋势强度分析 (35分)
            # 计算不同周期的均线
            ma5 = talib.SMA(close, timeperiod=5)   # 5小时均线
            ma10 = talib.SMA(close, timeperiod=10) # 10小时均线
            ma20 = talib.SMA(close, timeperiod=20) # 20小时均线
            
            # 计算最新涨跌幅
            latest_change = (close[-1] - close[-2]) / close[-2] * 100
            
            # 判断大趋势
            trend_strength = 0
            if not np.isnan(ma20[-1]):
                # 多头排列（短期均线在长期均线上方）
                if ma5[-1] > ma10[-1] > ma20[-1]:
                    trend_strength = 2  # 强势上涨
                elif ma5[-1] > ma20[-1]:
                    trend_strength = 1  # 普通上涨
                elif ma5[-1] < ma20[-1]:
                    trend_strength = 0  # 可能是反弹
            
            # 根据大趋势调整涨幅得分
            if trend_strength == 2 and latest_change > 5:
                positive_signals.append(20)  # 强势上涨中的大阳线
            elif trend_strength == 1 and latest_change > 3:
                positive_signals.append(15)  # 普通上涨中的中阳线
            elif trend_strength == 0 and latest_change > 5:
                positive_signals.append(10)  # 可能是反弹
            
            # 趋势扣分项
            if ma5[-1] < ma20[-1]:  # 空头排列
                if latest_change < -3:  # 下跌趋势中的大阴线
                    negative_signals.append(15)
                elif latest_change < -2:  # 下跌趋势中的中阴线
                    negative_signals.append(10)
            
            # 2. MACD指标分析 (25分)
            macd, signal, hist = talib.MACD(close)
            if not np.isnan(macd[-1]):
                # 正向信号
                if macd[-1] > 0 and signal[-1] > 0:  # 双线在零轴上方
                    positive_signals.append(15)
                elif macd[-1] > signal[-1]:  # MACD在信号线上方
                    positive_signals.append(10)
                
                # 负向信号
                if macd[-1] < 0 and signal[-1] < 0:  # 双线在零轴下方
                    negative_signals.append(15)
                elif macd[-1] < signal[-1]:  # MACD在信号线下方
                    negative_signals.append(10)
                
                # MACD柱状图动能
                if hist[-1] > 0:
                    hist_momentum = (hist[-1] - hist[-2]) / abs(hist[-2]) if hist[-2] != 0 else 0
                    momentum_score = min(10, max(0, hist_momentum * 50))
                    positive_signals.append(momentum_score)
                else:
                    hist_momentum = (hist[-1] - hist[-2]) / abs(hist[-2]) if hist[-2] != 0 else 0
                    momentum_score = min(10, max(0, -hist_momentum * 50))
                    negative_signals.append(momentum_score)
            
            # 3. 量价配合分析 (25分)
            vol_ma5 = talib.SMA(volume, timeperiod=5)
            if not np.isnan(vol_ma5[-1]):
                vol_ratio = volume[-1] / vol_ma5[-1]
                
                # 正向信号
                if latest_change > 0:  # 上涨放量
                    volume_score = min(15, max(0, (vol_ratio - 1) * 10))
                    positive_signals.append(volume_score)
                    
                    # 量价趋势一致性
                    price_trend = np.polyfit(range(5), close[-5:], 1)[0]
                    volume_trend = np.polyfit(range(5), volume[-5:], 1)[0]
                    if price_trend > 0 and volume_trend > 0:  # 价量齐升
                        positive_signals.append(10)
                
                # 负向信号
                else:  # 下跌放量
                    volume_score = min(15, max(0, (vol_ratio - 1) * 10))
                    negative_signals.append(volume_score)
                    
                    # 下跌量价配合
                    price_trend = np.polyfit(range(5), close[-5:], 1)[0]
                    volume_trend = np.polyfit(range(5), volume[-5:], 1)[0]
                    if price_trend < 0 and volume_trend > 0:  # 价跌量增
                        negative_signals.append(10)
            
            # 4. K线形态分析 (15分)
            upper_shadow = high[-1] - max(open_price[-1], close[-1])
            lower_shadow = min(open_price[-1], close[-1]) - low[-1]
            body = abs(open_price[-1] - close[-1])
            
            # 上影线过长，说明上涨动能受限
            if upper_shadow > body * 1.5:
                negative_signals.append(10)
            elif upper_shadow > body:
                negative_signals.append(5)
            
            # 大实体小下影，说明强势
            if body > (high[-1] - low[-1]) * 0.6 and lower_shadow < body * 0.3:
                positive_signals.append(15)
            
            # 5. 风险控制（减分项）
            # RSI过热检查
            rsi = talib.RSI(close, timeperiod=6)
            if not np.isnan(rsi[-1]):
                # 价格创新高但RSI没有创新高 -> 顶背离
                if len(close) >= 5:
                    if close[-1] > max(close[-5:-1]) and rsi[-1] < max(rsi[-5:-1]):
                        negative_signals.append(15)
            
            # 成交量异常检查
            if latest_change < 0:  # 下跌情况下的量能分析
                if vol_ratio > 5:  # 巨量下跌
                    negative_signals.append(20)  # 严重警告信号
                elif vol_ratio > 3:  # 大量下跌
                    negative_signals.append(15)  # 较强警告信号
                elif vol_ratio > 2:  # 放量下跌
                    negative_signals.append(10)  # 一般警告信号
                
                # 连续放量下跌检查（更危险）
                if len(volume) >= 2 and len(close) >= 2:
                    prev_vol_ratio = volume[-2] / vol_ma5[-2]
                    prev_change = (close[-2] - close[-3]) / close[-3] * 100
                    
                    if prev_change < 0 and prev_vol_ratio > 1.5 and vol_ratio > 1.5:
                        negative_signals.append(15)  # 连续放量下跌
            
            # 计算平方叠加效应
            positive_boost = 0
            if len(positive_signals) >= 3:  # 至少3个正向信号
                # 根据信号数量增加叠加强度
                boost_factor = min(2.0, 1 + (len(positive_signals) - 3) * 0.2)  # 每多一个信号增加0.2的权重，最高2倍
                positive_boost = (sum(x * x for x in positive_signals) ** 0.5) * boost_factor
            
            negative_penalty = 0
            if len(negative_signals) >= 2:  # 至少2个负向信号
                # 根据信号数量增加惩罚强度
                penalty_factor = min(2.5, 1 + (len(negative_signals) - 2) * 0.3)  # 每多一个信号增加0.3的权重，最高2.5倍
                negative_penalty = (sum(x * x for x in negative_signals) ** 0.5) * penalty_factor
            
            # 最终得分计算
            base_score = sum(positive_signals) - sum(negative_signals)
            final_score = base_score + positive_boost - negative_penalty
            
            # 确保得分在0-100之间
            score = max(0, min(100, final_score))
            print(f"计算得分: {score} (基础得分: {base_score}, 正向加成: {positive_boost:.2f}, 负向惩罚: {negative_penalty:.2f})")
            
            # 打印详细的得分信息
            stock_info = f"股票 {stock_code} ({stock_name})" if stock_code and stock_name else "股票"
            print(f"{stock_info} 得分计算: {score} "
                  f"(基础得分: {base_score}, "
                  f"正向信号数: {len(positive_signals)}, 正向加成: {positive_boost:.2f}, "
                  f"负向信号数: {len(negative_signals)}, 负向惩罚: {negative_penalty:.2f})")
            
            # 如果得分较高，打印更详细的信号信息
            if score >= 60:
                print(f"  - 正向信号: {positive_signals}")
                print(f"  - 负向信号: {negative_signals}")
            
            # 根据价格预测调整得分
            if price_prediction:
                current_price = df['收盘'].iloc[-1]
                pred_high = price_prediction['预测最高价']
                pred_low = price_prediction['预测最低价']
                pred_range = price_prediction['预测幅度']
                volume_ratio = price_prediction['成交量比']
                
                # 计算预期收益风险比
                potential_gain = (pred_high - current_price) / current_price * 100
                potential_loss = (current_price - pred_low) / current_price * 100
                
                # 收益风险比大于2且预期涨幅显著
                if potential_gain / potential_loss > 2 and potential_gain > 3:
                    positive_signals.append(15)
                    print(f"{stock_code} 预期收益风险比: {potential_gain/potential_loss:.2f}")
                
                # 预期区间过大，说明波动风险大
                if pred_range > 8:
                    negative_signals.append(10)
                    print(f"{stock_code} 预期波动过大: {pred_range:.2f}%")
                
                # 预期成交量异常
                if volume_ratio > 3 and trend_strength < 2:
                    negative_signals.append(10)
                    print(f"{stock_code} 预期放量但趋势不强: {volume_ratio:.2f}")
            
            return score
            
        except Exception as e:
            print(f"计算得分时出错: {str(e)}")
            return 0

    def _predict_next_day_price(self, df):
        try:
            # 获取最近的价格数据
            latest_close = df['收盘'].iloc[-1]
            latest_high = df['最高'].iloc[-1]
            latest_low = df['最低'].iloc[-1]
            latest_volume = df['成交量'].iloc[-1]
            latest_open = df['开盘'].iloc[-1]
            
            # 计算最近5天的数据
            avg_volume = df['成交量'].rolling(5).mean().iloc[-1]
            avg_range = (df['最高'] - df['最低']).rolling(5).mean().iloc[-1]
            
            # 计算涨跌幅
            change_pct = (latest_close - df['收盘'].iloc[-2]) / df['收盘'].iloc[-2] * 100
            
            # 判断是否涨停或打板
            is_limit_up = change_pct >= 9.5
            
            # 计算波动幅度（考虑最近5天平均波动）
            range_today = max(latest_high - latest_low, avg_range)
            
            # 使用黄金分割比例
            fib_up = 1.618
            fib_down = 0.618
            
            # 根据成交量计算动能因子
            volume_factor = latest_volume / avg_volume
            momentum_factor = min(2.0, max(0.5, volume_factor))
            
            # 根据不同情况预测价格
            if is_limit_up:
                # 涨停后第二天预测
                high_pred = latest_close * 1.05  # 最高预计5%
                low_pred = latest_close * 0.97   # 最低预计-3%
                
                # 根据量能调整
                if volume_factor > 2:  # 涨停放巨量
                    high_pred = latest_close * 1.08  # 继续看高
                    low_pred = latest_close * 0.98   # 支撑更强
            else:
                # 正常情况预测
                if volume_factor > 1.5:  # 放量
                    high_pred = latest_close + (range_today * fib_up * momentum_factor)
                    low_pred = latest_close - (range_today * fib_down)
                else:  # 缩量
                    high_pred = latest_close + (range_today * fib_down)
                    low_pred = latest_close - (range_today * fib_down * momentum_factor)
            
            # 确保预测价格合理（不超过涨跌停限制）
            limit_up = latest_close * 1.1
            limit_down = latest_close * 0.9
            
            high_pred = min(high_pred, limit_up)
            low_pred = max(low_pred, limit_down)
            
            # 计算预测波动幅度
            pred_range = (high_pred - low_pred) / latest_close * 100
            
            # 如果预测波动过小，适当扩大
            if pred_range < 2:
                high_pred = latest_close * 1.02
                low_pred = latest_close * 0.98
            
            # 根据技术指标状态调整预测
            if trend_strength == 2:  # 强势上涨趋势
                high_pred *= 1.1  # 上调预期高点
                low_pred *= 1.02  # 提高预期支撑
            elif trend_strength == 0:  # 可能是反弹
                high_pred *= 0.95  # 下调预期高点
                low_pred *= 0.98  # 降低预期支撑
            
            return {
                '预测最高价': round(high_pred, 2),
                '预测最低价': round(low_pred, 2),
                '预测幅度': round((high_pred - low_pred) / latest_close * 100, 2),
                '成交量比': round(volume_factor, 2)
            }
            
        except Exception as e:
            print(f"预测价格时出错: {str(e)}")
            return None 