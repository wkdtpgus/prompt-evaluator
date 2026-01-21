# 테스트 케이스 JSON 패턴

Swagger UI에서 바로 테스트 가능한 JSON 형태 예시입니다.

## 기본 구조

```json
{
  "id": "case_001",
  "description": "케이스 설명",
  "inputs": {
    // API request body
  }
}
```

## 케이스 유형별 예시

### Normal (정상)

```json
{
  "id": "case_001",
  "description": "정상 - 모든 필드 입력",
  "inputs": {
    "name": "홍길동",
    "items": ["item1", "item2", "item3"],
    "options": {"key": "value"}
  }
}
```

### Edge (경계)

```json
{
  "id": "case_011",
  "description": "엣지 - 빈 배열",
  "inputs": {
    "name": "테스트",
    "items": [],
    "options": {}
  }
}
```

```json
{
  "id": "case_012",
  "description": "엣지 - 특수문자 포함",
  "inputs": {
    "name": "테스트<script>",
    "items": ["item\"with'quotes"],
    "options": {"key": "값\n줄바꿈"}
  }
}
```

### Stress (부하)

```json
{
  "id": "case_016",
  "description": "스트레스 - 많은 항목",
  "inputs": {
    "name": "테스트",
    "items": ["item1", "item2", "...", "item50"],
    "options": {"key1": "v1", "key2": "v2", "...": "..."}
  }
}
```

## ID 규칙

- `case_001~010`: Normal
- `case_011~015`: Edge
- `case_016~020`: Stress
