# Notion to LINE

NotionのデータベースからスケジュールをLINEに送信するアプリ

## 機能
- 指定した年月のスケジュールをNotionから取得
- 社名ごとにグループ化してLINEに送信
- 夜勤・経費情報も整形して通知

## 使い方

### 必要なもの
- Python 3.10以上
- Notion APIトークン
- LINE Messaging APIトークン

### セットアップ

1. リポジトリをクローン
git clone https://github.com/Dabde23/Notion_to_Line.app

2. ライブラリをインストール
pip install -r requirements.txt

3. シークレットを設定
.streamlit/secrets.toml に以下を記載：
NOTION_TOKEN = "your_token"
NOTION_DATABASE_ID = "your_db_id"
LINE_ACCESS_TOKEN = "your_token"
LINE_USER_ID = "your_user_id"

4. 実行
python main.py

## 使用技術
- Python
- Notion API
- LINE Messaging API
- Streamlit
