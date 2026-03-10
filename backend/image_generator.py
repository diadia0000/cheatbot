import os
import base64
import random
import requests
from datetime import datetime

import fal_client

from tools.market_data import get_stocks_for_image


def generate_profit_image(session_id: str = "default") -> str:
    """
    基於 basic-picture.png 底圖，透過 Fal.ai Image-to-Image 生成獲利截圖。
    每個 session 會產生獨立的圖片檔案，避免多 session 互相覆蓋。
    """
    stocks = get_stocks_for_image(n=7)

    if not stocks:
        # Fallback dummy data
        stocks = [
            {"name": "台積電", "stock_id": "2330", "pct_change": 3.52},
            {"name": "聯發科", "stock_id": "2454", "pct_change": 4.18},
            {"name": "鴻海", "stock_id": "2317", "pct_change": 2.05},
            {"name": "台達電", "stock_id": "2308", "pct_change": 1.87},
            {"name": "富邦金", "stock_id": "2881", "pct_change": 1.45},
            {"name": "長榮", "stock_id": "2603", "pct_change": -1.23},
            {"name": "中鋼", "stock_id": "2002", "pct_change": 2.90},
        ]

    base_image_path = os.path.join(os.path.dirname(__file__), "assets", "basic-picture.png")
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 組合 Fal.ai prompt
    prompt_lines = [
        "A photorealistic mobile phone screenshot of a Taiwan stock trading profit report app called 股市隱者.",
        "The layout, dark blue color scheme, and styling MUST strictly follow the provided reference image.",
        f"Today's date: {today_str}",
        "The app shows a list of stock performance entries. Each row has: stock name, percentage change (漲跌幅), profit momentum (獲利動能%), and a score badge.",
        "Fill in the following stock data into the rows:",
    ]

    for s in stocks:
        sign = "+" if s["pct_change"] > 0 else ""
        color = "red/positive" if s["pct_change"] > 0 else "green/negative"
        prompt_lines.append(f"- {s['name']}: {sign}{s['pct_change']:.2f}% ({color})")

    prompt_lines.append(
        "Use red colored bars for positive changes and green colored bars for negative changes. "
        "Keep the overall dark navy blue theme. Traditional Chinese text must be present."
    )
    prompt = "\n".join(prompt_lines)

    try:
        print(f"[image_gen] session={session_id} 上傳底圖到 Fal.ai...")
        with open(base_image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            fal_url = f"data:image/png;base64,{img_b64}"

        print(f"[image_gen] 呼叫 Flux Image-to-Image API...")
        result = fal_client.subscribe(
            "fal-ai/flux/dev/image-to-image",
            arguments={
                "image_url": fal_url,
                "prompt": prompt,
                "strength": 0.75,
                "guidance_scale": 7.5,
            },
        )

        image_url = result["images"][0]["url"]

        # 下載生成的圖片，以 session_id 命名避免覆蓋
        output_filename = f"generated-{session_id}.png"
        output_path = os.path.join(os.path.dirname(__file__), "assets", output_filename)

        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)

        print(f"[image_gen] 圖片已儲存: {output_path}")
        return output_path

    except Exception as e:
        print(f"[image_gen] Fal API 錯誤: {e}")
        return base_image_path


if __name__ == "__main__":
    path = generate_profit_image(session_id="test")
    print(f"Generated at: {path}")
