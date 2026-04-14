import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
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
    
    # 這次我們改用字典清單來儲存詳細資訊： [{"title": "標題", "content": "內文", "link": "網址"}]
    activities = {"校內活動": [], "校友會活動": []}
    
    for section_name in ["校內活動", "校友會活動"]:
        # 1. 先找到包含該分類名稱的大標題 (例如找到 <h2>校內活動</h2>)
        # Webnode 的標題可能包在 h2, h3, div 等標籤中，我們找純文字符合的
        header = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'div', 'span'] and tag.get_text(strip=True) == section_name)
        
        if not header:
            continue
            
        # 2. 找到這個標題所屬的父層區塊，Webnode 通常將整個列表放在一個 section 或大 div 裡
        # 這裡我們往上找父層，通常會是 section 或一個有特定 class 的 div
        # 為了安全起見，我們往下尋找緊接著的列表區塊
        parent_section = header.find_parent('section') or header.find_parent('div', class_=lambda c: c and 'section' in c.lower())
        
        # 如果找不到明確的 section，我們就在 header 之後尋找所有的活動項目
        # Webnode 的活動項目通常會被包裝在特定的 class 裡，例如 'item', 'list-item', 或是有特定結構的 div/li
        # 觀察您的網站結構，活動通常包含一個標題 (h3/h4/strong) 加上一段內文 (p/span/div)
        
        # 這裡提供一個較通用的抓取方式：尋找包含標題特徵的容器
        # 我們假設在分類標題之後出現的 h3 或 strong 標籤就是活動標題
        
        search_area = parent_section if parent_section else soup # 若找不到專屬區塊就找全域，但要過濾
        
        # 我們從找到的 header 開始往下找
        next_elements = header.find_all_next()
        
        for elem in next_elements:
            # 如果碰到了下一個大分類標題，就停止尋找這個分類的活動
            elem_text = elem.get_text(strip=True)
            if elem.name in ['h1', 'h2'] and elem_text in ["校內活動", "校友會活動", "聯絡我們", "最新消息"]:
                if elem_text != section_name: # 避免一開始就停住
                    break

            # 假設活動標題使用了 h3, h4 或 strong，且有被 <a> 標籤包住 (如果有連結的話)
            if elem.name in ['h3', 'h4', 'strong']:
                title_text = elem.get_text(strip=True)
                
                # 過濾掉太長或太短的無效標題，以及純日期
                import re
                if not title_text or len(title_text) > 30 or re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', title_text):
                    continue
                    
                # 檢查是否已經抓過這個標題 (避免同一活動重複抓取)
                if any(act['title'] == title_text for act in activities[section_name]):
                    continue

                item_data = {"title": title_text, "content": "", "link": ""}

                # 找連結：先看自己身上有沒有 <a>，沒有的話往外找父層有沒有 <a>
                a_tag = elem.find('a') or elem.find_parent('a')
                if a_tag and a_tag.has_attr('href'):
                    # 處理相對路徑，確保是完整網址
                    item_data["link"] = urllib.parse.urljoin(URL, a_tag['href'])

                # 找內文：通常內文會緊接在標題之後的 <p> 或 <div> 裡
                # 我們抓取標題下一個相鄰文字區塊當作內文
                next_node = elem.find_next_sibling()
                
                # 有時候內文跟標題被包在同一個容器裡，我們要往外找再往下找
                if not next_node:
                    parent = elem.find_parent()
                    if parent:
                         next_node = parent.find_next_sibling()

                if next_node:
                    content_text = next_node.get_text(strip=True)
                    # 簡單過濾：內文通常比較長，且不能是日期
                    if content_text and len(content_text) > 5 and not re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', content_text):
                         item_data["content"] = content_text

                activities[section_name].append(item_data)

    return activities

# ... 前面的 fetch_activities 等函數保持不變 ...

def send_line_message(messages):
    if not LINE_TOKEN or not LINE_USER_ID:
        print("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID")
        return

    line_bot_api = LineBotApi(LINE_TOKEN)
    
    # 稍微調整開頭的視覺呈現
    text = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═" * 15 + "\n"
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
                # ====== 視覺優化區塊 ======
                
                # 1. 分類標籤 (加入表情符號點綴)
                icon = "🏫" if category == "校內活動" else "🤝"
                msg_block = f"{icon} [{category}]\n"
                
                # 2. 標題：為了達到「粗體/顯眼」的效果，我們加上特殊符號包覆
                msg_block += f"🌟 {item['title']} 🌟"
                
                # 3. 內文：直接換行接在標題下方，去除「內文：」字樣
                if item['content']:
                    msg_block += f"\n{item['content']}"
                    
                # 4. 連結：為了引導點擊，加上小箭頭
                if item['link']:
                    msg_block += f"\n👉 {item['link']}"
                    
                # ==========================
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
