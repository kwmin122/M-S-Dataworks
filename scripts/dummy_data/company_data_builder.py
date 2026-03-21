"""CompanyDB 적재 모듈"""
import sys
import os

# Add rag_engine to path
rag_engine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'rag_engine'))
if rag_engine_path not in sys.path:
    sys.path.insert(0, rag_engine_path)

from company_db import CompanyDB, TrackRecord, Personnel, CompanyCapabilityProfile

def load_company_to_db(company_id: str, profile: dict, projects: list, personnel: list, persist_directory: str = "./data/company_db", embedding_function=None):
    """
    CompanyDB ChromaDB에 회사 데이터 적재

    Args:
        company_id: 회사 ID (예: company_001)
        profile: 회사 프로필 dict
        projects: 프로젝트 실적 list
        personnel: 인력 정보 list
        persist_directory: ChromaDB 저장 경로
        embedding_function: 임베딩 함수 (테스트 시 mock 주입용, None이면 기본값)
    """
    db = CompanyDB(persist_directory=persist_directory, embedding_function=embedding_function)

    # TrackRecord 객체로 변환 및 등록
    track_records = []
    for project in projects:
        record = TrackRecord(
            project_name=project['name'],
            client=project['client'],
            amount=project['amount'],
            period=project['period'],
            description=project.get('description', ''),
            technologies=project.get('tech_stack', []),
            outcome=project.get('outcome', '')
        )
        db.add_track_record(record)
        track_records.append(record)

    # Personnel 객체로 변환 및 등록
    personnel_list = []
    for person in personnel:
        p = Personnel(
            name=person['name'],
            role=person['position'],
            experience_years=person.get('career_years', 5),
            certifications=person.get('certifications', []),
            key_projects=person.get('key_projects', []),
            specialties=person.get('expertise', [])
        )
        db.add_personnel(p)
        personnel_list.append(p)

    # CompanyCapabilityProfile 저장
    capability_profile = CompanyCapabilityProfile(
        name=profile.get('name', ''),
        registration_number=profile.get('registration_number', ''),
        licenses=profile.get('licenses', []),
        certifications=profile.get('certifications', []),
        capital=profile.get('capital', 0.0),
        employee_count=profile.get('employees', 0),
        track_records=track_records,
        personnel=personnel_list,
        writing_style=profile.get('writing_style', {})
    )
    db.save_profile(capability_profile)

    print(f"✅ {profile['name']}: 실적 {len(projects)}건, 인력 {len(personnel)}명 적재 완료")
