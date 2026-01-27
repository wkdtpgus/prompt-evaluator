# 프롬프트 버전 관리 (Versioning)

> Phase 1 구현 완료 ✅

프롬프트 변경을 추적하고, 버전을 관리하며, LangSmith와 동기화하는 시스템입니다.

---

## 1. 개요

### 1.1. 목표

- 프롬프트 변경 이력 추적
- 해시 기반 자동 변경 감지
- LangSmith와 버전 동기화
- 작성자/변경 내용 메타데이터 관리

### 1.2. 핵심 개념

| 개념 | 설명 |
|------|------|
| 메타데이터 | `.metadata.yaml` 파일에 저장되는 버전 정보 |
| 해시 | SHA256 기반 프롬프트 내용 해시 (앞 16자리) |
| 변경 감지 | 마지막 push 해시와 현재 해시 비교 |
| 자동 버전 | v1.0 → v1.1 → v1.2 자동 증가 |

---

## 2. 메타데이터 구조

### 2.1. 파일 위치

```
targets/{name}/.metadata.yaml
```

### 2.2. 스키마

```yaml
owner: john@example.com
created_at: "2026-01-20"
current_version: v1.2
last_pushed_hash: "abc123def456..."  # 마지막 push된 프롬프트 해시

versions:
  v1.0:
    date: "2026-01-20"
    author: john@example.com
    changes: "Initial version"
    langsmith_hash: "abc123"
  v1.1:
    date: "2026-01-22"
    author: jane@example.com
    changes: "톤 개선: 더 친근하게"
    langsmith_hash: "def456"
```

### 2.3. 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `owner` | string | 프롬프트 소유자 이메일 |
| `created_at` | string | 최초 생성일 (YYYY-MM-DD) |
| `current_version` | string | 현재 버전 태그 |
| `last_pushed_hash` | string | 마지막 LangSmith push 시점의 해시 |
| `versions` | dict | 버전별 상세 정보 |

---

## 3. 자동화 워크플로우

### 3.1. 완전 자동화 플로우

`experiment` 명령어 하나로 모든 것을 자동 처리합니다:

```
┌─────────────────────────────────────────────────────────────┐
│              완전 자동화 프롬프트 버전 관리 플로우              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   사용자가 실행하는 명령어는 이것 하나뿐:                       │
│                                                             │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ $ experiment --name prep_generate --changes "톤 개선" │ │
│   └──────────────────────────────────────────────────────┘ │
│                         │                                   │
│                         ▼                                   │
│   내부 자동 처리:                                            │
│                                                             │
│   1. 메타데이터 확인                                         │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ .metadata.yaml 없음?                                 │ │
│   │ → 자동 init (git config에서 owner 감지)              │ │
│   │ → v1.0 생성                                          │ │
│   └──────────────────────────────────────────────────────┘ │
│                         │                                   │
│                         ▼                                   │
│   2. 프롬프트 변경 감지 (해시 비교)                           │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ 변경됨?                                              │ │
│   │ → 자동 버전 증가 (v1.0 → v1.1)                       │ │
│   │ → .metadata.yaml 업데이트                            │ │
│   │                                                      │ │
│   │ 변경 없음?                                           │ │
│   │ → 기존 버전 유지                                      │ │
│   └──────────────────────────────────────────────────────┘ │
│                         │                                   │
│                         ▼                                   │
│   3. LangSmith 자동 push                                    │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ → 프롬프트 업로드                                     │ │
│   │ → description에 메타데이터 자동 포함:                  │ │
│   │   ┌────────────────────────────────────────────┐     │ │
│   │   │ Prompt for prep_generate                   │     │ │
│   │   │ ---                                        │     │ │
│   │   │ version: v1.1                              │     │ │
│   │   │ author: user@example.com                   │     │ │
│   │   │ changes: 톤 개선                            │     │ │
│   │   │ date: 2026-01-26                           │     │ │
│   │   └────────────────────────────────────────────┘     │ │
│   │ → last_pushed_hash 업데이트                          │ │
│   └──────────────────────────────────────────────────────┘ │
│                         │                                   │
│                         ▼                                   │
│   4. 평가 실행                                               │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ → LangSmith Experiment 실행                          │ │
│   │ → 결과 기록                                           │ │
│   └──────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2. 핵심 포인트

- **완전 자동화**: `experiment` 하나로 init → 버전 관리 → push → 평가
- **해시 기반 변경 감지**: 프롬프트 파일 변경 시에만 새 버전 생성
- **인터랙티브 입력**: `--changes` 없이 실행하면 변경 내용 입력 프롬프트
- **로컬 `.metadata.yaml`**: 버전 이력의 원본 (source of truth)
- **git config 연동**: owner/author 자동 감지

---

## 4. 구현 모듈

### 4.1. 파일 위치

```
src/versioning/prompt_metadata.py
```

### 4.2. 함수 목록

| 함수 | 설명 |
|------|------|
| `load_metadata(prompt_name)` | 메타데이터 로드 |
| `save_metadata(prompt_name, metadata)` | 메타데이터 저장 |
| `init_metadata(prompt_name, owner)` | 새 프롬프트 초기화 (v1.0) |
| `add_version(prompt_name, version, author, changes)` | 새 버전 추가 |
| `get_current_version(prompt_name)` | 현재 버전 조회 |
| `get_version_history(prompt_name)` | 버전 이력 조회 |
| `compute_prompt_hash(prompt_name)` | SHA256 해시 계산 (앞 16자리) |
| `is_prompt_changed(prompt_name)` | 마지막 push 이후 변경 여부 |
| `increment_version(version)` | v1.0 → v1.1 자동 증가 |
| `update_last_pushed_hash(prompt_name, hash)` | push 성공 시 해시 저장 |
| `auto_version_and_push_info(prompt_name, author, changes)` | 버전 증가 + push 정보 일괄 처리 |
| `update_langsmith_hash(prompt_name, version, hash)` | LangSmith 해시 기록 |

### 4.3. 사용 예시

```python
from src.versioning.prompt_metadata import (
    load_metadata,
    is_prompt_changed,
    auto_version_and_push_info,
    update_last_pushed_hash,
)

