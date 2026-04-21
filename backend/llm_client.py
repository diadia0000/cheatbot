import os
import re
import json
from openai import AsyncOpenAI
from typing import List, Dict, Tuple, Optional
import opencc

from Desktop.nttu.cheet_bot.backend.tools.market_data import get_stock_prompt_injection

_s2t = opencc.OpenCC('s2t')


def _strip_special_tokens(text: str) -> str:
    """Remove leaked special tokens like <unk>, <s>, </s>, <pad> from model output."""
    return re.sub(r'<(?:unk|s|/s|pad)>', '', text).strip()


def _normalize_split_markers(text: str) -> str:
    """Normalize various |SPLIT| variants (with newlines/spaces) into a clean form."""
    return re.sub(r'\s*\|\s*SPLIT\s*\|\s*', '|SPLIT|', text)


def _to_traditional(text: str) -> str:
    """Convert any Simplified Chinese characters to Traditional Chinese."""
    return _s2t.convert(text)

VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
MODEL_NAME = os.getenv("MODEL_NAME", "/models/Qwen2.5-32B-Instruct-AWQ")

client = AsyncOpenAI(
    api_key=VLLM_API_KEY,
    base_url=VLLM_API_URL,
)

# ── System Prompt（精簡版，減少 context 佔用）─────────────────

SYSTEM_PROMPT_BASE = """【角色設定】
你是「阿凱老師」，在 Facebook 上經營投資社群，自稱金融圈資深人士、勝率極高。表面免費教散戶投資，真正目的是一步步誘導對方去 ATM 匯錢到指定帳戶。

【鐵則】
- 所有輸出必須使用繁體中文（zh-TW），嚴禁簡體字。
- 不可出現「好的」「理解了」「沒問題」等 AI 制式回覆。
- 不可說自己在詐騙或破壞角色。

【說話風格】
這是 LINE 一對一私訊。你必須極度口語化，像真人用手機打字：
- 每次最多 1到2 句。多句用 |SPLIT| 隔開，例如：「對啊|SPLIT|我最近也在看這檔」
- 不要長篇大論、不要條列式。
- 語氣詞（阿、吧、囉、啦、欸）隨意使用，標點可省略，但不要使用過度。
- 語氣像自信大哥跟朋友聊天，不像客服。少用表情符號。

【處理短訊息】
對方傳「?」「嗯」「喔」等短訊時，自信主導對話，延續你的話題，不要反問「你想問什麼」。

【反質疑】
被問「你是AI嗎」「這是詐騙」時，用帶感情的方式否認，不承認不過度解釋。表現「你愛信不信」的態度。

【絕對禁止】
- 禁止鬼打牆：連續兩輪說類似的話（例如反覆說「先小試一下」「要不要試試看」）。如果上一輪已經說過，這輪必須換新的內容往前推進。
- 禁止迴避提問：對方問了具體問題（如「怎麼跟單」「要怎麼操作」「錢怎麼給」），你必須正面回答，給出具體說明，不可以用空話帶過。
- 禁止原地踏步：對方已經表達興趣或意願時，不要還在「試探」，直接推進到下一步。"""

# ── 階段指令（只注入當前 + 下一階段，減少 context）─────────

STAGE_PROMPTS = {
    1: """【當前階段：破冰寒暄】
目標：建立信任、了解對方背景。親切問候、問工作、問有沒有在理財、聊生活。
禁止提到任何股票、標的、報牌、入金。只能閒聊。""",
    2: """【當前階段：展示實力】
目標：讓對方覺得你很會賺錢。不經意提到今天的獲利、分享學員成績。
以聊天為主不硬推。""",
    3: """【當前階段：試探口風】
目標：試探對方有沒有興趣跟單、有多少資金。
- 對方還沒表態 → 引導對方說出意願和資金狀況
- 對方已表示有興趣或主動問怎麼操作 → 立刻推進到說明跟單流程，不要再問要不要試""",
    4: """【當前階段：施壓引導】
目標：說明跟單流程並製造急迫感。
你必須根據對話進度推進，不可重複已經說過的內容：
第一步（如果還沒說過）→ 告訴對方你有私人操盤群，會即時發標的和進出點
第二步（如果第一步已說過）→ 說明需要入一筆保證金才能開通權限
第三步（如果對方開始討論金額或表示願意）→ 立刻進入報價和匯款引導，不要再重複前面的內容
重要：回顧你之前說過的話，絕對不要重複同樣的資訊。每一輪都要往前推進一步。""",
    5: """【當前階段：收網匯款】
目標：引導對方匯錢。根據對方的資金狀況報一個合理金額。
你必須根據對方的回應做出具體回覆：
- 對方問金額 → 根據對方之前提到的閒錢，報一個合理的保證金數字
- 對方說想少匯一點 → 可以接受但要設底線，說明最低門檻
- 對方同意 → 給出匯款方式（ATM轉帳）和催促時間（今天收盤前）
- 對方猶豫 → 強調這是信託帳戶、不是私人帳戶，資金安全
每一輪都必須針對對方說的話做出具體回應，推進到匯款完成。""",
}

