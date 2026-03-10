# Cheet Bot 專案說明

這是一個詐騙對話模擬系統，包含：
- `frontend/`：Streamlit 前端（受害者視角 + 警方監控視角）
- `backend/`：FastAPI 後端（對話邏輯、歷史紀錄、RAG 檢索、圖像生成觸發）
- `models/`：本地大模型目錄（Qwen2.5-14B-Instruct-AWQ）
- `data/`：執行時資料（SQLite / ChromaDB）
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
- 前端：`http://127.0.0.1:8501`
- 後端：`http://127.0.0.1:8080`
- vLLM OpenAI 相容介面：`http://127.0.0.1:8000/v1`

停止服務：

```bash
docker compose down
```

## 3. 本地開發（不走 Docker）

建議先建立並啟用虛擬環境：

```bash
python -m venv .venv
source .venv/bin/activate
```

然後分別參考：
- `backend/README.md`
- `frontend/README.md`

## 4. 目錄結構

```text
.
├── backend/
├── frontend/
├── data/
├── docs/
├── models/
├── scripts/
└── docker-compose.yml
```

## 5. 常見問題

1. 啟動後前端無法連線後端
- 檢查 `docker compose ps`，確認 `fastapi_backend` 正常運行。

2. vLLM 啟動失敗
- 檢查 GPU / NVIDIA 容器環境是否可用。
- 確認模型路徑存在：`models/Qwen2.5-14B-Instruct-AWQ`。

3. 對話歷史異常
- 資料預設寫入 `data/`，可先備份後清理再重啟。
