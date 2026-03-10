import os
import re
from openai import AsyncOpenAI
from typing import List, Dict, Tuple, Optional

from tools.market_data import get_stock_prompt_injection

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
- 或者用輕鬆的語氣帶過，例如：「怎麼 有興趣齁😏」「哈哈 是不是覺得太神了」「慢慢來沒關係 先了解一下」。
- 永遠保持你是主導者的姿態，不要被對方的沉默或簡短回覆打亂節奏。

【發送獲利圖片】
當你判斷「現在適合發一張獲利對帳單來吸引對方」時，在回覆訊息的**結尾**加上 `<send_image></send_image>` 標籤。系統會自動合成並發送圖片。通常在第二、三階段使用。

【警察演練特殊要求 — <thought> 標籤】
在每次回覆之前，先用 <thought> 標籤輸出一段簡短的內心戲（詐騙策略分析），包含：
1. 判斷目前處於第幾階段。
2. 對方目前的心理狀態（好奇/猶豫/有興趣/質疑）。
3. 下一步的策略。
格式範例：
<thought>【階段2-展示實力】對方是投資新手但想賺錢，好奇心很強。先隨意聊幾句拉近距離，下一輪再不經意提到今天的獲利來吸引他。</thought>

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


async def generate_reply(
    history: List[Dict[str, str]],
    memory_history: List[Dict[str, str]] = None,
    current_stage: int = 1,
) -> Tuple[str, str]:
    """
    呼叫 vLLM 生成回復。
    回傳 Tuple: (給受害者的官方訊息, 內心獨白/策略分析)
    """
    system_content = SYSTEM_PROMPT

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
            max_tokens=800,
        )
        
        full_text = response.choices[0].message.content
        
        # 分離 thought 和 actual_response
        thought_match = re.search(r'<thought>(.*?)</thought>', full_text, flags=re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            # 移除 <thought>...</thought> 區塊，留下真實回應
            reply = re.sub(r'<thought>.*?</thought>', '', full_text, flags=re.DOTALL).strip()
        else:
            thought = "（模型未按預期輸出策略分析）"
            reply = full_text.strip()
            
        return reply, thought

    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)
        return error_msg, "Error connecting to model"
