"""
나라장터 공공데이터포털 Open API 클라이언트

공고 검색, 첨부파일 조회, 파일 다운로드를 지원한다.
API 키: DATA_GO_KR_API_KEY 환경변수
"""

from __future__ import annotations

import os
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import httpx

logger = logging.getLogger(__name__)

NARA_API_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"

CATEGORY_ENDPOINTS: dict[str, str] = {
    "goods": "getBidPblancListInfoThngPPSSrch",
    "service": "getBidPblancListInfoServcPPSSrch",
    "construction": "getBidPblancListInfoCnstwkPPSSrch",
    "foreign": "getBidPblancListInfoFrgcptPPSSrch",
    "etc": "getBidPblancListInfoEtcPPSSrch",
}

# 상세 조회 엔드포인트 (ntceSpecFileNm1~10 포함)
DETAIL_ENDPOINTS: dict[str, str] = {
    "goods": "getBidPblancListInfoThng",
    "service": "getBidPblancListInfoServc",
    "construction": "getBidPblancListInfoCnstwk",
    "foreign": "getBidPblancListInfoFrgcpt",
    "etc": "getBidPblancListInfoEtc",
}

ATTACHMENT_ENDPOINT = "getBidPblancListInfoEorderAtchFileInfo"

CATEGORY_LABEL: dict[str, str] = {
    "goods": "물품",
    "service": "용역",
    "construction": "공사",
    "foreign": "외자",
    "etc": "기타",
}

# 한글 → API 카테고리 코드 역매핑
CATEGORY_CODE: dict[str, str] = {v: k for k, v in CATEGORY_LABEL.items()}


def _get_api_key() -> str:
    key = os.getenv("DATA_GO_KR_API_KEY", "").strip()
    if not key:
        raise ValueError("DATA_GO_KR_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


def _kst_now() -> datetime:
    """현재 KST 시각."""
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _build_date_range(period: str) -> tuple[str, str]:
    """period → (inqryBgnDt, inqryEndDt) yyyyMMddHHmm 형식."""
    now = _kst_now()
    end_dt = now.strftime("%Y%m%d%H%M")

    delta_map = {"1w": timedelta(weeks=1), "1m": timedelta(days=30), "3m": timedelta(days=90), "6m": timedelta(days=180), "12m": timedelta(days=365)}
    delta = delta_map.get(period, timedelta(days=30))
    bgn = now - delta
    bgn_dt = bgn.strftime("%Y%m%d%H%M")
    return bgn_dt, end_dt


_CHUNK_DAYS = 27  # PPSSrch API 최대 조회 기간 ~28일, 안전 마진 확보


def _split_monthly_ranges(period: str) -> list[tuple[str, str]]:
    """기간을 최대 27일 단위 청크로 분할.

    PPSSrch API는 조회 기간이 약 28일을 초과하면
    '입력범위값 초과 에러'를 반환하므로 27일 단위로 분할한다.
    """
    now = _kst_now()
    delta_map = {"1w": timedelta(weeks=1), "1m": timedelta(days=30), "3m": timedelta(days=90), "6m": timedelta(days=180), "12m": timedelta(days=365)}
    total_delta = delta_map.get(period, timedelta(days=30))

    chunk = timedelta(days=_CHUNK_DAYS)

    # 청크 이내면 분할 불필요
    if total_delta <= chunk:
        bgn = now - total_delta
        return [(bgn.strftime("%Y%m%d%H%M"), now.strftime("%Y%m%d%H%M"))]

    # 27일 단위로 분할
    ranges: list[tuple[str, str]] = []
    end = now
    start = now - total_delta
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + chunk, end)
        ranges.append((cursor.strftime("%Y%m%d%H%M"), chunk_end.strftime("%Y%m%d%H%M")))
        cursor = chunk_end
    return ranges


