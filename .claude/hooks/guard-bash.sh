#!/bin/bash
# PreToolUse hook: 위험한 Bash 명령어 실행 전 차단
# rm -rf, git push --force, git reset --hard 등 차단

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))" 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# 차단할 패턴 목록
BLOCKED_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \."
  "git push.*--force"
  "git push.*-f "
  "git reset --hard"
  "git clean -fd"
  "git checkout \."
  "> /dev/sda"
  "mkfs\."
  ":(){ :|:& };:"
  "dd if=/dev/"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    # JSON으로 deny 응답 반환
    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "차단된 명령어 패턴: $pattern"
  }
}
EOF
    exit 0
  fi
done

# .env 파일 삭제/덮어쓰기 방지
if echo "$COMMAND" | grep -qE "(rm|>)\s+.*\.env"; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": ".env 파일 삭제/덮어쓰기 시도 차단"
  }
}
EOF
  exit 0
fi

exit 0
