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

def create_record(data, is_scheduled=False):
    """建立一筆標準格式的紀錄資料"""
    # 如果是排程存檔，強制使用 22:00 的時間標籤，否則使用當下時間
    if is_scheduled:
        timestamp = datetime.now().strftime('%Y-%m-%d 22:00')
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    return {
        'time': timestamp,
        'total': data['total_value'],
        'top1_coin': data['top_3'][0]['coin'] if len(data['top_3']) > 0 else 'N/A',
        'top1_val': data['top_3'][0]['value'] if len(data['top_3']) > 0 else 0,
        'top2_coin': data['top_3'][1]['coin'] if len(data['top_3']) > 1 else 'N/A',
        'top2_val': data['top_3'][1]['value'] if len(data['top_3']) > 1 else 0,
        'top3_coin': data['top_3'][2]['coin'] if len(data['top_3']) > 2 else 'N/A',
        'top3_val': data['top_3'][2]['value'] if len(data['top_3']) > 2 else 0,
    }

def save_history():
    """
    【排程專用】
    只在每天 22:00 執行，將當下數據寫入 history.json
    """
    print(f"[{datetime.now()}] 正在執行每日 22:00 定時存檔...")
    data = get_current_values()
    if not data:
        return

    # 讀取舊紀錄
    history = []
    if os.path.exists(HISTORY_FILENAME):
        try:
            with open(HISTORY_FILENAME, 'r') as f:
                history = json.load(f)
        except:
            pass
    
    # 建立新紀錄 (標記為排程)
    new_record = create_record(data, is_scheduled=True)
    
    # 簡單防呆：避免同一天重複寫入多筆 22:00 (如果手動重啟導致排程重跑)
    # 檢查最後一筆的時間是否跟這次要寫的一樣
    if history and history[-1]['time'] == new_record['time']:
        print("今日 22:00 資料已存在，更新該筆資料...")
        history[-1] = new_record
    else:
        history.append(new_record)
    
    # 寫入檔案
    with open(HISTORY_FILENAME, 'w') as f:
        json.dump(history, f, indent=4)
    
    print("每日歷史快照已儲存！")

# ===========================
# 排程執行緒
# ===========================
def run_schedule():
    # 每天 22:00 執行 save_history
    schedule.every().day.at("22:00").do(save_history)
    while True:
        schedule.run_pending()
        time.sleep(60)

t = threading.Thread(target=run_schedule)
t.daemon = True
t.start()

# 初始化：如果沒有檔案，建立一個空的 JSON list，但不要寫入數據 (以免產生非 22:00 的髒數據)
if not os.path.exists(HISTORY_FILENAME):
    with open(HISTORY_FILENAME, 'w') as f:
        json.dump([], f)

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
    """
    這個 API 是前端獲取圖表數據的關鍵。
    邏輯：
    1. 讀取 history.json (裡面只有過去每天 22:00 的固定資料)
    2. 即時計算當下這一刻的數據
    3. 把即時數據 'append' 到列表最後面，傳給前端
    
    這樣做的好處：不寫入硬碟，但圖表永遠看得到最新一分鐘的點。
    """
    history = []
    
    # 1. 讀取硬碟歷史資料
    if os.path.exists(HISTORY_FILENAME):
        try:
            with open(HISTORY_FILENAME, 'r') as f:
                history = json.load(f)
        except:
            pass
            
    # 2. 產生即時數據 (Real-time data point)
    current_data = get_current_values()
    if current_data:
        live_record = create_record(current_data, is_scheduled=False)
        # 標記時間為 "Current" 或是當下時間，這裡用當下時間
        # 將這筆即時資料加入列表尾端 (僅在記憶體中，不存檔)
        history.append(live_record)

    return jsonify({'status': 'success', 'history': history})

if __name__ == '__main__':
    print("Dashboard 啟動中...")
    print("模式：歷史圖表顯示 [每日22:00存檔] + [最後一筆即時更新]")
    app.run(debug=True, host='0.0.0.0', port=5000)