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
                a_tag = elem.find('a') or elem
