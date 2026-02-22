from __future__ import annotations
import io
import logging

logger = logging.getLogger(__name__)

# HWP 5.x compound document magic bytes
HWP_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'


def is_hwp_bytes(data: bytes) -> bool:
    """HWP 5.x compound document 파일인지 매직바이트로 확인."""
    return len(data) >= 8 and data[:8] == HWP_MAGIC


def extract_hwp_text_bytes(data: bytes) -> str:
    """HWP 바이트에서 텍스트를 추출한다. 파싱 실패 시 빈 문자열 반환."""
    if not is_hwp_bytes(data):
        logger.warning("Not a valid HWP file (magic bytes mismatch)")
        return ""

    try:
        import hwp5.hwp5txt as hwp5txt  # type: ignore
        import hwp5.filestructure as fs  # type: ignore

        hwp_file = fs.Hwp5File(io.BytesIO(data))
        out = io.StringIO()
        hwp5txt.generate_text(hwp_file, out)
        return out.getvalue()
    except Exception as exc:
        logger.error("HWP parsing failed: %s", exc)
        return ""
