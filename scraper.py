import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
import re
from linebot import LineBotApi
from linebot.models import TextSendMessage

# ==========================================
# 1. 基本設定與環境變數
# ==========================================
URL = "https://huagangkongshoudaoshexiaoyouhuiwangzhanjiagoufanli.webnode.tw/"
STATE_FILE = "state.json"

# 從 GitHub Secrets 讀取 LINE 憑證
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
# 發送目標：如果您想發到群組，請在 GitHub Secrets 設定 LINE_GROUP_ID
# (如果在 Secrets 找不到 LINE_GROUP_ID，為了相容舊版，會退而尋找 LINE_USER_ID)
LINE_TARGET_ID = os.environ.get("LINE_GROUP_ID") or os.environ.get("LINE_USER_ID")


# ==========================================
# 2. 爬蟲核心邏輯 (抓取標題、內文、連結)
# ==========================================
def fetch_activities():
    # 加入 Headers 模擬瀏覽器，降低被阻擋的機率
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 網頁抓取失敗: {e}")
        return {"校內活動": [], "校友會活動": []}
    
    activities = {"校內活動": [], "校友會活動": []}
    
    for section_name in ["校內活動", "校友會活動"]:
        # 尋找該區塊的大標題 (如 "校內活動")
        header = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'div', 'span'] and tag.get_text(strip=True) == section_name)
        
        if not header:
            continue
            
        next_elements = header.find_all_next()
        
        for elem in next_elements:
            elem_text = elem.get_text(strip=True)
            
            # 停止條件：如果掃到下一個大區塊的標題，就停止尋找
            if elem.name in ['h1', 'h2'] and elem_text in ["校內活動", "校友會活動", "聯絡我們", "最新消息"]:
                if elem_text != section_name:
                    break

            # 如果標籤是 h3, h4 或 strong，我們將其視為「活動標題」
            if elem.name in ['h3', 'h4', 'strong']:
                title_text = elem.get_text(strip=True)
                
                # [過濾] 排除空字串、太長的無效標題、或是純日期格式
                if not title_text or len(title_text) > 30 or re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', title_text):
                    continue
                    
                # [過濾] 避免同一個活動區塊內抓到重複的標題
                if any(act['title'] == title_text for act in activities[section_name]):
                    continue

                # 準備要儲存的活動資料結構
                item_data = {"title": title_text, "content": "", "link": ""}

                # (1) 找連結：尋找標題本身或其父層是否有 <a> 標籤
                a_tag = elem.find('a') or elem.find_parent('a')
                if a_tag and a_tag.has_attr('href'):
                    item_data["link"] = urllib.parse.urljoin(URL, a_tag['href'])

                # (2) 找內文：尋找標題後方相鄰的元素
                next_node = elem.find_next_sibling()
                
                # 如果沒有直接相鄰，就往上一層找其相鄰元素 (處理特定 HTML 結構)
                if not next_node:
                    parent = elem.find_parent()
                    if parent:
                         next_node = parent.find_next_sibling()

                if next_node:
                    content_text = next_node.get_text(strip=True)
                    # [過濾] 內文長度需大於 5，且不能是純日期
                    if content_text and len(content_text) > 5 and not re.match(r'^[0-9]{4}[/.-]?[0-9]{1,2}', content_text):
                         item_data["content"] = content_text

                activities[section_name].append(item_data)

    return activities


# ==========================================
# 3. 狀態存取邏輯 (讀取與寫入 state.json)
# ==========================================
def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            # 如果 json 損毀，回傳預設空字典
            return {"校內活動": [], "校友會活動": []}
    return {"校內活動": [], "校友會活動": []}

def save_current_state(state):
    # 為了穩定比對，state.json 裡面我們只儲存「標題」清單
    # 這樣可以避免網站管理員只改了內文錯字就觸發重新通知
    simplified_state = {
        "校內活動": [item["title"] for item in state["校內活動"]],
        "校友會活動": [item["title"] for item in state["校友會活動"]]
    }
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(simplified_state, f, ensure_ascii=False, indent=4)


# ==========================================
# 4. 發送 LINE 訊息邏輯
# ==========================================
def send_line_message(messages):
    if not LINE_TOKEN or not LINE_TARGET_ID:
        print("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN 或 目標 ID (LINE_GROUP_ID / LINE_USER_ID)")
        return

    line_bot_api = LineBotApi(LINE_TOKEN)
    
    # 訊息開頭：加上美觀的分隔線
    text = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═" * 15 + "\n\n"
    # 將所有新活動訊息以空行串接
    text += "\n\n".join(messages)
    
    try:
        # 將訊息推送給指定的 User ID 或 Group ID
        line_bot_api.push_message(LINE_TARGET_ID, TextSendMessage(text=text))
        print(f"✅ 訊息傳送成功！(目標 ID: {LINE_TARGET_ID[:8]}...)")
    except Exception as e:
        print(f"❌ 訊息傳送失敗: {e}")


# ==========================================
# 5. 主程式執行邏輯
# ==========================================
def main():
    print("🔍 開始抓取網頁...")
    current_activities = fetch_activities()
    
    # 印出抓取結果，方便在 GitHub Actions 日誌中除錯
    print(f"目前抓取到的活動：\n{json.dumps(current_activities, ensure_ascii=False, indent=2)}")
    
    previous_state_titles = load_previous_state()
    new_messages = []
    
    # 開始比對新舊活動
    for category in ["校內活動", "校友會活動"]:
        current_list = current_activities.get(category, [])
        previous_titles = previous_state_titles.get(category, [])
        
        for item in current_list:
            # 只要該活動標題不在舊的紀錄中，就視為新活動
            if item["title"] not in previous_titles:
                
                # ====== 視覺優化排版 ======
                # 給予分類專屬 Icon
                icon = "🏫" if category == "校內活動" else "🤝"
                msg_block = f"{icon} [{category}]\n"
                
                # 標題：利用星星符號夾擊，模擬粗體大標的視覺效果
                msg_block += f"🌟 {item['title']} 🌟" 
                
                # 內文：直接換行接續，去除生硬的前綴字
                if item['content']:
                    msg_block += f"\n{item['content']}" 
                    
                # 連結：加入手指符號引導點擊
                if item['link']:
                    msg_block += f"\n👉 {item['link']}"  
                # ==========================
                
                new_messages.append(msg_block)
            
    if new_messages:
        print(f"💡 發現 {len(new_messages)} 筆新活動，準備發送 LINE 訊息...")
        send_line_message(new_messages)
        # 訊息發送後，更新 state.json 以防下次重複發送
        save_current_state(current_activities)
    else:
        print("😴 目前沒有新的活動。")
        
        # 如果是第一次執行 (找不到檔案) 或 json 損毀，
        # 即使沒有新活動也要建立初始的狀態基準點
        if not os.path.exists(STATE_FILE) or not previous_state_titles["校內活動"]:
             save_current_state(current_activities)
             print("💾 已建立初始狀態檔 (state.json)。")

if __name__ == "__main__":
    main()
