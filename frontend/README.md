# Frontend 說明（Streamlit）

前端提供兩個視角：
- 受害者視角：模擬 LINE 聊天介面
- 警方監控視角：查看狀態、推理摘要與完整歷史

## 1. 安裝相依套件

在專案根目錄執行：

```bash
source .venv/bin/activate
pip install -r frontend/requirements.txt
```

## 2. 啟動前端

```bash
source .venv/bin/activate
streamlit run frontend/app.py --server.port 8501
```

## 3. 環境變數

- `BACKEND_API_URL`：後端位址，預設 `http://localhost:8080`

範例：

```bash
export BACKEND_API_URL=http://127.0.0.1:8080
streamlit run frontend/app.py --server.port 8501
```

## 4. 使用說明

1. 進入前端頁面後，可在側邊欄切換視角。
2. 點擊「清除歷史紀錄」會呼叫後端 `/clear` 清理目前會話。
3. 傳送訊息後，前端會依後端回傳的 `delay_seconds` 模擬打字延遲。

## 5. 注意事項

- 若頁面提示無法連線後端，請先確認後端服務已啟動。
- 如果使用 Docker Compose，容器內會自動注入 `BACKEND_API_URL=http://fastapi_backend:8080`。
