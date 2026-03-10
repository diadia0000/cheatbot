import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import random

from database import init_db, save_message, get_chat_history, update_session_state, get_session_state, get_relevant_history
from llm_client import generate_reply

app = FastAPI(title="Anti-Fraud Agent Backend")

@app.on_event("startup")
def on_startup():
    init_db()

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
    
    # 透過 RAG 從 Vector DB 取得與當下話題相關的歷史記憶
    memory_history = get_relevant_history(req.session_id, req.message, n_results=3)
    
    # 呼叫 vLLM
    reply, thought = await generate_reply(history, memory_history)
    
    image_url = None
    if "<send_image></send_image>" in reply:
        reply = reply.replace("<send_image></send_image>", "").strip()
        from image_generator import generate_profit_image
        # It takes ~1 second to generate but that's fast enough.
        # Call it in an executor if needed, but synchronous is fine for basic usage
        try:
            generate_profit_image()
            image_url = f"/image?session_id={req.session_id}" # or just serve a static one for now.
        except Exception as e:
            print(f"Error generating image: {e}")

    # 處理多段訊息分割
    reply_segments = [seg.strip() for seg in reply.split("|SPLIT|") if seg.strip()]

    # 儲存 AI 回覆 (只存對外回覆)
    # 這裡將陣列組裝起來存入資料庫，或者分多筆存入
    save_message(req.session_id, "assistant", " ".join(reply_segments))
    
    # 擬真化插件：計算打字延遲
    # 公式： len(text) * 0.4s + random(1, 3)s
    delay = len(reply) * 0.1 + random.uniform(1, 3) # 稍微縮短 0.4 -> 0.1 避免等太久，依需求可調
    
    # 更新狀態 (簡化版：目前皆為測試)
    update_session_state(req.session_id, fraud_stage="ongoing", victim_tags="待標註")

    return ChatResponse(
        reply=reply_segments,
        thought=thought,
        delay_seconds=delay,
        image_url=image_url
    )

from fastapi.responses import FileResponse
import os
@app.get("/image")
async def get_image():
    path = os.path.join(os.path.dirname(__file__), "assets", "generated-picture.png")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
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
