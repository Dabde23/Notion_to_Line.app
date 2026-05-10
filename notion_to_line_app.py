from collections import defaultdict
from dataclasses import dataclass
from sys import exception
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Self
from enum import StrEnum
from dotenv import load_dotenv
import os


load_dotenv()

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
MAX_PAGE = 10

class NotionProperties(StrEnum):
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
    count: int | None

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
        token = token.strip()
        if not token:
            raise NotionConfigError("トークンが見つかりません")
        db_id = db_id.strip()
        if not db_id:
            raise NotionConfigError("データベースIDが見つかりません")

        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        return cls(token, db_id, url)

    def get_month_schedule(self, year: int, month: int) -> list[dict]:
        #NotionからJsonを抽出する
        target_month = datetime(year, month, 1).strftime("%Y-%m-%d")
        end_month = (datetime(year, month, 1) + relativedelta(months=1)).strftime("%Y-%m-%d")
        results = []
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
        has_more = True
        next_cursor = None
        page_count = 0
        while has_more and page_count < MAX_PAGE:
            if next_cursor:
                query["start_cursor"] = next_cursor
            try:
                response = requests.post(self.url, headers=self.headers, json=query, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
                r = self._handle_response(response).json()
                results += r.get("results", [])
                has_more = r.get("has_more", False)
                page_count += 1
            except requests.exceptions.RequestException as e:
                raise NotionTransientError(e)

        return results
    @staticmethod
    def _handle_response(response):
        if response.status_code == 200:
            return response
        elif response.status_code ==400:
            raise NotionConfigError()
        elif response.status_code ==401:
            raise NotionConfigError(f"無効なAPIキー: {response.status_code}")
        elif response.status_code == 404:
            raise NotionDataError(response.status_code)
        elif response.status_code == 429:
            raise NotionRateLimitError(response.status_code)
        elif response.status_code >= 500:
            raise NotionServerError(response.status_code)

           
class NotionDataProcessor:
    def get_formatted_text(self, results):
        #データを整形するメソッドを順次呼び出す
        self.extract_text(results)
        self.group_by_tag_and_sort()
        self.format_grouped_text_to_plain_text()
        return self.formatted_text

    def extract_text(self, results: list[dict]):
        #Jsonから中身のデータをリスト化する
        text_list = []
        for page in results:
            props = page.get("properties", {})
            if not props:
                continue

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
        self.text_list = text_list

    def group_by_tag_and_sort(self):
        #グルーピング及びソート
        sorted_list = sorted(self.text_list, key=lambda x: x.day)
        grouped_data = defaultdict(list)

        for item in sorted_list:
            tag = item.tag if item.tag else "その他"
            grouped_data[tag].append(item)

        self.grouped_data = grouped_data

    def format_grouped_text_to_plain_text(self) -> str:
        #テキストのリストから実際に使う形に整形する
        if not self.grouped_data:
            return "予定はありません"
        
        blocks = []
        for company, schedules in self.grouped_data.items():
            current_block = [f"■ {company}"]
            for item in schedules:
                line = f"{item.day}日  {item.title}  {item.count}人"
                if item.is_night_work:
                    line += "（夜勤）"
                if item.expenses:
                    line += f"\n  経費: {item.expenses}"
                current_block.append(line)
            blocks.append("\n".join(current_block))

        self.formatted_text = "\n----------\n".join(blocks)

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
            raise NotionConfigError("トークンが見つかりません")
        if not user_id:
            raise NotionConfigError("ユーザーIDが見つかりません")

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

            r = requests.post(self.url, headers=self.headers, json=data, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))

            if r.status_code != 200:
                raise Exception(f"Line APIエラー: {r.status_code}")
        else:
            raise ValueError("文章が長過ぎます")

class AppError(Exception):
    pass

class NotionError(AppError):
    pass

class NotionConfigError(NotionError):
    pass

class NotionDataError(NotionError):
    def __init__(self, status_code: int | None = None):
        self.status_code = status_code
        if self.status_code is not None:
            super().__init__(f"データベースが存在しないかIDが間違っています: {status_code}")
        else:
            super().__init__("プロパティが存在しません")

class NotionTransientError(NotionError):
    def __init__(self,status_code: int | None = None, message: str | None = "接続エラー"):
        self.status_code = status_code
        super().__init__(message)

class NotionServerError(NotionTransientError):
    def __init__(self,status_code: int):
        self.status_code = status_code
        super().__init__(status_code, f"Notionサーバーエラー: {status_code}")

class NotionRateLimitError(NotionTransientError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(status_code, f"リクエスト過多: {status_code}")

class LineError(AppError):
    pass

class LineConfigError(LineError):
    pass

class LineMessageError(LineError):
    def __init__(self, length: int, limit: int):
        self.length = length
        self.limit = limit
        super().__init__(f"文字数超過: {length}文字　(上限文字数{limit}文字)")

if __name__ == "__main__":
    notion = NotionClient.setup(os.getenv("NOTION_TOKEN"), os.getenv("NOTION_DATABASE_ID"))
    line = LineClient.setup(os.getenv("LINE_ACCESS_TOKEN"), os.getenv("LINE_USER_ID"))
    formatter = NotionDataProcessor()
    year = int(input("西暦を入力"))
    month = int(input("月を入力"))
    results = notion.get_month_schedule(year, month)
    final_text = formatter.get_formatted_text(results)
    
    print(f"プレビュー \n {final_text}")
    confirm = input("lineに送信? y")
    if confirm == "y":
        line.send_message(final_text)
    
    
