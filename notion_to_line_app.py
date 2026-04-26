from collections import defaultdict
from dataclasses import dataclass
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Self

class NotionProperties:
    SITE_NAME = "現場"
    COMPANY = "社名"
    NIGHT_WORK = "夜勤"
    EXPENSES = "経費"
    DATE = "日付"
    WORKER_COUNT = "人数"
    BILLED = "請"

@dataclass
class ScheduleItem:
    title: str
    tag: str
    is_night_work: bool
    expenses: str | None
    day: int
    count: int

class NotionClient:
    def __init__(self, token: str, db_id: str, url: str) -> None:
        self.token = token
        self.db_id = db_id
        self.url = url
        self.headers = self._make_headers()
    
    def _make_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"  # Notion APIのバージョン指定
        }
        return headers

    @classmethod
    def setup(cls, token: str, db_id: str) -> Self:
        if not token:
            raise ValueError("トークンが見つかりません")
        if not db_id:
            raise ValueError("データベースIDが見つかりません")

        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        return cls(token, db_id, url)

    def get_month_schedule(self, year: int, month: int) -> list[dict]:
        #NotionからJsonを抽出する
        target_month = datetime(year, month, 1).strftime("%Y-%m-%d")
        end_month = (datetime(year, month, 1) + relativedelta(months=1)).strftime("%Y-%m-%d")

        query = {
            "filter": {
                "and": [
                    {
                        "property": NotionProperties.DATE,
                        "date": {
                            "on_or_after": target_month
                        }
                    },
                    {                        
                        "property": NotionProperties.DATE,
                        "date": {
                            "before": end_month
                        }
                    },
                    {
                        "property": NotionProperties.BILLED,
                        "checkbox": {
                            "equals": False
                        }
                    }
                ]
            }
        }

        r = requests.post(self.url, headers=self.headers, json=query, timeout=10)
        if r.status_code == 200:
            results = r.json().get("results", [])
            return results
        else:
            raise Exception(f"Notion APIエラー: {r.status_code}\n{r.text}")
           
class NotionDataProcessor:
    @staticmethod
    def extract_text(results: list[dict]) -> list[ScheduleItem]: 
        #Jsonから中身のデータをリスト化する
        text_list = []
        for page in results:
            props = page["properties"]

            title_list = props.get(NotionProperties.SITE_NAME, {}).get("title", [])
            title = title_list[0]["plain_text"] if title_list else "無題"

            tags_info = props.get(NotionProperties.COMPANY, {}).get("multi_select", [])
            tags = [t["name"] for t in tags_info]
            tags_str = ','.join(tags) if tags else ""

            is_night_work = props.get(NotionProperties.NIGHT_WORK, {}).get("checkbox", False)
            
            expenses_list = props.get(NotionProperties.EXPENSES, {}).get("rich_text", [])
            expenses = expenses_list[0]["plain_text"] if expenses_list else None

            date = props.get(NotionProperties.DATE, {}).get("date", {}).get("start", None)
            if not date: continue
            day = datetime.strptime(date, "%Y-%m-%d").day

            count = props.get(NotionProperties.WORKER_COUNT, {}).get("number", 0)

            item = ScheduleItem(
                title=title,
                tag=tags_str,
                is_night_work=is_night_work,
                expenses=expenses,
                day=day,
                count=count
            )
            text_list.append(item)

        return text_list

    @staticmethod
    def format_grouped_text_to_plain_text(grouped_data: dict[str, list[ScheduleItem]]) -> str:
        #テキストのリストから実際に使う形に整形する
        if not grouped_data:
            return "予定はありません"
        
        blocks = []
        for company, schedules in grouped_data.items():
            current_block = [f"■ {company}"]
            for item in schedules:
                line = f"{item.day}日  {item.title}  {item.count}人"
                if item.is_night_work:
                    line += "（夜勤）"
                if item.expenses:
                    line += f"\n  経費: {item.expenses}"
                current_block.append(line)
            blocks.append("\n".join(current_block))
            
        return "\n----------\n".join(blocks)

    @staticmethod
    def group_by_tag_and_sort(text_list: list[ScheduleItem]) -> dict[str, list[ScheduleItem]]:
        sorted_list = sorted(text_list, key=lambda x: x.day)
        grouped_data = defaultdict(list)

        for item in sorted_list:
            tag = item.tag if item.tag else "その他"
            grouped_data[tag].append(item)

        return grouped_data

class LineClient:
    MAX_TEXT_LENGTH = 4900

    def __init__(self, token: str, user_id: str, url: str) -> None:
        self.token = token
        self.user_id = user_id
        self.url = url
        self.headers = self._make_headers()
    
    def _make_headers(self) -> dict[str, str]:
        headers = {
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
        }
        return headers

    @classmethod
    def setup(cls, token: str, user_id: str) -> Self:
        if not token:
            raise ValueError("トークンが見つかりません")
        if not user_id:
            raise ValueError("ユーザーIDが見つかりません")

        url = "https://api.line.me/v2/bot/message/push"
        return cls(token, user_id, url)

    def send_message(self, final_text: str) -> None:
        if len(final_text) <= self.MAX_TEXT_LENGTH:
            data = {
                "to": self.user_id,
                "messages": [
                    {
                        "type": "text",
                        "text": final_text
                    }
                ]
            }

            r = requests.post(self.url, headers=self.headers, json=data, timeout=10)

            if r.status_code != 200:
                raise Exception(f"Line APIエラー: {r.status_code}\n{r.text}")
        else:
            raise ValueError("文章が長過ぎます")