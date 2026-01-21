# Claude Code Skill: LLM Judge 평가기준 생성기

> Claude Code에서 `/eval-criteria` 명령으로 프롬프트 평가기준을 자동 생성합니다.

## 사용법

1. Claude Code에서 프로젝트 열기
2. 평가기준을 만들고 싶은 프롬프트명 확인
3. `/eval-criteria [프롬프트명]` 또는 "평가기준 만들어줘" 요청
4. 생성된 코드를 `src/evaluators/llm_judge.py`에 복붙
5. `eval_config.yaml`에 criteria 추가

---

## 스킬 위치

```
.claude/skills/llm-judge-generator/
├── SKILL.md              # 스킬 정의
└── references/
    ├── general-criteria.md    # 범용 평가기준 예시
    └── oneonone-example.md    # 1on1 도메인 예시
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

1. `prompts/prep_analyzer_prompt.txt` 읽기
2. 도메인 컨텍스트 파악 (1on1 미팅, 코칭 힌트 등)
3. MUST/AVOID 규칙에서 체크리스트 추출
4. Python 코드로 평가 프롬프트 생성

### 출력 예시

```python
# ============================================================
# 1on1 Meeting 특화 평가 프롬프트
# ============================================================

ONEONONE_PROMPTS = {
    # 📋 purpose_alignment: 1on1 미팅 목적 부합도
    "purpose_alignment": """You are evaluating: 1on1 meeting coaching hint quality

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
}}""",
}

# ============================================================
# 적용 방법
# ============================================================

# 1. AVAILABLE_CRITERIA에 추가 (llm_judge.py 하단):
AVAILABLE_CRITERIA = {
    ...
    "purpose_alignment": "1on1 미팅 목적 부합도",
}

# 2. ALL_CHECKLIST_PROMPTS 업데이트:
ALL_CHECKLIST_PROMPTS = {**CHECKLIST_PROMPTS, **ONEONONE_PROMPTS}

# 3. eval_config.yaml에 추가:
# evaluators:
#   - type: llm_judge
#     criteria:
#       - purpose_alignment
```

---

## 워크플로우

```
프롬프트 작성 (prompts/{name}_prompt.txt)
    │
    ▼
Claude Code에서 /eval-criteria {name}
    │
    ▼
생성된 코드를 llm_judge.py에 복붙
    │
    ▼
eval_config.yaml에 criteria 추가
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
