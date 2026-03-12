# 系統架構（Mermaid）

## 整體架構

```mermaid
flowchart LR
    LINEUser["LINE 使用者\n(受害者視角)"]
    LINEPlatform["LINE Platform"]
    Nginx["Nginx Gateway(webhook_gateway)"]
    FastAPI["FastAPI Backend\n(業務邏輯 / 階段追蹤 / RAG)"]
    SQLite[("SQLite DB\n(會話歷史 + 階段狀態)")]
    ChromaDB[("ChromaDB\n(向量長期記憶 RAG)")]
    vLLM["vLLM Server\n(Qwen2.5-32B-AWQ @ GPU)"]
    FinMind{"FinMind API\n(台股即時行情)"}
    MarketData["market_data.py\n(股價篩選 + 快取)"]
    StageDetect["detect_stage()\n(輪數 + thought 雙重判斷)"]

    LINEUser -->|"傳送訊息"| LINEPlatform
    LINEPlatform -->|"Webhook POST"| Nginx
    Nginx -->|"proxy_pass"| FastAPI
    FastAPI -->|"Reply API"| LINEPlatform
    LINEPlatform -->|"回覆訊息"| LINEUser
    FastAPI -->|Short Memory| SQLite
    FastAPI -->|RAG Query| ChromaDB
    FastAPI -->|OpenAI Chat API| vLLM
    FastAPI --> StageDetect
    StageDetect -->|"parse &lt;thought&gt;"| vLLM
    FastAPI -->|"Stage ≥ 2: 注入股票"| MarketData
    MarketData -->|"批量查詢 (ThreadPool)"| FinMind
```

## 對話流程（階段推進）

```mermaid
flowchart TD
    Start([LINE 使用者發送訊息]) --> Webhook[LINE Webhook 接收]
    Webhook --> Save[儲存至 SQLite + ChromaDB]
    Save --> Count[計算 turn_count]
    Count --> GetStage[讀取 session_state.fraud_stage]
    GetStage --> LLM[呼叫 vLLM 生成回覆]
    GetStage -->|"Stage ≥ 2"| Inject[注入即時股票資訊至 system prompt]
    Inject --> LLM
    LLM --> ParseThought["解析 &lt;thought&gt; 標籤"]
    ParseThought --> DetectStage["detect_stage(thought, turns, current)\n只進不退"]
    DetectStage --> Split["|SPLIT| 分段"]
    Split --> UpdateState[更新 fraud_stage]
    UpdateState --> Reply([透過 LINE Reply API 回傳多段訊息])
```

## 服務元件說明

| 服務 | 容器名稱 | 說明 |
|------|----------|------|
| **vLLM Server** | `vllm_server` | 本地 GPU 推理引擎，部署 Qwen2.5-32B-AWQ 模型 |
| **FastAPI Backend** | `fastapi_backend` | 核心業務邏輯，處理對話、階段追蹤、RAG 記憶、LINE Webhook |
| **Webhook Gateway** | `webhook_gateway` | Nginx 反向代理，僅暴露 LINE Webhook 路由 |

> **備註**：使用者介面完全透過 LINE Messaging API 提供，不再使用獨立的 Streamlit 前端。
> LINE 使用者的訊息會經由 LINE Platform → Nginx → FastAPI `/line/webhook` 路由處理。
