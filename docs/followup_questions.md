# Follow-up Questions（實作前最後確認）

## 1. 階段判斷機制怎麼實作？

你說 Stage 2 之後才注入股票資訊、才觸發出圖。但目前程式端**沒有可靠的階段追蹤**：

- `session_state.fraud_stage` 每次都寫死 `"ongoing"`，沒有真正追蹤
- LLM 的 `<thought>` 裡有寫「階段2」之類的字眼，但需要 parse

**你想用哪種方式判斷階段？**

- **A**: Parse LLM `<thought>` 的內容（用 regex 抓「階段X」），每次回覆後更新 `fraud_stage`
- **B**: 用對話輪數（conversation turn count）做粗略判斷（例如 ≥4 輪 = 階段 2）
- **C**: 兩者結合（輪數為基底，`<thought>`為輔助更新）

回答：
C: 兩者結合（輪數為基底，`<thought>`為輔助更新）

## 2. yfinance 無法「掃描全台股」

yfinance 需要你給定 ticker list 才能查，它沒有「列出今天台股漲幅前 10」的 API。要拿到全市場漲幅排名，有幾個做法：

- **A**: 預定義一個 100~200 檔的廣泛 ticker list（涵蓋大中小型股），每次全部查詢後排序取前 10
- **B**: 用其他資料源（例如爬 Yahoo 奇摩股市排行榜網頁）取得當日漲幅排行，再用 yfinance 補細節
- **C**: 你有其他偏好的方式？

這會影響 `market_data.py` 的實作方式，需要你確認。

回答：
使用FinMind：台灣開源的金融數據 API，直接 pip install FinMind 就能用，涵蓋台股大量的盤後數據。

## 3. 「報明牌」和「出圖」分別在什麼時機？

你的回答提到：

- Stage 2 才開始出圖 + 注入股票資訊
- 「開始報明牌也需要爬股票來生成即時資料」

我的理解是：

- **Stage 2（展示實力）**：發獲利截圖（`<send_image>`）+ system prompt 裡附上股票資訊讓阿凱自然提及「今天又賺了」
- **Stage 3-4（試探/施壓）**：開始具體報明牌（「你跟著我買 XXX」），此時也需要即時股票資料

**這個理解正確嗎？（Y/N，或補充說明）**
回答：
理解差不多正確，但不需要施壓

## 4. Fal.ai 生成圖片的期望效果

看了底圖 `basic-picture.png`（股市隱者 APP 畫面），Fal.ai image-to-image 的 `strength` 參數會決定重繪程度：

- **strength 高**（0.8+）：會大幅改變圖片，可能失去原本 APP 的版面
- **strength 低**（0.3~0.5）：保留版面但文字可能改不動

Fal.ai 的 image-to-image **很難精確控制中文字的渲染**（它經常渲染出亂碼或錯字）。你對生成圖片的品質預期是？

- **A**: 只要「看起來像股票 APP 截圖」就好，文字不需要 100% 正確
- **B**: 股票名稱和數字必須清楚可讀（這幾乎做不到，建議改用 Pillow）

回答：
A: 只要「看起來像股票 APP 截圖」就好，文字不需要 100% 正確，有個70~80%准即可

## 5. FAL_KEY 處理方式

目前 `image_generator.py` 第 10 行有一組明文 FAL_KEY。我打算：

- 移到 `docker-compose.yml` 的環境變數
- 程式碼改為 `os.getenv("FAL_KEY")`
- 從程式碼中移除明文 key

**直接移除 OK 嗎？還是你希望保留一個 fallback default value？**

回答：直接移除
