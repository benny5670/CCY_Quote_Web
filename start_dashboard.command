#!/bin/bash

# 1. 進入你的專案資料夾 (這是最重要的一步，確保能讀到 templates 和 csv)
cd /Users/benny/VisualStudioProject/CCY_Quote_Web

# 2. 啟動虛擬環境 (載入你安裝好的 flask, ccxt)
source .venv/bin/activate

# 3. 執行 Python 程式
echo "=================================================="
echo "🚀 加密資產儀表板正在啟動..."
echo "請在瀏覽器打開: http://127.0.0.1:5000"
echo "若要關閉程式，請直接關閉此視窗，或按 Ctrl+C"
echo "=================================================="

python app.py