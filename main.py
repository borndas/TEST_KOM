import requests
from bs4 import BeautifulSoup
import json
import os
from linebot import LineBotApi
from linebot.models import TextSendMessage

# ================= 參數設定 =================
TARGET_URL = "https://huagangkongshoudaoshexiaoyouhuiwangzhanjiagoufanli.webnode.tw/"
LINE_CHANNEL_ACCESS_TOKEN = "69b870fda00ae6c7467ae89d34e6d453"
LINE_USER_ID = "2009792968"
CACHE_FILE = "activities_data.json"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def get_activities_from_website():
    """
    抓取網站並解析出「校內活動」與「校友會活動」的標題清單。
    這是一個結構化抓取的範例，您需要根據網頁實際的 HTML 結構調整 CSS 選擇器。
    """
    try:
        response = requests.get(TARGET_URL)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        activities_data = {
            "校內活動": [],
            "校友會活動": []
        }

        # =====================================================================
        # [重要] 以下的 find_all 條件必須根據網站的真實 HTML 結構 (F12) 進行修改！
        # 假設每個活動都被包在一個 class 為 'event-item' 的 div 中，
        # 且標題是 <h3>，日期是 class 為 'date' 的 <span>
        # =====================================================================
        
        # 範例：抓取全站所有的活動區塊 (請依實際網頁 DOM 結構改寫此段邏輯)
        # 這裡僅為概念展示，實務上可先定位「校內活動」的區塊，再抓底下的列表
        
        # 假設我們找到了一個包含所有校內活動的清單區塊 <ul> 或 <div>
        campus_section = soup.find('div', id='campus-events-section') # 需替換為實際的 ID 或 Class
        if campus_section:
            for item in campus_section.find_all('div', class_='event-item'): # 需替換為實際的 Class
                title = item.find('h3').get_text(strip=True) if item.find('h3') else "無標題"
                date = item.find('span', class_='date').get_text(strip=True) if item.find('span', class_='date') else ""
                activities_data["校內活動"].append(f"{title} ({date})")

        # 假設我們找到了校友會活動的區塊
        alumni_section = soup.find('div', id='alumni-events-section') # 需替換為實際的 ID 或 Class
        if alumni_section:
            for item in alumni_section.find_all('div', class_='event-item'): # 需替換為實際的 Class
                title = item.find('h3').get_text(strip=True) if item.find('h3') else "無標題"
                date = item.find('span', class_='date').get_text(strip=True) if item.find('span', class_='date') else ""
                activities_data["校友會活動"].append(f"{title} ({date})")

        return activities_data

    except Exception as e:
        print(f"網頁抓取或解析失敗: {e}")
        return None

def send_line_notify(message):
    """發送 LINE 訊息"""
    try:
        line_bot_api.push_message(LINE_USER_ID, TextSendMessage(text=message))
        print("訊息發送成功！")
    except Exception as e:
        print(f"LINE 訊息發送失敗: {e}")

def main():
    current_data = get_activities_from_website()
    
    if not current_data:
        print("無法取得當前網站資料。")
        return

    # 讀取舊的快取紀錄
    old_data = {"校內活動": [], "校友會活動": []}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        except json.JSONDecodeError:
            print("快取檔案格式錯誤，將重新建立。")

    # 比對找出新增的活動
    new_messages = []
    
    for category in ["校內活動", "校友會活動"]:
        current_list = current_data.get(category, [])
        old_list = old_data.get(category, [])
        
        # 找出存在於 current_list 但不在 old_list 的項目
        new_items = [item for item in current_list if item not in old_list]
        
        if new_items:
            new_messages.append(f"【{category}】新增：\n" + "\n".join(f"• {item}" for item in new_items))

    # 如果有新增內容，則發送 LINE 通知並更新快取
    if new_messages:
        print("偵測到新增活動！")
        
        # 組合最終要發送的訊息字串
        final_message = "📢 網站有最新活動更新！\n\n"
        final_message += "\n\n".join(new_messages)
        final_message += f"\n\n👉 點此查看詳情：\n{TARGET_URL}"
        
        send_line_notify(final_message)
        
        # 將最新的資料結構寫入 JSON 檔案
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, ensure_ascii=False, indent=4)
    else:
        print("目前沒有新增的活動。")

if __name__ == "__main__":
    main()