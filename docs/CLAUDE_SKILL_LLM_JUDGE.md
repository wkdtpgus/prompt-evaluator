# Claude Code Skill: LLM Judge 평가기준 생성기

> Claude Code에서 `/eval-criteria` 명령으로 프롬프트 평가기준을 자동 생성합니다.

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
├── general/                   # 범용 평가 기준
│   ├── instruction_following.txt
│   ├── factual_accuracy.txt
│   └── output_quality.txt
└── oneonone/                  # 1on1 특화 평가 기준
    ├── purpose_alignment.txt
    ├── coaching_quality.txt
    ├── tone_appropriateness.txt
    └── sensitive_topic_handling.txt

targets/                       # 평가 대상 프롬프트
└── {프롬프트명}_prompt.txt

configs/                       # 평가 설정
└── {프롬프트명}.yaml
```

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

1. `targets/prep_analyzer_prompt.txt` 읽기 (평가 대상 프롬프트)
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
{
    "checklist": {
        "focus_on_member": 0 or 1,
        "support_oriented": 0 or 1,
        "avoids_status_questions": 0 or 1,
        "explores_growth": 0 or 1,
        "relationship_building": 0 or 1
    },
    "score": <float 0-1, average of checklist>,
    "reasoning": "brief explanation"
}
```

**2. 설정 파일 생성: `configs/prep_analyzer.yaml`**

```yaml
# configs/prep_analyzer.yaml
evaluators:
  - type: llm_judge
    criteria:
      - purpose_alignment
      - coaching_quality
    enabled: true

thresholds:
  pass_rate: 0.85
  min_score: 0.70
```

---

## 워크플로우

```
프롬프트 작성 (targets/{name}_prompt.txt)
    │
    ▼
Claude Code에서 /eval-criteria {name}
    │
    ▼
평가 프롬프트 파일 생성 (eval_prompts/{도메인}/{criterion}.txt)
    │
    ▼
설정 파일 생성 (configs/{name}.yaml)
    │
    ▼
poetry run python main.py experiment --name {name} --mode full
    │
    ▼
LangSmith에서 결과 확인
```

---

## 관련 스킬

| 스킬 | 명령어 | 용도 |
|-----|--------|------|
| eval-criteria | `/eval-criteria [프롬프트명]` | LLM Judge 평가기준 생성 |
| ab-compare | `/ab-compare [비교대상]` | 프롬프트 A/B 비교 평가 |
| gen-testcases | `/gen-testcases [프롬프트명]` | 테스트 케이스 생성 |

---

## 참고

- 자동생성된 코드는 **시작점**입니다. 실제 사용하면서 체크리스트를 수정하세요.
- 도메인 지식이 필요한 평가 기준은 수동으로 추가하는 것이 더 정확합니다.
- 기존 `ONEONONE_PROMPTS`를 참고하면 좋은 체크리스트 패턴을 볼 수 있습니다.
