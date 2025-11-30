# 使用輕量級的 Python 3.9
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝必要的系統套件 (為了設定時區)
RUN apt-get update && apt-get install -y tzdata

# 設定時區為台北 (這對你的 22:00 排程非常重要！)
ENV TZ=Asia/Taipei

# 複製當前目錄所有檔案到容器內
COPY . /app

# 安裝 Python 庫
RUN pip install --no-cache-dir -r requirements.txt

# 開放 5000 Port
EXPOSE 5050

# 執行程式
CMD ["python", "app.py"]