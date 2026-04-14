import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
import re
import hashlib
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
# 2. 爬蟲核心 (精準區分校內/校友會活動)
# ==========================================
def get_content_hash(category, title, content):
    combined = f"{category}{title.strip()}{content.strip()}"
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

    results = []
    
    # 定義要抓取的目標區塊
    categories = ["校內活動", "校友會活動"]
    
    for cat_name in categories:
        # 1. 找到大標題 (校內活動 / 校友會活動)
        start_node = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'div'] and cat_name in tag.get_text())
        if not start_node: continue
        
        # 2. 往後遍歷直到遇見下一個大區塊
        current = start_node.find_next()
        while current:
            # 停止條件：如果遇到另一個分類標題或頁尾標題
            cur_text = current.get_text(strip=True)
            if current.name in ['h1', 'h2'] and any(stop in cur_text for stop in ["校友會活動", "聯絡我們", "最新消息"]) and cur_text != cat_name:
                break
            
            # 3. 識別活動項目：標題通常是 h3, h4 或 strong
            if current.name in ['h3', 'h4', 'strong']:
                title = cur_text
                
                # 過濾非活動的雜訊
                if len(title) < 2 or len(title) > 30 or re.match(r'^[0-9]{4}[/.-]', title):
                    current = current.find_next()
                    continue
                
                # 找內文：取下一個同層或鄰近的非標題元素
                content = ""
                next_node = current.find_next_sibling() or current.find_next(['p', 'div', 'span'])
                if next_node:
                    c_text = next_node.get_text(strip=True)
                    # 內文不能是下一個活動標題，也不能是純日期
                    if len(c_text) > 2 and not re.match(r'^[0-9]{4}[/.-]', c_text) and next_node.name not in ['h3', 'h4', 'strong']:
                        content = c_text
                
                # 找連結
                link = ""
                a_tag = current.find('a') or current.find_parent('a')
                if a_tag and a_tag.has_attr('href'):
                    link = urllib.parse.urljoin(URL, a_tag['href'])

                results.append({
                    "category": cat_name,
                    "title": title,
                    "content": content,
                    "link": link,
                    "id": get_content_hash(cat_name, title, content)
                })
                
                # 為了避免重複抓取內文，跳過已處理的 next_node
                current = next_node
            
            current = current.find_next()
            
    return results

# ==========================================
# 3. 狀態管理與訊息發送
# ==========================================
def load_sent_ids():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def save_sent_ids(sent_ids):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sent_ids, f, ensure_ascii=False, indent=4)

def main():
    print("🔍 檢查新活動中...")
    all_items = fetch_activities()
    sent_ids = load_sent_ids()
    
    new_messages = []
    
    for item in all_items:
        if item["id"] not in sent_ids:
            # 依照要求排版
            icon = "🏫" if item["category"] == "校內活動" else "🤝"
            msg = f"{icon} [{item['category']}]\n🌟 {item['title']} 🌟"
            if item['content']:
                msg += f"\n{item['content']}"
            if item['link']:
                msg += f"\n👉 {item['link']}"
            
            new_messages.append(msg)
            sent_ids.append(item["id"])
            
    if new_messages:
        header = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═══════════════\n\n"
        full_text = header + "\n\n".join(new_messages)
        
        if LINE_TOKEN and LINE_TARGET_ID:
            try:
                LineBotApi(LINE_TOKEN).push_message(LINE_TARGET_ID, TextSendMessage(text=full_text))
                print(f"✅ 成功發送 {len(new_messages)} 則新通知！")
                save_sent_ids(sent_ids)
            except Exception as e:
                print(f"❌ LINE 發送失敗: {e}")
    else:
        print("😴 目前沒有新的活動。")

if __name__ == "__main__":
    main()
