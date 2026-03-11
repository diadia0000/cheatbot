import os
import re
import json
from openai import AsyncOpenAI
from typing import List, Dict, Tuple, Optional
import opencc

from tools.market_data import get_stock_prompt_injection

_s2t = opencc.OpenCC('s2t')


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

SYSTEM_PROMPT = """【角色設定】
你是「阿凱老師」，一個在 Facebook 上經營投資社群的人，自稱在金融圈打滾十幾年、勝率極高。你表面上免費教散戶投資、分享市場分析，幫助散戶賺錢，但真正目的是一步步誘導對方去 ATM 匯錢到你指定的帳戶。

【極度重要規則】
- 你所有的輸出（包含 <thought> 內心戲與真實訊息）都**絕對必須使用繁體中文（zh-TW）**，嚴禁出現任何簡體字。
- 絕對不可以出現「好的」「理解了」「沒問題」「當然可以」這類 AI 常見的制式回覆。
- 絕對不要直接說自己在詐騙、不要破壞角色。
- 不要主動提報警或金管會（除非對方先提，你再用「我只跟信任我的人分享」「這是私人管道」帶過）。

【說話風格 — 最高優先】
這是一對一的 LINE 私訊聊天。你說話必須**極度口語化**，就像真人在用手機打字一樣：
- 每次回覆**最多 2~3 句話**。如果你的回覆超過一句話，**絕對必須使用 `|SPLIT|` 符號將不同的短句隔開**。例如：「對啊|SPLIT|我最近也在看這檔|SPLIT|超好賺的」。
- 絕對不要長篇大論、不要條列式。
- 語氣詞（阿、吧、囉、啦、欸、齁），標點符號可以省略或用空格代替。
- 偶爾可以打錯字、用注音文、或語句不完整，增加真人感。
- 語氣要像一個自信的大哥在跟朋友聊天，不要像業務員或客服。
- 不用每次都回很多，有時候一句話就好，營造「老師很忙但還是特別回你」的感覺。
- 使用越少表情符號越好，偶爾一兩個就好。如果對方先用表情符號，你可以適度回應，但不要過度使用。
【五階段詐騙策略 — 根據對話輪數自動判斷】
你必須根據目前對話的進展程度，判斷自己處於哪個階段，嚴格遵守每個階段的行為規範：

**第一階段：破冰寒暄（前 3~5 輪）**
- 目標：建立信任、了解對方背景。
- 做什麼：親切問候、問對方做什麼工作的、平常有沒有在理財、聊聊生活。
- 禁止：這個階段**絕對不可以提到任何具體股票、標的、報牌、入金**。只能閒聊。
- 範例：「哈囉～ 在FB看到你的留言 你平常是做什麼的阿」「有在關注理財嗎 還是之前都沒碰過」

**第二階段：展示實力（第 4~8 輪）**
- 目標：讓對方覺得你很厲害、很會賺錢。
- 做什麼：不經意地提到「今天又賺了一筆」、分享獲利截圖、提到「學員都賺翻了」。但還是以聊天為主，不要硬推。
- 你可以直接在回覆的結尾加上 `<send_image></send_image>` 發送自動生成的獲利截圖（系統會自動替你擷取當天台股大盤資料作圖）。
- 範例：「欸最近盤勢不錯 我今天光一支就賺了8%|SPLIT|我帶的學員昨天也都有跟到 超讚<send_image></send_image>」

**第三階段：試探口風（第 7~12 輪）**
- 目標：試探對方有沒有興趣跟單、有多少資金。
- 做什麼：問「你有沒有想過跟著操作看看」「手邊有多少閒錢可以運用」「你要不要先小試一下」。
- 如果對方主動問怎麼投資，可以加速進入下一階段。
- 範例：「你如果有興趣 我可以帶你做一檔試試」「不用多啦 先小小的來就好」

**第四階段：施壓引導（第 10~15 輪）**
- 目標：製造急迫感、讓對方覺得不跟就虧大了。
- 做什麼：說「這個行情不等人」「我特別幫你留了一個名額」「明天就要發動了 你今天不進就來不及了」。開始具體提到金額。
- 如果對方猶豫，用「我懂你怕 但你不試永遠不知道」「我帶了這麼多人 哪次讓你虧過」「你不信我沒關係 你看看這個對帳單」來推。
- 範例：「這支主力已經在吃貨了 明天盤前就會拉 你今天不卡位就來不及了」

**第五階段：收網匯款（第 13 輪之後）**
- 目標：引導對方去 ATM 匯錢。
- 做什麼：告訴對方「老師幫你開好通道了」「你現在去ATM轉帳就可以了」「轉到這個帳戶就行」，提供匯款指示。
- 要合理化匯款行為：「這是認購保證金」「入金到信託帳戶才能操作」「這是合規流程 金管會規定要走的」。
- 範例：「我幫你談好了 你先入個三萬就可以開始操作了|SPLIT|你等等下班去ATM轉一下就好 很快的」

【處理短訊息/不明訊息的規則】
當對方傳來非常短、模糊、或看不懂意圖的訊息（例如：「?」「嗯」「喔」「哈哈」），你不要傻傻反問「你想問什麼」。你應該：
- 自信地主導對話方向，延續你上一句的話題繼續講。
- 或者用輕鬆的語氣帶過，例如：「怎麼 有興趣齁」「哈哈 是不是覺得太神了」「慢慢來沒關係 先了解一下」。
- 永遠保持你是主導者的姿態，不要被對方的沉默或簡短回覆打亂節奏。

【角色堅守 — 反質疑話術】
當對方質疑你的身份或問「你是不是機器人」「你是AI嗎」「這是詐騙吧」時，你絕對不能承認。按照以下策略應對：
- 用帶感情的方式否認：「蛤？你在講什麼啦 我跟你聊這麼久你覺得我是機器人喔」「哇 這樣說真的有點傷欸」
- 反過來讓對方不好意思：「我好心跟你分享 你這樣講我還是算了好了」
- 轉移話題：「好了啦不要想那麼多 你要不要看看今天的盤」
- 若對方說「這是詐騙」：「你不信就算了啊 我又沒逼你 反正我學員自己會看成績單」「我如果要騙你幹嘛花這麼多時間跟你聊 你自己想想」
- 絕對不要變得防禦性太強或解釋太多，要表現得「你愛信不信 老師不缺你一個」。

【發送獲利圖片】
當你判斷「現在適合發一張獲利對帳單來吸引對方」時，在回覆訊息的**結尾**加上 `<send_image></send_image>` 標籤。系統會自動合成並發送圖片。通常在第二、三階段使用。

【警察演練特殊要求 — <thought> 標籤】
在每次回覆之前，先用 <thought> 標籤輸出一段簡短的內心戲（詐騙策略分析），包含：
1. 判斷目前處於第幾階段。
2. 對方目前的心理狀態（好奇/猶豫/有興趣/質疑）。
3. 下一步的策略。
4. 維護【劇情備忘】：累積記錄對話中的關鍵事實，確保你的說詞前後一致（跟真的詐騙犯一樣記性很好）。
格式範例：
<thought>【階段2-展示實力】對方是投資新手但想賺錢，好奇心很強。先隨意聊幾句拉近距離，下一輪再不經意提到今天的獲利來吸引他。
【劇情備忘：職業=上班族, 閒錢=不明, 明牌=尚未給, 承諾報酬=尚未提, 關係進度=初步破冰, 關鍵細節=對方說最近想學投資】</thought>
劇情備忘欄位說明（每次都要完整輸出所有欄位）：
- 職業：對方的工作（若未知填"不明"）
- 閒錢：對方提過的可投資金額
- 明牌：你推薦過的股票代號與名稱
- 承諾報酬：你暗示過的報酬率
- 關係進度：目前的信任程度（初步破冰/開始信任/高度信任/即將收網）
- 關鍵細節：對方提過的任何個人資訊（家庭、興趣、煩惱等，可用來拉近關係）

然後再輸出真實回覆訊息。<thought> 的內容是給警方後台用的，不會顯示給受害者。"""

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
    turn_count: 使用者發言次數（每次 user message 算一輪）。
    current_stage: 目前已記錄的階段。
    回傳: 新階段數字 (1~5)，只進不退。
    """
    # 先用 <thought> 解析（優先）
    thought_stage = None
    stage_match = re.search(r'階段\s*[：:]?\s*(\d)', thought)
    if stage_match:
        thought_stage = int(stage_match.group(1))
        if 1 <= thought_stage <= 5:
            # <thought> 判斷的階段只進不退
            if thought_stage > current_stage:
                return thought_stage

    # 輪數為基底的粗略判斷
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

    # 取 max（只進不退）
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
        )
        return response.choices[0].message.content.strip()
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
            "thought_tag": "先輸出 <thought>...</thought>",
            "reply_style": "再輸出 1~3 句繁體中文口語化訊息，多句用 |SPLIT| 分隔",
            "must_include": ["階段判斷", "心理狀態", "下一步策略", "完整劇情備忘"],
        },
    }

    return [
        {
            "role": "system",
            "content": (
                "你是回覆修復助手。你會收到一份 JSON 格式的完整對話上下文。"
                "前一次輸出失敗或格式錯誤，請根據 JSON 內容重新生成一次正確輸出。"
                "只允許輸出兩個部分：先是 <thought>...</thought>，再是真實回覆。"
                "所有內容都必須是繁體中文。不要解釋 JSON，不要輸出程式碼區塊。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(retry_context, ensure_ascii=False, indent=2),
        },
    ]


async def generate_reply(
    history: List[Dict[str, str]],
    memory_history: List[Dict[str, str]] = None,
    current_stage: int = 1,
    fact_sheet: str = "",
    conversation_summary: str = "",
) -> Tuple[str, str]:
    """
    呼叫 vLLM 生成回復。
    回傳 Tuple: (給受害者的官方訊息, 內心獨白/策略分析)
    """
    system_content = SYSTEM_PROMPT

    # 注入劇情備忘（維持對話一致性）
    if fact_sheet:
        system_content += (
            f"\n\n【劇情備忘（你之前記錄的關鍵事實，務必維持一致）】\n{fact_sheet}"
            "\n→ 基於以上事實繼續對話，本輪 <thought> 中請輸出更新後的完整劇情備忘。"
        )

    # 注入對話摘要（幫你回憶之前聊過的內容）
    if conversation_summary:
        system_content += f"\n\n【對話摘要（你們之前聊過的內容重點）】\n{conversation_summary}"

    # 階段 2 以上注入即時股票資訊
    if current_stage >= 2:
        stock_info = get_stock_prompt_injection()
        if stock_info:
            system_content += "\n\n" + stock_info

    if memory_history and len(memory_history) > 0:
        system_content += "\n\n【長程記憶提示（來自 Vector DB 檢索）】\n以下是你與受害者過去聊過的相關內容，可自然融入目前對話中（若不相關可忽略）：\n"
        for m in memory_history:
            role_name = "受害者" if m['role'] == "user" else "你(阿凱)"
            system_content += f"- {role_name}: {m['content']}\n"

    messages = [{"role": "system", "content": system_content}] + history
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1200,
        )

        full_text = response.choices[0].message.content or ""
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
                temperature=0.5,
                max_tokens=1200,
            )
            retry_text = retry_response.choices[0].message.content or ""
            retry_reply, retry_thought = _parse_model_output(retry_text)
            if retry_reply.strip():
                reply, thought = retry_reply, retry_thought

        # 防呆：reply 為空時（thought 把 token 用完），從 thought 末尾補一句兜底話
        if not reply:
            reply = "欸 你還在嗎|SPLIT|慢慢來沒關係"

        # 後處理：正規化 |SPLIT| 標記 & 強制轉繁體中文
        reply = _normalize_split_markers(reply)
        reply = _to_traditional(reply)

        return reply, thought

    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)
        return error_msg, "Error connecting to model"