def _parse_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """나라장터 API JSON 응답에서 item 리스트를 추출한다."""
    # PPSSrch 에러 응답: nkoneps.com.response.ResponseError
    error_resp = data.get("nkoneps.com.response.ResponseError")
    if error_resp:
        err_header = error_resp.get("header", {})
        err_code = str(err_header.get("resultCode", ""))
        err_msg = str(err_header.get("resultMsg", ""))
        logger.warning("나라장터 API 에러 응답 (nkoneps): code=%s, msg=%s", err_code, err_msg)
        return []

    response = data.get("response", {})

    # API 에러 코드 체크
    header = response.get("header", {})
    result_code = str(header.get("resultCode", "00"))
    if result_code != "00":
        result_msg = header.get("resultMsg", "Unknown error")
        logger.warning("나라장터 API 에러 응답: code=%s, msg=%s", result_code, result_msg)
        return []

    body = response.get("body", {})
    total = int(body.get("totalCount", 0))
    if total == 0:
        return []

    items = body.get("items", [])
    if isinstance(items, dict):
        item_list = items.get("item", [])
    elif isinstance(items, list):
        item_list = items
    else:
        return []

    if isinstance(item_list, dict):
        item_list = [item_list]

    return item_list if isinstance(item_list, list) else []


def _normalize_bid_notice(item: dict[str, Any], category: str = "") -> dict[str, Any]:
    """나라장터 API 응답 item → 통일된 BidNotice dict."""
    bid_ntce_no = str(item.get("bidNtceNo", "")).strip()
    bid_ntce_ord = str(item.get("bidNtceOrd", "")).strip()

    deadline_raw = str(item.get("bidClseDt", "") or "").strip()
    deadline_at = None
    if deadline_raw:
        # 20260220180000 → 2026-02-20T18:00:00
        cleaned = re.sub(r"[^0-9]", "", deadline_raw)
        if len(cleaned) >= 12:
            try:
                dt = datetime.strptime(cleaned[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
                deadline_at = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    # 추정 가격 (presmptPrce 우선, 없으면 asignBdgtAmt / bsisAmt 대체)
    estimated_price = None
    estimated_price_raw: float | None = None
    for price_field in ("presmptPrce", "asignBdgtAmt", "bsisAmt"):
        raw = item.get(price_field, None)
        if raw:
            try:
                amt = float(str(raw).replace(",", ""))
                if amt > 0:
                    estimated_price = f"{amt:,.0f}원"
                    estimated_price_raw = amt
                    break
            except (ValueError, TypeError):
                pass

    # 공고 게시일시 (bidNtceDt)
    published_raw = str(item.get("bidNtceDt", "") or "").strip()
    published_at = None
    if published_raw:
        cleaned_pub = re.sub(r"[^0-9]", "", published_raw)
        if len(cleaned_pub) >= 8:
            try:
                dt = datetime.strptime(cleaned_pub[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
                published_at = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    # 입찰서 제출 시작일시 (bidBeginDt)
    submit_start_raw = str(item.get("bidBeginDt", "") or "").strip()
    submit_start_at = None
    if submit_start_raw:
        cleaned_sub = re.sub(r"[^0-9]", "", submit_start_raw)
        if len(cleaned_sub) >= 8:
            try:
                dt = datetime.strptime(cleaned_sub[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
                submit_start_at = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    # 공고 URL
    url = str(item.get("bidNtceUrl", "") or "").strip() or None

    # 지역 — 참가제한지역명, 없으면 공고기관 담당자명 대체
    prtcpt_rgn = str(item.get("prtcptLmtRgnNm", "") or "").strip()
    rgn_nm = prtcpt_rgn or str(item.get("ntceInsttOfclNm", "") or "").strip()

    # 계약/입찰 방식
    contract_method = str(item.get("cntrctCnclsMthdNm", "") or "").strip() or None
    bid_method = str(item.get("bidMethdNm", "") or "").strip() or None

    # 상세 URL
    detail_url = str(item.get("bidNtceDtlUrl", "") or "").strip() or None

    # 개찰일시
    openg_raw = str(item.get("opengDt", "") or "").strip()
    openg_at = None
    if openg_raw:
        cleaned_openg = re.sub(r"[^0-9]", "", openg_raw)
        if len(cleaned_openg) >= 12:
            try:
                dt = datetime.strptime(cleaned_openg[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
                openg_at = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    # 첨부파일 URL (PPSSrch 응답에 포함, 최대 10개)
    attachments: list[dict[str, str]] = []
    for i in range(1, 11):
        file_nm = str(item.get(f"ntceSpecFileNm{i}", "") or "").strip()
        file_url = str(item.get(f"ntceSpecDocUrl{i}", "") or "").strip()
        if file_nm and file_url:
            attachments.append({"fileNm": file_nm, "fileUrl": file_url})

    return {
        "id": bid_ntce_no,
        "title": str(item.get("bidNtceNm", "")).strip(),
        "issuingOrg": str(item.get("ntceInsttNm", "")).strip(),
        "demandOrg": str(item.get("dminsttNm", "")).strip() or None,
        "department": str(item.get("dminsttNm", "")).strip() or None,
        "region": rgn_nm or None,
        "deadlineAt": deadline_at,
        "publishedAt": published_at,
        "submitStartAt": submit_start_at,
        "opengAt": openg_at,
        "awardMethod": str(item.get("sucsfbidMthdNm", "")).strip() or None,
        "contractMethod": contract_method,
        "bidMethod": bid_method,
        "url": url,
        "detailUrl": detail_url,
        "estimatedPrice": estimated_price,
        "estimatedPriceRaw": estimated_price_raw,
        "category": CATEGORY_LABEL.get(category, category),
        "bidNtceOrd": bid_ntce_ord or None,
        "attachments": attachments if attachments else None,
    }


async def _fetch_category(
    client: httpx.AsyncClient,
    endpoint: str,
    category: str,
    params: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """단일 카테고리 엔드포인트 호출 (자동 페이지네이션)."""
    url = f"{NARA_API_BASE}/{endpoint}"
    all_items: list[dict[str, Any]] = []
    total = 0
    page_no = 1
    rows_per_page = int(params.get("numOfRows", 500))

    while True:
        paged_params = {**params, "pageNo": str(page_no)}
        try:
            resp = await client.get(url, params=paged_params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("나라장터 API HTTP 오류 (%s, page=%d): %s", endpoint, page_no, exc)
            break
        except Exception as exc:
            logger.warning("나라장터 API 호출 실패 (%s, page=%d): %s", endpoint, page_no, exc)
            break

        items = _parse_items(data)
        if page_no == 1:
            total = int(data.get("response", {}).get("body", {}).get("totalCount", 0))

        all_items.extend(items)

        # 더 이상 가져올 페이지가 없으면 중단
        if len(items) < rows_per_page or len(all_items) >= total:
            break
        page_no += 1
        # 안전 장치: 최대 10페이지
        if page_no > 10:
            logger.warning("페이지네이션 최대 한도 초과 (%s, total=%d)", endpoint, total)
            break

    notices = [_normalize_bid_notice(item, category) for item in all_items]
    return notices, total


async def search_bids(
    *,
    keywords: str = "",
    category: str = "all",
    region: str = "",
    region_code: str = "",
    min_amt: float | None = None,
    max_amt: float | None = None,
    period: str = "1m",
    start_date: str = "",
    end_date: str = "",
    industry: str = "",
    demand_org: str = "",
    exclude_expired: bool = True,
    bid_close_excl: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """나라장터 공고 검색 (PPSSrch 엔드포인트).

    Args:
        keywords: 공고명 키워드 (bidNtceNm)
        category: all/service/goods/construction/foreign/etc
        region: 참가제한지역명 (prtcptLmtRgnNm) — 부분매칭
        region_code: 참가제한지역코드 (prtcptLmtRgnCd) — 11:서울, 26:부산 등
        min_amt: 추정가격 하한 (원)
        max_amt: 추정가격 상한 (원)
        period: 조회기간 ("1w"/"1m"/"3m"/"6m"/"12m")
        start_date: 직접 지정 시작일 (YYYYMMDD), period보다 우선
        end_date: 직접 지정 종료일 (YYYYMMDD), period보다 우선
        industry: 업종명 (indstrytyNm) — 부분매칭
        demand_org: 수요기관명 (dminsttNm) — 부분매칭
        exclude_expired: 마감된 공고 클라이언트 필터 (기본 True)
        bid_close_excl: API 마감 제외 (bidClseExcpYn=Y) — 서버 측 필터
        page: 페이지 번호
        page_size: 페이지 크기

    Returns:
        {"notices": [...], "total": int, "page": int, "pageSize": int}
    """
    api_key = _get_api_key()

    # 직접 날짜 지정이 있으면 period 무시
    if start_date and end_date:
        # YYYYMMDD → YYYYMMDDHHMM
        bgn = start_date.replace("-", "")[:8] + "0000"
        end = end_date.replace("-", "")[:8] + "2359"
        date_ranges = [(bgn, end)]
        # 27일 초과 시 분할 (PPSSrch 최대 28일 제한)
        from datetime import datetime as dt_cls
        try:
            d_bgn = dt_cls.strptime(bgn[:8], "%Y%m%d")
            d_end = dt_cls.strptime(end[:8], "%Y%m%d")
            if (d_end - d_bgn).days > _CHUNK_DAYS:
                ranges: list[tuple[str, str]] = []
                cursor = d_bgn
                while cursor < d_end:
                    chunk_end = min(cursor + timedelta(days=_CHUNK_DAYS), d_end)
                    ranges.append((cursor.strftime("%Y%m%d0000"), chunk_end.strftime("%Y%m%d2359")))
                    cursor = chunk_end
                date_ranges = ranges
        except ValueError:
            pass
    else:
        date_ranges = _split_monthly_ranges(period)

    # 각 청크 API 호출에서는 충분히 많은 결과를 가져온다.
    # 페이지네이션은 전체 결과 병합 후 적용.
    # _fetch_category가 자동 페이지네이션하므로 500이면 대부분 1회 호출로 충족.
    CHUNK_ROWS = 500

    shared_params: dict[str, Any] = {
        "serviceKey": api_key,
        "numOfRows": str(CHUNK_ROWS),
        "pageNo": "1",
        "inqryDiv": "1",  # 공고일 기준
        "type": "json",
    }
    if keywords:
        shared_params["bidNtceNm"] = keywords
    if region and region != "전국":
        shared_params["prtcptLmtRgnNm"] = region
    if region_code:
        shared_params["prtcptLmtRgnCd"] = region_code
    if min_amt is not None:
        shared_params["presmptPrceBgn"] = str(int(min_amt))
    if max_amt is not None:
        shared_params["presmptPrceEnd"] = str(int(max_amt))
    if industry:
        shared_params["indstrytyNm"] = industry
    if demand_org:
        shared_params["dminsttNm"] = demand_org
    if bid_close_excl:
        shared_params["bidClseExcpYn"] = "Y"

    all_notices: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient() as client:
        for bgn_dt, end_dt in date_ranges:
            chunk_params = {**shared_params, "inqryBgnDt": bgn_dt, "inqryEndDt": end_dt}

            if category != "all" and category in CATEGORY_ENDPOINTS:
                endpoint = CATEGORY_ENDPOINTS[category]
                chunk_notices, _ = await _fetch_category(client, endpoint, category, chunk_params)
            else:
                chunk_notices = []
                for cat, endpoint in CATEGORY_ENDPOINTS.items():
                    cat_notices, _ = await _fetch_category(client, endpoint, cat, chunk_params)
                    chunk_notices.extend(cat_notices)

            # 중복 제거 (여러 청크에서 같은 공고 반환 가능)
            for n in chunk_notices:
                nid = n.get("id", "")
                if nid and nid not in seen_ids:
                    seen_ids.add(nid)
                    all_notices.append(n)

    notices = all_notices

    # 마감일 지난 공고 필터 (KST 기준)
    if exclude_expired:
        now_kst = _kst_now().strftime("%Y-%m-%dT%H:%M:%S")
        notices = [
            n for n in notices
            if not n.get("deadlineAt") or n["deadlineAt"] >= now_kst
        ]

    # 진행중 공고 우선, 그 안에서 마감 임박순 정렬
    now_kst = _kst_now().strftime("%Y-%m-%dT%H:%M:%S")
    notices.sort(key=lambda n: (
        0 if (n.get("deadlineAt") or "9999-12-31") >= now_kst else 1,
        n.get("deadlineAt") or "9999-12-31",
    ))

    # 전체 결과에서 페이지네이션 적용
    total = len(notices)
    start = (page - 1) * page_size
    end = start + page_size
    paged_notices = notices[start:end]

    return {
        "notices": paged_notices,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }




async def get_bid_detail_attachments(
    bid_ntce_no: str,
    bid_ntce_ord: str = "00",
    category: str = "",
) -> list[dict[str, Any]]:
    """공고 상세 API에서 ntceSpecFileNm1~10 / ntceSpecDocUrl1~10 추출.

    category: 한글 라벨("물품","용역",...) 또는 API 코드("goods","service",...)
    카테고리를 모르면 5개 엔드포인트 순차 시도.
    """
    api_key = _get_api_key()
    params = {
        "serviceKey": api_key,
        "numOfRows": "1",
        "pageNo": "1",
        "inqryDiv": "2",
        "bidNtceNo": bid_ntce_no,
        "bidNtceOrd": bid_ntce_ord,
        "type": "json",
    }

    # 카테고리 코드 결정
    cat_code = CATEGORY_CODE.get(category, category) if category else ""
    if cat_code and cat_code in DETAIL_ENDPOINTS:
        endpoints_to_try = [(cat_code, DETAIL_ENDPOINTS[cat_code])]
    else:
        endpoints_to_try = list(DETAIL_ENDPOINTS.items())

    async with httpx.AsyncClient() as client:
        for cat, endpoint in endpoints_to_try:
            url = f"{NARA_API_BASE}/{endpoint}"
            try:
                resp = await client.get(url, params=params, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.debug("상세 API 호출 실패 (%s): %s", endpoint, exc)
                continue

            items = _parse_items(data)
            if not items:
                continue

            item = items[0]
            attachments: list[dict[str, Any]] = []

            for i in range(1, 11):
                file_nm = str(item.get(f"ntceSpecFileNm{i}", "") or "").strip()
                file_url = str(item.get(f"ntceSpecDocUrl{i}", "") or "").strip()
                doc_div = str(item.get(f"ntceSpecDocDivNm{i}", "") or "").strip()

                if file_nm and file_url:
                    attachments.append({
                        "fileNm": file_nm,
                        "fileUrl": file_url,
                        "fileSize": 0,
                        "docDiv": doc_div,
                        "source": "detail",
                    })

            if attachments:
                logger.info("상세 API 첨부파일 %d개 발견 (bid=%s, cat=%s)", len(attachments), bid_ntce_no, cat)
                return attachments

    logger.info("상세 API 첨부파일 없음 (bid=%s)", bid_ntce_no)
    return []


async def get_bid_attachments(bid_ntce_no: str, bid_ntce_ord: str = "00") -> list[dict[str, Any]]:
    """공고 첨부파일 목록 조회 (e발주 첨부파일 API).

    inqryDiv=2 (공고번호 기준) 필수.
    응답 필드: eorderAtchFileNm, eorderAtchFileUrl.
    """
    api_key = _get_api_key()
    params = {
        "serviceKey": api_key,
        "numOfRows": "100",
        "pageNo": "1",
        "bidNtceNo": bid_ntce_no,
        "bidNtceOrd": bid_ntce_ord,
        "inqryDiv": "2",  # 공고번호 기준 검색 (필수)
        "type": "json",
    }

    url = f"{NARA_API_BASE}/{ATTACHMENT_ENDPOINT}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("첨부파일 API HTTP 오류: %s", exc)
            return []
        except Exception as exc:
            logger.warning("첨부파일 API 호출 실패: %s", exc)
            return []

    items = _parse_items(data)
    if not items:
        logger.info("첨부파일 없음 (bid=%s)", bid_ntce_no)
        return []

    attachments: list[dict[str, Any]] = []
    for item in items:
        # e발주 API 필드명: eorderAtchFileNm, eorderAtchFileUrl
        file_nm = str(item.get("eorderAtchFileNm", "") or "").strip()
        file_url = str(item.get("eorderAtchFileUrl", "") or "").strip()
        doc_div = str(item.get("eorderDocDivNm", "") or "").strip()

        if file_nm and file_url:
            attachments.append({
                "fileNm": file_nm,
                "fileUrl": file_url,
                "fileSize": 0,
                "docDiv": doc_div,  # 제안요청서 / 기타문서
            })

    if attachments:
        logger.info("첨부파일 %d개 발견 (bid=%s)", len(attachments), bid_ntce_no)
    return attachments


async def download_attachment(file_url: str, dest_dir: str, fallback_name: str = "") -> str:
    """첨부파일 다운로드 → 로컬 경로 반환."""
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(file_url, timeout=60.0)
        resp.raise_for_status()

        # Content-Disposition에서 파일명 추출
        from urllib.parse import urlparse, unquote
        cd = resp.headers.get("content-disposition", "")
        filename = ""
        if "filename=" in cd:
            parts = cd.split("filename=")
            if len(parts) > 1:
                raw = parts[1].strip().strip('"').strip("'").rstrip(";").strip()
                filename = unquote(raw)

        if not filename:
            parsed = urlparse(file_url)
            filename = unquote(parsed.path.split("/")[-1]) if parsed.path else ""

        if not filename:
            filename = fallback_name or f"attachment_{uuid.uuid4().hex[:8]}"

        # 확장자를 보존하면서 파일명만 sanitize
        stem, ext = os.path.splitext(filename)
        safe_stem = re.sub(r"[^0-9A-Za-z._\-가-힣]", "_", stem).strip("_")
        # 연속 점(..) 제거 — 파일 서빙 시 path traversal 차단 방지
        safe_stem = re.sub(r"\.{2,}", ".", safe_stem)
        safe_name = f"{safe_stem}{ext}"
        local_path = dest_path / safe_name

        local_path.write_bytes(resp.content)
        return str(local_path)


def pick_best_attachment(attachments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """공고서(변환본) PDF > 공고서(원본) > 제안요청서 PDF > 기타 순으로 최적 첨부파일 선택."""
    if not attachments:
        return None

    def _is_pdf(nm: str) -> bool:
        return nm.endswith(".pdf")

    def _is_hwp(nm: str) -> bool:
        return nm.endswith(".hwp") or nm.endswith(".hwpx")

    def _score(att: dict[str, Any]) -> int:
        nm = str(att.get("fileNm", "")).lower()
        doc_div = str(att.get("docDiv", "")).strip()

        is_convert = "변환본" in doc_div or "변환" in doc_div
        is_original = "원본" in doc_div
        is_notice = "공고서" in doc_div or "공고" in nm
        is_rfp = doc_div == "제안요청서" or "제안" in nm or "rfp" in nm
        is_task = "과업" in doc_div or "과업" in nm

        # 공고서(변환본) — 가장 높은 우선순위
        if (is_convert or (is_notice and is_convert)) and _is_pdf(nm):
            return 120
        if (is_convert or (is_notice and is_convert)) and _is_hwp(nm):
            return 110

        # 공고서(원본)
        if (is_original or is_notice) and _is_pdf(nm):
            return 115
        if (is_original or is_notice) and _is_hwp(nm):
            return 105

        # 제안요청서
        if is_rfp and _is_pdf(nm):
            return 100
        if is_rfp and _is_hwp(nm):
            return 90

        # 과업지시서
        if is_task and _is_pdf(nm):
            return 75
        if is_task and _is_hwp(nm):
            return 70

        # 기타
        if _is_pdf(nm):
            return 60
        if _is_hwp(nm):
            return 40
        return 10

    scored = sorted(attachments, key=_score, reverse=True)
    return scored[0]


# ── 발주계획현황서비스 (OrderPlanSttusService) ──

ORDER_PLAN_API_BASE = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"

# PPSSrch: 사업명(bizNm), 지역(insttLctNm), 조달방식(prcrmntMethd) 등 확장 검색
ORDER_PLAN_ENDPOINTS: dict[str, str] = {
    "goods": "getOrderPlanSttusListThngPPSSrch",
    "service": "getOrderPlanSttusListServcPPSSrch",
    "construction": "getOrderPlanSttusListCnstwkPPSSrch",
    "foreign": "getOrderPlanSttusListFrgcptPPSSrch",
}


def _get_order_plan_api_key() -> str:
    """발주계획현황서비스 전용 API 키. 미설정 시 DATA_GO_KR_API_KEY 폴백."""
    key = os.environ.get("ORDER_PLAN_API_KEY", "").strip()
    if key:
        return key
    return _get_api_key()


def _parse_amt(value: Any) -> int:
    """금액 문자열 → 정수 (원)."""
    if not value:
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return 0


# 소관구분코드 → 라벨
_JRSDCTN_LABEL: dict[str, str] = {
    "01": "국가기관", "02": "지자체", "03": "교육기관",
    "51": "공기업", "52": "준정부기관", "53": "기타공공기관",
    "71": "지방공기업", "72": "기타기관", "81": "지자체출자출연",
}


def _normalize_order_plan(item: dict[str, Any], category: str = "") -> dict[str, Any]:
    """발주계획 API 응답 item → OrderPlan dict (API 62개 필드 → 핵심 25개)."""
    return {
        "id": str(item.get("orderPlanUntyNo", "")).strip(),
        "bizNm": str(item.get("bizNm", "")).strip(),
        "orderInsttNm": str(item.get("orderInsttNm", "")).strip(),
        "orderYear": str(item.get("orderYear", "")).strip(),
        "orderMnth": str(item.get("orderMnth", "")).strip(),
        "orderAmt": _parse_amt(item.get("orderContrctAmt")),
        "sumOrderAmt": _parse_amt(item.get("sumOrderAmt")),
        "prcrmntMethd": str(item.get("prcrmntMethd", "")).strip(),
        "cntrctMthdNm": str(item.get("cntrctMthdNm", "")).strip(),
        "deptNm": str(item.get("deptNm", "")).strip(),
        "ofclNm": str(item.get("ofclNm", "")).strip(),
        "telNo": str(item.get("telNo", "")).strip(),
        "category": CATEGORY_LABEL.get(category, category),
        "bidNtceNoList": str(item.get("bidNtceNoList", "")).strip(),
        "ntcePblancYn": str(item.get("ntceNticeYn", "")).strip(),
        # 신규 필드
        "bsnsTyNm": str(item.get("bsnsTyNm", "")).strip(),
        "jrsdctnDivNm": _JRSDCTN_LABEL.get(
            str(item.get("jrsdctnDivCd", "")).strip(),
            str(item.get("jrsdctnDivNm", "")).strip(),
        ),
        "totlmngInsttNm": str(item.get("totlmngInsttNm", "")).strip(),
        "cnstwkRgnNm": str(item.get("cnstwkRgnNm", "")).strip(),
        "usgCntnts": str(item.get("usgCntnts", "")).strip(),
        "specCntnts": str(item.get("specCntnts", "")).strip(),
        "rmrkCntnts": str(item.get("rmrkCntnts", "")).strip(),
        "nticeDt": str(item.get("nticeDt", "")).strip(),
        "chgDt": str(item.get("chgDt", "")).strip(),
        "prdctClsfcNoNm": str(item.get("prdctClsfcNoNm", "")).strip(),
    }


async def search_order_plans(
    *,
    org_name: str = "",
    biz_name: str = "",
    region: str = "",
    year: int | None = None,
    category: str = "all",
) -> dict[str, Any]:
    """발주계획 검색 (PPSSrch 엔드포인트 — 확장 검색 조건 지원).

    Args:
        org_name: 발주기관명 (예: "한국도로공사")
        biz_name: 사업명 키워드 (예: "소프트웨어")
        region: 기관소재지 (예: "서울특별시")
        year: 발주년도 (기본: 올해)
        category: all / goods / service / construction / foreign

    Returns:
        {"plans": [...], "total": int}
    """
    api_key = _get_order_plan_api_key()
    now = _kst_now()
    yr = year or now.year

    bgn_ym = f"{yr}01"
    end_ym = f"{yr}12"
    bgn_dt = f"{yr}01010000"
    end_dt = f"{yr}12312359"

    shared_params: dict[str, Any] = {
        "serviceKey": api_key,
        "numOfRows": "500",
        "pageNo": "1",
        "type": "json",
        "orderBgnYm": bgn_ym,
        "orderEndYm": end_ym,
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
    }
    if org_name:
        shared_params["orderInsttNm"] = org_name
    if biz_name:
        shared_params["bizNm"] = biz_name
    if region:
        shared_params["insttLctNm"] = region

    all_plans: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    endpoints = (
        [(category, ORDER_PLAN_ENDPOINTS[category])]
        if category != "all" and category in ORDER_PLAN_ENDPOINTS
        else list(ORDER_PLAN_ENDPOINTS.items())
    )

    async with httpx.AsyncClient() as client:
        for cat, endpoint in endpoints:
            url = f"{ORDER_PLAN_API_BASE}/{endpoint}"
            try:
                resp = await client.get(url, params=shared_params, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("발주계획 API 호출 실패 (%s): %s", endpoint, exc)
                continue

            items = _parse_items(data)
            for item in items:
                plan = _normalize_order_plan(item, cat)
                pid = plan["id"]
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_plans.append(plan)

    return {"plans": all_plans, "total": len(all_plans)}
