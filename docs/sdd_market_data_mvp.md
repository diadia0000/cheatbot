# MVP SDD: Real-time Market Data & Image Gen Integration (阿凱老師真實金融與出圖升級)

## 1. 簡介 (Introduction)

為增強「阿凱老師」人設的真實感與說服力，MVP 階段將全面棄用原本不穩定的 TWSE Open API，改採 `yfinance` 套件。
我們會用它來找出當天「最高且最有價值」的股票作為報明牌的依據。同時，阿凱老師出圖時，將嚴格基於警方提供的底圖 (`backend/assets/basic-picture.png`)，並將抓取到的真實驗證獲利數據，透過 Fal.ai 結合底圖進行重繪生成。

## 2. 系統架構設計 (Architecture Design)

- **外部依賴**:
  - 核心數據：使用輕量且穩定的 `yfinance` 取代 `https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`。
  - 圖片生成：Fal.ai API (Flux Image-to-Image)。
- **核心流程**:
  1. 鎖定台灣最有價值（權值股/0050成分股）的數十檔指標股票作為觀察池。
  2. 透過 `yfinance` 一次性拉取觀察池的當日報價，並排序找出「當日漲幅最高」的股票作為阿凱老師的「明牌」。
  3. 將此明牌資訊注入 LLM Prompt 中，讓阿凱老師在對話中能自然提及。
  4. 當觸發圖片生成時，讀取 `backend/assets/basic-picture.png`，將明牌股票資訊寫入 Image-to-Image 的 prompt，透過 Fal.ai 生成。

## 3. 功能規格 (Functional Specification)

### 3.1 股價篩選模組 (`backend/tools/market_data.py`)

- **功能**: 維護一個高價值台股清單，使用 `yfinance` 獲取這些股票的報價，即時更新數據。
- **輸出**: 排序後的字典，挑出漲幅（或價值）最高的股票。
- **使用時機**:
  - 對話時：若使用者問到要買什麼，或者阿凱到了「展示實力」階段，主動提供漲最多的股票資訊。
  - 出圖時：作為圖片生成假數據的來源。

### 3.2 圖片生成重構 (`backend/image_generator.py`)

- **刪除舊代碼**: 徹底移除 `urllib.request` 呼叫 TWSE Open API 的邏輯。
- **匯入新數據源**: 呼叫 `backend.tools.market_data` 獲取當日強勢股。
- **Fal.ai 整合**:
  - 確保讀取底圖 `backend/assets/basic-picture.png` 並轉為 base64 URL。
  - 在 Fal prompt 中清楚描述：將底圖中的股票名稱與獲利數字，替換為從 `yfinance` 抓取到的強勢股與自訂的高額獲利趴數（例如把漲幅誇大，符合詐騙集團人設）。

## 4. 實作步驟 (Implementation Steps)

### Step 1: 安裝套件

- 確保安裝或更新 `yfinance` (`pip install yfinance`)。
- 確保所有安裝套件都加入到`requirements.txt`內

### Step 2: 實作 `market_data.py`

- 建立一個 `get_top_stocks()` 函式。
- 定義 Ticker 清單，使用 `yf.Tickers("2330.TW 2317.TW 2454.TW ...").tickers` 批次獲取。
- 計算每檔股票的 `(currentPrice - previousClose) / previousClose`，並進行排序。

### Step 3: 更新 `image_generator.py`

- 移除 `fetch_stock_data` 中對 TWSE 的依賴。
- 引入 Step 2 的 `get_top_stocks()`。
- 將拿到的最強股票放入 prompt_lines 裡面，並呼叫 Fal API 結合 `basic-picture.png` 執行 Image-to-Image。

### Step 4: 整合至 `llm_client.py`

- 若對話進展到需要展示實力，將抓到的「明牌股票」名稱直接放進系統提示，讓 LLM 說出：「今天我都帶會員做這檔 XXX，賺翻了」。
