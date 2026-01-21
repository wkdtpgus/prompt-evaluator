# 프롬프트 평가 시스템 구현 TODO

> 기획안 기반 단계별 구현 태스크

---

## Phase 1: 환경 설정 및 기초 구축

### 1.1 프로젝트 초기화
- [x] 프로젝트 폴더 생성 (`prompt-evaluator`)
- [x] `pyproject.toml` 작성 (의존성 정의)
- [x] `.env.example` 생성 (환경 변수 템플릿)
- [x] `.gitignore` 설정

### 1.2 의존성 설치
- [x] Python 가상환경 생성
- [x] 필수 패키지 설치
  - [x] `langsmith`
  - [x] `langchain`
  - [x] `openai`
  - [x] `python-dotenv`
  - [x] `pyyaml`
  - [x] `typer` (CLI)

**명령어 비교 (venv vs Poetry):**

| 작업 | venv + pip | Poetry |
|------|------------|--------|
| 가상환경 생성 | `python3 -m venv .venv` | `poetry install` (자동 생성) |
| 의존성 설치 | `.venv/bin/pip install -e ".[dev]"` | `poetry install` |
| 패키지 추가 | `pip install <pkg>` + requirements.txt 수동 | `poetry add <pkg>` |
| 스크립트 실행 | `.venv/bin/python main.py` | `poetry run python main.py` |
| 쉘 진입 | `source .venv/bin/activate` | `poetry shell` |
| Lock 파일 | 없음 (`pip freeze` 필요) | `poetry.lock` 자동 생성 |
| 가상환경 위치 | 프로젝트 내 `.venv/` | `~/Library/Caches/pypoetry/virtualenvs/` |

**사용한 명령어 (Poetry 기반):**
```bash
poetry install
```

**생성된 파일:**
- `poetry.lock` - 의존성 버전 고정 파일 (재현 가능한 빌드)

### 1.3 디렉토리 구조 생성
- [x] `prompts/` 폴더 생성
- [x] `prompts/_shared/` 폴더 생성
- [x] `src/` 폴더 생성
- [x] `src/evaluators/` 폴더 생성
- [x] `src/utils/` 폴더 생성
- [x] `results/` 폴더 생성
- [x] `tests/` 폴더 생성

**사용한 명령어:**
```bash
mkdir -p prompts/_shared src/evaluators src/utils results tests
```

### 1.4 LangSmith 연동 테스트
- [x] `.env` 파일에 API Key 설정
- [x] LangSmith 연결 테스트 스크립트 작성
- [x] 테스트 실행 및 대시보드 확인

**사용한 명령어:**
```bash
poetry run python scripts/test_langsmith.py
```

**테스트 결과:**
```
✅ LangSmith 연결 성공
✅ OpenAI API 연결 성공
```

---

## Phase 2: 데이터셋 구축

### 2.1 샘플 평가 세트 생성 (분리 구조)
- [x] `prompts/prep_analyzer_prompt.txt` 작성 (평가 대상 프롬프트)
- [x] `datasets/prep_analyzer_data/` 폴더 생성 (평가 데이터)
- [x] `datasets/prep_analyzer_data/test_cases.json` 작성 (15개 케이스)
- [x] `datasets/prep_analyzer_data/expected.json` 작성 (기대 결과)
- [x] `datasets/prep_analyzer_data/eval_config.yaml` 작성 (평가 설정)

**디렉토리 구조 (분리됨):**
```
prompts/                           # 평가 대상 (프롬프트)
└── prep_analyzer_prompt.txt

datasets/                          # 평가 데이터
└── prep_analyzer_data/
    ├── test_cases.json
    ├── expected.json
    └── eval_config.yaml
```

**생성된 테스트 케이스:**
- case_001~010: 한국어 케이스 (기본 흐름, 조기 종료, 모호한 답변, 민감 주제 등)
- case_011~012: 엣지 케이스 (서베이만, 빈 입력)
- case_013: 영어 케이스
- case_014: 베트남어 케이스
- case_015: 프로필 카드 포함 케이스

### 2.2 기본 설정 파일
- [x] `prompts/_shared/default_config.yaml` 작성

### 2.3 데이터 로더 구현
- [x] `src/utils/loader.py` 구현
  - [x] `load_evaluation_set()` - 로컬 파일 로드
  - [x] `upload_to_langsmith()` - LangSmith Dataset 업로드
  - [x] `list_evaluation_sets()` - 사용 가능한 평가 세트 목록

---

## Phase 3: 평가자 구현

### 3.1 Rule-based 평가자
- [x] `src/evaluators/__init__.py` 생성
- [x] `src/evaluators/rule_based.py` 구현
  - [x] `keyword_inclusion()` 함수
  - [x] `forbidden_word_check()` 함수
  - [x] `length_compliance()` 함수
  - [x] `format_validity()` 함수
  - [x] `exact_match()` 함수
  - [x] `run_rule_evaluators()` 통합 실행 함수