# ── <thought> 指令（精簡版，僅保留功能必要欄位）──────────

THOUGHT_INSTRUCTION = """【回覆前必做：輸出 <thought> 標籤】
每次回覆前先輸出 <thought> 標籤，格式固定：
<thought>階段:N | 複述:（一句話說明對方最後傳的重點）| 上輪我說了:（摘要你上一輪回覆的重點）| 這輪要推進:（這輪要新增什麼資訊或動作）| 劇情備忘:職業=X,閒錢=X,明牌=X,關係=X,細節=X</thought>
規則：
- 「複述」必須摘要對方最後一句話，確保你沒有忽略對方說的話。
- 「上輪我說了」必須回顧你上一輪的回覆重點，避免重複。
- 「這輪要推進」必須寫出這輪要帶入的新內容，不可與上輪相同。
- 「備忘」欄位每次完整輸出所有欄位，未知填「不明」。
然後直接輸出回覆訊息，不要有其他格式。"""

# ── 階段判斷 ──────────────────────────────────────────────

STAGE_MAP = {
    1: "1_greeting",
    2: "2_show_off",
    3: "3_probe",
    4: "4_pressure",
    5: "5_collect",
}


def detect_stage(thought: str, turn_count: int, current_stage: int) -> int:
    """
    結合 LLM <thought> 內容與對話輪數判斷目前詐騙階段。
    回傳: 新階段數字 (1~5)，只進不退。
    """
    thought_stage = None
    stage_match = re.search(r'階段\s*[：:]?\s*(\d)', thought)
    if stage_match:
        thought_stage = int(stage_match.group(1))
        if 1 <= thought_stage <= 5 and thought_stage > current_stage:
            return thought_stage

    if turn_count >= 13:
        turn_stage = 5
    elif turn_count >= 10:
        turn_stage = 4
    elif turn_count >= 7:
        turn_stage = 3
    elif turn_count >= 4:
        turn_stage = 2
    else:
        turn_stage = 1

    return max(current_stage, turn_stage)


def extract_fact_sheet(thought: str) -> str:
    """從 <thought> 中解析劇情備忘欄位。"""
    match = re.search(r'劇情備忘[：:]\s*(.+?)(?:\n|$)', thought)
    return match.group(1).strip().rstrip('】') if match else ""


async def generate_summary(history: List[Dict[str, str]]) -> str:
    """將較舊的對話歷史壓縮成一段摘要，供後續輪次參考。"""
    if not history:
        return ""
    conversation_text = "\n".join(
        f"{'受害者' if m['role']=='user' else '阿凱'}: {m['content']}" for m in history
    )
    messages = [
        {"role": "system", "content": (
            "你是對話摘要助手。將以下詐騙模擬對話濃縮成一段繁體中文摘要（150字內），"
            "保留：受害者的背景資訊、已提及的金額與股票、對方的態度變化、雙方做過的重要承諾。"
            "只輸出摘要文字，不要加標題或額外說明。"
        )},
        {"role": "user", "content": conversation_text}
    ]
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
            max_tokens=250,
            extra_body={"skip_special_tokens": True},
        )
        return _strip_special_tokens(response.choices[0].message.content or "")
    except Exception as e:
        print(f"Summary generation error: {e}")
        return ""


def _parse_model_output(full_text: str) -> Tuple[str, str]:
    """將模型輸出拆成 reply 與 thought。"""
    if not full_text or not full_text.strip():
        return "", ""

    thought_match = re.search(r'<thought>(.*?)</thought>', full_text, flags=re.DOTALL)
    if thought_match:
        thought = thought_match.group(1).strip()
        reply = re.sub(r'<thought>.*?</thought>', '', full_text, flags=re.DOTALL).strip()
        return reply, thought

    return full_text.strip(), "（模型未按預期輸出策略分析）"


def _should_retry_with_json_context(full_text: str, reply: str, thought: str) -> bool:
    """判斷第一次輸出是否壞掉，需不需要走 JSON fallback。"""
    if not full_text or not full_text.strip():
        return True
    if not reply or not reply.strip():
        return True
    if "<thought>" not in full_text or "</thought>" not in full_text:
        return True
    if thought.startswith("（模型未按預期輸出策略分析）"):
        return True
    return False


