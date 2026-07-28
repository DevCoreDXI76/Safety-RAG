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

TEST_PROJECT_NAME = "xlsx_export_테스트현장"
TEST_RECORD_ID = "20c1c6d12755"

app.dependency_overrides[require_telegram_auth] = lambda: {
    "user_id": "xlsx_export_test_user", "username": None, "first_name": None,
}
client = TestClient(app, raise_server_exceptions=False)


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def run():
    print("=== export.hwpx / export.pdf 라우트 스모크 테스트 ===\n")
    all_ok = True

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/{TEST_RECORD_ID}/export.hwpx")
    all_ok &= check("export.hwpx 200 응답", r.status_code == 200)
    all_ok &= check("export.hwpx zip 매직바이트(PK)", r.content[:2] == b"PK")

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/{TEST_RECORD_ID}/export.pdf")
    all_ok &= check("export.pdf 200 응답", r.status_code == 200)
    all_ok &= check("export.pdf 매직바이트(%PDF-)", r.content[:5] == b"%PDF-")

    r = client.get(f"/projects/{TEST_PROJECT_NAME}/records/nonexistent-id/export.hwpx")
    all_ok &= check("존재하지 않는 record_id -> 404", r.status_code == 404)

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
