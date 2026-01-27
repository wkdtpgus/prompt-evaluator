# CLI 레퍼런스

프롬프트 평가 시스템의 전체 CLI 명령어 가이드입니다.

---

## 1. 개요

### 1.1. 기본 사용법

```bash
poetry run python main.py <command> [options]
```

### 1.2. 명령어 구조

```
main.py
├── experiment          # 평가 실행
├── regression          # 회귀 테스트
├── validate            # 설정 검증
├── criteria            # 평가 기준 목록
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
| `main.py` | 앱 엔트리포인트 (조립만) |
| `cli/prompt.py` | `prompt` 서브커맨드 |
| `cli/baseline.py` | `baseline` 서브커맨드 |
| `cli/experiment.py` | `experiment`, `regression` 명령어 |
| `cli/config.py` | `validate`, `criteria` 명령어 |
| `cli/dataset.py` | `list`, `upload` 명령어 |

---

## 2. 평가 실행

### 2.1. experiment

LangSmith Experiment 실행 (정식 평가, 버전 비교용)

```bash
poetry run python main.py experiment --name <name> [options]
```

**자동화 플로우**:
1. 메타데이터 없으면 자동 init
2. 프롬프트 변경 감지 시 자동 버전 증가 + LangSmith push
3. 평가 실행

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 평가 세트 이름 | 필수 |
| `--mode` | `-m` | 실행 모드 (quick/full) | full |
| `--prefix` | `-p` | 실험 이름 접두사 | None |
| `--version` | `-v` | LangSmith 프롬프트 버전 태그 | None |
| `--changes` | `-c` | 변경 내용 (프롬프트 변경 시) | None |
| `--no-push` | | 자동 push 비활성화 | false |

**예시**:

```bash
# 기본 실행 (자동 버전 관리)
poetry run python main.py experiment --name prep_generate

# 변경 내용 직접 지정
poetry run python main.py experiment --name prep_generate --changes "톤 개선"

# 빠른 테스트 (quick 모드)
poetry run python main.py experiment --name prep_generate --mode quick

# 특정 버전으로 평가
poetry run python main.py experiment --name prep_generate --version v1.0

# 자동 push 없이 실행
poetry run python main.py experiment --name prep_generate --no-push
```

---

### 2.2. regression

회귀 테스트 실행 (기준선과 비교)

```bash
poetry run python main.py regression --name <name> --experiment <experiment_name> [options]
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
poetry run python main.py regression --name prep_generate --experiment "prep_generate-full-2026-01-26"

# CI/CD에서 회귀 시 실패 처리
poetry run python main.py regression --name prep_generate --experiment "..." --fail

# 임계값 10%로 조정
poetry run python main.py regression --name prep_generate --experiment "..." --threshold 0.1

