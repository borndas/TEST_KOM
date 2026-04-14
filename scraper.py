import requests
from bs4 import BeautifulSoup
import json
import os
import re
from linebot import LineBotApi
from linebot.models import TextSendMessage

# 設定參數
URL = "https://huagangkongshoudaoshexiaoyouhuiwangzhanjiagoufanli.webnode.tw/"
STATE_FILE = "state.json"

# 從環境變數讀取 LINE Bot 憑證
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

def fetch_activities():
    # 加上 headers 模擬真實瀏覽器，避免被阻擋
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(URL, headers=headers)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    activities = {"校內活動": [], "校友會活動": []}
    current_section = None
    
    # 使用 stripped_strings：它會依序抽出網頁上所有肉眼可見的文字，無視 HTML 標籤！
    for text in soup.stripped_strings:
        # 清理字串
        text = text.strip()
        
        # 1. 判斷是否進入目標大區塊 (精確比對)
        if text == "校內活動":
            current_section = "校內活動"
            continue
        elif text == "校友會活動":
            current_section = "校友會活動"
            continue
        # 遇到其他區塊標題就停止收集
        elif current_section and text in ["聯絡我們", "最新消息", "校友專區", "更多", "聯誼傳承"]:
            current_section = None
            
        # 2. 如果正在目標區塊內，開始收集活動標題
        if current_section:
            # 過濾條件：
            # - 排除純日期 (例如 2025/02/26, 2024/09/09~)
            # - 排除太長的內文說明 (設定小於 20 個字)
            # - 排除太短的無意義符號
            is_pure_date = re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}([/.-]?[0-9]{1,2})?(~)?.*$', text)
            
            if 2 < len(text) < 20 and not is_pure_date:
                # 排除一些常見的非標題雜訊
                ignore_words = ["說明", "地點", "時間", "特別感謝"]
                if not any(word in text for word in ignore_words):
                    # 避免重複加入
                    if text not in activities[current_section]:
                        activities[current_section].append(text)
                        
    return activities

def load_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"校內活動": [], "校友會活動": []}

def save_current_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def send_line_message(messages):
    if not LINE_TOKEN or not LINE_USER_ID:
        print("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID")
        return

    line_bot_api = LineBotApi(LINE_TOKEN)
    
    text = "【華岡空手道校友會 - 新活動通知】\n\n" + "\n".join(messages)
    try:
        line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=text))
        print("✅ 訊息傳送成功！")
    except Exception as e:
        print(f"❌ 訊息傳送失敗: {e}")

def main():
    print("🔍 開始抓取網頁...")
    current_activities = fetch_activities()
    print(f"目前抓取到的活動：\n{json.dumps(current_activities, ensure_ascii=False, indent=2)}")
    
    previous_activities = load_previous_state()
    
    new_messages = []
    
    for category in ["校內活動", "校友會活動"]:
        current_list = current_activities.get(category, [])
        previous_list = previous_activities.get(category, [])
        
        new_items = [item for item in current_list if item not in previous_list]
        
        if new_items:
            new_messages.append(f"📌 {category}:")
            for item in new_items:
                new_messages.append(f" - {item}")
            new_messages.append("") 
            
    if new_messages:
        print("💡 發現新活動，準備發送 LINE 訊息...")
        send_line_message(new_messages)
        save_current_state(current_activities)
    else:
        print("😴 目前沒有新的活動。")
        # 如果是第一次執行，即使沒新活動也要存檔，建立初始基準點
        if not os.path.exists(STATE_FILE) and (current_activities["校內活動"] or current_activities["校友會活動"]):
             save_current_state(current_activities)

if __name__ == "__main__":
    main()
