# CLI 레퍼런스

프롬프트 평가 시스템의 전체 CLI 명령어 가이드입니다.

---

## 1. 개요

### 1.1. 기본 사용법

```bash
# 패키지 설치 후
prompt-eval <command> [options]

# 또는 개발 시
poetry run python main.py <command> [options]
```

### 1.2. 명령어 구조

```
prompt-eval
├── init                # 평가 환경 초기화
├── experiment          # 평가 실행
├── regression          # 회귀 테스트
├── validate            # 설정 검증
├── list                # 평가 세트 목록
├── upload              # 데이터셋 업로드
├── prompt              # 프롬프트 서브커맨드
│   ├── info
│   ├── init
│   ├── add-version
│   ├── push
│   ├── pull
│   ├── keys
│   └── versions
└── baseline            # 기준선 서브커맨드
    ├── list
    ├── set
    └── delete
```

### 1.3. CLI 모듈 구조

| 파일 | 역할 |
|------|------|
| `prompt_evaluator/cli/__init__.py` | Typer app 정의 (entry point) |
| `prompt_evaluator/cli/scaffold.py` | `init` 명령어 |
| `prompt_evaluator/cli/prompt.py` | `prompt` 서브커맨드 |
| `prompt_evaluator/cli/baseline.py` | `baseline` 서브커맨드 |
| `prompt_evaluator/cli/experiment.py` | `experiment`, `regression` 명령어 |
| `prompt_evaluator/cli/config.py` | `validate` 명령어 |
| `prompt_evaluator/cli/dataset.py` | `list`, `upload` 명령어 |
| `main.py` | 개발용 thin wrapper |

---

## 2. 환경 초기화

### 2.0. init

프로덕션 프로젝트에서 평가 환경 초기화

```bash
prompt-eval init [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--dir` | `-d` | 평가 산출물 디렉토리 | `.prompt-eval` |
| `--targets-dir` | `-t` | 프로덕션 프롬프트 위치 | None |
| `--no-skills` | | Claude Code 스킬 설치 생략 | false |
| `--no-eval-prompts` | | 범용 평가 기준 복사 생략 | false |

**수행 작업**:
1. 평가 산출물 디렉토리 생성 (`datasets/`, `eval_prompts/`, `results/`)
2. `config.yaml` 생성 (경로 설정)
3. Claude Code 스킬 복사 (`.claude/skills/`)
4. 범용 평가 기준 복사 (`eval_prompts/general/`)
5. `.gitignore` 업데이트 (`results/` 추가)

**예시**:

```bash
# 기본 초기화
prompt-eval init --dir .prompt-eval --targets-dir src/prompts

# 스킬 없이 초기화
prompt-eval init --dir .prompt-eval --no-skills
```

---

## 3. 평가 실행

### 3.1. experiment

평가 실험 실행 (LangSmith, Langfuse, 또는 동시 실행)

```bash
prompt-eval experiment --name <name> [options]
```

**자동화 플로우** (LangSmith 백엔드):
1. 메타데이터 없으면 자동 init
2. 프롬프트 변경 감지 시 자동 버전 증가 + LangSmith push
3. 평가 실행

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 평가 세트 이름 | 필수 |
| `--mode` | `-m` | 실행 모드 (quick/full) | full |
| `--prefix` | `-p` | 실험 이름 접두사 | None |
| `--version` | `-v` | 프롬프트 버전 태그 | None |
| `--changes` | `-c` | 변경 내용 (프롬프트 변경 시) | None |
| `--no-push` | | 자동 push 비활성화 (LangSmith만) | false |
| `--backend` | `-b` | 실험 백엔드 (langsmith/langfuse/both) | both |

**백엔드 옵션**:
- `both` (기본값): Langfuse → LangSmith 순서로 동시 실행
- `langfuse`: Langfuse만 실행 (Docker 로컬 또는 클라우드)
- `langsmith`: LangSmith만 실행 (자동 버전 관리 포함)

**예시**:

```bash
# 기본 실행 (Langfuse + LangSmith 동시)
prompt-eval experiment --name prep_generate

# Langfuse만 실행
prompt-eval experiment --name prep_generate --backend langfuse

# LangSmith만 실행 (자동 버전 관리)
prompt-eval experiment --name prep_generate --backend langsmith

# 변경 내용 직접 지정 (LangSmith 백엔드)
prompt-eval experiment --name prep_generate --backend langsmith --changes "톤 개선"

# 빠른 테스트 (quick 모드)
prompt-eval experiment --name prep_generate --mode quick

# 특정 버전으로 평가
prompt-eval experiment --name prep_generate --version v1.0

# 자동 push 없이 실행 (LangSmith만)
prompt-eval experiment --name prep_generate --backend langsmith --no-push
```

