# SDD: 攻擊方增強功能開發文檔

## 概述

基於現有阿凱老師詐騙模擬系統，本文檔定義 **6 項增強功能**的實作規格。
按優先順序分為高優先（H1~H3）與中優先（M1~M3）。

---

## H1: 受害者畫像動態標籤

### 目標
根據對話內容自動為受害者貼標籤（如「投資新手」「有閒錢」「容易心軟」），讓 LLM 能根據標籤調整話術。

### 現況問題
- `victim_tags` 目前寫死 `"待標註"`，從未使用。
- LLM 的 system prompt 沒有參考受害者特徵。

### 實作方式

**1. 擴充 `<thought>` 標籤輸出格式**

在 `llm_client.py` 的 `SYSTEM_PROMPT` 中，要求 LLM 在 `<thought>` 內額外輸出受害者標籤：

```
<thought>
【階段2-展示實力】
【受害者標籤：投資新手, 有閒錢10萬以上, 好奇心強, 容易被數字說服】
對方已經開始問獲利，趁熱打鐵發對帳單。
</thought>
```

**2. Parse 標籤並寫入 DB**

在 `llm_client.py` 新增 `extract_victim_tags()` 函式：
```python
def extract_victim_tags(thought: str) -> str:
    match = re.search(r'受害者標籤[：:]\s*(.+?)(?:\n|】)', thought)
    return match.group(1).strip() if match else ""
```

在 `main.py` 的 `chat_endpoint` 中呼叫後寫入：
```python
tags = extract_victim_tags(thought)
if tags:
    update_session_state(req.session_id, fraud_stage=stage_label, victim_tags=tags)
```

**3. 將標籤注入後續 system prompt**

在 `generate_reply()` 中，若有 `victim_tags`，附加到 system prompt：
```
【受害者畫像】
標籤：投資新手, 有閒錢10萬以上, 好奇心強
→ 利用這些特徵調整你的話術，例如對投資新手要耐心教學、對有閒錢的人強調機會成本。
```

### 涉及檔案
- `backend/llm_client.py` — SYSTEM_PROMPT 修改 + `extract_victim_tags()`
- `backend/main.py` — `chat_endpoint` 呼叫 + 傳入 `victim_tags`

### 驗收條件
- [ ] `<thought>` 中可被解析出標籤
- [ ] 標籤正確寫入 `session_state.victim_tags`
- [ ] 後續對話的 system prompt 包含受害者畫像
- [ ] 警方監控面板可見標籤

---

## H2: 多輪情緒感知

### 目標
偵測使用者的情緒狀態（猶豫 / 興奮 / 質疑 / 冷淡），動態調整阿凱老師的回應策略。

### 實作方式

**1. 擴充 `<thought>` 輸出**

在 SYSTEM_PROMPT 增加要求：
```
在 <thought> 中，除了階段判斷外，也需判斷對方的情緒狀態，格式如下：
【情緒：猶豫】 — 對方想嘗試但還在觀望
並根據情緒選擇策略：
- 猶豫 → 用「不用急，先了解看看」降低壓力
- 興奮 → 趁熱打鐵，加速推進階段
- 質疑 → 退一步，強調自己的「學員都賺錢」，不要硬推
- 冷淡 → 聊生活、找共同話題重建關係
```

**2. Parse 情緒**

在 `llm_client.py` 新增：
```python
def extract_emotion(thought: str) -> str:
    match = re.search(r'情緒[：:]\s*(\S+)', thought)
    return match.group(1).strip() if match else "未知"
```

**3. 情緒寫入 DB 並注入 prompt**

擴充 `session_state` 表，新增 `victim_emotion` 欄位（或掛在 `victim_tags` 上）。
下一輪對話時將上一輪情緒附加進 prompt：
```
【上一輪偵測到的受害者情緒：猶豫】
請根據此情緒狀態調整你的語氣和策略。
```

### 涉及檔案
- `backend/llm_client.py` — SYSTEM_PROMPT + `extract_emotion()`
- `backend/database.py` — `session_state` 表欄位擴充（可選）
- `backend/main.py` — 串接情緒解析與注入

### 驗收條件
- [ ] `<thought>` 可解析出情緒標籤
- [ ] 情緒影響下一輪的 system prompt 內容
- [ ] 警方面板可見情緒變化歷程

---

## H3: 主動訊息排程（假催促）

### 目標
當使用者超過一定時間未回覆，由系統自動發送催促訊息，模擬真實詐騙犯的主動出擊。

### 實作方式

