# Claude Code 프로젝트 규칙

## 파일 생성 규칙

### `__init__.py` 생성 금지
- 새 Python 패키지(폴더) 생성 시 `__init__.py` 파일을 만들지 마세요
- Python 3.3+ namespace packages 방식 사용
- 기존 `__init__.py`가 있는 폴더는 그대로 유지

### 파일 생성 시 주의사항
- 불필요한 boilerplate 파일 생성 금지
- 기존 프로젝트 구조와 일관성 유지
- README, 문서 파일은 요청 시에만 생성

## 코드 스타일

### Python
- 타입 힌트 사용 권장
- docstring은 한글 작성 가능
- Black 포매터 스타일 준수

### 네이밍
- 파일명: snake_case
- 클래스명: PascalCase
- 변수/함수명: snake_case

## 프로젝트 구조

```
prompt-evaluator/
├── prompt_evaluator/          # pip install 대상 패키지
│   ├── __init__.py            # 공개 API
│   ├── context.py             # EvalContext (프로젝트 경로 설정)
│   ├── config.py              # 모델, 임계값 기본값
│   ├── models.py              # LLM 인스턴스
│   ├── schema.yaml            # config 스키마
│   ├── cli/                   # CLI 명령어 모듈
│   ├── loaders/               # 데이터 로더
│   ├── evaluators/            # 평가자 (Rule-based, LLM Judge)
│   ├── pipelines/             # 평가 파이프라인
│   ├── regression/            # 회귀 테스트
│   ├── versioning/            # 버전 관리
│   ├── utils/                 # 유틸리티
│   ├── skills/                # 번들 스킬 (init 시 복사)
│   └── evaluators/eval_prompts/  # 번들 평가 기준 (init 시 복사)
├── main.py                    # 개발용 CLI 진입점
├── pyproject.toml             # 패키지 설정
├── targets/                   # 평가 대상 프롬프트 (개발용)
├── datasets/                  # 테스트 데이터 (개발용)
├── eval_prompts/              # LLM Judge 평가 프롬프트 (개발용)
└── results/                   # 평가 결과 (개발용)
```

## 커밋 규칙

- 한글 커밋 메시지 허용
- 변경 사항을 명확하게 설명
