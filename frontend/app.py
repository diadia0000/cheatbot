import streamlit as st
import requests
import os
from components import (
    load_css,
    render_session_card,
    render_line_chat,
    render_monitor_thought,
    render_status_badge,
)

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8080")

st.set_page_config(
    page_title="LINE Bot 詐騙演練控制台",
    page_icon="🛡️",
    layout="wide",
)
load_css()

# ── 側邊欄 ─────────────────────────────────────────────────
st.sidebar.title("🛡️ 控制台")

page = st.sidebar.radio("功能", [
    "即時監控",
    "對話詳情",
    "系統狀態",
])

# ── 共用：取得所有 sessions ────────────────────────────────
@st.cache_data(ttl=5)
def fetch_sessions():
    try:
        res = requests.get(f"{BACKEND_API_URL}/sessions", timeout=5)
        if res.status_code == 200:
            return res.json().get("sessions", [])
    except Exception:
        pass
    return []


def fetch_monitor(session_id: str):
    try:
        res = requests.get(f"{BACKEND_API_URL}/monitor/{session_id}", timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def clear_session(session_id: str):
    try:
        requests.post(f"{BACKEND_API_URL}/clear", json={"session_id": session_id}, timeout=5)
        return True
    except Exception:
        return False


def check_health():
    try:
        res = requests.get(f"{BACKEND_API_URL}/health", timeout=3)
        return res.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# 頁面一：即時監控
# ═══════════════════════════════════════════════════════════
if page == "即時監控":
    st.title("📡 LINE Bot 即時監控")
    st.caption("自動顯示所有來自 LINE 的活躍對話。點擊左側「對話詳情」進入單一對話分析。")

    if st.button("🔄 重新整理"):
        st.cache_data.clear()

    sessions = fetch_sessions()

    if not sessions:
        st.info("目前沒有任何活躍的 LINE 對話。等待使用者從 LINE 發送訊息後，這裡會自動出現。")
    else:
        # 統計
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("總對話數", len(sessions))
        line_sessions = [s for s in sessions if s["session_id"].startswith("line_")]
        col_b.metric("LINE 對話", len(line_sessions))
        stage5 = [s for s in sessions if s.get("fraud_stage", "").startswith("5")]
        col_c.metric("已進入收網階段", len(stage5))

        st.divider()

        for s in sessions:
            render_session_card(s)


# ═══════════════════════════════════════════════════════════
# 頁面二：對話詳情
# ═══════════════════════════════════════════════════════════
elif page == "對話詳情":
    st.title("🔍 對話詳情")

    sessions = fetch_sessions()
    session_ids = [s["session_id"] for s in sessions] if sessions else []

    if not session_ids:
        st.info("尚無可檢視的對話。")
    else:
        selected = st.selectbox("選擇對話 Session", session_ids)

        if selected:
            data = fetch_monitor(selected)
            if data:
                state = data.get("state", {})
                history = data.get("history", [])

                # 頂部狀態列
                c1, c2, c3 = st.columns(3)
                c1.metric("詐騙階段", state.get("fraud_stage", "未知"))
                c2.metric("對話輪數", sum(1 for m in history if m["role"] == "user"))
                c3.metric("受害者標籤", state.get("victim_tags", "未標註"))

                st.divider()

                col_left, col_right = st.columns([1, 1])

                with col_left:
                    st.subheader("💬 對話記錄")
                    render_line_chat(history)

                with col_right:
                    st.subheader("🧠 AI 策略分析")

                    st.markdown("**劇情備忘**")
                    st.text(state.get("fact_sheet") or "尚未產生")

                    st.markdown("**對話摘要**")
                    st.text(state.get("conversation_summary") or "尚未產生（對話滿 8 輪後自動生成）")

                    st.markdown("**最新 AI 獨白**")
                    render_monitor_thought(state.get("fact_sheet", "暫無推論記錄"))

                st.divider()

                # 操作
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("🗑️ 清除此對話", key=f"clear_{selected}"):
                        if clear_session(selected):
                            st.success(f"已清除 {selected}")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("清除失敗")

                with col_act2:
                    with st.expander("📋 Raw JSON"):
                        st.json(data)


# ═══════════════════════════════════════════════════════════
# 頁面三：系統狀態
# ═══════════════════════════════════════════════════════════
elif page == "系統狀態":
    st.title("⚙️ 系統狀態")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("後端 API")
        healthy = check_health()
        render_status_badge("FastAPI Backend", healthy)

        st.subheader("LINE Bot 設定")
        st.markdown("""
        **Webhook URL**: `https://<你的公開域名>/line/webhook`

        設定步驟：
        1. 到 [LINE Developers Console](https://developers.line.biz/) 建立 Messaging API Channel
        2. 取得 **Channel Secret** 和 **Channel Access Token**
        3. 設定環境變數 `LINE_CHANNEL_SECRET` 和 `LINE_CHANNEL_ACCESS_TOKEN`
        4. 在 LINE Console 設定 Webhook URL 指向你的伺服器
        5. 重啟 docker compose
        """)

    with col2:
        st.subheader("環境變數檢查")
        env_vars = [
            ("BACKEND_API_URL", BACKEND_API_URL),
            ("LINE_CHANNEL_SECRET", "已設定" if os.getenv("LINE_CHANNEL_SECRET") else "❌ 未設定"),
            ("LINE_CHANNEL_ACCESS_TOKEN", "已設定" if os.getenv("LINE_CHANNEL_ACCESS_TOKEN") else "❌ 未設定"),
        ]
        for name, val in env_vars:
            st.text(f"{name}: {val}")

        st.subheader("快速操作")
        if st.button("🗑️ 清除所有對話"):
            sessions = fetch_sessions()
            for s in sessions:
                clear_session(s["session_id"])
            st.cache_data.clear()
            st.success("已清除所有對話！")
            st.rerun()