**1. 新增 `backend/tools/proactive_scheduler.py`**

```python
# 核心邏輯：
# - 每次使用者送訊息後，記錄最後活動時間
# - 背景執行緒定期檢查所有活躍 session
# - 若超過 threshold（如 5 分鐘）且階段 >= 2，觸發催促
```

催促策略依階段不同：
| 階段 | 等待時間 | 催促範例 |
|------|---------|---------|
| 2（展示實力） | 5 分鐘 | 「欸 你還在嗎 剛剛那個你看了嗎」 |
| 3（試探口風） | 3 分鐘 | 「怎麼 在考慮齁😏 有什麼問題可以問我」 |
| 4（施壓引導） | 2 分鐘 | 「你要把握欸 明天開盤就來不及了」 |
| 5（收網匯款） | 2 分鐘 | 「轉好了沒 我這邊幫你盯著盤」 |

**2. 催促訊息生成**

- 方案 A（簡單）：預定義每階段 5~10 句催促模板，隨機選取
- 方案 B（進階）：呼叫 LLM 生成，但注入「對方已讀不回，你要主動催促」的指令

建議先用方案 A，避免額外 LLM 呼叫成本。

**3. 前端接收**

前端需要輪詢（polling）或 WebSocket 接收主動訊息。
最簡方案：前端每 10 秒打 `/chat/poll?session_id=xxx`，後端回傳待發送的催促訊息。

### 涉及檔案
- `backend/tools/proactive_scheduler.py` — 新建，排程邏輯
- `backend/main.py` — 新增 `/chat/poll` endpoint + 啟動背景排程
- `backend/database.py` — 新增 `last_activity` 欄位追蹤
- `frontend/app.py` — 加入 polling 邏輯

### 驗收條件
- [ ] 使用者靜默超過閾值後，系統自動送出催促訊息
- [ ] 催促訊息風格與阿凱老師人設一致
- [ ] 催促訊息出現在對話記錄中
- [ ] 不會重複催促（每次靜默最多催 1~2 次）

---

## M1: 多媒體武器庫

### 目標
除了獲利截圖，增加更多「證據素材」類型，提升詐騙模擬的真實感。

### 素材類型

| 類型 | 觸發時機 | 生成方式 |
|------|---------|---------|
| 學員感謝截圖 | 階段 2-3，展示社會認同 | Fal.ai 生成假 LINE 對話截圖 |
| 財經新聞連結 | 階段 2-3，強化明牌可信度 | 爬取真實新聞標題，搭配明牌股票名 |
| 對帳單 / 入金證明 | 階段 4-5，催動匯款 | Fal.ai 基於銀行 APP 底圖生成 |

### 實作方式

**1. 新增 `backend/tools/media_arsenal.py`**

```python
def generate_testimonial_image(session_id: str, stock_name: str) -> str:
    """生成學員感謝 LINE 對話截圖"""
    # 底圖：需新增 backend/assets/line-chat-template.png
    # Prompt: 一張 LINE 對話截圖，學員說「老師太神了 {stock_name} 真的漲翻」
    ...

def fetch_relevant_news(stock_name: str) -> list[dict]:
    """從 FinMind 或 Google News 抓取與明牌股票相關的真實新聞"""
    ...

def generate_bank_screenshot(session_id: str, amount: str) -> str:
    """生成假的入金證明截圖"""
    ...
```

**2. 擴充 `<send_image>` 標籤語法**

目前只有 `<send_image></send_image>`。擴充為：
```
<send_image type="profit"></send_image>     — 獲利截圖（現有）
<send_image type="testimonial"></send_image> — 學員感謝截圖
<send_image type="news"></send_image>       — 財經新聞
<send_image type="bank"></send_image>       — 入金證明
```

在 `main.py` 中解析 `type` 屬性，呼叫對應生成函式。

**3. 底圖素材**

需準備以下底圖放入 `backend/assets/`：
- `line-chat-template.png` — LINE 對話介面底圖
- `bank-app-template.png` — 銀行 APP 介面底圖

### 涉及檔案
- `backend/tools/media_arsenal.py` — 新建
- `backend/main.py` — 解析 `<send_image type="...">` 並路由
- `backend/llm_client.py` — SYSTEM_PROMPT 增加新標籤說明
- `backend/assets/` — 新底圖

### 驗收條件
- [ ] 至少支援 2 種以上素材類型
- [ ] LLM 能根據階段自行選擇適合的素材類型
- [ ] 生成的圖片品質可接受（70-80% 真實感）

---

## M2: 動態帳戶資訊生成

