import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"  # Notion APIのバージョン指定
}

def get_todays_schedules():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    today = datetime.now().strftime("%Y-%m-%d")

    query_data = {
        "filter": {
            "property": "日付",
            "date": {
                "equals": today
            }
        }
    }

    r = requests.post(url, headers=headers, json=query_data)

    if r.status_code == 200:
        results = r.json().get("results", [])

        if not results:
            print(f"{today}の予定はありません")
            return
        
        print(f"--- {today}の予定一覧 ---")
        for page in results:
            props = page["properties"]

            title_list = props.get("現場", {}).get("title", [])
            title = title_list[0]["plain_text"] if title_list else "無題"

            tags_info = props.get("社名", {}).get("multi_select", [])
            tags = [t["name"] for t in tags_info]

            tags_str = f"[{','.join(tags)}]" if tags else ""
            print(f"・{title} {tags_str}")
    else:
        print(f"エラー: {r.status_code}\n{r.text}") 

if __name__ == "__main__":
    get_todays_schedules()