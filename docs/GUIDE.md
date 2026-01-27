# Prompt Evaluator 사용 가이드

> LLM 프롬프트 평가 체계 활용 방법

---

## 1. 시작하기

### 1.1. 환경 설정

```bash
# 의존성 설치
poetry install

# 환경변수 설정
cp .env.example .env
# .env 파일에 LANGSMITH_API_KEY, OPENAI_API_KEY 등 설정
```

### 1.2. 프로젝트 구조

```
prompt-evaluator/
├── targets/                    # 평가 대상 프롬프트
│   └── {name}/
│       ├── prompt.*            # 프롬프트 템플릿 (.txt, .py, .xml, .md)
│       └── config.yaml         # 평가 설정
│
├── datasets/                   # 테스트 데이터
│   └── {name}/
│       ├── test_cases.json     # 입력 데이터
│       └── expected.json       # 기대 결과 (키워드, 금지어 등)
│
├── eval_prompts/               # LLM Judge 평가 프롬프트
│   ├── general/                # 범용 평가 기준
│   └── {domain}/               # 도메인별 평가 기준
│
└── configs/                    # 전역 설정
    ├── config.py               # 모델, 임계값 기본값
    └── schema.yaml             # config 스키마 참고
```

---

## 2. 새 프롬프트 평가 추가

### 2.1. 폴더 생성

```bash
mkdir -p targets/my_prompt
mkdir -p datasets/my_prompt
```

### 2.2. 프롬프트 파일 작성

`targets/my_prompt/prompt.txt`:
```
당신은 {role}입니다.

사용자 질문: {query}
컨텍스트: {context}

위 정보를 바탕으로 답변해주세요.
```

**지원 형식:**
| 확장자 | 설명 |
|--------|------|
| `.txt` | 단일 템플릿 |
| `.md` | 마크다운 형식 |
| `.py` | Python 변수 (`SYSTEM_PROMPT`, `USER_PROMPT` 등) |
| `.xml` | XML 구조 (`<system>`, `<user>` 태그) |

### 2.3. 평가 설정 작성

`targets/my_prompt/config.yaml`:
```yaml
name: my_prompt
description: 프롬프트 설명
output_format: text  # text | json
eval_prompts_domain: general  # eval_prompts/{domain}/ 폴더명

evaluators:
  # Rule-based 평가 (무료)
  - type: rule_based
    checks:
      - keyword_inclusion      # 필수 키워드 포함
      - forbidden_word_check   # 금지어 미포함

  # LLM Judge 평가 (유료)
  - type: llm_judge
    enabled: true
    criteria:
      - instruction_following
      - output_quality

thresholds:
  pass_rate: 0.85    # 전체 케이스 중 85% 통과
  min_score: 0.70    # 개별 케이스 최소 점수

run_mode: quick  # quick: Rule만 | full: Rule + LLM Judge
```

### 2.4. 테스트 데이터 작성

`datasets/my_prompt/test_cases.json`:
```json
[
  {
    "id": "case_001",
    "description": "기본 테스트",
    "inputs": {
      "role": "친절한 고객상담사",
      "query": "환불 절차가 어떻게 되나요?",
      "context": "7일 이내 환불 가능"
    }
  },
  {
    "id": "case_002",
    "description": "복잡한 상황 테스트",
    "inputs": {
      "role": "친절한 고객상담사",
      "query": "배송이 늦어지고 있는데 환불도 가능한가요?",
      "context": "배송 지연 시 전액 환불 가능, 7일 이내"
    }
  }
]
```

`datasets/my_prompt/expected.json`:
```json
{
  "case_001": {
    "keywords": ["환불", "7일"],
    "forbidden": ["불가능", "안됩니다"]
  },
  "case_002": {
    "keywords": ["환불", "배송", "지연"],
    "forbidden": ["불가능"]
  }
}
```

### 2.5. 검증 및 실행

```bash
# 설정 검증
poetry run python main.py validate --name my_prompt

# 평가 실행 (Langfuse + LangSmith 동시 - 기본값)
poetry run python main.py experiment --name my_prompt

# Langfuse만 실행
poetry run python main.py experiment --name my_prompt --backend langfuse

# LangSmith만 실행 (자동 버전 관리)
poetry run python main.py experiment --name my_prompt --backend langsmith

# 정식 평가 (full 모드 - Rule + LLM Judge)
poetry run python main.py experiment --name my_prompt --mode full
```

---

## 3. CLI 명령어

### 3.1. 평가 실행

```bash
# 기본 실행 (Langfuse + LangSmith 동시)
poetry run python main.py experiment --name {name}

# 백엔드 지정
poetry run python main.py experiment --name {name} --backend langfuse  # Langfuse만
poetry run python main.py experiment --name {name} --backend langsmith # LangSmith만

# 모드 지정
poetry run python main.py experiment --name {name} --mode full

# 특정 프롬프트 버전으로 평가
poetry run python main.py experiment --name {name} --version v1.0

# 실험 이름 접두사 지정
poetry run python main.py experiment --name {name} --prefix "feature-branch"
```

### 3.2. 설정 검증

