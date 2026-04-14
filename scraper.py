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
    response = requests.get(URL)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    activities = {"校內活動": [], "校友會活動": []}
    
    # 策略更新：抓取網頁由上到下所有可能是標題的標籤
    # Webnode 的活動標題通常使用 h3, h4 或是粗體 (strong, b)
    tags = soup.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
    
    current_section = None
    
    for tag in tags:
        text = tag.get_text(strip=True)
        
        # 過濾掉空白內容
        if not text:
            continue
            
        # 判斷是否進入目標大區塊
        if "校內活動" in text:
            current_section = "校內活動"
            continue
        elif "校友會活動" in text:
            current_section = "校友會活動"
            continue
        # 如果遇到頁底或其他的標題，就停止目前區塊的抓取
        elif current_section and ("聯絡我們" in text or "最新消息" in text or "校友專區" in text):
            current_section = None
            
        # 如果程式正在「校內活動」或「校友會活動」的區塊內掃描
        if current_section:
            # 過濾條件：
            # 1. 字數太長通常是內文說明，不是標題 (設定小於25字)
            # 2. 排除純日期的文字
            # 3. 避免重複加入
            is_date = re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', text)
            if len(text) < 25 and not is_date and text not in activities[current_section]:
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
    print("目前抓取到的活動：", current_activities)  # 印出抓取結果方便除錯
    
    previous_activities = load_previous_state()
    
    new_messages = []
    
    for category in ["校內活動", "校友會活動"]:
        current_list = current_activities.get(category, [])
        previous_list = previous_activities.get(category, [])
        
        # 比對新活動
        new_items = [item for item in current_list if item not in previous_list]
        
        if new_items:
            new_messages.append(f"📌 {category}:")
            for item in new_items:
                new_messages.append(f" - {item}")
            new_messages.append("") # 空行
            
    if new_messages:
        print("💡 發現新活動，準備發送 LINE 訊息...")
        send_line_message(new_messages)
        save_current_state(current_activities)
    else:
        print("😴 目前沒有新的活動。")
        if not os.path.exists(STATE_FILE):
             save_current_state(current_activities)

if __name__ == "__main__":
    main()
