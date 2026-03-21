"""Hermetic tests for company_data_builder — no network/OpenAI dependency."""
import sys
import os

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
rag_engine_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'rag_engine'))
if rag_engine_path not in sys.path:
    sys.path.insert(0, rag_engine_path)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from company_data_builder import load_company_to_db
from company_db import CompanyDB
import chromadb.utils.embedding_functions as ef


def _mock_embedding_fn():
    """Deterministic embedding function — no network calls."""
    return ef.DefaultEmbeddingFunction()


def test_load_company_basic(tmp_path):
    """CompanyDB 기본 적재 테스트 (hermetic — no OpenAI API)."""
    db_dir = str(tmp_path / "company_db")
    company_id = "test_company_001"
    profile = {
        "name": "테스트회사",
        "revenue": 50000000000,
        "employees": 100
    }

    projects = [
        {
            "name": "테스트 프로젝트 1",
            "client": "행정안전부",
            "amount": 5000000000,
            "period": "2023.03 ~ 2024.12",
            "description": "클라우드 전환 사업",
            "tech_stack": ["AWS", "Kubernetes"],
            "category": "클라우드",
            "role": "주관사"
        }
    ]

    personnel = [
        {
            "name": "김철수",
            "position": "수석컨설턴트",
            "certifications": ["PMP", "AWS SAA"],
            "expertise": ["클라우드 아키텍처"],
            "career_years": 12
        }
    ]

    emb_fn = _mock_embedding_fn()
    load_company_to_db(company_id, profile, projects, personnel,
                       persist_directory=db_dir, embedding_function=emb_fn)

    # 검증 — semantic search로 확인 (local embedding, no API)
    db = CompanyDB(persist_directory=db_dir, embedding_function=emb_fn)
    results = db.search_similar_projects("클라우드 전환", top_k=3)
    assert len(results) >= 1
    project_names = [r['metadata'].get('project_name') for r in results]
    assert "테스트 프로젝트 1" in project_names


def test_load_company_personnel(tmp_path):
    """인력 정보 적재 테스트 (hermetic — no OpenAI API)."""
    db_dir = str(tmp_path / "company_db")
    company_id = "test_company_002"
    profile = {"name": "인력테스트회사", "employees": 50}
    projects = []
    personnel = [
        {
            "name": "이영희",
            "position": "프로젝트 매니저",
            "certifications": ["정보처리기사", "PMP"],
            "expertise": ["프로젝트 관리", "아키텍처 설계"],
            "career_years": 8,
            "key_projects": ["차세대 시스템 구축"]
        }
    ]

    emb_fn = _mock_embedding_fn()
    load_company_to_db(company_id, profile, projects, personnel,
                       persist_directory=db_dir, embedding_function=emb_fn)

    # 검증
    db = CompanyDB(persist_directory=db_dir, embedding_function=emb_fn)
    results = db.find_matching_personnel("프로젝트 관리 경험자", top_k=3)
    assert len(results) >= 1
    personnel_names = [r['metadata'].get('name') for r in results]
    assert "이영희" in personnel_names