---

### 3.2. regression

회귀 테스트 실행 (기준선과 비교)

```bash
prompt-eval regression --name <name> --experiment <experiment_name> [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 프롬프트 이름 | 필수 |
| `--baseline` | `-b` | 기준선 버전 | latest |
| `--experiment` | `-e` | 비교할 실험 이름 | 필수 |
| `--threshold` | `-t` | 회귀 임계값 | 0.05 (5%) |
| `--fail` | `-f` | 회귀 시 exit code 1 반환 | false |

**예시**:

```bash
# 기본 회귀 테스트
prompt-eval regression --name prep_generate --experiment "prep_generate-full-2026-01-26"

# CI/CD에서 회귀 시 실패 처리
prompt-eval regression --name prep_generate --experiment "..." --fail

# 임계값 10%로 조정
prompt-eval regression --name prep_generate --experiment "..." --threshold 0.1

# 특정 기준선 버전과 비교
prompt-eval regression --name prep_generate --baseline v1.0 --experiment "..."
```

---

## 4. 설정 및 검증

### 4.1. validate

설정 파일 검증

```bash
prompt-eval validate [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 특정 평가 세트만 검증 | None |
| `--all` | | 전체 평가 세트 검증 | false |

**예시**:

```bash
# 특정 세트 검증
prompt-eval validate --name prep_generate

# 전체 검증
prompt-eval validate --all
```

---

## 5. 데이터셋 관리

### 5.1. list

사용 가능한 평가 세트 목록 출력

```bash
prompt-eval list
```

**출력 예시**:

```
사용 가능한 평가 세트:
  - prep_generate
  - feedback_generator
  - summary_writer
```

---

### 5.2. upload

데이터셋을 LangSmith에 업로드

```bash
prompt-eval upload --name <name>
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 평가 세트 이름 | 필수 |

**예시**:

```bash
prompt-eval upload --name prep_generate
```

---

## 6. 프롬프트 관리 (prompt 서브커맨드)

### 6.1. prompt info

프롬프트 메타데이터 조회 (로컬 버전 이력)

```bash
prompt-eval prompt info <name>
```

**출력 예시**:

```
📋 프롬프트 정보: prep_generate
------------------------------------------------------------
  소유자: user@example.com
  생성일: 2026-01-20
  현재 버전: v1.2

  [버전 이력] (3개)
    • v1.2 (2026-01-25) - 민감 주제 처리 강화 | abc123de
    • v1.1 (2026-01-22) - 톤 개선 | def456ab
    • v1.0 (2026-01-20) - Initial version | 12345678
```

---

### 6.2. prompt init

프롬프트 메타데이터 초기화

```bash
prompt-eval prompt init <name> [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--owner` | `-o` | 소유자 이메일 | git config |

**예시**:

```bash
# git config에서 owner 자동 감지
prompt-eval prompt init prep_generate

# owner 직접 지정
prompt-eval prompt init prep_generate --owner user@example.com
```

---

### 6.3. prompt add-version

새 버전 추가

```bash
prompt-eval prompt add-version <name> <version> <changes> [options]
```

| 인자 | 설명 |
|------|------|
| `name` | 프롬프트 이름 |
| `version` | 버전 태그 (예: v1.2) |
| `changes` | 변경 내용 |

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--author` | `-a` | 작성자 이메일 | git config |

**예시**:

```bash
prompt-eval prompt add-version prep_generate v1.2 "민감 주제 처리 강화"
```

---

### 6.4. prompt push

로컬 프롬프트를 LangSmith에 업로드

```bash
prompt-eval prompt push --name <name> [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 프롬프트 이름 | 필수 |
| `--tag` | `-t` | 버전 태그 | None |
| `--desc` | `-d` | 프롬프트 설명 | None |
| `--key` | `-k` | .py/.xml 파일의 특정 프롬프트 키 | None |

**지원 형식**: `.txt`, `.py`, `.xml`

**예시**:

```bash
# 기본 업로드
prompt-eval prompt push --name prep_generate

# 버전 태그 지정
prompt-eval prompt push --name prep_generate --tag v1.0

# 특정 키만 업로드 (.py/.xml 파일)
prompt-eval prompt push --name prep_generate --key SYSTEM_PROMPT
```

---

### 6.5. prompt pull

LangSmith에서 프롬프트 가져오기

```bash
prompt-eval prompt pull --name <name> [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 프롬프트 이름 | 필수 |
| `--tag` | `-t` | 특정 버전 태그 | None |
| `--save` | `-s` | 로컬 파일로 저장 | false |

**예시**:

```bash
# 프롬프트 조회 (출력만)
prompt-eval prompt pull --name prep_generate

# 특정 버전 조회
prompt-eval prompt pull --name prep_generate --tag v1.0

# 로컬 파일로 저장
prompt-eval prompt pull --name prep_generate --save
```

---

### 6.6. prompt keys

로컬 프롬프트 파일의 키 목록 조회 (.py/.xml 파일용)

```bash
prompt-eval prompt keys --name <name>
```

**출력 예시**:

```
프롬프트 파일: targets/prep_generate/prompt.py
형식: .py
------------------------------------------------------------
  • SYSTEM_PROMPT: 당신은 1:1 미팅 준비 도우미입니다...
  • USER_PROMPT: 다음 정보를 바탕으로 대화 안건을 생성...

특정 프롬프트 업로드: prompt push --name prep_generate --key SYSTEM_PROMPT
```

---

### 6.7. prompt versions

프롬프트의 LangSmith 버전 목록 조회

```bash
prompt-eval prompt versions --name <name>
```

**출력 예시**:

```
프롬프트 버전 목록: prep_generate
------------------------------------------------------------
  1. abc123de | v1.2, latest | 2026-01-25T10:30:00
  2. def456ab | v1.1 | 2026-01-22T14:20:00
  3. 12345678 | v1.0 | 2026-01-20T09:00:00
```

---

## 7. 기준선 관리 (baseline 서브커맨드)

### 7.1. baseline list

기준선 목록 조회

```bash
prompt-eval baseline list <name>
```

**출력 예시**:

```
기준선 목록: prep_generate
------------------------------------------------------------
  • v1.2 (2026-01-25) - Pass Rate: 86.7%, Avg Score: 0.82
  • v1.1 (2026-01-22) - Pass Rate: 80.0%, Avg Score: 0.78
  • v1.0 (2026-01-20) - Pass Rate: 75.0%, Avg Score: 0.75
```

---

### 7.2. baseline set

LangSmith 실험을 기준선으로 설정

```bash
prompt-eval baseline set <name> <experiment_name>
```

| 인자 | 설명 |
|------|------|
| `name` | 프롬프트 이름 |
| `experiment_name` | LangSmith 실험 이름 |

**예시**:

```bash
prompt-eval baseline set prep_generate "prep_generate-full-2026-01-26"
```

---

### 7.3. baseline delete

기준선 삭제

```bash
prompt-eval baseline delete <name> <version>
```

| 인자 | 설명 |
|------|------|
| `name` | 프롬프트 이름 |
| `version` | 삭제할 버전 |

**예시**:

```bash
prompt-eval baseline delete prep_generate v1.0
```

---

## 8. 빠른 참조

### 8.1. 일반 워크플로우

```bash
# 1. 평가 세트 목록 확인
prompt-eval list

# 2. 설정 검증
prompt-eval validate --name prep_generate

# 3. 평가 실행 (Langfuse + LangSmith 동시 - 기본값)
prompt-eval experiment --name prep_generate

# 3-1. Langfuse만 실행
prompt-eval experiment --name prep_generate --backend langfuse

# 3-2. LangSmith만 실행 (자동 버전 관리)
prompt-eval experiment --name prep_generate --backend langsmith

# 4. 기준선 설정
prompt-eval baseline set prep_generate "prep_generate-full-2026-01-26"

# 5. 회귀 테스트
prompt-eval regression --name prep_generate --experiment "prep_generate-full-2026-01-27"
```

### 8.2. 프롬프트 버전 관리

```bash
# 메타데이터 조회
prompt-eval prompt info prep_generate

# LangSmith 버전 목록
prompt-eval prompt versions --name prep_generate

# 수동 push
prompt-eval prompt push --name prep_generate --tag v1.0
```

### 8.3. CI/CD 사용

```bash
# 회귀 시 실패 처리 (exit code 1)
prompt-eval regression --name prep_generate --experiment "..." --fail
```

---

## 9. 관련 문서

- [버전 관리](./versioning.md) - 프롬프트 버전 추적 상세
- [회귀 테스트](./regression.md) - 회귀 테스트 상세
- [PromptOps 기획서](../PROMPTOPS_PLAN.md) - 전체 로드맵
- [Langfuse 마이그레이션 계획](../langfuse-migration-plan.md) - Langfuse 통합 상세
