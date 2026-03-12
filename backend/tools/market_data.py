"""
股價篩選模組：使用 FinMind 取得台股每日行情，篩選漲幅最高的股票。
結果會快取 30 分鐘以避免頻繁呼叫 API。
"""

import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

from FinMind.data import DataLoader

# ── 快取機制 ──────────────────────────────────────────────
_cache_lock = threading.Lock()
_cached_stocks: List[Dict] = []
_cached_stock_names: Dict[str, str] = {}
_cache_timestamp: float = 0
CACHE_TTL = 1800  # 30 分鐘

# ── 觀察池：涵蓋大、中、小型股的代表性台股 ─────────────────
STOCK_POOL = [
    # 半導體
    "2330", "2454", "2303", "3034", "2379", "3711", "6770", "3529", "2408", "5274",
    "3443", "6488", "3661", "8150", "2436", "6415", "3035", "4966", "2449", "6679",
    # 電子代工 / 零組件
    "2317", "2382", "3231", "2345", "2353", "2356", "2395", "3037", "3036", "6269",
    "2327", "3533", "8046", "3665", "2352", "5425", "3044", "2301", "6409", "3023",
    # 金融
    "2881", "2882", "2891", "2886", "2884", "2885", "2880", "2883", "2887", "2890",
    "5880", "2892", "2888", "2889", "2838", "2801", "2834", "5876", "2816", "2812",
    # 傳產 / 塑化 / 鋼鐵
    "1301", "1303", "1326", "1101", "1102", "2002", "1216", "1402", "9910", "1476",
    "2015", "1513", "1504", "2014", "1440", "9917", "5522", "2542", "1477", "2201",
    # 航運 / 觀光
    "2603", "2609", "2615", "2610", "2618", "2606", "5765", "2634", "2633", "2636",
    # 生技醫療
    "6446", "4743", "1707", "4142", "4147", "6472", "1760", "4174", "6547", "4119",
    # 通訊 / 網路
    "2412", "3045", "4904", "2498", "6285", "3005", "2439", "4977", "6214", "3704",
    # 電機 / 機械
    "2308", "1503", "2049", "1590", "4523", "2376", "3026", "6257", "2404", "8114",
    # 綠能 / 儲能
    "3576", "6244", "3691", "6443", "3708", "6464", "3698", "6674", "3548", "6509",
    # 中小型飆股潛力股
    "3615", "6552", "3293", "4971", "6139", "8271", "5269", "3105", "6153", "3029",
    "2114", "3703", "6024", "8044", "6116", "3017", "6104", "4162", "5388", "2478",
]


def _fetch_one_stock(stock_id: str, date_str: str) -> Optional[Dict]:
    """取得單一股票的當日行情"""
    try:
        dl = DataLoader()
        df = dl.taiwan_stock_daily(stock_id=stock_id, start_date=date_str, end_date=date_str)
        if len(df) > 0:
            return df.iloc[-1].to_dict()
    except Exception:
        pass
    return None


def _load_stock_names() -> Dict[str, str]:
    """從 FinMind 載入 stock_id → stock_name 對照表"""
    global _cached_stock_names
    if _cached_stock_names:
        return _cached_stock_names
    try:
        dl = DataLoader()
        info = dl.taiwan_stock_info()
        _cached_stock_names = dict(zip(info["stock_id"], info["stock_name"]))
    except Exception as e:
        print(f"[market_data] 載入股票名稱失敗: {e}")
    return _cached_stock_names


def _refresh_cache() -> List[Dict]:
    """從 FinMind 批量抓取觀察池股票的當日報價"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    names = _load_stock_names()

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(_fetch_one_stock, sid, today): sid
            for sid in STOCK_POOL
        }
        results = []
        for future in futures:
            row = future.result()
            if row and row.get("close") and row.get("close") > 0:
                sid = row["stock_id"]
                spread = row.get("spread", 0)
                close = row["close"]
                prev_close = close - spread
                if prev_close > 0:
                    pct = (spread / prev_close) * 100
                else:
                    pct = 0.0
                results.append({
                    "stock_id": sid,
                    "name": names.get(sid, sid),
                    "close": close,
                    "spread": spread,
                    "pct_change": round(pct, 2),
                })

    # 按漲幅排序
    results.sort(key=lambda x: x["pct_change"], reverse=True)
    return results


def get_top_stocks(n: int = 10) -> List[Dict]:
    """
    取得當日漲幅最高的 n 檔股票。
    回傳 list of dict: [{"stock_id", "name", "close", "spread", "pct_change"}, ...]
    """
    global _cached_stocks, _cache_timestamp

    with _cache_lock:
        now = time.time()
        if _cached_stocks and (now - _cache_timestamp) < CACHE_TTL:
            return _cached_stocks[:n]

    # 快取過期或首次呼叫，重新拉取
    stocks = _refresh_cache()

    with _cache_lock:
        _cached_stocks = stocks
        _cache_timestamp = time.time()

    return stocks[:n]


def get_stock_prompt_injection() -> str:
    """
    生成要注入 LLM system prompt 的股票資訊字串。
    讓阿凱老師能自然提及當天的「明牌」。
    """
    top = get_top_stocks(n=5)
    if not top:
        return ""

    lines = ["【今日台股即時資訊（供你自然融入對話使用）】"]
    for s in top:
        sign = "+" if s["pct_change"] > 0 else ""
        lines.append(f"- {s['name']}({s['stock_id']}) 收盤 {s['close']}，漲幅 {sign}{s['pct_change']}%")
    lines.append("你可以在對話中不經意地提到這些股票來展現你的實力，但不要一次列出全部，自然提一兩檔就好。")
    return "\n".join(lines)
