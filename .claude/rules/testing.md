---
paths:
  - "tests/**"
  - "**/tests/**"
  - "**/__tests__/**"
---

## MANDATORY

### web_saas Jest
- 테스트 위치: `src/lib/<module>/__tests__/<name>.test.ts`
- `testMatch: ['**/__tests__/**/*.test.ts']`
- `@/lib/prisma` → `src/__mocks__/prisma.ts` 자동 모킹
- `@/lib/ids` → `src/__mocks__/ids.ts`
- `src/__mocks__/prisma.ts`에 테스트에서 사용하는 prisma 메서드 추가 필요

### Studio Backend (services/web_app/tests/)
- PostgreSQL 필수: `BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test'`
- 테스트 격리: transactional isolation (savepoint rollback)
- Classifier regression corpus: 18 parametrized cases

### 테스트 파일 매핑

**레거시 Python (tests/)**
| 테스트 | 대상 |
|--------|------|
| test_constraint_evaluator | matcher.py ConstraintEvaluator |
| test_matcher_detail_rules | matcher.py 규칙형 판단 |
| test_rfx_analyzer_multipass | rfx_analyzer.py 멀티패스 |
| test_hybrid_search | engine.py BM25+벡터 |
| test_chat_router | chat_router.py 인텐트 분류 |

**rag_engine (rag_engine/tests/)**
| 테스트 | 대상 |
|--------|------|
| test_proposal_orchestrator | 전체 파이프라인 |
| test_wbs_orchestrator | WBS 파이프라인 |
| test_ppt_orchestrator | PPT 파이프라인 |
| test_track_record_orchestrator | 실적기술서 파이프라인 |
| test_knowledge_* | Layer 1 지식 파이프라인 |
| test_quality_checker | 블라인드/모호 감지 |

**Studio API (services/web_app/tests/)**
| 테스트 | 대상 |
|--------|------|
| test_studio_projects_api | 프로젝트 CRUD + ACL |
| test_studio_classify_api | 패키지 분류 |
| test_studio_company_assets_api | 회사 자산 staging/promote |
| test_studio_style_skills_api | 스타일 pin/derive/promote |
| test_studio_generate_proposal_api | 제안서 생성 + contract |
| test_studio_generate_execution_plan_api | WBS 생성 |
| test_studio_generate_ppt_api | PPT 생성 |
| test_studio_generate_track_record_api | 실적기술서 생성 |
| test_studio_package_items_api | 체크리스트 + evidence |
| test_studio_relearn_api | review/relearn 루프 |
| test_package_classifier | 분류기 + 18건 corpus |
