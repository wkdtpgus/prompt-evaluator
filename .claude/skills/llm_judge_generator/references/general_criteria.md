# 일반 평가 기준

프롬프트 종류에 관계없이 사용할 수 있는 범용 LLM Judge 평가 기준입니다.

## instruction_following
프롬프트 지시사항 준수도

**체크리스트:**
1. Output Format: 지정된 출력 형식 준수
2. All Requirements: 모든 지시사항 충족
3. Constraints: 제약조건 준수
4. No Extras: 불필요한 추가 없음
5. Language: 요청된 언어 사용

## factual_accuracy
사실 정확성 / 할루시네이션 검사

**체크리스트:**
1. Grounded: 입력 데이터에 기반
2. No Fabrication: 없는 정보 생성 안함
3. Consistent: 내부 일관성
4. Verifiable: 검증 가능한 주장
5. Source Faithful: 원본에 충실

## output_quality
전반적 출력 품질

**체크리스트:**
1. Completeness: 완전한 응답
2. Clarity: 명확한 표현
3. Coherence: 논리적 일관성
4. Usefulness: 실용적 가치
5. Professionalism: 전문성
