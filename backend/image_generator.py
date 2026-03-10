import urllib.request
import json
import random
import os
import fal_client
from datetime import datetime

# 請把你在 fal.ai 申請到的 API Key 填寫在這裡，或者透過環境變數傳入
os.environ["FAL_KEY"] = os.getenv("FAL_KEY", "03193660-9255-47e6-b250-fb55ac9f22dd:489731d657ec92c7ffce765c124d961f")

def fetch_stock_data():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        valid_stocks = []
        for s in data:
            try:
                name = s.get('Name', '').strip()
                close = float(s.get('ClosingPrice', 0))
                open_p = float(s.get('OpeningPrice', 0))
                
                # TWSE 'Change' is just a positive number, the direction is usually indicated but Open API doesn't have it clearly sometimes.
                # Let's calculate from (Close - Open) / Open. 
                # Note: this is intraday change based on Open, which is roughly OK for demonstration.
                if open_p > 0:
                    pct = (close - open_p) / open_p * 100
                    valid_stocks.append({
                        'name': name,
                        'code': s.get('Code', ''),
                        'pct': pct,
                        'close': close
                    })
            except Exception:
                continue
                
        # Sort by percentage
        valid_stocks.sort(key=lambda x: x['pct'], reverse=True)
        return valid_stocks
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return []

def generate_profit_image():
    stocks = fetch_stock_data()
    if not stocks:
        # Fallback dummy data if API fails
        gainers = [{'name': '台積電', 'pct': 2.5}, {'name': '聯發科', 'pct': 4.1}, {'name': '鴻海', 'pct': 1.8}]
        losers = [{'name': '長榮', 'pct': -1.2}]
    else:
        # Top 10 gainers
        top_10 = stocks[:10]
        # Bottom 10 (losers)
        bottom_10 = stocks[-10:]
        
        # Pick 3-5 gainers randomly
        num_gainers = random.randint(3, 5)
        gainers = random.sample(top_10, min(num_gainers, len(top_10)))
        
        # Pick 1-2 losers
        num_losers = random.randint(1, 2)
        losers = random.sample(bottom_10, min(num_losers, len(bottom_10)))

    # Combine and shuffle
    selected = gainers + losers
    random.shuffle(selected)
    
    base_image_path = os.path.join(os.path.dirname(__file__), "assets", "basic-picture.png")
    
    prompt_lines = [
        "A photorealistic mobile phone screenshot of a Taiwan stock trading app.",
        "The layout, colors, and styling MUST strictly follow the provided reference image.",
        "Do not change the structure of the app, just fill in the following stock data perfectly:",
    ]
    
    for s in selected[:4]:
        sign = "+" if s['pct'] > 0 else ""
        prompt_lines.append(f"- 【{s['name']}】: {sign}{s['pct']:.2f}%")
        
    prompt_lines.append("Ensure the typography is flawless. The traditional Chinese characters for the stock names must be accurate. Use red colors for positive (+) changes.")
    prompt = "\n".join(prompt_lines)
    
    try:
        print("Uploading base image to Fal.ai...")
        with open(base_image_path, "rb") as f:
            import base64
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            fal_url = f"data:image/png;base64,{img_b64}"
            
        print("Calling Flux Image-to-Image API...")
        # Use Flux dev image-to-image for good text rendering
        result = fal_client.subscribe(
            "fal-ai/flux/dev/image-to-image",
            arguments={
                "image_url": fal_url,
                "prompt": prompt,
                "strength": 0.85, # Preserve layout but allow changing text
                "guidance_scale": 7.5
            }
        )
        
        image_url = result['images'][0]['url']
        
        # Download the generated image back to local
        output_path = os.path.join(os.path.dirname(__file__), "assets", "generated-picture.png")
        req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
                
        return output_path
        
    except Exception as e:
        print(f"Error during Fal API generation: {e}")
        # Return base image as fallback if API fails
        return base_image_path

if __name__ == "__main__":
    path = generate_profit_image()
    print(f"Generated at: {path}")