```bash
# 단일 config 검증
poetry run python main.py validate --name {name}

# 모든 config 검증
poetry run python main.py validate --all
```

### 3.3. 프롬프트 버전 관리

```bash
# LangSmith에 업로드
poetry run python main.py prompt push --name {name} --tag v1.0

# LangSmith에서 가져오기
poetry run python main.py prompt pull --name {name} --tag v1.0

# 버전 목록 조회
poetry run python main.py prompt versions --name {name}

# .py/.xml 파일의 프롬프트 키 확인
poetry run python main.py prompt keys --name {name}
```

### 3.4. 유틸리티

```bash
# 평가 가능한 세트 목록
poetry run python main.py list

# 사용 가능한 LLM Judge 평가 기준 확인
poetry run python main.py criteria

# 데이터셋 LangSmith 업로드
poetry run python main.py upload --name {name}
```

---

## 4. 평가 기준 설정

### 4.1. Rule-based 평가 (무료)

| 항목 | 설명 |
|------|------|
| `keyword_inclusion` | `expected.json`의 `keywords` 포함 비율 |
| `forbidden_word_check` | `expected.json`의 `forbidden` 미포함 여부 |

### 4.2. LLM Judge 평가 (유료)

평가 기준 프롬프트는 `eval_prompts/{domain}/` 폴더에 `.txt` 파일로 작성합니다.

**일반 기준 (`eval_prompts/general/`):**
- `instruction_following.txt` - 지시사항 준수도
- `output_quality.txt` - 전반적 출력 품질
- `factual_accuracy.txt` - 사실 정확성

**도메인별 기준 예시 (`eval_prompts/oneonone/`):**
- `tone_appropriateness.txt` - 톤/어조 적절성
- `coaching_quality.txt` - 코칭 품질
- `sensitive_topic_handling.txt` - 민감 주제 처리

### 4.3. 새 평가 기준 추가

1. `eval_prompts/{domain}/{criterion}.txt` 파일 생성
2. 평가 프롬프트 작성 (점수 1-5 또는 0-1 기준)
3. `config.yaml`의 `llm_judge.criteria`에 추가

---

## 5. 실행 모드

| 모드 | 평가자 | 용도 | 비용 |
|------|--------|------|:----:|
| `quick` | Rule-based만 | 개발 중 빠른 검증 | 무료 |
| `full` | Rule + LLM Judge | 정식 평가, 버전 비교 | 유료 |

```yaml
# config.yaml에서 기본 모드 설정
run_mode: quick
```

```bash
# CLI에서 오버라이드
poetry run python main.py experiment --name {name} --mode full
```

---

## 6. 결과 확인

### 6.1. 평가 대시보드

평가 결과는 **LangSmith** 또는 **Langfuse** 대시보드에서 확인합니다:
- 각 테스트 케이스별 점수
- 평가 기준별 상세 결과
- 실패 케이스 분석
- 버전 간 비교

> **Note**: 기본값 `--backend both`로 실행 시 두 플랫폼에서 동시에 결과 확인 가능

### 6.2. 회귀 테스트

프롬프트 수정 시 이전 버전과 비교:

| 지표 | 허용 변동폭 | 조치 |
|------|:----------:|------|
| 평균 점수 | -0.2 이내 | 초과 시 리뷰 필요 |
| Pass Rate | -5% 이내 | 초과 시 경고 |
| 특정 케이스 실패 | Pass → Fail | 반드시 리뷰 필요 |

---

## 7. 기존 프롬프트 마이그레이션

### 7.1. .py 파일 프롬프트

기존 `.py` 파일이 있는 경우:

```
# Before (평가 불가)
targets/prep_output/
├── coaching_analyzer.py
└── question_generator.py

# After (평가 가능)
targets/coaching_analyzer/
├── prompt.py              # 기존 파일 이동 또는 복사
└── config.yaml            # 새로 작성
```

### 7.2. 변환 단계

1. 새 폴더 생성: `mkdir -p targets/{name}`
2. 프롬프트 파일 이동: `prompt.py`로 이름 변경
3. `config.yaml` 작성
4. 테스트 데이터 생성: `datasets/{name}/`
5. 검증: `poetry run python main.py validate --name {name}`

---

## 8. 문제 해결

### config 검증 실패

```
✗ 프롬프트 파일 없음
```
→ `targets/{name}/prompt.*` 파일 확인

```
⚠ eval_prompt 파일 없음
```
→ `eval_prompts/{domain}/{criterion}.txt` 파일 생성 필요

### 평가 실행 오류

```
KeyError: '{placeholder}'
```
→ `test_cases.json`의 `inputs`가 프롬프트 placeholder와 일치하는지 확인

---

## 9. 참고

- [기능 명세서](./SPECIFICATION.md) - 시스템 상세 스펙
- [LangSmith 프롬프트 관리](./LANGSMITH_PROMPTS.md) - 버전 관리 상세
- [Langfuse 마이그레이션 계획](./langfuse-migration-plan.md) - Langfuse 통합 상세
- [CLI 레퍼런스](./features/cli-reference.md) - 전체 CLI 명령어
