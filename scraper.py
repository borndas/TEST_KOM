import requests
from bs4 import BeautifulSoup
import json
import os
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
    
    # 由於 Webnode 網頁結構可能會變動，這裡採用尋找標題關鍵字的方式
    # 尋找包含「校內活動」與「校友會活動」的區塊
    # 註：這裡的選擇器 (h2, h3, li 等) 可能需要根據網頁實際的 HTML 結構進行微調
    for section_name in activities.keys():
        # 找尋標題標籤 (假設是 h2 或 h3)
        header = soup.find(lambda tag: tag.name in ['h2', 'h3', 'h4'] and section_name in tag.text)
        if header:
            # 尋找標題底下的活動列表或區塊
            # 假設活動是放在緊接在標題後面的容器內
            parent_container = header.find_parent('div')
            if parent_container:
                # 假設活動標題使用了特定的粗體或標題標籤，這裡以抓取所有文字區塊為例
                # 實務上請使用開發者工具 (F12) 確認確切的 class name，例如 'b-text' 或 'item-title'
                items = parent_container.find_all(['h3', 'h4', 'strong']) 
                for item in items:
                    title = item.text.strip()
                    if title and title not in activities[section_name] and title != section_name:
                        activities[section_name].append(title)
                        
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
        print("未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID")
        return

    line_bot_api = LineBotApi(LINE_TOKEN)
    
    # 將訊息合併發送
    text = "【華岡空手道校友會 - 新活動通知】\n\n" + "\n".join(messages)
    try:
        line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=text))
        print("訊息傳送成功！")
    except Exception as e:
        print(f"訊息傳送失敗: {e}")

def main():
    print("開始抓取網頁...")
    current_activities = fetch_activities()
    previous_activities = load_previous_state()
    
    new_messages = []
    
    for category in ["校內活動", "校友會活動"]:
        current_list = current_activities.get(category, [])
        previous_list = previous_activities.get(category, [])
        
        # 找出新的活動標題
        new_items = [item for item in current_list if item not in previous_list]
        
        if new_items:
            new_messages.append(f"📌 {category}:")
            for item in new_items:
                new_messages.append(f" - {item}")
            new_messages.append("") # 空行分隔
            
    if new_messages:
        print("發現新活動，準備發送 LINE 訊息...")
        send_line_message(new_messages)
        # 更新狀態檔
        save_current_state(current_activities)
    else:
        print("目前沒有新的活動。")
        # 第一次執行時建立狀態檔
        if not os.path.exists(STATE_FILE):
             save_current_state(current_activities)

if __name__ == "__main__":
    main()
