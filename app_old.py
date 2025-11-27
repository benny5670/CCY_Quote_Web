import csv
import os
import json
import ccxt
import time
import schedule
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# ===========================
# 初始化設定
# ===========================
exchange = ccxt.okx()
CSV_FILENAME = 'portfolio.csv'
HISTORY_FILENAME = 'history.json'

# ===========================
# 核心功能函數
# ===========================

def load_portfolio_from_csv():
    """從 CSV 讀取持倉"""
    portfolio = {}
    if not os.path.exists(CSV_FILENAME):
        return {}
    try:
        with open(CSV_FILENAME, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row['Symbol'].strip().upper()
                try:
                    amount = float(row['Amount'].strip())
                    portfolio[symbol] = amount
                except ValueError:
                    pass
        return portfolio
    except:
        return {}

def get_current_values():
    """計算當前所有資產價值"""
    my_portfolio = load_portfolio_from_csv()
    if not my_portfolio:
        return None

    # 1. 準備交易對
    symbol_map = {}
    for coin in my_portfolio.keys():
        if coin != 'USDT':
            symbol_map[f"{coin}/USDT"] = coin
    
    # 2. 抓取 OKX 價格
    market_data = {}
    try:
        if symbol_map:
            market_data = exchange.fetch_tickers(list(symbol_map.keys()))
    except:
        try:
            market_data = exchange.fetch_tickers() # 備用方案
        except:
            pass

    # 3. 計算價值
    asset_details = []
    total_value = 0

    for coin, amount in my_portfolio.items():
        price = 1.0 # USDT 預設為 1
        if coin != 'USDT':
            pair = f"{coin}/USDT"
            if pair in market_data:
                price = float(market_data[pair]['last'])
            else:
                price = 0 # 獲取失敗
        
        val = amount * price
        total_value += val
        
        # 這裡將 price 也傳回給前端
        asset_details.append({
            'coin': coin,
            'amount': amount,
            'price': price,
            'value': val
        })

    # 4. 排序找出前三名
    sorted_assets = sorted(asset_details, key=lambda x: x['value'], reverse=True)
    top_3 = sorted_assets[:3]

    return {
        'total_value': total_value,
        'top_3': top_3,
        'details': sorted_assets
    }

def save_history():
    """記錄當下的資產快照"""
    print(f"[{datetime.now()}] 正在執行資產快照記錄...")
    data = get_current_values()
    if not data:
        return

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    record = {
        'time': timestamp,
        'total': data['total_value'],
        'top1_coin': data['top_3'][0]['coin'] if len(data['top_3']) > 0 else 'N/A',
        'top1_val': data['top_3'][0]['value'] if len(data['top_3']) > 0 else 0,
        'top2_coin': data['top_3'][1]['coin'] if len(data['top_3']) > 1 else 'N/A',
        'top2_val': data['top_3'][1]['value'] if len(data['top_3']) > 1 else 0,
        'top3_coin': data['top_3'][2]['coin'] if len(data['top_3']) > 2 else 'N/A',
        'top3_val': data['top_3'][2]['value'] if len(data['top_3']) > 2 else 0,
    }

    history = []
    if os.path.exists(HISTORY_FILENAME):
        try:
            with open(HISTORY_FILENAME, 'r') as f:
                history = json.load(f)
        except:
            pass
    
    history.append(record)
    
    with open(HISTORY_FILENAME, 'w') as f:
        json.dump(history, f, indent=4)
    
    print("資產快照已儲存！")

# ===========================
# 排程執行緒
# ===========================
def run_schedule():
    schedule.every().day.at("22:00").do(save_history)
    while True:
        schedule.run_pending()
        time.sleep(60)

t = threading.Thread(target=run_schedule)
t.daemon = True
t.start()

# 啟動時若無紀錄則強制記錄一筆
if not os.path.exists(HISTORY_FILENAME):
    save_history()

# ===========================
# Flask 路由
# ===========================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def api_portfolio():
    data = get_current_values()
    if data:
        return jsonify({'status': 'success', 'data': data})
    return jsonify({'status': 'error'})

@app.route('/api/history')
def api_history():
    if os.path.exists(HISTORY_FILENAME):
        try:
            with open(HISTORY_FILENAME, 'r') as f:
                history = json.load(f)
            return jsonify({'status': 'success', 'history': history})
        except:
            return jsonify({'status': 'error', 'history': []})
    return jsonify({'status': 'success', 'history': []})

if __name__ == '__main__':
    print("Dashboard 啟動中...")
    print("Port 已設定為 5000 (請確認 Mac AirPlay 已關閉)")
    # 修改這裡：Port 改回 5000
    app.run(debug=True, host='0.0.0.0', port=5000)