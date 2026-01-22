# Claude Code Skill: LLM Judge 평가기준 생성기

> Claude Code에서 `/eval-criteria` 명령으로 프롬프트 평가기준을 자동 생성합니다.
> **최종 수정일**: 2026-01-22

## 사용법

1. Claude Code에서 프로젝트 열기
2. 평가기준을 만들고 싶은 프롬프트명 확인 (`targets/` 폴더에 위치)
3. `/eval-criteria [프롬프트명]` 또는 "평가기준 만들어줘" 요청
4. 생성된 평가 프롬프트 파일이 `eval_prompts/{도메인명}/` 폴더에 저장됨
5. `configs/{프롬프트명}.yaml`에 criteria 자동 생성

---

## 폴더 구조

```
eval_prompts/                       # 평가 프롬프트 (LLM Judge용)
├── general/                        # 범용 평가 기준
│   ├── instruction_following.txt
│   ├── factual_accuracy.txt
│   └── output_quality.txt
└── oneonone/                       # 1on1 특화 평가 기준
    ├── purpose_alignment.txt
    ├── coaching_quality.txt
    ├── tone_appropriateness.txt
    └── sensitive_topic_handling.txt

targets/                            # 평가 대상 프롬프트
├── {name}.txt                      # .txt 형식
├── {name}.py                       # .py 형식 (*_PROMPT 변수)
└── {name}.xml                      # .xml 형식

configs/                            # 평가 설정
└── {name}.yaml
```

## 지원하는 프롬프트 파일 형식

| 형식 | 파일 패턴 | 설명 |
|------|----------|------|
| `.txt` | `{name}.txt` 또는 `{name}_prompt.txt` | 단일 템플릿 텍스트 |
| `.py` | `{name}.py` 또는 `{name}_prompt.py` | Python 변수 (`*_PROMPT`) |
| `.xml` | `{name}.xml` 또는 `{name}_prompt.xml` | XML 구조 (`<system>`, `<user>`) |

## 스킬 위치

```
.claude/skills/llm_judge_generator/
├── SKILL.md              # 스킬 정의
└── references/
    ├── general_criteria.md    # 범용 평가기준 예시
    └── oneonone_criteria.md   # 1on1 도메인 예시
```

---

## 예시

### 요청

```
/eval-criteria prep_analyzer
```

또는

```
prep_analyzer 프롬프트의 평가기준 만들어줘
```

### Claude Code가 하는 일

1. `targets/prep_analyzer.[txt|py|xml]` 읽기 (평가 대상 프롬프트)
2. 도메인 컨텍스트 파악 (1on1 미팅, 코칭 힌트 등)
3. MUST/AVOID 규칙에서 체크리스트 추출
4. 평가 프롬프트 파일을 `eval_prompts/{도메인}/` 폴더에 생성

### 출력 예시

**1. 평가 프롬프트 파일 생성: `eval_prompts/oneonone/purpose_alignment.txt`**

```
You are evaluating: 1on1 meeting coaching hint quality

## Input:
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **Focus on Member**: Does the hint focus on member's feelings or well-being?
2. **Support Oriented**: Does it suggest how leader can support (not request info)?
3. **Avoids Status Questions**: Does it avoid asking about basic work status?
4. **Explores Growth**: Does it touch on growth, learning, or career aspects?
5. **Relationship Building**: Does it help build trust and open communication?

## Response Format (JSON):
{{
    "checklist": {{
        "focus_on_member": 0 or 1,
        "support_oriented": 0 or 1,
        "avoids_status_questions": 0 or 1,
        "explores_growth": 0 or 1,
        "relationship_building": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "reasoning": "brief explanation"
}}
```

> **중요**: JSON 예시의 중괄호는 `{{`, `}}`로 이스케이프해야 합니다.
> Python의 `.format()` 메서드와 충돌을 방지하기 위함입니다.

**2. 설정 파일 생성: `configs/prep_analyzer.yaml`**

