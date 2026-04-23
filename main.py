import streamlit as st
from datetime import datetime
from notion_to_line_app import NotionClient, LineClient, NotionDataProcessor

st.set_page_config(page_title="出面出力マシーン")
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    placeholder = st.empty()
    with placeholder.container():
        password = st.text_input("パスワードを入力", type="password")
        if password == st.secrets.get("password"):
            st.session_state["authenticated"] = True
            placeholder.empty()
            st.rerun()
        elif password != "":
            st.error("パスワードが違います") 
    st.stop()
    
st.title ("Notion to Line Notification")
st.markdown("指定した月の出面をNotionからテキストに変換してLineに送信")

st.sidebar.header("取得設定")
target_year = st.sidebar.number_input("年", min_value=2024, max_value=2100, value=datetime.now().year)
target_month = st.sidebar.selectbox("月", range(1, 13), index=datetime.now().month)

if st.button("スケジュールの取得、確認"):
    try:
        with st.spinner("Notionからデータを取得中..."):
            #Notionから取得
            notion = NotionClient.setup()
            results = notion.get_month_schedule(target_year, target_month)

            #データの加工
            processed_data = NotionDataProcessor.extract_text(results)
            grouped_data = NotionDataProcessor.group_by_tag_and_sort(processed_data)
            final_text = NotionDataProcessor.format_grouped_text_to_plain_text(grouped_data)

            #プレビュー表示
            st.subheader("プレビュー")
            st.text_area("以下の内容を送信", value=final_text, height=300)

            #セッションに保存
            st.session_state["final_text"] = final_text

    except Exception as e:
        st.error(f"エラーが発生しました {e}")

if "final_text" in st.session_state:
    if st.button("この内容で出力"):
        try:
            with st.spinner("送信中..."):
                line = LineClient.setup()
                line.send_message(st.session_state["final_text"])
                st.success("送信完了！")

                del st.session_state["final_text"]
        except Exception as e:
            st.error(f"送信エラー {e}")    
 
