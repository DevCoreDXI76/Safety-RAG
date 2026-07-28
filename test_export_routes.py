# -*- coding: utf-8 -*-
"""
export.hwpx / export.pdf 라우트 스모크 테스트 — TestClient로 인증 의존성을
오버라이드하고, 실제 저장된 기록을 대상으로 두 엔드포인트가 200과 올바른
매직바이트를 반환하는지 확인한다.

사용 예:
  python test_export_routes.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from api.main import app
from api.telegram_auth import require_telegram_auth
from generate_draft import save_project_record

TEST_USER_ID = "xlsx_export_test_user"
TEST_PROJECT_NAME = "xlsx_export_테스트현장"

SAMPLE_DRAFT = (
    "| 작업단계 | 유해위험요인 | 감소대책 | 위험성 |\n"
    "|------|------|------|------|\n"
    "| 사전조사 | 매설물 손상(가스·전력·상수도) | 매설물 관리기관 확인 및 이설·보호대책 수립, "
    "굴착 착수 전 관계 기관(한국가스공사, 한전, 상수도사업본부 등) 협의 후 착공계 제출 | 9 |\n"
    "| 굴착 | 토사 붕괴 | 흙막이 지보공 설치, 구배 기준 준수, 굴착 깊이 2m 이상 시 사다리 등 승강설비 설치 | 12 |\n"
    "| 되메우기 | 장비 협착 | 신호수 배치, 출입 통제, 후진 경고음 확인 | 6 |\n"
)


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def run():
    print("=== export.hwpx / export.pdf 라우트 스모크 테스트 ===\n")

    app.dependency_overrides[require_telegram_auth] = lambda: {
        "user_id": TEST_USER_ID, "username": None, "first_name": None,
    }
    client = TestClient(app, raise_server_exceptions=False)
    all_ok = True

    record = save_project_record(
        TEST_USER_ID, TEST_PROJECT_NAME, "위험성평가표", "테스트용 작업 정보", SAMPLE_DRAFT,
    )
    record_id = record["id"]

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/{record_id}/export.hwpx")
    all_ok &= check("export.hwpx 200 응답", r.status_code == 200)
    all_ok &= check("export.hwpx zip 매직바이트(PK)", r.content[:2] == b"PK")

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/{record_id}/export.pdf")
    all_ok &= check("export.pdf 200 응답", r.status_code == 200)
    all_ok &= check("export.pdf 매직바이트(%PDF-)", r.content[:5] == b"%PDF-")

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/nonexistent-id/export.hwpx")
    all_ok &= check("존재하지 않는 record_id -> 404", r.status_code == 404)

    app.dependency_overrides.clear()

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
