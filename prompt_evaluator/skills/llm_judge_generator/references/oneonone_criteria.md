# 1on1 Meeting 도메인 평가기준 예시

이 프로젝트의 실제 도메인 특화 평가기준입니다.
새로운 평가기준 생성 시 이 패턴을 참고하세요.

## 도메인 컨텍스트

**1on1 미팅이란?**
- 리더와 구성원이 1:1로 대화하는 시간
- 업무 현황 보고가 **아님** (리더는 이미 알고 있음)
- 구성원의 어려움, 성장, 웰빙에 집중

**핵심 목적:**
- Member support: 구성원의 어려움과 필요 이해
- Relationship building: 진정한 관심 표현
- Growth facilitation: 성장과 성찰 지원
- Trust building: 안전한 소통 공간 형성

---

## purpose_alignment (1on1 미팅 목적 부합도)

```python
"purpose_alignment": """You are an expert evaluator for 1on1 meeting coaching quality.

## Evaluation Criteria
1on1 meetings are NOT work status report meetings. Leaders already know basic work status.

The PURPOSE of 1on1 is:
- **Member support**: Understand member's challenges, blockers, and needs
- **Relationship building**: Show genuine care about the member's well-being
- **Growth facilitation**: Help member reflect and grow
- **Trust building**: Create safe space for open communication

## Input:
{input}

## AI's Output (coaching hints):
{output}

## Checklist - Score each item (0 or 1):

1. **Focus on Member**: Does the hint focus on member's feelings, struggles, or well-being?
2. **Support Oriented**: Does it suggest how leader can support/help (not request information)?
3. **Avoids Status Questions**: Does it avoid asking about basic work status/progress?
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
    "good_examples": ["list of hints that serve 1on1 purpose well"],
    "bad_examples": ["list of hints that feel like status reports"]
}}"""
```

### 이 평가기준이 좋은 이유

| 특징 | 설명 |
|-----|------|
| "무엇이 아닌지" 명시 | "NOT work status report meetings" |
| 목적 4가지 명확화 | support, relationship, growth, trust |
| 안티패턴 체크 | "Avoids Status Questions" 항목 |
| good/bad 예시 출력 | 구체적 피드백 제공 |

---

## coaching_quality (코칭 힌트 품질)

```python
"coaching_quality": """You are evaluating coaching hint quality for 1on1 meetings.

## Context:
A coaching hint helps leaders prepare better questions for 1on1 meetings.

## Input (member's response data):
{input}

## AI's Coaching Hints:
{output}

## Checklist - Score each item (0 or 1):

1. **Actionable**: Can the leader act on this hint immediately?
2. **Specific**: Is it specific to this member's situation (not generic)?
3. **Empathetic**: Does it show understanding of member's perspective?
4. **Safe**: Does it respect boundaries and sensitive topics?
5. **Contextual**: Does it connect to what the member actually said/expressed?

## Response Format (JSON):
{{
    "checklist": {{
        "actionable": 0 or 1,
        "specific": 0 or 1,
        "empathetic": 0 or 1,
        "safe": 0 or 1,
        "contextual": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "feedback": "brief constructive feedback on how to improve"
}}"""
```

### 이 평가기준이 좋은 이유

- **Actionable**: 실제로 쓸 수 있는지 체크
- **Specific**: 뻔한 조언이 아닌지 체크
- **Contextual**: 구성원이 실제로 말한 내용과 연결되는지

---

## sensitive_topic_handling (민감한 주제 처리)

```python
"sensitive_topic_handling": """You are evaluating how well the AI handles sensitive topics.

## Sensitive Topics in 1on1:
- Burnout signals
- Team conflicts
- Career concerns
- Personal struggles
- Avoided responses (member deflecting questions)

## Input:
{input}

## AI's Coaching Hints:
{output}

## Checklist - Score each item (0 or 1):

1. **Recognizes Signals**: Does it identify sensitive signals in member's response?
2. **Respects Boundaries**: Does it suggest respecting member's boundaries?
3. **Safe Approach**: Does it recommend gentle, non-intrusive follow-up?
4. **Alternative Topics**: Does it suggest alternative safer topics when needed?
5. **No Pressure**: Does it avoid pushing members to share more than comfortable?

## Response Format (JSON):
{{
    "checklist": {{
        "recognizes_signals": 0 or 1,
        "respects_boundaries": 0 or 1,
        "safe_approach": 0 or 1,
        "alternative_topics": 0 or 1,
        "no_pressure": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "sensitive_areas": ["list of sensitive topics detected"],
    "handling_quality": "brief assessment of how well sensitive areas were handled"
}}"""
```

### 이 평가기준이 좋은 이유

- **민감 주제 목록 명시**: 번아웃, 갈등, 경력, 개인 고민
- **"회피 응답" 케이스 포함**: 구성원이 질문을 피할 때
- **안전 우선**: respects_boundaries, no_pressure

---

## 패턴 요약

새 도메인 평가기준 작성 시 이 패턴을 따르세요:

1. **Evaluation Criteria 섹션**에서 도메인 컨텍스트 설명
2. **"무엇이 아닌지"** 명시 (안티패턴)
3. **체크리스트 5개**: Yes/No로 판단 가능
4. **도메인 용어** 사용 (coaching hint, burnout signals 등)
5. **추가 출력 필드**: good/bad_examples, feedback, sensitive_areas 등
