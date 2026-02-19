# Prompt Evaluator 로드맵

> **최종 수정일**: 2026-02-19
> 구현 완료된 기능은 [ARCHITECTURE.md](./ARCHITECTURE.md) 참조

---

## 미구현 항목 요약

| 항목 | 출처 | 우선순위 |
|------|------|:--------:|
| 리포트 시스템 (실패 분석, Markdown 리포트) | PromptOps Phase 3 | P1 |
| GitHub Actions CI/CD | PromptOps Phase 2 | P1 |
| Langfuse 스코어링 리포트 고도화 | Langfuse Phase 8 | P1 |
| GCP 운영 (백업, 모니터링, 자동시작) | Langfuse Phase 7 잔여 | P2 |
| Human Spot-check | PromptOps Phase 4 | P2 |
| 평가자 가중치 로직 | PromptOps Phase 4 | P2 |
| 프로덕션 트레이스 → 데이터 자동 수집 | Langfuse Phase 9 | P2 |
| 데이터셋 버전 관리 | PromptOps Phase 1 잔여 | P3 |
| LLM 응답 캐싱 | SPECIFICATION | P3 |
| Slack 알림 연동 | SPECIFICATION | P3 |
| LangSmith 완전 비활성화 (Langfuse 단독) | Langfuse 마이그레이션 | P3 |

---

## 1. 리포트 시스템 (PromptOps Phase 3) — P1

### 1.1. 실패 분석 자동화

모듈: `prompt_evaluator/evaluators/failure_analyzer.py` (신규)

```python
@dataclass
class FailurePattern:
    pattern_type: str       # "long_input", "sensitive_topic"
    affected_cases: list[str]
    description: str
    frequency: float        # 전체 실패 중 비율

@dataclass
class FailureAnalysis:
    total_failures: int
    by_evaluator: dict[str, list[str]]  # evaluator → [case_ids]
    patterns: list[FailurePattern]
    recommendations: list[str]

def analyze_failures(results: dict) -> FailureAnalysis
def detect_patterns(failures: list[dict]) -> list[FailurePattern]
```

패턴 감지 예시:
- "민감 주제 케이스에서 tone_appropriateness 실패율 40%"
- "긴 대화(10턴 이상)에서 format 오류 빈발"
- "특정 키워드('퇴사', '연봉') 포함 시 실패 집중"

### 1.2. Markdown 리포트

모듈: `prompt_evaluator/reporters/markdown_reporter.py` (신규)

CLI 추가:
```bash
prompt-eval report --name {name} --format markdown
prompt-eval experiment --name {name} --save --report
```

### 1.3. 관련 리팩토링

| 파일 | 변경 내용 |
|------|----------|
| `pipelines/pipeline.py` | 결과 저장, 가중치, 리포트 연동 |
| `config.py` | 회귀 임계값, 가중치 기본값 |
| `utils/config_validator.py` | 새 필드 검증 |

---

## 2. GitHub Actions CI/CD — P1

`.github/workflows/prompt-eval.yml`

```yaml
name: Prompt Evaluation
on:
  pull_request:
    paths:
      - 'targets/**'
      - 'datasets/**'
      - 'eval_prompts/**'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run evaluation
        run: prompt-eval experiment --name ${{ steps.changes.outputs.prompt }}
      - name: Check regression
        run: prompt-eval regression --name ${{ steps.changes.outputs.prompt }} --fail
      - name: Comment PR
        uses: actions/github-script@v7
```

---

## 3. Langfuse 스코어링 리포트 고도화 (Phase 8) — P1

- [ ] comment 필드 JSON 구조화
  - `LangfuseEvaluation(comment=json.dumps({...}))` 형태로 저장
  - failed_items, passed_items, reasoning, suggestions 포함
- [ ] 실험 종료 시 자동 리포트 생성
  - `_run_langfuse_experiment()` 완료 후 리포트 출력
  - Langfuse API로 스코어 데이터 추출 → JSON 파싱
  - 실패 케이스 상세 분석 포함
  - 결과를 `results/{experiment_name}/report.md` 저장

---

## 4. GCP Langfuse 운영 (Phase 7 잔여) — P2

> 인프라/배포/보안은 완료됨. 내부용이라 도메인/HTTPS는 생략 (nginx basic auth 대체)

### 백업 설정

- [ ] PostgreSQL 정기 백업 (pg_dump cron 또는 Cloud SQL 자동 백업)
- [ ] ClickHouse 데이터 스냅샷
- [ ] Persistent Disk 스냅샷 스케줄

### 모니터링

- [ ] Cloud Monitoring 대시보드 (CPU, 메모리, 디스크)
- [ ] Uptime Check (80 포트 헬스체크, Nginx 경유)
- [ ] 디스크 용량 알림 (80% 초과 시)

### 자동 시작

- [ ] systemd 서비스로 Docker Compose 등록
- [ ] VM 재시작 시 자동 복구

