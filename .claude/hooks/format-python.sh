#!/bin/bash
# PostToolUse hook: Python 파일 쓰기/수정 후 ruff로 포맷팅 + 린팅
# Write, Edit tool 사용 후 .py 파일에 대해 자동 실행

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('file_path', ''))" 2>/dev/null)

# .py 파일이 아니면 스킵
if [[ ! "$FILE_PATH" == *.py ]]; then
  exit 0
fi

# 파일이 존재하는지 확인
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# ruff가 설치되어 있는지 확인
if ! command -v ruff &>/dev/null; then
  # poetry 환경에서 실행 시도
  if command -v poetry &>/dev/null; then
    RUFF_CMD="poetry run ruff"
  else
    echo "ruff not found, skipping format" >&2
    exit 0
  fi
else
  RUFF_CMD="ruff"
fi

# ruff format 실행
$RUFF_CMD format "$FILE_PATH" 2>&1 | while read -r line; do
  echo "[format] $line" >&2
done

# ruff check --fix 실행 (자동 수정 가능한 것만)
$RUFF_CMD check --fix "$FILE_PATH" 2>&1 | while read -r line; do
  echo "[lint] $line" >&2
done

exit 0
