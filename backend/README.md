# Backend 說明（FastAPI）

後端負責：
- 接收前端聊天請求
- 呼叫 vLLM（OpenAI 相容介面）生成回覆
- 維護短期歷史（SQLite）
- 檢索長期記憶（ChromaDB）
- 提供監控介面與會話清理介面

## 1. 安裝相依套件

在專案根目錄（或 `backend/`）執行：

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 2. 啟動後端

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

如果你目前目錄是 `backend/`，可使用：

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## 3. 關鍵環境變數

- `VLLM_API_URL`：vLLM 介面位址，容器內預設為 `http://vllm_server:8000/v1`
- `MODEL_NAME`：模型名稱或路徑（由 `llm_client.py` 使用）
- `DB_PATH`：SQLite 檔案路徑，預設 `/data/chat_history.db`
- `LINE_CHANNEL_SECRET`：LINE Messaging API channel secret
- `LINE_CHANNEL_ACCESS_TOKEN`：LINE Messaging API channel access token
- `LINE_BACKEND_PUBLIC_URL`：可選；公開網址前綴（留空時會自動從 proxy header 推導）

## 4. 主要介面

1. `POST /chat`
- 輸入參數：`session_id`, `message`
- 輸出參數：`reply`（分段列表）, `thought`

2. `GET /monitor/{session_id}`
- 回傳會話歷史與狀態，用於警方監控視角。

3. `POST /clear`
- 輸入參數：`session_id`
- 清理 SQLite 與 ChromaDB 中該會話的紀錄。

## 5. 開發提示

- 聊天介面會把 AI 回覆依 `|SPLIT|` 拆段。
