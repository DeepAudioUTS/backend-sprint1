# ベースとなるイメージ（Python 3.11）
FROM python:3.11-slim

# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# requirements.txtをコンテナにコピーしてインストール
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# UvicornでFastAPIを起動するコマンド
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]