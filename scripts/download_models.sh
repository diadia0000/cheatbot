#!/bin/bash

# download Qwen2.5-14B-Instruct-AWQ (4-bit AWQ safetensors) model from Hugging Face Hub
# requirement : huggingface_hub ( yourpath/.venv)

MODEL_REPO="Qwen/Qwen2.5-32B-Instruct-AWQ"
DOWNLOAD_DIR="./models/Qwen2.5-32B-Instruct-AWQ"
VENV_PYTHON="./.venv/bin/python"

echo "=== download model ==="
echo "Repo: $MODEL_REPO"
echo "Destination: $DOWNLOAD_DIR"

mkdir -p "$DOWNLOAD_DIR"

# check venv python exist
if [ ! -f "$VENV_PYTHON" ]; then
    echo "venv python can not find: $VENV_PYTHON"
    echo "make sure you already create venv in root dir：python3 -m venv .venv"
    exit 1
fi

# using huggingface_hub snapshot_download download entire repo
$VENV_PYTHON -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='${MODEL_REPO}',
    local_dir='${DOWNLOAD_DIR}',
    resume_download=True,
)
print('=== complet download ===')
"

echo "=== dir list ==="
ls -lh "$DOWNLOAD_DIR"