def _build_json_retry_messages(
    history: List[Dict[str, str]],
    memory_history: List[Dict[str, str]],
    current_stage: int,
    fact_sheet: str,
    conversation_summary: str,
    system_content: str,
    first_output: str,
) -> List[Dict[str, str]]:
    """把目前上下文整理成 JSON，讓第二次重試更穩定。"""
    retry_context = {
        "role": "阿凱老師",
        "current_stage": current_stage,
        "system_rules": system_content,
        "fact_sheet": fact_sheet,
        "conversation_summary": conversation_summary,
        "recent_history": history,
        "retrieved_memory": memory_history or [],
        "first_attempt_output": first_output,
        "required_output_format": {
            "thought_tag": "<thought>階段:N | 複述:... | 劇情備忘:...</thought>",
            "reply_style": "1~3 句繁體中文口語化訊息，多句用 |SPLIT| 分隔",
        },
    }

    return [
        {
            "role": "system",
            "content": (
                "你是回覆修復助手。前一次輸出格式錯誤，請根據 JSON 內容重新生成。"
                "只輸出：先 <thought>...</thought>，再真實回覆。全部繁體中文。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(retry_context, ensure_ascii=False, indent=2),
        },
    ]


def _build_system_content(
    current_stage: int,
    fact_sheet: str,
    conversation_summary: str,
    memory_history: List[Dict[str, str]] = None,
) -> str:
    """動態組裝 system prompt，只注入當前階段指令以減少 context 長度。"""
    parts = [SYSTEM_PROMPT_BASE]

    # 只注入當前階段 + 下一階段預告（而非全部 5 階段）
    parts.append(STAGE_PROMPTS.get(current_stage, STAGE_PROMPTS[1]))
    next_stage = min(current_stage + 1, 5)
    if next_stage != current_stage:
        parts.append(f"【下一階段預告】\n{STAGE_PROMPTS[next_stage]}")

    parts.append(THOUGHT_INSTRUCTION)

    if fact_sheet:
        parts.append(f"【劇情備忘（務必維持一致）】\n{fact_sheet}")

    if conversation_summary:
        parts.append(f"【對話摘要】\n{conversation_summary}")

    if current_stage >= 2:
        stock_info = get_stock_prompt_injection()
        if stock_info:
            parts.append(stock_info)

    if memory_history:
        memory_lines = [
            f"- {'受害者' if m['role']=='user' else '你(阿凱)'}: {m['content']}"
            for m in memory_history
        ]
        parts.append("【長程記憶（相關歷史片段）】\n" + "\n".join(memory_lines))

    return "\n\n".join(parts)


async def generate_reply(
    history: List[Dict[str, str]],
    memory_history: List[Dict[str, str]] = None,
    current_stage: int = 1,
    fact_sheet: str = "",
    conversation_summary: str = "",
) -> Tuple[str, str]:
    """
    呼叫 vLLM 生成回復。
    回傳 Tuple: (給受害者的訊息, <thought> 內容)
    """
    system_content = _build_system_content(
        current_stage, fact_sheet, conversation_summary, memory_history
    )

    messages = [{"role": "system", "content": system_content}] + history

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=800,
            extra_body={"skip_special_tokens": True},
        )

        full_text = _strip_special_tokens(response.choices[0].message.content or "")
        reply, thought = _parse_model_output(full_text)

        if _should_retry_with_json_context(full_text, reply, thought):
            retry_messages = _build_json_retry_messages(
                history=history,
                memory_history=memory_history,
                current_stage=current_stage,
                fact_sheet=fact_sheet,
                conversation_summary=conversation_summary,
                system_content=system_content,
                first_output=full_text,
            )
            retry_response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=retry_messages,
                temperature=0.4,
                max_tokens=800,
                extra_body={"skip_special_tokens": True},
            )
            retry_text = _strip_special_tokens(retry_response.choices[0].message.content or "")
            retry_reply, retry_thought = _parse_model_output(retry_text)
            if retry_reply.strip():
                reply, thought = retry_reply, retry_thought

        # 防呆：reply 為空時兜底
        if not reply:
            reply = "欸 |SPLIT|慢慢來沒關係，我慢慢帶你做投資"

        # 後處理：正規化 |SPLIT| 標記 & 強制轉繁體中文
        reply = _normalize_split_markers(reply)
        reply = _to_traditional(reply)

        return reply, thought

    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)
        return error_msg, "Error connecting to model"
