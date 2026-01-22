# Prompt Evaluator

LangSmith 기반 프롬프트 정량 평가 시스템

## 빠른 시작

```bash
# 의존성 설치
poetry install

# 평가 실행
poetry run python main.py eval --name prep_analyzer

# LangSmith Experiment 실행
poetry run python main.py experiment --name prep_analyzer --mode full
```

## 프로젝트 구조

```
prompt-evaluator/
├── targets/                    # 평가 대상 프롬프트
│   └── {name}.txt
│
├── datasets/                   # 테스트 데이터
│   └── {name}_data/
│       ├── test_cases.json     # 입력 케이스
│       └── expected.json       # 기대 결과 (keywords, forbidden, reference)
│
├── configs/                    # 평가 설정
│   └── {name}.yaml             # evaluators, thresholds, output_schema
│
├── eval_prompts/               # LLM Judge 평가 프롬프트
│   ├── general/                # 범용 평가 기준
│   │   ├── instruction_following.txt
│   │   ├── factual_accuracy.txt
│   │   └── output_quality.txt
│   └── {domain}/               # 도메인 특화 평가 기준
│       └── {criterion}.txt
│
├── src/
│   ├── pipeline.py             # 평가 파이프라인
│   ├── data.py                 # 데이터 로더
│   ├── report.py               # 결과 리포터
│   └── evaluators/
│       ├── rule_based.py       # 규칙 기반 평가 (무료)
│       ├── similarity.py       # 유사도 평가 (저비용)
│       └── llm_judge.py        # LLM 평가 (고비용)
│
├── results/                    # 평가 결과 저장
├── tests/                      # 단위 테스트
├── main.py                     # CLI 진입점
└── docs/                       # 문서
```

## 평가자 종류

| 평가자 | 파일 | 비용 | 설명 |
|--------|------|------|------|
| Rule-based | `rule_based.py` | 무료 | 키워드, 금지어, 포맷 검증 |
| Similarity | `similarity.py` | 저비용 | 임베딩/문자열 유사도 (OpenAI, Vertex AI) |
| LLM Judge | `llm_judge.py` | 고비용 | 체크리스트 기반 LLM 평가 |

## 실행 모드

```bash
# quick: Rule-based만 (빠름)
poetry run python main.py eval --name prep_analyzer --mode quick

# standard: Rule-based + Similarity
poetry run python main.py eval --name prep_analyzer --mode standard

# full: 모든 평가자
poetry run python main.py eval --name prep_analyzer --mode full
```

## 설정 예시

**configs/{name}.yaml:**

```yaml
evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check
      - format_validity

  - type: similarity
    name: embedding_distance
    threshold: 0.75
    # provider: vertex  # GCP Vertex AI 사용 시

  - type: llm_judge
    criteria:
      - instruction_following
      - output_quality
    enabled: true

thresholds:
  pass_rate: 0.85
  min_score: 0.70

output_schema:
  required:
    - question_context  # format_validity에서 사용
```

## 환경 변수

```bash
# .env
LANGSMITH_API_KEY=your_key
OPENAI_API_KEY=your_key

# 임베딩 프로바이더 (선택)
EMBEDDING_PROVIDER=openai  # 또는 vertex
```

## CLI 명령어

```bash
# 평가 실행
poetry run python main.py eval --name {name} --mode {quick|standard|full}

# LangSmith Experiment
poetry run python main.py experiment --name {name}

# 평가 세트 목록
poetry run python main.py list

# 사용 가능한 LLM Judge 기준
poetry run python main.py criteria
```

## Claude Code 스킬

| 스킬 | 용도 |
|------|------|
| `/eval-criteria {name}` | LLM Judge 평가기준 생성 |
| `/gen-testcases {name}` | 테스트 케이스 생성 |
| `/ab-compare` | 프롬프트 A/B 비교 |

## 문서

- [기획안](docs/PROMPT_EVALUATION_PLAN.md)
- [구현 TODO](docs/TODO.md)
- [Claude Skill 가이드](docs/CLAUDE_SKILL_LLM_JUDGE.md)
