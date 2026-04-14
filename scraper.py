import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
import re
import hashlib # 用於產生內容指紋
from linebot import LineBotApi
from linebot.models import TextSendMessage

# ==========================================
# 1. 設定區
# ==========================================
URL = "https://huagangkongshoudaoshexiaoyouhuiwangzhanjiagoufanli.webnode.tw/"
STATE_FILE = "state.json"
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TARGET_ID = os.environ.get("LINE_GROUP_ID") or os.environ.get("LINE_USER_ID")

# ==========================================
# 2. 爬蟲與去重核心
# ==========================================
def get_content_hash(title, content):
    """將標題與內文結合，產生唯一的指紋碼，確保內容完全一樣時不重發"""
    combined = f"{title.strip()}{content.strip()}"
    return hashlib.md5(combined.encode('utf-8')).hexdigest()

def fetch_activities():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return []

    found_activities = []
    # 掃描所有可能的標題標籤
    for elem in soup.find_all(['h3', 'h4', 'strong']):
        title = elem.get_text(strip=True)
        # 過濾日期與無意義短字
        if not title or len(title) < 2 or re.match(r'^[0-9]{4}', title):
            continue
            
        # 找內文
        content = ""
        next_node = elem.find_next_sibling() or (elem.parent.find_next_sibling() if elem.parent else None)
        if next_node:
            content = next_node.get_text(strip=True)
            if re.match(r'^[0-9]{4}', content): content = "" # 如果下一行是日期，不列入內文

        # 找連結
        link = ""
        a_tag = elem.find('a') or elem.find_parent('a')
        if a_tag and a_tag.has_attr('href'):
            link = urllib.parse.urljoin(URL, a_tag['href'])

        found_activities.append({
            "title": title,
            "content": content,
            "link": link,
            "id": get_content_hash(title, content) # 產生指紋
        })
    return found_activities

# ==========================================
# 3. 狀態管理
# ==========================================
def load_sent_ids():
    """讀取已經發送過的指紋清單"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 兼容舊格式，確保回傳的是列表
                return data if isinstance(data, list) else data.get("sent_ids", [])
        except:
            return []
    return []

def save_sent_ids(sent_ids):
    """儲存已發送過的指紋清單"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sent_ids, f, ensure_ascii=False, indent=4)

# ==========================================
# 4. 主程式
# ==========================================
def main():
    print("🔍 檢查新活動中...")
    all_items = fetch_activities()
    sent_ids = load_sent_ids()
    
    new_items_to_send = []
    
    for item in all_items:
        if item["id"] not in sent_ids:
            # 這是新活動！
            msg = f"🌟 {item['title']} 🌟"
            if item['content']: msg += f"\n{item['content']}"
            if item['link']: msg += f"\n👉 {item['link']}"
            
            new_items_to_send.append(msg)
            sent_ids.append(item["id"]) # 加入已發送清單
            
    if new_items_to_send:
        # 分類發送，避免一次訊息太長
        full_text = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═"*15 + "\n\n"
        full_text += "\n\n".join(new_items_to_send)
        
        if LINE_TOKEN and LINE_TARGET_ID:
            try:
                LineBotApi(LINE_TOKEN).push_message(LINE_TARGET_ID, TextSendMessage(text=full_text))
                print(f"✅ 成功發送 {len(new_items_to_send)} 則新通知！")
                save_sent_ids(sent_ids) # 成功後才存檔
            except Exception as e:
                print(f"❌ LINE 發送失敗: {e}")
    else:
        print("😴 沒有新活動，不發送訊息。")

if __name__ == "__main__":
    main()
