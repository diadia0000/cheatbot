import sqlite3
import os
from typing import List, Dict

DB_PATH = os.getenv("DB_PATH", "/data/chat_history.db")

import chromadb
chroma_client = None
collection = None

def init_db():
    global chroma_client, collection
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Initialize ChromaDB
    try:
        chroma_path = os.path.join(os.path.dirname(DB_PATH), "chroma_db")
        os.makedirs(chroma_path, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection(name="chat_history")
    except Exception as e:
        print(f"Warning: Failed to initialize ChromaDB: {e}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 建立 Persona 狀態表，紀錄推演階段或是受害者的標籤
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_state (
            session_id TEXT PRIMARY KEY,
            fraud_stage TEXT DEFAULT '1_greeting',
            victim_tags TEXT DEFAULT '',
            conversation_summary TEXT DEFAULT '',
            fact_sheet TEXT DEFAULT ''
        )
    ''')
    # 避移：為既有資料庫新增欄位（若已存在則忽略）
    for col in ["conversation_summary", "fact_sheet"]:
        try:
            cursor.execute(f"ALTER TABLE session_state ADD COLUMN {col} TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Save to Chroma DB for Vector Search
    if collection is not None and content.strip():
        try:
            collection.add(
                documents=[content],
                metadatas=[{"session_id": session_id, "role": role}],
                ids=[f"{session_id}_{msg_id}"]
            )
        except Exception as e:
            print(f"ChromaDB Save Error: {e}")

def get_chat_history(session_id: str, limit: int = 50) -> List[Dict[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    history = [{"role": row[0], "content": row[1]} for row in rows]
    return history

def update_session_state(session_id: str, **kwargs):
    """更新 session 狀態，只更新傳入的欄位，未傳入的保留原值。"""
    current = get_session_state(session_id)
    current.update({k: v for k, v in kwargs.items() if v is not None})
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR REPLACE INTO session_state
           (session_id, fraud_stage, victim_tags, conversation_summary, fact_sheet)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id,
         current.get("fraud_stage", "1_greeting"),
         current.get("victim_tags", ""),
         current.get("conversation_summary", ""),
         current.get("fact_sheet", ""))
    )
    conn.commit()
    conn.close()

def get_session_state(session_id: str) -> Dict[str, str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT fraud_stage, victim_tags, conversation_summary, fact_sheet FROM session_state WHERE session_id = ?",
        (session_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "fraud_stage": row[0],
            "victim_tags": row[1],
            "conversation_summary": row[2] or "",
            "fact_sheet": row[3] or "",
        }
    return {"fraud_stage": "1_greeting", "victim_tags": "", "conversation_summary": "", "fact_sheet": ""}

def get_relevant_history(session_id: str, query: str, n_results: int = 3) -> List[Dict[str, str]]:
    if collection is None or not query.strip():
        return []
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"session_id": session_id}
        )
        if not results['documents'] or not results['documents'][0]:
            return []
            
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        return [{"role": m["role"], "content": d} for d, m in zip(docs, metas)]
    except Exception as e:
        print(f"ChromaDB Query Error: {e}")
        return []

def get_all_sessions() -> List[Dict]:
    """取得所有 session 清單，含最新訊息時間與對話輪數。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            ss.session_id,
            ss.fraud_stage,
            ss.victim_tags,
            (SELECT COUNT(*) FROM messages m WHERE m.session_id = ss.session_id AND m.role = 'user') AS turn_count,
            (SELECT MAX(m.timestamp) FROM messages m WHERE m.session_id = ss.session_id) AS last_active
        FROM session_state ss
        ORDER BY last_active DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "session_id": r[0],
            "fraud_stage": r[1],
            "victim_tags": r[2],
            "turn_count": r[3] or 0,
            "last_active": r[4] or "",
        }
        for r in rows
    ]
