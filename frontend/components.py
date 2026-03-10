import streamlit as st

def load_css():
    st.markdown("""
        <style>
        .chat-container {
            background-color: #8bb7f0;
            padding: 20px;
            border-radius: 10px;
            height: 600px;
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
        .monitor-thought {
            background-color: #fce4ec;
            color: #c2185b;
            padding: 10px;
            border-left: 4px solid #c2185b;
            margin: 10px 0;
            font-size: 0.9em;
            border-radius: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

def render_line_chat(history):
    html = '<div class="chat-container">'
    for msg in history:
        if msg["role"] == "user":
            html += f'<div class="bubble-user">{msg["content"]}</div>'
        elif msg["role"] == "assistant":
            html += f'<div class="bubble-bot">{msg["content"]}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_monitor_thought(thought):
    if thought:
        st.markdown(f'<div class="monitor-thought">🕵️ <strong>AI 獨白：</strong><br>{thought}</div>', unsafe_allow_html=True)
