"""
일회성 마이그레이션 스크립트.
projects/*.json 안의 기록 중 id가 없는 것에 uuid를 부여한다.
실행 후에는 삭제해도 무방하다 (재실행해도 안전 — 이미 id 있으면 건드리지 않음).
"""

import os
import json
import uuid

PROJECTS_DIR = "projects"


def migrate():
    if not os.path.exists(PROJECTS_DIR):
        print("projects 폴더가 없습니다. 마이그레이션할 대상이 없습니다.")
        return

    total_files = 0
    total_updated = 0

    for filename in os.listdir(PROJECTS_DIR):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(PROJECTS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        changed = False
        for record in data.get("records", []):
            if not record.get("id"):
                record["id"] = uuid.uuid4().hex[:12]
                changed = True
                total_updated += 1

        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[갱신] {filename}")

        total_files += 1

    print(f"\n완료: {total_files}개 파일 확인, {total_updated}개 기록에 id 부여")


if __name__ == "__main__":
    migrate()