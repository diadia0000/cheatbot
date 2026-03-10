import streamlit as st
import requests
import os
import time
from components import load_css, render_line_chat, render_monitor_thought

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8080")
SESSION_ID = "test_session_001"

st.set_page_config(page_title="Anti-Fraud Simulator", layout="wide")
load_css()

# Sidebar for Navigation
view_mode = st.sidebar.radio("切換視角", ("受害者視角 (LINE UI)", "警方監控視角 (God Mode)"))

if st.sidebar.button("清除歷史紀錄"):
    requests.post(f"{BACKEND_API_URL}/clear", json={"session_id": SESSION_ID})
    st.session_state.history = []
    st.session_state.thought = ""
    st.sidebar.success("已清除對話狀態！")

if "history" not in st.session_state:
    st.session_state.history = []
if "thought" not in st.session_state:
    st.session_state.thought = ""

def fetch_history():
    try:
        res = requests.get(f"{BACKEND_API_URL}/monitor/{SESSION_ID}")
        if res.status_code == 200:
            return res.json().get("history", [])
    except Exception as e:
        st.error(f"無法連接到後端 API: {e}")
    return []

if view_mode == "受害者視角 (LINE UI)":
    st.title("LINE 聊天室模擬")
    
    st.session_state.history = fetch_history()
    render_line_chat(st.session_state.history)
    
    user_input = st.text_input("輸入訊息...", key="chat_input")
    if st.button("送出") and user_input:
        # Optimistic UI Update
        st.session_state.history.append({"role": "user", "content": user_input})
        
        with st.spinner("陳呆呆正在輸入..."):
            try:
                res = requests.post(f"{BACKEND_API_URL}/chat", json={
                    "session_id": SESSION_ID,
                    "message": user_input
                })
                if res.status_code == 200:
                    data = res.json()
                    delay = data.get("delay_seconds", 0)
                    time.sleep(delay)  # 模擬打字延遲
                    
                    reply_text = data["reply"]
                    if data.get("image_url"):
                        img_url = f"{BACKEND_API_URL}{data['image_url']}"
                        reply_text += f"\n\n![對帳單]({img_url})"
                    
                    st.session_state.history.append({"role": "assistant", "content": reply_text})
                    st.session_state.thought = data["thought"]
            except Exception as e:
                st.error(f"連線失敗: {e}")
                
        st.rerun()

elif view_mode == "警方監控視角 (God Mode)":
    st.title("系統監控後台")
    
    try:
        res = requests.get(f"{BACKEND_API_URL}/monitor/{SESSION_ID}")
        if res.status_code == 200:
            data = res.json()
            state = data.get("state", {})
            history = data.get("history", [])
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("當前對話狀態")
                st.write(f"**欺詐階段:** {state.get('fraud_stage')}")
                st.write(f"**受害者標籤:** {state.get('victim_tags')}")
                
                st.subheader("最新策略分析")
                render_monitor_thought(st.session_state.get("thought", "暫無推論記錄"))
                
            with col2:
                st.subheader("完整 Raw History")
                st.json(history)
    except Exception as e:
        st.error(f"無法獲取監控數據: {e}")
