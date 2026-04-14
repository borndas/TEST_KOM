import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(URL, headers=headers)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    activities = {"校內活動": [], "校友會活動": []}
    
    for section_name in ["校內活動", "校友會活動"]:
        header = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'div', 'span'] and tag.get_text(strip=True) == section_name)
        
        if not header:
            continue
            
        next_elements = header.find_all_next()
        
        for elem in next_elements:
            elem_text = elem.get_text(strip=True)
            # 如果碰到下一個大分類，就停止尋找
            if elem.name in ['h1', 'h2'] and elem_text in ["校內活動", "校友會活動", "聯絡我們", "最新消息"]:
                if elem_text != section_name:
                    break

            if elem.name in ['h3', 'h4', 'strong']:
                title_text = elem.get_text(strip=True)
                
                # 過濾無效標題與純日期
                if not title_text or len(title_text) > 30 or re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', title_text):
                    continue
                    
                if any(act['title'] == title_text for act in activities[section_name]):
                    continue

                item_data = {"title": title_text, "content": "", "link": ""}

                # 找連結
                a_tag = elem.find('a') or elem.find_parent('a')
                if a_tag and a_tag.has_attr('href'):
                    item_data["link"] = urllib.parse.urljoin(URL, a_tag['href'])

                # 找內文
                next_node = elem.find_next_sibling()
                if not next_node:
                    parent = elem.find_parent()
                    if parent:
                         next_node = parent.find_next_sibling()

                if next_node:
                    content_text = next_node.get_text(strip=True)
                    if content_text and len(content_text) > 5 and not re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', content_text):
                         item_data["content"] = content_text

                activities[section_name].append(item_data)

    return activities

def load_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"校內活動": [], "校友會活動": []}

def save_current_state(state):
    # 只存標題，避免內文微調導致重複發送通知
    simplified_state = {
        "校內活動": [item["title"] for item in state["校內活動"]],
        "校友會活動": [item["title"] for item in state["校友會活動"]]
    }
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(simplified_state, f, ensure_ascii=False, indent=4)

def send_line_message(messages):
    if not LINE_TOKEN or not LINE_USER_ID:
        print("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID")
        return

    line_bot_api = LineBotApi(LINE_TOKEN)
    
    text = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═" * 15 + "\n\n"
    text += "\n\n".join(messages)
    
    try:
        line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=text))
        print("✅ 訊息傳送成功！")
    except Exception as e:
        print(f"❌ 訊息傳送失敗: {e}")

def main():
    print("🔍 開始抓取網頁...")
    current_activities = fetch_activities()
    print(f"目前抓取到的活動：\n{json.dumps(current_activities, ensure_ascii=False, indent=2)}")
    
    previous_state_titles = load_previous_state()
    
    new_messages = []
    
    for category in ["校內活動", "校友會活動"]:
        current_list = current_activities.get(category, [])
        previous_titles = previous_state_titles.get(category, [])
        
        for item in current_list:
            if item["title"] not in previous_titles:
                # 視覺優化排版
                icon = "🏫" if category == "校內活動" else "🤝"
                msg_block = f"{icon} [{category}]\n"
                msg_block += f"🌟 {item['title']} 🌟" # 星星夾擊產生大標題效果
                
                if item['content']:
                    msg_block += f"\n{item['content']}" # 直接接內文，無前綴字
                if item['link']:
                    msg_block += f"\n👉 {item['link']}"  # 加上手指 Emoji 提示連結
                    
                new_messages.append(msg_block)
            
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
