from collections import defaultdict
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from dateutil.relativedelta import relativedelta
import streamlit as st

load_dotenv()

class NotionClient:
    def __init__(self, token, db_id, url):
        self.token = token
        self.db_id = db_id
        self.url = url
        self.headers = self._make_headers()
    
    def _make_headers(self):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"  # Notion APIのバージョン指定
        }
        return headers

    @classmethod
    def setup(cls):
        token = st.secrets.get("NOTION_TOKEN")
        db_id = st.secrets.get("NOTION_DATABASE_ID")
        if not token:
            raise ValueError("トークンが見つかりません")
        if not db_id:
            raise ValueError("データベースIDが見つかりません")

        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        return cls(token, db_id, url)

    def get_month_schedule(self, year, month):  #NotionからJsonを抽出する
        target_month = datetime(year, month, 1).strftime("%Y-%m-%d")
        end_month = (datetime(year, month, 1) + relativedelta(months=1)).replace(day=1).strftime("%Y-%m-%d")

        query = {
            "filter": {
                "and": [
                    {
                        "property": "日付",
                        "date": {
                            "on_or_after": target_month
                        }
                    },
                    {                        
                        "property": "日付",
                        "date": {
                            "before": end_month
                        }
                    },
                    {
                        "property": "請",
                        "checkbox": {
                            "equals": False
                        }
                    }
                ]
            }
        }

        response = requests.post(self.url, headers=self.headers, json=query)
        if response.status_code == 200:
            self.results = response.json().get("results", [])
            return self.results
        else:
            print(f"エラー: {response.status_code}\n{response.text}")
           
class NotionDataProcessor:
    @staticmethod
    def extract_text(results):  #Jsonから中身のデータをリスト化する
        text_list = []
        for page in results:
            props = page["properties"]

            title_list = props.get("現場", {}).get("title", [])
            title = title_list[0]["plain_text"] if title_list else "無題"

            tags_info = props.get("社名", {}).get("multi_select", [])
            tags = [t["name"] for t in tags_info]
            tags_str = f"{','.join(tags)}" if tags else ""

            is_night_work = props.get("夜勤", {}).get("checkbox", False)
            
            expenses_list = props.get("経費", {}).get("rich_text", [])
            expenses = expenses_list[0]["plain_text"] if expenses_list else None

            date = props.get("日付", {}).get("date", {}).get("start", None)
            if not date: continue
            day = datetime.strptime(date, "%Y-%m-%d").day

            worker_count = props.get("人数", {}).get("number", {})

            text = {"title": title, "tag": tags_str, "is_night_work": is_night_work, "expenses": expenses, "day":day, "count": worker_count}
            text_list.append(text)

        return text_list

    @staticmethod
    def format_grouped_text_to_plain_text(grouped_data):   #テキストのリストから実際に使う形に整形する
        if not grouped_data:
            return "予定はありません"
        
        blocks = []
        for tag, items in grouped_data.items():
            current_block = [f"■ {tag}"]
            for item in items:
                day = str(item["day"])
                line = f"{day}日  {item['title']}  {item['count']}人"

                if item["is_night_work"]:
                    line += "（夜勤）"

                if item["expenses"]:
                    line += f"\n  経費: {item['expenses']}"
                
                current_block.append(line)
            blocks.append("\n".join(current_block))
            
        return "\n----------\n".join(blocks)

    @staticmethod
    def group_by_tag_and_sort(text_list):
        sorted_list = sorted(text_list, key=lambda x: x["day"])
        grouped_data = defaultdict(list)

        for item in sorted_list:
            tag = item["tag"] if item["tag"] else "[その他]"
            grouped_data[tag].append(item)

        return grouped_data

class LineClient:
    def __init__(self, token, user_id, url):
        self.token = token
        self.user_id = user_id
        self.url = url
        self.headers = self._make_headers()
    
    def _make_headers(self):
        headers = {
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
        }
        return headers

    @classmethod
    def setup(cls):
        token = st.secrets.get("LINE_ACCESS_TOKEN")
        user_id = st.secrets.get("LINE_USER_ID")
        if not token:
            raise ValueError("トークンが見つかりません")
        if not user_id:
            raise ValueError("ユーザーIDが見つかりません")

        url = f"https://api.line.me/v2/bot/message/push"
        return cls(token, user_id, url)

    def send_message(self, final_text):
        data = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "text",
                    "text": final_text
                }
            ]
        }

        r = requests.post(self.url, headers=self.headers, json=data)

        if r.status_code == 200:
            print("送信完了")

        else:
            print(f"送信失敗: {r.status_code}")
            print(r.text)

if __name__ == "__main__":
    notion = NotionClient.setup()
    line = LineClient.setup()
    target_year = int(input("年を入力"))
    target_month = int(input("月を入力"))
    results = notion.get_month_schedule(target_year, target_month)
    processed_data = NotionDataProcessor.extract_text(results)
    grouped_data = NotionDataProcessor.group_by_tag_and_sort(processed_data)
    final_text = NotionDataProcessor.format_grouped_text_to_plain_text(grouped_data)
    line.send_message(final_text)