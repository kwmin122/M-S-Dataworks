# 나라장터 검색 업그레이드 계획

## 근본 문제

현재 `nara_api.py`는 **이전 API** (`getBidPblancListInfoServc` — 등록일시 기반 조회)를 사용.
이 API는 `bidNtceNm` (공고명 검색) 파라미터를 **지원하지 않음**.

**PPSSrch API** (`getBidPblancListInfoServcPPSSrch`)로 전환해야 공고명 키워드 검색이 가능.

## API 참고

- 문서: `/Users/min-kyungwook/Downloads/조달청_OpenAPI참고자료_나라장터_입찰공고정보서비스_1.1 (1).docx`
- 인증키: `ed9bf229a321d186fa563fc3482525aeaec37faf8ca387c54f08b6be873f3c03`
- 서비스 URL: `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/`

### PPSSrch 오퍼레이션 (나라장터검색조건)

| 오퍼레이션 | 용도 |
|-----------|------|
| `getBidPblancListInfoCnstwkPPSSrch` | 공사 |
| `getBidPblancListInfoServcPPSSrch` | 용역 |
| `getBidPblancListInfoFrgcptPPSSrch` | 외자 |
| `getBidPblancListInfoThngPPSSrch` | 물품 |

### PPSSrch 요청 파라미터 (전체)

| 파라미터 | 한글명 | 필수 | 설명 |
|---------|--------|------|------|
| numOfRows | 한 페이지 결과 수 | 1 | |
| pageNo | 페이지 번호 | 1 | |
| ServiceKey | 서비스키 | 1 | |
| type | 타입 | 0 | json |
| inqryDiv | 조회구분 | 1 | 1:공고게시일시, 2:개찰일시 |
| inqryBgnDt | 조회시작일시 | 0 | YYYYMMDDHHMM |
| inqryEndDt | 조회종료일시 | 0 | YYYYMMDDHHMM |
| **bidNtceNm** | **입찰공고명** | 0 | **키워드 검색 (부분 매칭)** |
| ntceInsttNm | 공고기관명 | 0 | 부분 매칭 |
| dminsttNm | 수요기관명 | 0 | 부분 매칭 |
| prtcptLmtRgnNm | 참가제한지역명 | 0 | 부분 매칭 |
| prtcptLmtRgnCd | 참가제한지역코드 | 0 | 11:서울, 26:부산, 27:대구... |
| indstrytyNm | 업종명 | 0 | 부분 매칭 |
| indstrytyCd | 업종코드 | 0 | |
| presmptPrceBgn | 추정가격시작 | 0 | 원 |
| presmptPrceEnd | 추정가격종료 | 0 | 원 |
| bidClseExcpYn | 입찰마감제외여부 | 0 | N |

### PPSSrch 응답 주요 필드

| 필드 | 한글명 |
|------|--------|
| bidNtceNo | 입찰공고번호 |
| bidNtceNm | 입찰공고명 |
| ntceInsttNm | 공고기관명 |
| dminsttNm | 수요기관명 |
| bidNtceDt | 입찰공고일시 |
| bidClseDt | 입찰마감일시 |
| opengDt | 개찰일시 |
| presmptPrce | 추정가격 |
| bdgtAmt | 예산금액 |
| cntrctCnclsMthdNm | 계약체결방법명 |
| bidMethdNm | 입찰방식명 |
| ntceSpecDocUrl1~10 | 공고규격서URL (첨부파일) |
| bidNtceDtlUrl | 입찰공고상세URL |
| sucsfbidMthdNm | 낙찰방법명 |

## 구현 계획

### 1. nara_api.py 수정
- 기존 `getBidPblancListInfoServc` → `PPSSrch` 엔드포인트로 전환
- `bidNtceNm` 파라미터로 공고명 키워드 검색 지원
- 응답 파싱을 새 필드명에 맞게 업데이트

### 2. Studio 검색 UI 확장
RfpStage.tsx 검색 패널에 필터 추가:
- 공고명 (현재 있음)
- **지역 (prtcptLmtRgnNm/Cd)** — 드롭다운
- **금액 범위 (presmptPrceBgn/End)** — 최소/최대 입력
- **기간 (inqryBgnDt/EndDt)** — 날짜 선택
- **업종 (indstrytyNm)** — 텍스트 입력
- **카테고리 (용역/물품/공사/외자)** — 이미 있음
- **입찰마감 제외 (bidClseExcpYn)** — 체크박스

### 3. 검색 결과 카드 강화
- 추정가격 표시
- 계약체결방법 표시
- 마감일시 D-day 표시
- 첨부파일 다운로드 링크
- "선택 → 텍스트 채우기" + "선택 → 바로 분석" 2가지 액션

### 4. Chat 검색도 동일하게 업그레이드
- Chat의 공고 검색도 PPSSrch API 사용하도록 통일

### 5. 알림 시스템 연동
- 알림 필터도 PPSSrch 파라미터와 동일한 기준으로 설정 가능하게
