import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import talib
import numpy as np

def calculate_kdj(df, n=9, m1=3, m2=3):
    df = df.copy()
    
    low_list = df['最低'].rolling(n).min()
    high_list = df['最高'].rolling(n).max()
    
    rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
    
    df['K'] = pd.DataFrame(rsv).ewm(com=m1-1).mean()
    df['D'] = pd.DataFrame(df['K']).ewm(com=m2-1).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    return df

def create_stock_charts(df):
    # 确保数据类型正确
    df['收盘'] = pd.to_numeric(df['收盘'])
    df['开盘'] = pd.to_numeric(df['开盘'])
    df['最高'] = pd.to_numeric(df['最高'])
    df['最低'] = pd.to_numeric(df['最低'])
    df['成交量'] = pd.to_numeric(df['成交量'])
    
    # 计算MACD
    close = df['收盘'].values
    macd, signal, hist = talib.MACD(close)
    
    # 计算KDJ
    df = calculate_kdj(df)
    
    # 创建子图
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.25, 0.25],
        specs=[[{"secondary_y": True}],
               [{"secondary_y": False}],
               [{"secondary_y": False}]]
    )
    
    # 先添加成交量图（在主Y轴）
    colors = ['red' if row['收盘'] >= row['开盘'] else 'green' for _, row in df.iterrows()]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['成交量'],
            name='成交量',
            marker_color=colors,
            opacity=0.3
        ),
        row=1, col=1,
        secondary_y=False
    )
    
    # 再添加K线图（在副Y轴）
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['开盘'],
            high=df['最高'],
            low=df['最低'],
            close=df['收盘'],
            name='K线',
            increasing_line_color='red',
            decreasing_line_color='green'
        ),
        row=1, col=1,
        secondary_y=True
    )
    
    # MACD图
    fig.add_trace(go.Scatter(x=df.index, y=macd, name='MACD', line=dict(color='blue')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=signal, name='Signal', line=dict(color='orange')), row=2, col=1)
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=hist,
            name='MACD Hist',
            marker_color=['red' if val >= 0 else 'green' for val in hist]
        ),
        row=2, col=1
    )
    
    # KDJ图
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='blue')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='orange')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['J'], name='J', line=dict(color='purple')), row=3, col=1)
    
    # 更新布局
    fig.update_layout(
        height=800,
        title_text="60分钟K线图表",
        showlegend=True,
        xaxis3_rangeslider_visible=True,
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False
    )
    
    # 更新Y轴标题
    fig.update_yaxes(title_text="成交量", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="价格", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="KDJ", row=3, col=1)
    
    # 统一设置X轴格式
    fig.update_xaxes(
        rangeslider_visible=False,
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGrey',
        showline=True,
        linewidth=1,
        linecolor='Grey'
    )
    
    # 统一设置Y轴格式
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGrey',
        showline=True,
        linewidth=1,
        linecolor='Grey'
    )
    
    return fig