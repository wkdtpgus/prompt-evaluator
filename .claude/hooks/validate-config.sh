#!/bin/bash
# PostToolUse hook: YAML/JSON 설정 파일 작성 후 구문 검증
# config.yaml, test_cases.json, expected.json 등 작성 시 자동 실행

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('file_path', ''))" 2>/dev/null)

# 파일이 없으면 스킵
if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# YAML 파일 검증
if [[ "$FILE_PATH" == *.yaml || "$FILE_PATH" == *.yml ]]; then
  python3 -c "
import yaml, sys
try:
    with open('$FILE_PATH', 'r') as f:
        yaml.safe_load(f)
except yaml.YAMLError as e:
    print(f'YAML syntax error: {e}', file=sys.stderr)
    sys.exit(2)
" 2>&1
  exit $?
fi

# JSON 파일 검증
if [[ "$FILE_PATH" == *.json ]]; then
  python3 -c "
import json, sys
try:
    with open('$FILE_PATH', 'r') as f:
        json.load(f)
except json.JSONDecodeError as e:
    print(f'JSON syntax error: {e}', file=sys.stderr)
    sys.exit(2)
" 2>&1
  exit $?
fi

exit 0
