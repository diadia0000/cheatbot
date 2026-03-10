import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
import random

from database import init_db, save_message, get_chat_history, update_session_state, get_session_state, get_relevant_history
from llm_client import generate_reply, detect_stage, STAGE_MAP

app = FastAPI(title="Anti-Fraud Agent Backend")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    reply: list[str]
    thought: str
    delay_seconds: float
    image_url: str | None = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # 保存用戶訊息
    save_message(req.session_id, "user", req.message)
    
    # 取得完整的對話歷史 (縮減為短期對話，避免 Token 過長)
    history = get_chat_history(req.session_id, limit=6)
    
    # 計算使用者對話輪數
    full_history = get_chat_history(req.session_id, limit=200)
    turn_count = sum(1 for m in full_history if m["role"] == "user")
    
    # 取得目前階段
    state = get_session_state(req.session_id)
    current_stage_str = state.get("fraud_stage", "1_greeting")
    current_stage = int(current_stage_str[0]) if current_stage_str[0].isdigit() else 1
    
    # 透過 RAG 從 Vector DB 取得與當下話題相關的歷史記憶
    memory_history = get_relevant_history(req.session_id, req.message, n_results=3)
    
    # 呼叫 vLLM，傳入目前階段以決定是否注入股票資訊
    reply, thought = await generate_reply(history, memory_history, current_stage=current_stage)
    
    # 更新階段判斷（結合 thought + 輪數）
    new_stage = detect_stage(thought, turn_count, current_stage)
    stage_label = STAGE_MAP.get(new_stage, f"{new_stage}_unknown")
    
    image_url = None
    if "<send_image></send_image>" in reply:
        reply = reply.replace("<send_image></send_image>", "").strip()
        from image_generator import generate_profit_image
        try:
            generate_profit_image(session_id=req.session_id)
            image_url = f"/image?session_id={req.session_id}"
        except Exception as e:
            print(f"Error generating image: {e}")

    # 處理多段訊息分割
    reply_segments = [seg.strip() for seg in reply.split("|SPLIT|") if seg.strip()]

    # 儲存 AI 回覆
    save_message(req.session_id, "assistant", " ".join(reply_segments))
    
    # 擬真化插件：計算打字延遲
    delay = len(reply) * 0.1 + random.uniform(1, 3)
    
    # 更新狀態
    update_session_state(req.session_id, fraud_stage=stage_label, victim_tags="待標註")

    return ChatResponse(
        reply=reply_segments,
        thought=thought,
        delay_seconds=delay,
        image_url=image_url
    )

@app.get("/image")
async def get_image(session_id: str = Query(default="default")):
    # 先嘗試 session 專屬圖片
    session_path = os.path.join(os.path.dirname(__file__), "assets", f"generated-{session_id}.png")
    if os.path.exists(session_path):
        return FileResponse(session_path, media_type="image/png")
    # Fallback 到預設圖片
    default_path = os.path.join(os.path.dirname(__file__), "assets", "generated-default.png")
    if os.path.exists(default_path):
        return FileResponse(default_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Image not found")

@app.get("/monitor/{session_id}")
async def monitor_endpoint(session_id: str):
    history = get_chat_history(session_id)
    state = get_session_state(session_id)
    return {
        "session_id": session_id,
        "history": history,
        "state": state
    }

class ClearRequest(BaseModel):
    session_id: str

@app.post("/clear")
async def clear_session(req: ClearRequest):
    import sqlite3
    DB_PATH = os.getenv("DB_PATH", "/data/chat_history.db")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (req.session_id,))
    cursor.execute("DELETE FROM session_state WHERE session_id = ?", (req.session_id,))
    conn.commit()
    conn.close()
    
    # 清除 ChromaDB 資料
    from database import collection
    if collection is not None:
        try:
            collection.delete(where={"session_id": req.session_id})
        except Exception:
            pass
            
    return {"status": "ok"}
