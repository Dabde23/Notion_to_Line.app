import os
import requests
from dotenv import load_dotenv

load_dotenv()

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
            "to": LINE_USER_ID,
            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }

    r = requests.post(url, headers=headers, json=data)

    if r.status_code == 200:
        print("送信完了")

    else:
        print(f"送信失敗: {r.status_code}")
        print(r.text)

if __name__ == "__main__":
    send_line_message("test")