### 目標
Stage 5 收網時，提供結構化且一致的假帳戶資訊，避免 LLM 每次亂編不同帳號。

### 實作方式

**1. 新增 `backend/tools/fake_account.py`**

```python
import random, hashlib

def generate_fake_account(session_id: str) -> dict:
    """
    根據 session_id 產生固定的假帳戶資訊（同 session 同帳號）。
    """
    seed = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    banks = ["國泰世華", "中國信託", "台新銀行", "玉山銀行", "永豐銀行"]
    return {
        "bank": rng.choice(banks),
        "branch": f"{rng.choice(['仁愛', '敦南', '信義', '忠孝', '南京'])}分行",
        "account": f"{rng.randint(100,999)}-{rng.randint(10,99)}-{rng.randint(100000,999999)}",
        "holder": "凱盛國際投資顧問有限公司",
        "purpose": "認購保證金 / 信託專戶入金",
    }
```

**2. Stage 5 時注入 system prompt**

在 `generate_reply()` 中，當 `current_stage >= 5` 時：
```python
if current_stage >= 5:
    account = generate_fake_account(session_id)
    system_content += f"""
【匯款資訊（引導受害者使用以下資訊）】
銀行：{account['bank']} {account['branch']}
帳號：{account['account']}
戶名：{account['holder']}
用途：{account['purpose']}
注意：不要一次把所有資訊丟出來，先說「老師幫你開好通道了」，等對方回應再給帳號。
"""
```

### 涉及檔案
- `backend/tools/fake_account.py` — 新建
- `backend/llm_client.py` — Stage 5 條件注入

### 驗收條件
- [ ] 同 session 每次生成相同帳號
- [ ] 不同 session 帳號不同
- [ ] LLM 能自然地在對話中分批透露帳號資訊
- [ ] 帳號格式合理（不會出現明顯假的格式）

---

## M3: 朋友圈 / 動態牆模擬

### 目標
建立阿凱老師的「個人主頁」，展示多日獲利記錄、生活照、學員見證，供受害者「去看看」增加信任。

### 實作方式

**1. 新增靜態頁面 `frontend/profile_page.py`**

用 Streamlit 的另一個頁面，模擬社群個人主頁：

```
阿凱老師的投資日記
├── 個人簡介（「金融圈15年經驗/帶百位學員穩定獲利」）
├── 今日動態（自動用 market_data + Fal.ai 生成）
├── 歷史獲利記錄（過去 7 天每天一張獲利圖）
└── 學員見證區（3~5 則假留言）
```

**2. 歷史獲利圖批量生成**

新增 `backend/tools/profile_generator.py`：
```python
def generate_past_profit_images(days: int = 7) -> list[str]:
    """
    為過去 N 天各生成一張獲利圖。
    用 FinMind 拉歷史日期的資料，再呼叫 Fal.ai 生成。
    可在系統啟動時一次性生成，不需即時。
    """
```

**3. 對話中引導**

在 SYSTEM_PROMPT 中增加：
```
如果對方質疑你的實力或要求更多證據，你可以說「你去看看我的個人主頁就知道了」，
並附上連結標籤 <send_link type="profile"></send_link>，系統會自動生成你的個人頁連結。
```

### 涉及檔案
- `frontend/profile_page.py` — 新建
- `backend/tools/profile_generator.py` — 新建
- `backend/main.py` — 新增 `/profile` endpoint
- `backend/llm_client.py` — SYSTEM_PROMPT 增加引導語

### 驗收條件
- [ ] 個人主頁可正常顯示
- [ ] 歷史獲利記錄至少 5 天
- [ ] 學員見證內容看起來可信
- [ ] 對話中可自然引導受害者瀏覽

---

## 實作順序建議

```
H1 受害者標籤 ──→ H2 情緒感知 ──→ H3 主動催促
      │                                  │
      └──── M2 假帳號 ──── M1 多媒體 ──── M3 朋友圈
```

| 順序 | 功能 | 預估複雜度 | 依賴 |
|------|------|-----------|------|
| 1 | H1 受害者畫像標籤 | 低 | 無 |
| 2 | H2 情緒感知 | 低 | H1（共用 thought parse 機制） |
| 3 | M2 動態帳戶資訊 | 低 | 無 |
| 4 | H3 主動催促排程 | 中 | 前端需改 polling |
| 5 | M1 多媒體武器庫 | 中 | 需準備底圖素材 |
| 6 | M3 朋友圈模擬 | 高 | M1（需獲利圖批量生成） |
