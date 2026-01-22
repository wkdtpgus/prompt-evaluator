# 프롬프트 평가 시스템 구현 TODO

> 기획안 기반 단계별 구현 태스크
> **최종 수정일**: 2026-01-22

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
- [x] `targets/` 폴더 생성
- [x] `targets/_shared/` 폴더 생성
- [x] `src/` 폴더 생성
- [x] `src/evaluators/` 폴더 생성
- [x] `src/utils/` 폴더 생성
- [x] `results/` 폴더 생성
- [x] `tests/` 폴더 생성

**사용한 명령어:**
```bash
mkdir -p targets/_shared src/evaluators src/utils results tests
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
- [x] `targets/prep_analyzer.txt` 작성 (평가 대상 프롬프트)
- [x] `datasets/prep_analyzer_data/` 폴더 생성 (평가 데이터)
- [x] `datasets/prep_analyzer_data/test_cases.json` 작성 (15개 케이스)
- [x] `datasets/prep_analyzer_data/expected.json` 작성 (기대 결과)
- [x] `configs/prep_analyzer.yaml` 작성 (평가 설정)

**디렉토리 구조 (분리됨):**
```
targets/                           # 평가 대상 (프롬프트)
└── prep_analyzer.txt              # .txt, .py, .xml 지원

datasets/                          # 평가 데이터
└── prep_analyzer_data/
    ├── test_cases.json
    └── expected.json

