"""
LINE Bot Webhook Handler
將 LINE 使用者的訊息轉發到現有的聊天邏輯，並透過 LINE Messaging API 回覆。
"""
import os
import re
import asyncio
import hashlib
import hmac
import base64

from fastapi import APIRouter, Request, HTTPException, Header

from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from database import (
    save_message,
    get_chat_history,
    update_session_state,
    get_session_state,
    get_relevant_history,
)
from llm_client import (
    generate_reply,
    detect_stage,
    STAGE_MAP,
    extract_fact_sheet,
    generate_summary,
)

# ── 環境變數 ──────────────────────────────────────────────
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

router = APIRouter()

# ── LINE SDK 初始化 ───────────────────────────────────────
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(async_api_client)
parser = WebhookParser(LINE_CHANNEL_SECRET)


def _make_session_id(line_user_id: str) -> str:
    """將 LINE user ID 轉為 session_id，加上 prefix 方便辨識。"""
    return f"line_{line_user_id}"


@router.post("/webhook")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    """LINE Platform 會把使用者訊息 POST 到這裡。"""
    if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="LINE credentials not configured")

    body = await request.body()
    body_text = body.decode("utf-8")

    # 驗證簽章
    try:
        events = parser.parse(body_text, x_line_signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        user_message = event.message.text
        line_user_id = event.source.user_id
        reply_token = event.reply_token
        session_id = _make_session_id(line_user_id)

        # ── 走既有的聊天流程 ──────────────────────────
        reply_text = await _process_chat(session_id, user_message)

        # ── 回覆 LINE ────────────────────────────────
        messages = []
        # 支援 |SPLIT| 多段訊息（用 regex 處理換行/空白變體）
        segments = [s.strip() for s in re.split(r'\s*\|\s*SPLIT\s*\|\s*', reply_text) if s.strip()]
        if not segments:
            segments = [reply_text or "…"]

        for seg in segments:
            messages.append(TextMessage(text=seg))

        # LINE reply API 最多 5 則訊息
        await line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages[:5],
            )
        )

    return "OK"


async def _process_chat(session_id: str, user_message: str):
    """
    複用 main.py 中 chat_endpoint 的核心邏輯，回傳 reply_text。
    """
    # 儲存使用者訊息
    save_message(session_id, "user", user_message)

    # 取得短期對話（加大 limit 避免重複問已回答過的問題）
    history = get_chat_history(session_id, limit=10)

    # 計算輪數
    full_history = get_chat_history(session_id, limit=200)
    turn_count = sum(1 for m in full_history if m["role"] == "user")

    # 取得狀態
    state = get_session_state(session_id)
    current_stage_str = state.get("fraud_stage", "1_greeting")
    current_stage = int(current_stage_str[0]) if current_stage_str[0].isdigit() else 1
    fact_sheet = state.get("fact_sheet", "")
    conversation_summary = state.get("conversation_summary", "")

    # RAG 記憶
    memory_history = get_relevant_history(session_id, user_message, n_results=3)

    # 呼叫 vLLM
    reply, thought = await generate_reply(
        history, memory_history,
        current_stage=current_stage,
        fact_sheet=fact_sheet,
        conversation_summary=conversation_summary,
    )

    # 階段判斷
    new_stage = detect_stage(thought, turn_count, current_stage)
    stage_label = STAGE_MAP.get(new_stage, f"{new_stage}_unknown")

    # 移除 LLM 可能殘留的 <send_image> 標籤
    reply = reply.replace("<send_image></send_image>", "").strip()

    # 儲存回覆
    reply_segments = [seg.strip() for seg in reply.split("|SPLIT|") if seg.strip()]
    save_message(session_id, "assistant", " ".join(reply_segments))

    # 劇情備忘
    new_fact_sheet = extract_fact_sheet(thought)

    # 滾動摘要
    new_summary = conversation_summary
    if turn_count >= 8 and (turn_count % 5 == 0 or not conversation_summary):
        older_messages = full_history[:-6] if len(full_history) > 6 else []
        if older_messages:
            new_summary = await generate_summary(older_messages)

    # 更新狀態（含 thought 供監控）
    update_session_state(
        session_id,
        fraud_stage=stage_label,
        victim_tags="待標註",
        fact_sheet=new_fact_sheet if new_fact_sheet else fact_sheet,
        conversation_summary=new_summary,
    )

    return reply
