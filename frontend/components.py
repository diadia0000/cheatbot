from html import escape
from urllib.parse import urlparse

import streamlit as st

# ── 階段 → 中文標籤 & 顏色 ────────────────────────────────
STAGE_LABELS = {
    "1": ("破冰寒暄", "#4caf50"),
    "2": ("展示實力", "#2196f3"),
    "3": ("試探口風", "#ff9800"),
    "4": ("施壓引導", "#f44336"),
    "5": ("收網匯款", "#9c27b0"),
}


def _stage_info(fraud_stage: str):
    """從 fraud_stage 字串（如 '3_probe'）取得階段數字、中文名、顏色。"""
    num = fraud_stage[0] if fraud_stage and fraud_stage[0].isdigit() else "1"
    label, color = STAGE_LABELS.get(num, ("未知", "#9e9e9e"))
    return num, label, color


def load_css():
    st.markdown("""
        <style>
        /* LINE 聊天泡泡 */
        .chat-container {
            background-color: #8bb7f0;
            padding: 20px;
            border-radius: 10px;
            height: 500px;
            overflow-y: scroll;
            display: flex;
            flex-direction: column;
        }
        .bubble-user {
            background-color: #79e35b;
            color: black;
            padding: 10px 15px;
            border-radius: 20px;
            margin: 5px 0 5px auto;
            max-width: 70%;
            word-wrap: break-word;
            align-self: flex-end;
            box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
        }
        .bubble-bot {
            background-color: white;
            color: black;
            padding: 10px 15px;
            border-radius: 20px;
            margin: 5px auto 5px 0;
            max-width: 70%;
            word-wrap: break-word;
            align-self: flex-start;
            box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
        }

        /* 監控獨白 */
        .monitor-thought {
            background-color: #fce4ec;
            color: #c2185b;
            padding: 10px;
            border-left: 4px solid #c2185b;
            margin: 10px 0;
            font-size: 0.9em;
            border-radius: 4px;
        }

        /* Session 卡片 */
        .session-card {
            background: white;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .session-card .left { flex: 1; }
        .session-card .stage-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            color: white;
            font-size: 0.85em;
            font-weight: 600;
        }
        .session-card .meta {
            color: #666;
            font-size: 0.85em;
            margin-top: 4px;
        }

        /* 狀態指示燈 */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            margin: 4px 0;
        }
        .status-ok { background: #e8f5e9; color: #2e7d32; }
        .status-err { background: #ffebee; color: #c62828; }
        </style>
    """, unsafe_allow_html=True)


def _escape_multiline_text(value: str) -> str:
    return escape(value).replace("\n", "<br>")


def _is_safe_image_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


# ── 聊天記錄渲染 ──────────────────────────────────────────
def render_line_chat(history):
    html = '<div class="chat-container">'
    for msg in history:
        content = _escape_multiline_text(str(msg.get("content", "")))
        image_html = ""
        image_url = msg.get("image_url")
        if isinstance(image_url, str) and _is_safe_image_url(image_url):
            safe_url = escape(image_url, quote=True)
            image_html = (
                f'<div style="margin-top:8px;">'
                f'<img src="{safe_url}" alt="對帳單" '
                f'style="max-width:220px;border-radius:12px;display:block;">'
                f'</div>'
            )
        if msg["role"] == "user":
            html += f'<div class="bubble-user">{content}</div>'
        elif msg["role"] == "assistant":
            html += f'<div class="bubble-bot">{content}{image_html}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ── AI 獨白 ──────────────────────────────────────────────
def render_monitor_thought(thought):
    if thought:
        safe_thought = _escape_multiline_text(str(thought))
        st.markdown(
            f'<div class="monitor-thought">🕵️ <strong>AI 獨白：</strong><br>{safe_thought}</div>',
            unsafe_allow_html=True,
        )


# ── Session 卡片（即時監控頁面用）─────────────────────────
def render_session_card(session: dict):
    sid = session.get("session_id", "")
    fraud_stage = session.get("fraud_stage", "1_greeting")
    turn_count = session.get("turn_count", 0)
    last_active = session.get("last_active", "")

    num, label, color = _stage_info(fraud_stage)
    source = "LINE" if sid.startswith("line_") else "Web"

    html = f"""
    <div class="session-card">
        <div class="left">
            <strong>{escape(sid)}</strong>
            <span style="margin-left:8px;font-size:0.8em;color:#888;">[{source}]</span>
            <div class="meta">輪次: {turn_count} ｜最後活躍: {escape(last_active) if last_active else '—'}</div>
        </div>
        <div>
            <span class="stage-badge" style="background:{color};">階段{num} {label}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── 系統狀態徽章 ─────────────────────────────────────────
def render_status_badge(name: str, is_ok: bool):
    cls = "status-ok" if is_ok else "status-err"
    icon = "✅" if is_ok else "❌"
    label = "正常運作" if is_ok else "無法連線"
    st.markdown(
        f'<div class="status-badge {cls}">{icon} {escape(name)}: {label}</div>',
        unsafe_allow_html=True,
    )