configs/                           # 평가 설정
└── prep_analyzer.yaml
```

**생성된 테스트 케이스:**
- case_001~010: 한국어 케이스 (기본 흐름, 조기 종료, 모호한 답변, 민감 주제 등)
- case_011~012: 엣지 케이스 (서베이만, 빈 입력)
- case_013: 영어 케이스
- case_014: 베트남어 케이스
- case_015: 프로필 카드 포함 케이스

### 2.2 기본 설정 파일
- [x] `targets/_shared/default_config.yaml` 작성

### 2.3 데이터 로더 구현
- [x] `src/data_loader.py` 구현
  - [x] `load_evaluation_set()` - 로컬 파일 로드
  - [x] `upload_to_langsmith()` - LangSmith Dataset 업로드
  - [x] `list_evaluation_sets()` - 사용 가능한 평가 세트 목록
  - [x] `find_prompt_file()` - 다중 형식 프롬프트 파일 탐색
  - [x] `load_prompt_file()` - .txt/.py/.xml 로드 지원

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

### 3.2 유사도 기반 평가자
- [x] `src/evaluators/similarity.py` 구현
  - [x] `create_embedding_distance_evaluator()` 함수 (OpenAI/Vertex AI 지원)
  - [x] `create_string_distance_evaluator()` 함수
  - [x] `get_langsmith_evaluators()` 함수

### 3.3 LLM-as-a-Judge 평가자
- [x] `src/evaluators/llm_judge.py` 구현
  - [x] 체크리스트 기반 평가 (checklist evaluation)
  - [x] 도메인별 eval_prompts 로드 (`eval_prompts/{domain}/`)
  - [x] `run_checklist_evaluation()` 로컬 실행 함수
  - [x] `create_checklist_evaluator()` LangSmith 평가자 생성
  - [x] `list_available_criteria()` 사용 가능한 평가 기준 목록

### 3.4 eval_prompts 템플릿
- [x] `eval_prompts/general/` 범용 평가 기준
  - [x] `instruction_following.txt`
  - [x] `factual_accuracy.txt`
  - [x] `output_quality.txt`
- [x] `eval_prompts/oneonone/` 1on1 특화 평가 기준
  - [x] `purpose_alignment.txt`
  - [x] `coaching_quality.txt`
  - [x] `tone_appropriateness.txt`
  - [x] `sensitive_topic_handling.txt`
- [x] JSON 중괄호 이스케이프 처리 (`{{`, `}}`)

### 3.5 평가자 단위 테스트
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
  - [x] `run_pipeline()` - 전체 파이프라인 (로컬 모드)
  - [x] `run_langsmith_experiment()` - LangSmith Experiment 모드

### 4.2 실행 모드 구현
- [x] 로컬 모드 (기본, 빠른 개발용)
  - [x] `quick` 모드 (Rule-based만)
  - [x] `standard` 모드 (Rule + String Distance)
  - [x] `full` 모드 (모든 평가자 + LLM Judge)
- [x] LangSmith 모드 (정식 평가용)
  - [x] Dataset 업로드 (`upload` 명령어)
  - [x] `evaluate()` 함수로 Experiment 기록
  - [x] LLM Judge 평가자 자동 추가
  - [x] 대시보드 연동

### 4.3 CLI 진입점
- [x] `main.py` 구현 (typer 기반)
  - [x] `eval` 명령어 (로컬 평가)
  - [x] `experiment` 명령어 (LangSmith Experiment)
  - [x] `upload` 명령어 (데이터셋 업로드)
  - [x] `list` 명령어 (평가 세트 목록)
  - [x] `criteria` 명령어 (평가 기준 목록)
  - [x] `prompt push` 명령어 (프롬프트 업로드)
  - [x] `prompt pull` 명령어 (프롬프트 가져오기)
  - [x] `prompt keys` 명령어 (프롬프트 키 조회)
  - [x] `prompt versions` 명령어 (버전 목록)
  - [x] `--name` 옵션 (평가 세트 이름)
  - [x] `--mode` 옵션 (quick/standard/full)
  - [x] `--case-id` 옵션 (특정 케이스만)
  - [x] `--verbose` 옵션 (상세 출력)

### 4.4 결과 리포터
- [x] `src/report.py` 구현
  - [x] `print_summary()` - 콘솔 요약 출력
  - [x] `print_case_details()` - 상세 출력
  - [x] `print_failed_cases()` - 실패 케이스만
  - [x] `save_results()` - JSON 저장 (`results/{name}/`)
  - [x] `generate_markdown_report()` - 마크다운 리포트

### 4.5 파이프라인 테스트
- [x] 로컬 평가 실행 테스트 완료 ✅
- [x] LangSmith Experiment 실행 테스트 완료 ✅

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

## 추가 구현 완료

### 다중 프롬프트 형식 지원
- [x] `.txt` 형식 지원 (단일 템플릿)
- [x] `.py` 형식 지원 (AST 파싱, `*_PROMPT` 변수)
- [x] `.xml` 형식 지원 (XML 파싱)
- [x] 파일명 패턴: `{name}.ext` 또는 `{name}_prompt.ext`

### LangSmith 프롬프트 버전 관리
- [x] `push_prompt()` - 로컬 → LangSmith 업로드
- [x] `pull_prompt()` - LangSmith → 로컬 가져오기
- [x] `list_prompt_versions()` - 버전 목록 조회
- [x] 태그 기반 버전 관리 (`--tag v1.0`)

### 캐싱
- [ ] LLM 응답 캐싱 구현
- [ ] 캐시 무효화 로직

### 병렬 처리
- [ ] 동시 실행 설정 (CONCURRENCY)
- [ ] Rate Limiting 적용

### 문서화
- [x] `docs/PROMPT_EVALUATION_PLAN.md` 기획 문서
- [x] `docs/TODO.md` 구현 진행 상황
- [x] `docs/CLAUDE_SKILL_LLM_JUDGE.md` 스킬 가이드
- [ ] README.md 작성
- [ ] 사용 예시 추가

---

## 진행 상황

| Phase | 상태 | 완료율 |
|-------|------|--------|
| Phase 1 | ✅ 완료 | 100% |
| Phase 2 | ✅ 완료 | 100% |
| Phase 3 | ✅ 완료 | 100% |
| Phase 4 | ✅ 완료 | 100% |
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

# 정식 평가 (LangSmith Experiment)
poetry run python main.py experiment --name prep_analyzer

# 프롬프트 버전 관리
poetry run python main.py prompt push --name prep_analyzer --tag v1.0
poetry run python main.py prompt versions --name prep_analyzer
```
