import streamlit as st
import pandas as pd
import akshare as ak
from strategy.stock_screener import StockScreener
from charts.stock_detail import create_stock_charts

def main():
    st.set_page_config(page_title="A股智能选股器", layout="wide")
    st.title("A股智能选股器")
    
    # 初始化 session state
    if 'selected_stock' not in st.session_state:
        st.session_state.selected_stock = None
    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'progress' not in st.session_state:
        st.session_state.progress = None
    
    if st.button("开始选股") or st.session_state.results is not None:
        if st.session_state.results is None:  # 只在第一次点击时执行选股
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(current, total, message):
                progress = int(current * 100 / total)
                progress_bar.progress(progress)
                status_text.text(f"{message} ({progress}%)")
            
            with st.spinner("正在分析市场活跃股票，请稍候..."):
                screener = StockScreener()
                results = screener.screen_stocks(progress_callback=update_progress)
                st.session_state.results = results
            
            progress_bar.empty()
            status_text.empty()
        
        show_results()

def show_results():
    if st.session_state.results:
        # 创建DataFrame并设置正确的列名
        df = pd.DataFrame(st.session_state.results)
        df.columns = [
            '股票代码', '股票名称', '推荐指数', '当前价格', '涨跌幅(%)',
            '预测最高价', '预测最低价', '预测波动(%)', '量比'
        ]
        
        # 创建两列布局
        left_col, right_col = st.columns([0.4, 0.6])
        
        with left_col:
            st.subheader("推荐股票列表")
            
            # 创建表头
            cols = st.columns([1, 1.2, 0.8, 0.8, 0.8])
            cols[0].write("**股票代码**")
            cols[1].write("**股票名称**")
            cols[2].write("**推荐指数**")
            cols[3].write("**当前价格**")
            cols[4].write("**涨跌幅(%)**")
            
            # 显示每行数据，每个股票代码都是一个按钮
            for _, row in df.iterrows():
                cols = st.columns([1, 1.2, 0.8, 0.8, 0.8])
                
                # 股票代码作为按钮
                if cols[0].button(row['股票代码'], key=f"btn_{row['股票代码']}"):
                    st.session_state.selected_stock = row['股票代码']
                
                # 其他列正常显示
                cols[1].write(row['股票名称'])
                
                # 推荐指数带颜色
                score = row['推荐指数']
                color = 'red' if score >= 80 else 'orange' if score >= 70 else 'black'
                cols[2].markdown(f"<span style='color: {color}'>{score:.0f}</span>", unsafe_allow_html=True)
                
                cols[3].write(f"{row['当前价格']:.2f}")
                
                # 涨跌幅带颜色
                change = row['涨跌幅(%)']
                color = 'red' if change > 0 else 'green' if change < 0 else 'black'
                cols[4].markdown(f"<span style='color: {color}'>{change:.2f}%</span>", unsafe_allow_html=True)
            
            # 下载按钮
            st.download_button(
                label="下载选股结果",
                data=df.to_csv(index=False),
                file_name="stock_recommendations.csv",
                mime="text/csv"
            )
        
        with right_col:
            if st.session_state.selected_stock:
                show_stock_details(st.session_state.selected_stock)

def show_stock_details(stock_code):
    try:
        # 获取股票数据
        df = pd.DataFrame(st.session_state.results)
        df.columns = [
            '股票代码', '股票名称', '推荐指数', '当前价格', '涨跌幅(%)',
            '预测最高价', '预测最低价', '预测波动(%)', '量比'
        ]
        stock_info = df[df['股票代码'] == stock_code].iloc[0]
        
        st.write(f"### {stock_code} - {stock_info['股票名称']}")
        
        # 创建两列布局显示预测信息
        col1, col2 = st.columns(2)
        
        with col1:
            delta_pct = ((stock_info['预测最高价']/stock_info['当前价格']-1)*100)
            st.metric(
                label="预测最高价", 
                value=f"¥{stock_info['预测最高价']:.2f}",
                delta=f"{delta_pct:.1f}%",
                delta_color="inverse"  # "normal"表示上涨红色，下跌绿色
            )
            
        with col2:
            delta_pct = ((stock_info['预测最低价']/stock_info['当前价格']-1)*100)
            st.metric(
                label="预测最低价", 
                value=f"¥{stock_info['预测最低价']:.2f}",
                delta=f"{delta_pct:.1f}%",
                delta_color="inverse"  # "normal"表示上涨红色，下跌绿色
            )
        
        # 显示预测详情
        st.write("### 预测详情")
        details = pd.DataFrame({
            '指标': ['预测波动幅度', '当前量比', '推荐指数'],
            '数值': [
                f"{stock_info['预测波动(%)']}%",
                f"{stock_info['量比']:.2f}",
                f"{stock_info['推荐指数']:.0f}"
            ]
        })
        st.table(details)
        
        # 获取分时数据并显示图表
        hist_data = ak.stock_zh_a_hist_min_em(
            symbol=stock_code,
            period='60',
            adjust='qfq',
            start_date=(pd.Timestamp.now() - pd.Timedelta(days=30)).strftime("%Y%m%d"),
            end_date=pd.Timestamp.now().strftime("%Y%m%d")
        )
        
        if not hist_data.empty:
            charts = create_stock_charts(hist_data)
            st.plotly_chart(charts, use_container_width=True)
            
    except Exception as e:
        st.error(f"获取股票数据失败: {str(e)}")

if __name__ == "__main__":
    main() 