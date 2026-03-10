# 系統架構（Mermaid）

以下內容由 `architecture.drawio` 轉換而來。

```mermaid
flowchart LR
    VictimUI["Streamlit Frontend\n(受害者視角 - LINE UI)"]
    PoliceUI["Streamlit Frontend\n(警方視角 - 監控面板)"]
    FastAPI["FastAPI Backend\n(業務邏輯 / 分段回覆 / RAG)"]
    SQLite[("SQLite DB\n(短期會話歷史)")]
    ChromaDB[("ChromaDB\n(向量長期記憶 RAG)")]
    vLLM["vLLM Server\n(Qwen2.5-14B-AWQ @ GPU)"]
    FalAPI{{"Fal.ai Cloud API\n(Flux 圖像生成)"}}

    VictimUI -->|REST / Chat API| FastAPI
    PoliceUI -->|REST / Stream API| FastAPI
    FastAPI -->|Short Memory| SQLite
    FastAPI -->|RAG Query| ChromaDB
    FastAPI -->|OpenAI Chat API| vLLM
    FastAPI -->|REST(Base64 + Prompt)| FalAPI
```