```yaml
# configs/prep_analyzer.yaml
eval_prompts_domain: oneonone  # eval_prompts/{domain}/ 폴더 지정

evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check
      - format_validity

  - type: llm_judge
    criteria:
      - instruction_following
      - output_quality
      - purpose_alignment
      - coaching_quality
      - tone_appropriateness
      - sensitive_topic_handling
    enabled: true

thresholds:
  pass_rate: 0.85
  min_score: 0.70
```

---

## 워크플로우

```
프롬프트 작성 (targets/{name}.[txt|py|xml])
    │
    ▼
Claude Code에서 /eval-criteria {name}
    │
    ▼
평가 프롬프트 파일 생성 (eval_prompts/{도메인}/{criterion}.txt)
    │
    ▼
설정 파일 생성/수정 (configs/{name}.yaml)
    │
    ▼
poetry run python main.py experiment --name {name}
    │
    ▼
LangSmith에서 결과 확인
```

---

## 현재 지원하는 평가 기준

사용 가능한 평가 기준 확인:
```bash
poetry run python main.py criteria
```

### 일반 평가 기준 (general/)

| 기준 | 설명 |
|------|------|
| `instruction_following` | 프롬프트 지시사항 준수도 |
| `factual_accuracy` | 사실 정확성 / 할루시네이션 검사 |
| `output_quality` | 전반적 출력 품질 |

### 1on1 Meeting 특화 평가 기준 (oneonone/)

| 기준 | 설명 |
|------|------|
| `purpose_alignment` | 1on1 미팅 목적 부합도 |
| `coaching_quality` | 코칭 힌트 품질 |
| `tone_appropriateness` | 톤/어조 적절성 |
| `sensitive_topic_handling` | 민감한 주제 처리 |

---

## CLI 명령어

### 평가 실행

```bash
# 로컬 평가 (빠른 개발용)
poetry run python main.py eval --name prep_analyzer
poetry run python main.py eval --name prep_analyzer --mode full

# LangSmith Experiment (정식 평가)
poetry run python main.py experiment --name prep_analyzer
```

### 프롬프트 버전 관리

```bash
# 프롬프트 푸시 (LangSmith에 업로드)
poetry run python main.py prompt push --name prep_analyzer --tag v1.0

# .py 파일의 특정 키만 업로드
poetry run python main.py prompt push --name prep_analyzer --key SYSTEM_PROMPT

# 프롬프트 키 조회 (.py/.xml 파일용)
poetry run python main.py prompt keys --name prep_analyzer

# 프롬프트 버전 목록
poetry run python main.py prompt versions --name prep_analyzer
```

---

## 관련 스킬

| 스킬 | 명령어 | 용도 |
|-----|--------|------|
| eval-criteria | `/eval-criteria [프롬프트명]` | LLM Judge 평가기준 생성 |
| ab-compare | `/ab-compare [비교대상]` | 프롬프트 A/B 비교 평가 |
| gen-testcases | `/gen-testcases [프롬프트명]` | 테스트 케이스 생성 |

---

## eval_prompts 작성 규칙

### 1. 플레이스홀더

| 플레이스홀더 | 설명 |
|-------------|------|
| `{prompt}` | 평가 대상 프롬프트 템플릿 (instruction_following 등에서 사용) |
| `{input}` | 테스트 케이스 입력 데이터 |
| `{output}` | LLM이 생성한 출력 |

### 2. JSON 중괄호 이스케이프

```
## Response Format (JSON):
{{
    "checklist": {{
        "item1": 0 or 1,
        "item2": 0 or 1
    }},
    "score": <float 0-1>
}}
```

- JSON의 `{`는 `{{`로, `}`는 `}}`로 이스케이프
- 플레이스홀더 `{prompt}`, `{input}`, `{output}`은 단일 중괄호 사용

### 3. 체크리스트 구조

```
## Checklist - Score each item (0 or 1):

1. **항목명**: 평가 질문?
2. **항목명**: 평가 질문?
...
```

---

## 참고

- 자동생성된 코드는 **시작점**입니다. 실제 사용하면서 체크리스트를 수정하세요.
- 도메인 지식이 필요한 평가 기준은 수동으로 추가하는 것이 더 정확합니다.
- 기존 `eval_prompts/oneonone/` 폴더의 템플릿을 참고하면 좋은 체크리스트 패턴을 볼 수 있습니다.
