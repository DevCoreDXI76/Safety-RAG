# -*- coding: utf-8 -*-
"""
generate_draft.py의 system_prompt에 이격거리 가드레일 문구가 포함돼
있는지 정적으로 확인한다. _build_generation_prompt()를 직접 호출하면
RAG 검색이 Voyage 임베딩 API를 호출하게 되므로, 그 호출을 피하기 위해
소스 파일 텍스트만 읽어서 검사한다 (API 비용 없음).

사용 예:
  python test_system_prompt_static.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("generate_draft.py", "r", encoding="utf-8") as f:
    source = f.read()

EXPECTED_PHRASES = [
    "이격거리·간격 등 안전거리 수치를 다룰 때도",
    "현장 실측 후 확보",
]


def run():
    ok = True
    for phrase in EXPECTED_PHRASES:
        found = phrase in source
        print(f"[{'PASS' if found else 'FAIL'}] system_prompt에 '{phrase}' 포함")
        ok = ok and found

    print()
    print("=" * 50)
    print("전체 결과:", "PASS" if ok else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
