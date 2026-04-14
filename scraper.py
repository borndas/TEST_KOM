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
# 1. 基本設定
# ==========================================
URL = "https://huagangkongshoudaoshexiaoyouhuiwangzhanjiagoufanli.webnode.tw/"
STATE_FILE = "state.json"
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TARGET_ID = os.environ.get("LINE_GROUP_ID") or os.environ.get("LINE_USER_ID")

# ==========================================
# 2. 爬蟲核心 (精準範圍鎖定與解析)
# ==========================================
def get_content_hash(category, title, content):
    """產生唯一指紋，避免內容稍有變動就重發"""
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
    # 定義要追蹤的兩大區塊
    target_categories = ["校內活動", "校友會活動"]

    for cat_name in target_categories:
        # A. 找到大區塊的起點 (例如：<h2>校內活動</h2>)
        start_node = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'div'] and tag.get_text(strip=True) == cat_name)
        if not start_node: continue
        
        # B. 取得該區塊內所有的下級元素進行掃描
        # 我們往後找直到遇見下一個大分類標題為止
        current = start_node.find_next()
        while current:
            cur_text = current.get_text(strip=True)
            
            # 停止條件：如果遇到另一個分類大標題或聯絡資訊，就結束此區塊搜尋
            if current.name in ['h1', 'h2'] and any(stop in cur_text for stop in ["校友會活動", "聯絡我們", "最新消息"]) and cur_text != cat_name:
                break
            
            # 識別活動標題 (通常為 h3, h4 或 strong)
            if current.name in ['h3', 'h4', 'strong'] and len(cur_text) > 1:
                # 排除純日期或太長的雜訊
                if re.match(r'^[0-9]{4}[/.-]', cur_text) or len(cur_text) > 40:
                    current = current.find_next()
                    continue

                title = cur_text
                content = ""
                link = ""

                # (1) 找連結
                a_tag = current.find('a') or current.find_parent('a')
                if a_tag and a_tag.has_attr('href'):
                    link = urllib.parse.urljoin(URL, a_tag['href'])

                # (2) 找內文：在標題後方尋找第一個描述性的文字段落
                # 我們跳過日期格式，找第一個長度足夠的文字
                next_node = current.find_next(['p', 'div', 'span'])
                if next_node:
                    c_text = next_node.get_text(strip=True)
                    # 內文不能是下一個活動標題
                    if len(c_text) > 3 and not re.match(r'^[0-9]{4}[/.-]', c_text) and next_node.name not in ['h3', 'h4', 'strong']:
                        content = c_text

                results.append({
                    "category": cat_name,
                    "title": title,
                    "content": content,
                    "link": link,
                    "id": get_content_hash(cat_name, title, content)
                })
                # 避免重複掃描已作為內文處理過的節點
                current = next_node if next_node else current
            
            current = current.find_next()
            
    return results

# ==========================================
# 3. 狀態儲存與發送
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
    print("🔍 啟動精準偵測程序...")
    all_items = fetch_activities()
    sent_ids = load_sent_ids()
    
    new_messages = []
    
    for item in all_items:
        if item["id"] not in sent_ids:
            # 依照要求的「正確格式」排版
            icon = "🏫" if item["category"] == "校內活動" else "🤝"
            msg = f"{icon} [{item['category']}]\n🌟 {item['title']} 🌟"
            
            if item['content']:
                msg += f"\n{item['content']}"
            if item['link']:
                msg += f"\n👉 {item['link']}"
            
            new_messages.append(msg)
            sent_ids.append(item["id"])
            
    if new_messages:
        # 組裝整篇訊息
        header = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═══════════════\n\n"
        full_text = header + "\n\n".join(new_messages)
        
        if LINE_TOKEN and LINE_TARGET_ID:
            try:
                LineBotApi(LINE_TOKEN).push_message(LINE_TARGET_ID, TextSendMessage(text=full_text))
                print(f"✅ 已成功發送 {len(new_messages)} 筆新內容至 LINE。")
                save_sent_ids(sent_ids)
            except Exception as e:
                print(f"❌ LINE 發送錯誤: {e}")
    else:
        print("😴 掃描完畢，目前網頁無新增內容。")

if __name__ == "__main__":
    main()
