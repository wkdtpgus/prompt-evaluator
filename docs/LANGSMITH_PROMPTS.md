# LangSmith 프롬프트 버전 관리

로컬 프롬프트를 LangSmith에 업로드하고 버전을 관리합니다.

## CLI 명령어

### 프롬프트 업로드

```bash
# 기본 업로드
poetry run python main.py prompt push --name prep_chatbot

# 버전 태그 지정
poetry run python main.py prompt push --name prep_chatbot --tag v1.0

# 설명 추가
poetry run python main.py prompt push --name prep_chatbot --tag v1.0 --desc "초기 버전"

# .py 파일의 특정 프롬프트만 업로드
poetry run python main.py prompt push --name prep_chatbot --key SYSTEM_PROMPT
```

### 프롬프트 가져오기

```bash
# 최신 버전 가져오기
poetry run python main.py prompt pull --name prep_chatbot

# 특정 버전 가져오기
poetry run python main.py prompt pull --name prep_chatbot --tag v1.0

# 로컬 파일로 저장
poetry run python main.py prompt pull --name prep_chatbot --save
```

### 버전 목록 조회

```bash
poetry run python main.py prompt versions --name prep_chatbot
```

출력 예시:
```
프롬프트 버전 목록: prep_chatbot
------------------------------------------------------------
  1. a1b2c3d4 | v1.0 | 2026-01-26 10:00:00
  2. e5f6g7h8 | production | 2026-01-25 15:30:00
  3. i9j0k1l2 | (태그 없음) | 2026-01-24 09:00:00
```

### 프롬프트 키 확인

`.py` 또는 `.xml` 파일에 여러 프롬프트가 정의된 경우:

```bash
poetry run python main.py prompt keys --name prep_chatbot
```

출력 예시:
```
프롬프트 파일: targets/prep_chatbot/prompt.py
형식: .py
------------------------------------------------------------
  • SYSTEM_PROMPT: You are a 'Strategic 1on1 Meeting Advisor'...
  • USER_PROMPT: Generate a formal 1on1 Prep Report based on...

특정 프롬프트 업로드: prompt push --name prep_chatbot --key SYSTEM_PROMPT
```

## 코드에서 사용하기

```python
from src.utils.langsmith_prompts import push_prompt, pull_prompt, list_prompt_versions

# 업로드
url = push_prompt("prep_chatbot", version_tag="v1.0")

# 가져오기
template = pull_prompt("prep_chatbot", version_tag="v1.0")

# 버전 목록
versions = list_prompt_versions("prep_chatbot")
```

## 파일 구조

```
src/
└── utils/
    ├── __init__.py
    └── langsmith_prompts.py   # push/pull/list_versions 함수
```

## 지원 형식

| 형식 | 설명 | 예시 |
|------|------|------|
| `.txt` | 단일 템플릿 | `prompt.txt` |
| `.md` | 마크다운 형식 | `prompt.md` |
| `.py` | Python 변수 | `SYSTEM_PROMPT = """..."""` |
| `.xml` | XML 구조 | `<prompts><system>...</system></prompts>` |
