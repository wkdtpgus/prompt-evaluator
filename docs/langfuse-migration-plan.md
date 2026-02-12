# Langfuse 마이그레이션 — 미완료 작업

> 완료된 Phase 1-6 및 Phase 7 인프라/배포/보안 내용은 [기능 명세서](./SPECIFICATION.md), [사용 가이드](../prompt_evaluator/GUIDE.md)로 이관됨

---

## Phase 7: GCP 클라우드 배포 (잔여)

**도메인/HTTPS** (내부용이라 하지 않고, nginx basic auth로 대체)

- [ ] 도메인 구매 및 DNS A 레코드 연결
- [ ] Let's Encrypt + certbot으로 SSL 인증서 발급
- [ ] `NEXTAUTH_URL` HTTPS로 변경

**운영**

- [ ] 백업 설정
  - [ ] PostgreSQL 정기 백업 (pg_dump cron 또는 Cloud SQL 자동 백업)
  - [ ] ClickHouse 데이터 스냅샷
  - [ ] Persistent Disk 스냅샷 스케줄
- [ ] 모니터링
  - [ ] Cloud Monitoring 대시보드 (CPU, 메모리, 디스크)
  - [ ] Uptime Check (80 포트 헬스체크, Nginx 경유)
  - [ ] 디스크 용량 알림 (80% 초과 시)
- [ ] 자동 시작 설정
  - [ ] systemd 서비스로 Docker Compose 등록
  - [ ] VM 재시작 시 자동 복구

**코드 수정 (프로젝트)**

- [ ] `.env` 업데이트
  - [ ] `LANGFUSE_HOST` → 클라우드 서버 URL로 변경
  - [ ] `.env.example`에 클라우드 설정 예시 추가
- [ ] 연결 테스트
  - [ ] 로컬에서 클라우드 Langfuse로 실험 실행
  - [ ] 트레이싱/데이터셋/실험 결과 확인

---

## Phase 8: 스코어링 리포트 고도화

**목표**: 실험 실행 시 상세 스코어 리포트 자동 생성

- [ ] comment 필드 JSON 구조화
  - [ ] `LangfuseEvaluation(comment=json.dumps({...}))` 형태로 저장
  - [ ] failed_items, passed_items, reasoning, suggestions 포함
- [ ] 실험 종료 시 자동 리포트 생성
  - [ ] `_run_langfuse_experiment()` 완료 후 리포트 출력
  - [ ] Langfuse API로 스코어 데이터 추출 → JSON 파싱
  - [ ] 실패 케이스 상세 분석 포함
  - [ ] 결과를 `results/{experiment_name}/report.md` 저장

---

## Phase 9: 프로덕션 트레이스 → 테스트 데이터 자동 수집

**목표**: Langfuse 프로덕션 트레이스에서 실제 사용자 데이터를 자동 추출하여 평가 데이터셋에 추가

**전제 조건**: Phase 7 (GCP 배포) 완료, 프로덕션 앱의 트레이싱이 Langfuse로 전환된 상태

### CLI 커맨드

```bash
# Langfuse 트레이스에서 데이터 수집
python main.py dataset collect \
  --name prep_output_analyze \
  --source langfuse \
  --limit 10 \
  --since 2026-01-25

# 수집 후 Langfuse/LangSmith 데이터셋에 재업로드
python main.py dataset upload --name prep_output_analyze
```

### 구현 범위

- [ ] `utils/trace_collector.py` — 트레이스 데이터 수집 모듈
  - [ ] Langfuse `client.fetch_traces()` 활용
  - [ ] 필터링: 날짜 범위, 프로젝트/세션 단위, 성공/실패 여부
  - [ ] 트레이스 input → `test_cases.json` 형식 변환
  - [ ] 중복 제거 (기존 데이터셋의 inputs와 비교)
- [ ] `cli/dataset.py` — `collect` 커맨드
  - [ ] `--source langfuse|langsmith` 트레이스 소스 선택
  - [ ] `--name` 타겟 데이터셋 이름
  - [ ] `--limit` 최대 수집 건수
  - [ ] `--since` / `--until` 날짜 필터
  - [ ] `--append` 기존 데이터셋에 추가 (기본) vs `--overwrite`
  - [ ] `--dry-run` 미리보기 (저장 없이 추출 결과만 출력)
- [ ] `expected.json` 스텁 자동 생성
  - [ ] 수집된 케이스에 대해 빈 껍데기 엔트리 추가
  - [ ] `{"keywords": [], "forbidden": [], "reference": {}}`
- [ ] 입력 키 매핑
  - [ ] 프로덕션 트레이스 input 키 → 프롬프트 플레이스홀더 변수명 자동 매핑
  - [ ] 매핑 불일치 시 경고 + 수동 매핑 설정 지원 (`config.yaml`의 `input_mapping` 필드)
- [ ] `cli/dataset.py` — `upload` 커맨드 (기존 기능 통합)
  - [ ] 로컬 `test_cases.json` + `expected.json` → Langfuse/LangSmith 데이터셋 업로드

### 데이터 흐름

```
프로덕션 앱 → Langfuse 트레이스
                  ↓ dataset collect
              datasets/{name}/test_cases.json  (로컬, 추가)
              datasets/{name}/expected.json    (스텁 추가)
                  ↓ 수동 큐레이션 (expected 보강)
                  ↓ dataset upload
              Langfuse/LangSmith dataset items (평가용)
                  ↓ experiment
              평가 실행
```

---

## 마이그레이션 완료 후

- [ ] LangSmith 환경변수 비활성화 (`LANGSMITH_TRACING=false`)
- [ ] README.md 업데이트 (Langfuse 사용법 추가)
- [ ] 팀 공유 및 문서화
