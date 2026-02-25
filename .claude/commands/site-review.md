# /site-review — 사이트 리뷰 & 개선 워크플로우

이 커맨드는 KiraBot 사이트를 종합적으로 리뷰하고 개선하는 에이전트 팀 워크플로우를 안내합니다.

## 에이전트 팀 구성

| 역할 | 도구 | 에이전트 | 설명 |
|------|------|---------|------|
| QA 리뷰어 | 크롬 Claude | (외부) | 사이트를 직접 보며 이슈 발견 |
| UX 최적화 | Claude Code | `site-qa-optimizer` | QA 리포트 기반 코드 수정 |
| 페이지 빌더 | Claude Code | `page-builder` | 새 페이지/컴포넌트 구현 |
| 이미지 생성 | Gemini 3.1 Pro | (외부/나노바나나) | 일러스트/아이콘 생성 |
| 에셋 통합 | Claude Code | `asset-integrator` | 이미지를 사이트에 반영 |
| 코드 리뷰 | Claude Code | `code-review-veteran` | 최종 코드 품질 검증 |

## 워크플로우 순서

### Phase 1: QA 리뷰 (크롬 Claude)
1. `docs/agent-prompts/chrome-qa-reviewer.md`의 프롬프트를 크롬 Claude에 입력
2. localhost:5173 또는 배포 URL에서 전체 워크플로우 테스트
3. 이슈 리포트를 마크다운으로 작성
4. 리포트를 이 세션에 붙여넣기

### Phase 2: 이슈 수정 (Claude Code)
리포트가 들어오면:
1. `site-qa-optimizer` 에이전트로 코드 수정 가능한 이슈 처리
2. 신규 페이지가 필요한 이슈는 `page-builder` 에이전트에 전달
3. 빌드 확인 후 결과 보고

### Phase 3: 이미지 생성 (Gemini)
1. `docs/agent-prompts/gemini-image-generator.md`의 템플릿을 나노바나나 프로에서 사용
2. Gemini 3.1 Pro 모델 선택
3. 생성된 이미지를 다운로드하여 `frontend/kirabot/public/images/`에 저장
4. 이미지 경로를 이 세션에 알려주기

### Phase 4: 에셋 통합 (Claude Code)
1. `asset-integrator` 에이전트로 이미지를 컴포넌트에 연결
2. 빌드 확인

### Phase 5: 최종 검증
1. `code-review-veteran` 에이전트로 전체 변경사항 리뷰
2. 크롬 Claude로 수정 결과 재검증

## 핸드오프 체크리스트

각 Phase 전환 시 확인:
- [ ] 이전 Phase 결과물이 완전한가?
- [ ] 빌드가 깨지지 않았는가?
- [ ] 다음 에이전트에 전달할 컨텍스트가 충분한가?

## 빠른 시작

사용자에게 물어볼 것:
1. "크롬 Claude QA 리포트가 있나요, 아니면 특정 이슈를 지정하시나요?"
2. "이미지 생성이 필요한가요?"
3. "어떤 Phase부터 시작하시나요?"
