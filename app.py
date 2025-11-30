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

    symbol_map = {}
    for coin in my_portfolio.keys():
        if coin != 'USDT':
            symbol_map[f"{coin}/USDT"] = coin
    
    market_data = {}
    try:
        if symbol_map:
            market_data = exchange.fetch_tickers(list(symbol_map.keys()))
    except:
        try:
            market_data = exchange.fetch_tickers()
        except:
            pass

    asset_details = []
    total_value = 0

    for coin, amount in my_portfolio.items():
        price = 1.0 
        if coin != 'USDT':
            pair = f"{coin}/USDT"
            if pair in market_data:
                price = float(market_data[pair]['last'])
            else:
                price = 0
        
        val = amount * price
        total_value += val
        
        asset_details.append({
            'coin': coin,
            'amount': amount,
            'price': price,
            'value': val
        })

    # 排序找出前三名 (為了相容舊邏輯)
    sorted_assets = sorted(asset_details, key=lambda x: x['value'], reverse=True)
    top_3 = sorted_assets[:3]

    return {
        'total_value': total_value,
        'top_3': top_3,
        'details': sorted_assets 
    }

def create_record(data, is_scheduled=False):
    """建立紀錄 (升級版：儲存所有幣種細節)"""
    if is_scheduled:
        timestamp = datetime.now().strftime('%Y-%m-%d 22:00')
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 為了 Top 9 頁面，我們需要把當下所有幣種的價值存下來
    # 格式：{'BTC': 50000, 'ETH': 3000, ...}
    all_coins_value = { item['coin']: item['value'] for item in data['details'] }

    return {
        'time': timestamp,
        'total': data['total_value'],
        # 保留舊欄位以維持相容性
        'top1_coin': data['top_3'][0]['coin'] if len(data['top_3']) > 0 else 'N/A',
        'top1_val': data['top_3'][0]['value'] if len(data['top_3']) > 0 else 0,
        'top2_coin': data['top_3'][1]['coin'] if len(data['top_3']) > 1 else 'N/A',
        'top2_val': data['top_3'][1]['value'] if len(data['top_3']) > 1 else 0,
        'top3_coin': data['top_3'][2]['coin'] if len(data['top_3']) > 2 else 'N/A',
        'top3_val': data['top_3'][2]['value'] if len(data['top_3']) > 2 else 0,
        # 新增欄位：儲存所有持倉價值快照
        'coins': all_coins_value
    }

def save_history():
    """每日 22:00 定時存檔"""
    print(f"[{datetime.now()}] 正在執行每日 22:00 定時存檔...")
    data = get_current_values()
    if not data:
        return

    history = []
    if os.path.exists(HISTORY_FILENAME):
        try:
            with open(HISTORY_FILENAME, 'r') as f:
                history = json.load(f)
        except:
            pass
    
    new_record = create_record(data, is_scheduled=True)
    
    if history and history[-1]['time'] == new_record['time']:
        history[-1] = new_record
    else:
        history.append(new_record)
    
    with open(HISTORY_FILENAME, 'w') as f:
        json.dump(history, f, indent=4)
    
    print("每日歷史快照已儲存！")

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

if not os.path.exists(HISTORY_FILENAME):
    with open(HISTORY_FILENAME, 'w') as f:
        json.dump([], f)

# ===========================
# Flask 路由
# ===========================

@app.route('/')
def index():
    return render_template('index.html')

# 新增：Top 9 頁面路由
@app.route('/top9')
def top9():
    return render_template('top9ccy.html')

@app.route('/api/portfolio')
def api_portfolio():
    data = get_current_values()
    if data:
        return jsonify({'status': 'success', 'data': data})
    return jsonify({'status': 'error'})

@app.route('/api/history')
def api_history():
    history = []
    if os.path.exists(HISTORY_FILENAME):
        try:
            with open(HISTORY_FILENAME, 'r') as f:
                history = json.load(f)
        except:
            pass
            
    current_data = get_current_values()
    if current_data:
        live_record = create_record(current_data, is_scheduled=False)
        history.append(live_record)

    return jsonify({'status': 'success', 'history': history})

if __name__ == '__main__':
    print("Dashboard 啟動中...")
    print("Port: 5050")
    app.run(debug=True, host='0.0.0.0', port=5050)