# 특정 기준선 버전과 비교
poetry run python main.py regression --name prep_generate --baseline v1.0 --experiment "..."
```

---

## 3. 설정 및 검증

### 3.1. validate

설정 파일 검증

```bash
poetry run python main.py validate [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 특정 평가 세트만 검증 | None |
| `--all` | | 전체 평가 세트 검증 | false |

**예시**:

```bash
# 특정 세트 검증
poetry run python main.py validate --name prep_generate

# 전체 검증
poetry run python main.py validate --all
```

---

### 3.2. criteria

사용 가능한 평가 기준 목록 출력

```bash
poetry run python main.py criteria
```

**출력 예시**:

```
사용 가능한 평가 기준:

[도메인: oneonone]
  - tone_appropriateness
  - sensitive_topic_handling
  - empathy_expression

[도메인: general]
  - relevance
  - clarity
  - factual_accuracy
```

---

## 4. 데이터셋 관리

### 4.1. list

사용 가능한 평가 세트 목록 출력

```bash
poetry run python main.py list
```

**출력 예시**:

```
사용 가능한 평가 세트:
  - prep_generate
  - feedback_generator
  - summary_writer
```

---

### 4.2. upload

데이터셋을 LangSmith에 업로드

```bash
poetry run python main.py upload --name <name>
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 평가 세트 이름 | 필수 |

**예시**:

```bash
poetry run python main.py upload --name prep_generate
```

---

## 5. 프롬프트 관리 (prompt 서브커맨드)

### 5.1. prompt info

프롬프트 메타데이터 조회 (로컬 버전 이력)

```bash
poetry run python main.py prompt info <name>
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

### 5.2. prompt init

프롬프트 메타데이터 초기화

```bash
poetry run python main.py prompt init <name> [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--owner` | `-o` | 소유자 이메일 | git config |

**예시**:

```bash
# git config에서 owner 자동 감지
poetry run python main.py prompt init prep_generate

# owner 직접 지정
poetry run python main.py prompt init prep_generate --owner user@example.com
```

---

### 5.3. prompt add-version

새 버전 추가

```bash
poetry run python main.py prompt add-version <name> <version> <changes> [options]
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
poetry run python main.py prompt add-version prep_generate v1.2 "민감 주제 처리 강화"
```

---

### 5.4. prompt push

로컬 프롬프트를 LangSmith에 업로드

```bash
poetry run python main.py prompt push --name <name> [options]
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
poetry run python main.py prompt push --name prep_generate

# 버전 태그 지정
poetry run python main.py prompt push --name prep_generate --tag v1.0

# 특정 키만 업로드 (.py/.xml 파일)
poetry run python main.py prompt push --name prep_generate --key SYSTEM_PROMPT
```

---

### 5.5. prompt pull

LangSmith에서 프롬프트 가져오기

```bash
poetry run python main.py prompt pull --name <name> [options]
```

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 프롬프트 이름 | 필수 |
| `--tag` | `-t` | 특정 버전 태그 | None |
| `--save` | `-s` | 로컬 파일로 저장 | false |

**예시**:

```bash
# 프롬프트 조회 (출력만)
poetry run python main.py prompt pull --name prep_generate

# 특정 버전 조회
poetry run python main.py prompt pull --name prep_generate --tag v1.0

# 로컬 파일로 저장
poetry run python main.py prompt pull --name prep_generate --save
```

---

### 5.6. prompt keys

로컬 프롬프트 파일의 키 목록 조회 (.py/.xml 파일용)

```bash
poetry run python main.py prompt keys --name <name>
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

### 5.7. prompt versions

프롬프트의 LangSmith 버전 목록 조회

```bash
poetry run python main.py prompt versions --name <name>
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

## 6. 기준선 관리 (baseline 서브커맨드)

### 6.1. baseline list

기준선 목록 조회

```bash
poetry run python main.py baseline list <name>
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

### 6.2. baseline set

LangSmith 실험을 기준선으로 설정

```bash
poetry run python main.py baseline set <name> <experiment_name>
```

| 인자 | 설명 |
|------|------|
| `name` | 프롬프트 이름 |
| `experiment_name` | LangSmith 실험 이름 |

**예시**:

```bash
poetry run python main.py baseline set prep_generate "prep_generate-full-2026-01-26"
```

---

### 6.3. baseline delete

기준선 삭제

```bash
poetry run python main.py baseline delete <name> <version>
```

| 인자 | 설명 |
|------|------|
| `name` | 프롬프트 이름 |
| `version` | 삭제할 버전 |

**예시**:

```bash
poetry run python main.py baseline delete prep_generate v1.0
```

---

## 7. 빠른 참조

### 7.1. 일반 워크플로우

```bash
# 1. 평가 세트 목록 확인
poetry run python main.py list

# 2. 설정 검증
poetry run python main.py validate --name prep_generate

# 3. 평가 실행 (자동 버전 관리)
poetry run python main.py experiment --name prep_generate

# 4. 기준선 설정
poetry run python main.py baseline set prep_generate "prep_generate-full-2026-01-26"

# 5. 회귀 테스트
poetry run python main.py regression --name prep_generate --experiment "prep_generate-full-2026-01-27"
```

### 7.2. 프롬프트 버전 관리

```bash
# 메타데이터 조회
poetry run python main.py prompt info prep_generate

# LangSmith 버전 목록
poetry run python main.py prompt versions --name prep_generate

# 수동 push
poetry run python main.py prompt push --name prep_generate --tag v1.0
```

### 7.3. CI/CD 사용

```bash
# 회귀 시 실패 처리 (exit code 1)
poetry run python main.py regression --name prep_generate --experiment "..." --fail
```

---

## 8. 관련 문서

- [버전 관리](./versioning.md) - 프롬프트 버전 추적 상세
- [회귀 테스트](./regression.md) - 회귀 테스트 상세
- [PromptOps 기획서](../PROMPTOPS_PLAN.md) - 전체 로드맵
