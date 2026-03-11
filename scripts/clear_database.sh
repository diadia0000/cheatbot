#!/usr/bin/env bash
# =============================================================================
# clear_database.sh
# 安全清空 cheet_bot 的測試資料（SQLite + ChromaDB）
#
# 用法：
#   ./scripts/clear_database.sh               # 互動確認後執行
#   ./scripts/clear_database.sh --force       # 跳過確認直接清空
#   ./scripts/clear_database.sh --dry-run     # 只顯示將要執行的動作，不實際清空
# =============================================================================

set -euo pipefail

# ─── 路徑設定 ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${PROJECT_ROOT}/data"
SQLITE_DB="${DATA_DIR}/chat_history.db"
CHROMA_DIR="${DATA_DIR}/chroma_db"

# ─── 顏色輸出 ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ─── 旗標 ────────────────────────────────────────────────────────────────────
FORCE=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=true ;;
    --dry-run) DRY_RUN=true ;;
    *)
      echo -e "${RED}未知參數：$arg${RESET}"
      echo "用法：$0 [--force] [--dry-run]"
      exit 1
      ;;
  esac
done

# ─── 顯示函式 ────────────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
dryrun()  { echo -e "${YELLOW}[DRY-RUN]${RESET} $*"; }

# ─── 找可用的 Python ──────────────────────────────────────────────────────────
find_python() {
  # 優先使用 venv 內的 python
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    echo "${PROJECT_ROOT}/.venv/bin/python"
  elif command -v python3 &>/dev/null; then
    echo "python3"
  elif command -v python &>/dev/null; then
    echo "python"
  else
    echo -e "${RED}[ERROR] 找不到 Python，請確認環境設定。${RESET}" >&2
    exit 1
  fi
}

PYTHON="$(find_python)"
info "使用 Python：${PYTHON}"

# ─── 取得目前資料量（清空前統計）─────────────────────────────────────────────
show_stats() {
  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║         目前 Database 資料統計           ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"

  # SQLite 統計（用 Python）
  if [[ -f "$SQLITE_DB" ]]; then
    local stats
    stats=$("$PYTHON" - <<PYEOF
import sqlite3, os
db = "$SQLITE_DB"
try:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM messages")
    msg = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM session_state")
    sess = cur.fetchone()[0]
    conn.close()
    size = os.path.getsize(db)
    print(f"{msg}|{sess}|{size}")
except Exception as e:
    print(f"0|0|0")
PYEOF
)
    IFS='|' read -r msg_count session_count db_bytes <<< "$stats"
    local db_size_kb=$(( db_bytes / 1024 ))
    echo ""
    echo -e "  ${BOLD}SQLite:${RESET} ${SQLITE_DB}"
    echo -e "    messages 筆數  : ${RED}${msg_count}${RESET}"
    echo -e "    session 數量   : ${RED}${session_count}${RESET}"
    echo -e "    檔案大小       : ${db_size_kb} KB"
  else
    warn "SQLite 資料庫不存在：${SQLITE_DB}"
  fi

  # ChromaDB 統計
  if [[ -d "$CHROMA_DIR" ]]; then
    local chroma_bytes
    chroma_bytes=$(du -sb "$CHROMA_DIR" 2>/dev/null | cut -f1 || echo 0)
    local chroma_size_kb=$(( chroma_bytes / 1024 ))
    echo ""
    echo -e "  ${BOLD}ChromaDB:${RESET} ${CHROMA_DIR}"
    echo -e "    目錄大小       : ${RED}${chroma_size_kb} KB${RESET}"
  else
    warn "ChromaDB 目錄不存在：${CHROMA_DIR}"
  fi

  echo ""
}

# ─── 清空 SQLite ─────────────────────────────────────────────────────────────
clear_sqlite() {
  if [[ ! -f "$SQLITE_DB" ]]; then
    warn "SQLite 資料庫不存在，跳過。"
    return
  fi

  if $DRY_RUN; then
    dryrun "會執行：DELETE FROM messages"
    dryrun "會執行：DELETE FROM session_state"
    dryrun "會執行：VACUUM（壓縮檔案）"
    return
  fi

  info "清空 SQLite（messages + session_state）..."
  "$PYTHON" - <<PYEOF
import sqlite3
db = "$SQLITE_DB"
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("DELETE FROM messages")
cur.execute("DELETE FROM session_state")
conn.commit()
cur.execute("VACUUM")
conn.commit()
conn.close()
print("SQLite 清空成功")
PYEOF
  success "SQLite 清空完成！"
}

# ─── 清空 ChromaDB ────────────────────────────────────────────────────────────
clear_chroma() {
  if [[ ! -d "$CHROMA_DIR" ]]; then
    warn "ChromaDB 目錄不存在，跳過。"
    return
  fi

  if $DRY_RUN; then
    dryrun "會執行：rm -rf ${CHROMA_DIR}/*"
    dryrun "會執行：mkdir -p ${CHROMA_DIR}（保留空目錄讓 init_db 重建）"
    return
  fi

  info "清空 ChromaDB 目錄..."
  rm -rf "${CHROMA_DIR:?}/"*
  # 保留空目錄，init_db() 啟動時會自動重建 collection
  mkdir -p "$CHROMA_DIR"
  success "ChromaDB 清空完成！"
}

# ─── 主流程 ──────────────────────────────────────────────────────────────────
main() {
  echo ""
  echo -e "${BOLD}${RED}════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}${RED}       cheet_bot Database 清空工具          ${RESET}"
  echo -e "${BOLD}${RED}════════════════════════════════════════════${RESET}"

  show_stats

  if $DRY_RUN; then
    echo -e "${YELLOW}[DRY-RUN 模式] 以下是將執行的操作（不會實際修改資料）：${RESET}"
    echo ""
    clear_sqlite
    clear_chroma
    echo ""
    echo -e "${YELLOW}DRY-RUN 結束，未做任何實際變更。${RESET}"
    exit 0
  fi

  # 確認提示
  if ! $FORCE; then
    echo -e "${RED}${BOLD}⚠️  警告：此操作將永久刪除所有對話記錄與向量記憶，無法復原！${RESET}"
    echo ""
    read -rp "$(echo -e "${BOLD}確認要清空所有資料嗎？請輸入 YES 繼續：${RESET} ")" confirm
    if [[ "$confirm" != "YES" ]]; then
      echo ""
      info "操作已取消。"
      exit 0
    fi
  fi

  echo ""
  info "開始清空資料庫..."
  echo ""

  clear_sqlite
  clear_chroma

  echo ""
  echo -e "${GREEN}${BOLD}✅  所有資料已清空完畢！${RESET}"
  show_stats
}

main
