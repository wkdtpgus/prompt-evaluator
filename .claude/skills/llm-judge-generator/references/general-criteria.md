# 기존 평가 기준 참조

이 프로젝트에서 이미 정의된 LLM Judge 평가 기준입니다.
새 평가기준 생성 시 중복을 피하고 일관성을 유지하기 위해 참조하세요.

## 일반 평가 기준

### instruction_following
프롬프트 지시사항 준수도

**체크리스트:**
1. Output Format: 지정된 출력 형식 준수
2. All Requirements: 모든 지시사항 충족
3. Constraints: 제약조건 준수
4. No Extras: 불필요한 추가 없음
5. Language: 요청된 언어 사용

### factual_accuracy
사실 정확성 / 할루시네이션 검사

**체크리스트:**
1. Grounded: 입력 데이터에 기반
2. No Fabrication: 없는 정보 생성 안함
3. Consistent: 내부 일관성
4. Verifiable: 검증 가능한 주장
5. Source Faithful: 원본에 충실

### output_quality
전반적 출력 품질

**체크리스트:**
1. Completeness: 완전한 응답
2. Clarity: 명확한 표현
3. Coherence: 논리적 일관성
4. Usefulness: 실용적 가치
5. Professionalism: 전문성

## 1on1 Meeting 특화 평가 기준

### purpose_alignment
1on1 미팅 목적 부합도

**체크리스트:**
1. Focus on Member: 구성원 감정/어려움에 집중
2. Support Oriented: 지원 방법 제안
3. Avoids Status Questions: 업무 현황 질문 회피
4. Explores Growth: 성장/경력 측면 다룸
5. Relationship Building: 신뢰/소통 구축

### coaching_quality
코칭 힌트 품질

**체크리스트:**
1. Actionable: 즉시 실행 가능
2. Specific: 상황에 특화
3. Empathetic: 공감적 이해
4. Safe: 경계 존중
5. Contextual: 맥락 연결

### tone_appropriateness
톤/어조 적절성

**체크리스트:**
1. Professional: 전문적이면서 따뜻함
2. Non-judgmental: 비판단적
3. Constructive: 건설적 프레이밍
4. Appropriate Length: 적절한 길이
5. Language Match: 언어 일치

### sensitive_topic_handling
민감한 주제 처리

**체크리스트:**
1. Recognizes Signals: 민감 신호 인식
2. Respects Boundaries: 경계 존중
3. Safe Approach: 안전한 접근
4. Alternative Topics: 대안 주제 제시
5. No Pressure: 압박 없음
