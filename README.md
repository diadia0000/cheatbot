![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![LINE](https://img.shields.io/badge/LINE-00C300?style=for-the-badge&logo=line&logoColor=white)

# Cheet Bot 專案說明

> [!WARNING]
> **此系統只提供做教育用途做使用，除此之外的事情作者既不負責。**

這是一個詐騙對話模擬系統，透過 LINE Bot 作為使用者介面。包含：

- `backend/`：FastAPI 後端（對話邏輯、歷史紀錄、RAG 檢索、圖像生成觸發、LINE Webhook 處理）
- `models/`：本地大模型目錄（Qwen2.5-14B-Instruct-AWQ）
- `data/`：執行時資料（SQLite / ChromaDB）
- `ops/`：Nginx 配置等運維檔案
- `docs/`：文件與架構圖

## 1. 架構圖（Mermaid）

架構圖已轉換為 Mermaid：

- `docs/architecture.md`

## 2. 推薦啟動方式（Docker Compose）

在專案根目錄執行：

```bash
docker compose up --build
```

啟動後預設存取位址：

- Webhook Gateway（供 ngrok 轉發）：`http://127.0.0.1:8080`
- vLLM OpenAI 相容介面：`http://127.0.0.1:8000/v1`

停止服務：

```bash
docker compose down
```

### LINE Bot Webhook（ngrok 本機執行）

1. 建立環境變數檔（只要第一次）：

```bash
cp .env.example .env
```

2. 編輯 `.env`，至少填入：

- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `FAL_KEY`（若你有使用圖片生成功能）

3. 啟動服務：

```bash
docker compose up -d --build
```

4. 在主機啟動 ngrok（本機安裝版）：

```bash
ngrok http 8080
```

5. 取得 ngrok 公網網址：

```bash
curl -s http://127.0.0.1:4040/api/tunnels | jq -r '.tunnels[] | select(.proto=="https") | .public_url'
```

6. 到 LINE Developers Console，把 Webhook URL 設為：

```text
https://<你的-ngrok-網址>/line/webhook
```

說明：

- `webhook_gateway` 已對外開在 `127.0.0.1:8080`，供本機 ngrok 轉發。
- 若你使用 ngrok 隨機網域，每次重啟 ngrok 可能需要更新 LINE Console 的 Webhook URL。
- 可使用 `./scripts/sync_line_webhook.sh` 自動同步 LINE Webhook URL。
- `LINE_BACKEND_PUBLIC_URL` 可留空，後端會嘗試從 ngrok 轉發標頭自動推導公開網址（用於圖片訊息 URL）。
- 安全強化後，ngrok 只會對外轉發 `/line/webhook`，其他 backend 路徑會回傳 `404`。

## 3. 本地開發（不走 Docker）

建議先建立並啟用虛擬環境：

```bash
python -m venv .venv
source .venv/bin/activate
```

然後參考：
- `backend/README.md`

## 4. 目錄結構

```text
.
├── backend/
├── data/
├── docs/
├── models/
├── ops/
└── docker-compose.yml
```

## 5. 常見問題

1. LINE Bot 無法收到回覆

- 檢查 `docker compose ps`，確認 `fastapi_backend` 和 `webhook_gateway` 正常運行。
- 確認 ngrok 已啟動且 Webhook URL 已正確設定在 LINE Developers Console。

2. vLLM 啟動失敗

- 檢查 GPU / NVIDIA 容器環境是否可用。
- 確認模型路徑存在：`models/Qwen2.5-14B-Instruct-AWQ`。

3. 對話歷史異常

- 資料預設寫入 `data/`，可先備份後清理再重啟。

## 6. License

本專案採用 [MIT License](./LICENSE)。
