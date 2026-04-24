import requests
from bs4 import BeautifulSoup
import json
import os
import urllib.parse
import re
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
# 2. 爬蟲核心 (包含時間偵測與複標記產生)
# ==========================================
def fetch_activities():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 網頁抓取失敗: {e}")
        return []

    results = []
    target_categories = ["校內活動", "校友會活動"]

    for cat_name in target_categories:
        start_node = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'div'] and tag.get_text(strip=True) == cat_name)
        if not start_node: continue
        
        current = start_node.find_next()
        while current:
            cur_text = current.get_text(strip=True)
            
            if current.name in ['h1', 'h2'] and any(stop in cur_text for stop in ["校友會活動", "聯絡我們", "最新消息"]) and cur_text != cat_name:
                break
            
            if current.name in ['h3', 'h4', 'strong'] and len(cur_text) > 1:
                if re.match(r'^[0-9]{4}[/.-]', cur_text):
                    current = current.find_next()
                    continue

                title = cur_text
                content = ""
                time_str = ""
                link = ""

                # 找連結
                a_tag = current.find('a') or current.find_parent('a')
                if a_tag and a_tag.has_attr('href'):
                    link = urllib.parse.urljoin(URL, a_tag['href'])

                # 往後搜尋內文與時間 (搜尋鄰近 5 個節點)
                search_limit = 0
                temp_node = current.find_next()
                while temp_node and search_limit < 5:
                    t_text = temp_node.get_text(strip=True)
                    if re.match(r'^[0-9]{4}[/.-][0-9]{1,2}', t_text) and not time_str:
                        time_str = t_text
                    elif len(t_text) > 3 and not content and temp_node.name not in ['h3', 'h4', 'strong']:
                        content = t_text
                    if temp_node.name in ['h3', 'h4', 'strong']:
                        break
                    temp_node = temp_node.find_next()
                    search_limit += 1

                # 重點修改：產生包含 標題 + 內文 + 時間 的唯一標記
                # 如果其中一項有變動，這串 ID 就會改變，從而觸發新通知
                unique_id = f"[{cat_name}] {title} | 內容：{content} | 時間：{time_str}"

                results.append({
                    "category": cat_name,
                    "title": title,
                    "content": content,
                    "time": time_str,
                    "link": link,
                    "id": unique_id
                })
            
            current = current.find_next()
            
    return results

# ==========================================
# 3. 狀態管理與發送
# ==========================================
def load_sent_ids():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def save_sent_ids(sent_ids):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sent_ids, f, ensure_ascii=False, indent=4)

def main():
    print("🔍 掃描中 (比對標題+內文+時間)...")
    all_items = fetch_activities()
    sent_ids = load_sent_ids()
    
    new_messages = []
    
    for item in all_items:
        # 比對完整的 unique_id
        if item["id"] not in sent_ids:
            icon = "🏫" if item["category"] == "校內活動" else "🤝"
            
            msg = f"{icon} [{item['category']}]\n🌟 {item['title']} 🌟"
            if item['content']:
                msg += f"\n{item['content']}"
            if item['time']:
                msg += f"\n📅 時間：{item['time']}"
            if item['link']:
                msg += f"\n👉 {item['link']}"
            msg += f"\n👉 {URL}"
            new_messages.append(msg)
            sent_ids.append(item["id"])
            
    if new_messages:
        header = "【🎓 華岡空手道校友會 - 最新動態】\n" + "═══════════════\n\n"
        full_text = header + "\n\n".join(new_messages)
        
        if LINE_TOKEN and LINE_TARGET_ID:
            try:
                line_bot_api = LineBotApi(LINE_TOKEN)
                line_bot_api.push_message(LINE_TARGET_ID, TextSendMessage(text=full_text))
                print(f"✅ 成功發送 {len(new_messages)} 筆新內容。")
                save_sent_ids(sent_ids)
            except Exception as e:
                print(f"❌ LINE 發送錯誤: {e}")
    else:
        print("😴 標題、內文與時間均無變動，跳過發送。")

if __name__ == "__main__":
    main()
