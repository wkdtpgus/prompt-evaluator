# prompt-evaluator

LLM 프롬프트 정량 평가 엔진. LangSmith / Langfuse 기반 실험, 회귀 테스트, 버전 관리를 지원합니다.

## 설치

### 요구사항

- Python 3.10+
- 가상환경 (venv, Poetry 등) — macOS는 시스템 Python에 직접 설치 불가

### Public 레포

```bash
# pip
pip install git+https://github.com/wkdtpgus/prompt-evaluator.git

# Poetry
poetry add git+https://github.com/wkdtpgus/prompt-evaluator.git
```

### Private 레포 (GitHub PAT 필요)

1. GitHub에서 Personal Access Token 생성:
   - Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - 권한: `Contents: Read-only` (해당 레포)

2. PAT를 사용해 설치:

```bash
# pip
pip install git+https://<PAT>@github.com/wkdtpgus/prompt-evaluator.git

# Poetry
poetry add git+https://<PAT>@github.com/wkdtpgus/prompt-evaluator.git
```

> `<PAT>` 부분에 생성한 토큰을 넣으세요. 예: `ghp_xxxxxxxxxxxx`

### 설치 확인

```bash
prompt-eval --help
```

> **주의**: 반드시 가상환경 안에서 설치하세요.
> macOS에서 `pip3 install ...` 하면 `externally-managed-environment` 에러가 납니다.
> ```bash
> # venv 사용 시
> source .venv/bin/activate && pip install ...
>
> # Poetry 사용 시 (자동으로 가상환경에 설치)
> poetry add ...
> ```

## 프로덕션 프로젝트에 적용하기

### 1단계: 평가 환경 초기화

프로젝트 루트에서 실행:

```bash
cd your-project/
prompt-eval init --dir .prompt-eval --targets-dir src/prompts
```

생성되는 구조:

```
your-project/
├── .prompt-eval/
│   ├── config.yaml              # 경로 설정
│   ├── GUIDE.md                 # 상세 사용 가이드
│   ├── datasets/                # 테스트 데이터
│   ├── eval_prompts/
│   │   └── general/             # 범용 평가 기준 (3개)
│   └── results/                 # 평가 결과 (gitignore됨)
├── .claude/skills/              # Claude Code 스킬 (3개)
│   ├── test_case_generator/
│   ├── llm_judge_generator/
│   └── prompt_ab_comparator/
└── .gitignore                   # results 경로 자동 추가
```

init 옵션:

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--dir`, `-d` | 평가 산출물 디렉토리 | `.prompt-eval` |
| `--targets-dir`, `-t` | 프로덕션 프롬프트 위치 | None |
| `--no-skills` | Claude Code 스킬 설치 생략 | false |
| `--no-eval-prompts` | 범용 평가 기준 복사 생략 | false |

### 2단계: 환경변수 설정

`.env` 파일에 추가:

```bash
# LLM (필수 - 하나 이상)
OPENAI_API_KEY=sk-...

# 또는 GCP Vertex AI (Gemini)
GOOGLE_CLOUD_PROJECT=your-project-id

# LangSmith (선택)
LANGSMITH_API_KEY=lsv2_...

# Langfuse (선택)
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
```

### 3단계: 평가 데이터 준비

```
.prompt-eval/
├── datasets/
│   └── {name}/
│       ├── test_cases.json    # 테스트 입력
│       └── expected.json      # 기대 결과 (keywords, forbidden)
└── eval_prompts/
    └── {name}/
        └── {criterion}.txt    # LLM Judge 평가 기준
```

Claude Code 스킬로 자동 생성 가능:
- `/gen-testcases` - 테스트 케이스 생성
- `/eval-criteria` - 평가 기준 생성

### 4단계: 평가 실행

```bash
# 평가 실험 실행
prompt-eval experiment --name {name}

# Langfuse만
prompt-eval experiment --name {name} --backend langfuse

# LangSmith만
prompt-eval experiment --name {name} --backend langsmith

# 빠른 테스트 (Rule-based만)
prompt-eval experiment --name {name} --mode quick
```

## CLI 명령어

```
prompt-eval
├── init                # 평가 환경 초기화
├── experiment          # 평가 실행
├── regression          # 회귀 테스트 (기준선 비교)
├── validate            # 설정 검증
├── list                # 평가 세트 목록
├── upload              # 데이터셋 업로드
├── prompt              # 프롬프트 버전 관리
│   ├── info / init / add-version
│   ├── push / pull / keys / versions
└── baseline            # 기준선 관리
    ├── list / set / delete
```

## 평가자 종류

| 평가자 | 비용 | 설명 |
|--------|------|------|
| Rule-based | 무료 | 키워드 포함, 금지어 검사 |
| LLM Judge | API 호출 | 체크리스트 기반 LLM 평가 (커스텀 기준) |

## Python API

```python
from prompt_evaluator import run_experiment, EvalContext, set_context

# 컨텍스트 설정
ctx = EvalContext(root=".prompt-eval", targets_dir="src/prompts")
set_context(ctx)

# 평가 실행
result = run_experiment("my_prompt", backend="langfuse")
```

## 개발

```bash
git clone https://github.com/wkdtpgus/prompt-evaluator.git
cd prompt-evaluator
poetry install
poetry run prompt-eval --help
```

## 문서

- `.prompt-eval/GUIDE.md` - init 후 생성되는 상세 사용 가이드
- [CLI 레퍼런스](docs/features/cli-reference.md)
- [회귀 테스트](docs/features/regression.md)
- [버전 관리](docs/features/versioning.md)