### 3.2 LangSmith 내장 평가자 연동
- [x] `src/evaluators/langsmith_builtin.py` 구현
  - [x] `create_embedding_distance_evaluator()` 함수
  - [x] `create_string_distance_evaluator()` 함수
  - [x] `get_langsmith_evaluators()` 함수

### 3.3 LLM-as-a-Judge 평가자
- [x] `src/evaluators/llm_judge.py` 구현
  - [x] `helpfulness` 기준 프롬프트
  - [x] `relevance` 기준 프롬프트
  - [x] `coherence` 기준 프롬프트
  - [x] `create_llm_judge_evaluator()` 함수
  - [x] `run_llm_judge_local()` 로컬 실행 함수

### 3.4 평가자 단위 테스트
- [x] `tests/test_evaluators.py` 작성
- [x] 각 평가자별 테스트 케이스 추가 (20개)
- [x] 테스트 실행 및 통과 확인 ✅

---

## Phase 4: 실행 파이프라인 구축

### 4.1 핵심 파이프라인 로직
- [x] `src/pipeline.py` 구현
  - [x] `execute_prompt()` - LLM 호출
  - [x] `run_evaluation()` - 평가 실행
  - [x] `evaluate_single_case()` - 단일 케이스 평가
  - [x] `run_pipeline()` - 전체 파이프라인

### 4.2 실행 모드 구현
- [x] 로컬 모드 (기본, 빠른 개발용)
  - [x] `quick` 모드 (Rule-based만)
  - [x] `standard` 모드 (Rule + String Distance)
  - [x] `full` 모드 (모든 평가자 + LLM Judge)
- [ ] LangSmith 모드 (정식 평가용) - TODO
  - [x] Dataset 업로드 (`--upload` 옵션)
  - [ ] `evaluate()` 함수로 Experiment 기록
  - [ ] 대시보드 연동

### 4.3 CLI 진입점
- [x] `main.py` 구현 (typer 기반)
  - [x] `eval` 명령어
  - [x] `--name` 옵션 (평가 세트 이름)
  - [x] `--mode` 옵션 (quick/standard/full)
  - [x] `--upload` 옵션 (LangSmith 업로드)
  - [x] `--case-id` 옵션 (특정 케이스만)
  - [x] `--model` 옵션 (LLM 모델 선택)
  - [x] `--verbose` 옵션 (상세 출력)
  - [x] `list` 명령어 (평가 세트 목록)
  - [x] `upload` 명령어 (데이터셋 업로드)

### 4.4 결과 리포터
- [x] `src/utils/reporter.py` 구현
  - [x] `print_summary()` - 콘솔 요약 출력
  - [x] `print_case_details()` - 상세 출력
  - [x] `print_failed_cases()` - 실패 케이스만
  - [x] `save_results()` - JSON 저장
  - [x] `generate_markdown_report()` - 마크다운 리포트

### 4.5 파이프라인 테스트
- [x] 실행 테스트 완료 (case_001 통과) ✅

---

## Phase 5: CI/CD 연동 및 자동화

### 5.1 GitHub Actions
- [ ] `.github/workflows/` 폴더 생성
- [ ] `eval_on_pr.yml` 작성
  - [ ] PR 트리거 설정
  - [ ] Python 환경 설정
  - [ ] 평가 실행 스텝
  - [ ] 회귀 체크 스텝

### 5.2 회귀 테스트 자동화
- [ ] `check-regression` 명령어 구현
- [ ] 이전 결과와 비교 로직
- [ ] 임계값 초과 시 실패 처리

### 5.3 알림 연동 (선택)
- [ ] Slack 웹훅 연동
- [ ] 실패 시 알림 발송

---

## 추가 개선 (Optional)

### 캐싱
- [ ] LLM 응답 캐싱 구현
- [ ] 캐시 무효화 로직

### 병렬 처리
- [ ] 동시 실행 설정 (CONCURRENCY)
- [ ] Rate Limiting 적용

### 문서화
- [ ] README.md 작성
- [ ] 사용 예시 추가

---

## 진행 상황

| Phase | 상태 | 완료율 |
|-------|------|--------|
| Phase 1 | ✅ 완료 | 100% |
| Phase 2 | ✅ 완료 | 100% |
| Phase 3 | ✅ 완료 | 100% |
| Phase 4 | ✅ 완료 | 95% (LangSmith Experiment 연동 제외) |
| Phase 5 | 대기 | 0% |

---

## 실행 모드 요약

```
[로컬 모드] 개발 단계 - 빠른 반복
────────────────────────────────
datasets/ → 로컬 파이프라인 → 콘솔 출력 + results/
           (LangSmith 트레이싱만)

[LangSmith 모드] 정식 평가 - 버전 비교/분석
────────────────────────────────
datasets/ → LangSmith Dataset 업로드
                    ↓
            evaluate() + Experiment 기록
                    ↓
            대시보드에서 버전 비교/분석
```

**CLI 사용 예시:**
```bash
# 로컬 개발 (빠름)
poetry run python main.py eval --name prep_analyzer

# 정식 평가 (LangSmith 연동)
poetry run python main.py eval --name prep_analyzer --upload
```