# 변경 감지
if is_prompt_changed("prep_generate"):
    # 자동 버전 증가
    info = auto_version_and_push_info("prep_generate", "user@example.com", "톤 개선")
    print(f"새 버전: {info['version']}")

    # push 후 해시 업데이트
    update_last_pushed_hash("prep_generate", info["prompt_hash"])
```

---

## 5. LangSmith 연동

### 5.1. 업로드 형식

| 프롬프트 구조 | 업로드 형식 |
|--------------|------------|
| 단일 템플릿 (`template` 키 또는 1개) | `PromptTemplate` |
| 여러 프롬프트 (`SYSTEM_PROMPT` + `USER_PROMPT`) | `ChatPromptTemplate` (System/Human 구분) |

플레이그라운드에서 System/Human 메시지가 분리되어 표시됩니다.

### 5.2. 메타데이터 포함

push 시 description에 메타데이터가 자동으로 포함됩니다:

```
Prompt for prep_generate
---
version: v1.1
author: user@example.com
changes: 톤 개선
date: 2026-01-26
```

### 5.3. 구현 파일

```
utils/langsmith_prompts.py
```

---

## 6. CLI 명령어

### 6.1. 자동화 (권장)

```bash
# 기본 사용 (변경 감지 시 인터랙티브 입력)
poetry run python main.py experiment --name prep_generate

# 변경 내용 직접 지정
poetry run python main.py experiment --name prep_generate --changes "톤 개선"

# 자동 push 없이 기존 버전으로 평가
poetry run python main.py experiment --name prep_generate --no-push

# 특정 버전으로 평가 (수동 push한 경우)
poetry run python main.py experiment --name prep_generate --version v1.0
```

### 6.2. 수동 관리

```bash
# 메타데이터 초기화 (git config에서 owner 자동 감지)
poetry run python main.py prompt init prep_generate

# 버전 추가 (git config에서 author 자동 감지)
poetry run python main.py prompt add-version prep_generate v1.2 "민감 주제 처리 강화"

# 메타데이터 조회
poetry run python main.py prompt info prep_generate

# LangSmith에 수동 push
poetry run python main.py prompt push --name prep_generate --tag v1.0

# LangSmith 버전 목록 조회
poetry run python main.py prompt versions --name prep_generate
```

---

## 7. 데이터셋 버전 관리 (계획)

> 후순위 - 필요 시 구현 예정

### 7.1. 파일 구조

```
datasets/{name}/.versions.yaml
```

### 7.2. 스키마

```yaml
current_hash: "abc123"
case_count: 15

versions:
  - hash: "abc123"
    date: "2026-01-25"
    case_count: 15
    changes:
      added: ["edge_case_03"]
      modified: []
      removed: []
```

### 7.3. 계획 모듈

```
src/versioning/dataset_snapshot.py
```

| 함수 | 설명 |
|------|------|
| `compute_hash(dataset_path)` | 데이터셋 해시 계산 |
| `track_changes(prompt_name)` | 변경 사항 추적 |
| `create_snapshot(prompt_name, message)` | 스냅샷 생성 |
| `list_snapshots(prompt_name)` | 스냅샷 목록 조회 |

---

## 8. 관련 문서

- [CLI 레퍼런스](./cli-reference.md) - 전체 CLI 명령어
- [회귀 테스트](./regression.md) - 버전 간 성능 비교
- [PromptOps 기획서](../PROMPTOPS_PLAN.md) - 전체 로드맵