---

## 5. Human Spot-check (PromptOps Phase 4) — P2

모듈: `prompt_evaluator/evaluators/human_feedback.py` (신규)

```python
@dataclass
class HumanFeedback:
    case_id: str
    reviewer: str
    timestamp: str
    overall_rating: int         # 1-5
    checklist: dict[str, bool]
    feedback: str
    tags: list[str]             # ["tone_issue", "factual_error"]
```

워크플로우:
1. 매주 10개 샘플 자동 추출
2. 리뷰 폼 생성 (Markdown)
3. 리뷰어가 피드백 제출
4. 결과 집계 → 리포트 반영

---

## 6. 평가자 가중치 (PromptOps Phase 4) — P2

config.yaml 확장:

```yaml
evaluators:
  - type: rule_based
    weight: 0.2
    checks:
      - keyword_inclusion
      - forbidden_word_check
  - type: llm_judge
    weight: 0.6
    criteria:
      - oneonone/professional_tone
  - type: human_feedback
    weight: 0.2
    sample_rate: 0.1
```

리팩토링: `pipelines/pipeline.py`에 가중 평균 계산 로직 추가

---

## 7. 프로덕션 트레이스 → 데이터 자동 수집 (Phase 9) — P2

전제: GCP 배포 완료, 프로덕션 앱의 트레이싱이 Langfuse로 전환된 상태

### CLI 커맨드

```bash
# Langfuse 트레이스에서 데이터 수집
prompt-eval dataset collect \
  --name prep_output_analyze \
  --source langfuse \
  --limit 10 \
  --since 2026-01-25

# 수집 후 Langfuse/LangSmith 데이터셋에 재업로드
prompt-eval dataset upload --name prep_output_analyze
```

### 구현 범위

- [ ] `utils/trace_collector.py` — 트레이스 데이터 수집 모듈
  - Langfuse `client.fetch_traces()` 활용
  - 필터링: 날짜 범위, 프로젝트/세션 단위, 성공/실패 여부
  - 트레이스 input → `test_cases.json` 형식 변환
  - 중복 제거 (기존 데이터셋의 inputs와 비교)
- [ ] `cli/dataset.py` — `collect` 커맨드
  - `--source langfuse|langsmith` 트레이스 소스 선택
  - `--limit`, `--since`, `--until`, `--append`, `--dry-run`
- [ ] `expected.json` 스텁 자동 생성
- [ ] 입력 키 매핑 (프로덕션 input 키 → 프롬프트 placeholder 자동 매핑)

### 데이터 흐름

```
프로덕션 앱 → Langfuse 트레이스
                  ↓ dataset collect
              datasets/{name}/test_cases.json  (로컬, 추가)
              datasets/{name}/expected.json    (스텁 추가)
                  ↓ 수동 큐레이션 (expected 보강)
                  ↓ dataset upload
              Langfuse/LangSmith dataset items (평가용)
                  ↓ experiment
              평가 실행
```

---

## 8. 기타 미구현 — P3

### 데이터셋 버전 관리

모듈: `prompt_evaluator/versioning/dataset_snapshot.py` (신규)

```yaml
# datasets/{name}/.versions.yaml
current_hash: "abc123"
case_count: 15
versions:
  - hash: "abc123"
    date: "2026-01-25"
    case_count: 15
    changes:
      added: ["edge_case_03"]
```

### LLM 응답 캐싱

동일 입력에 대한 LLM 응답을 캐싱하여 평가 비용 절감

### Slack 알림 연동

평가 완료/회귀 감지 시 Slack 알림

### Langfuse 단독 전환

- LangSmith 환경변수 비활성화 (`LANGSMITH_TRACING=false`)
- README.md 업데이트

---

## 성공 지표

### 정량적
- [ ] 프롬프트 변경 시 자동 회귀 테스트 실행
- [ ] PR에 평가 결과 자동 코멘트
- [ ] 회귀 발생 시 머지 차단
- [ ] 실패 패턴 자동 감지 (80%+ 정확도)

### 정성적
- [ ] "프롬프트 변경의 영향을 숫자로 설명 가능"
- [ ] "어떤 케이스가 왜 실패했는지 즉시 파악 가능"
- [ ] "버전별 성능 추이 한눈에 확인 가능"

### 평가 체계 성숙도 로드맵

```
[현재] Stage 1: Bootstrap
├── 자동생성으로 빠른 시작
├── 기본 평가 기준으로 MVP 검증
└── 피드백 루프 구축

[다음] Stage 2: Curate
├── 실전 좋은/나쁜 출력 수집
├── Golden Dataset 점진적 구축
└── 자동생성 평가기준 검증 & 수정

[향후] Stage 3: Refine
├── 실전 데이터 기반 평가기준 재정의
├── Edge case 중심 테스트 강화
└── 도메인 전문가 리뷰 반영
```
