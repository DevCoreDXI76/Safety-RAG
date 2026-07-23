import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from generate_draft import _display_project_name


def run():
    results = [
        ("언더스코어 1개를 공백으로 치환", _display_project_name("송파지사_국사전원") == "송파지사 국사전원"),
        ("언더스코어 여러 개도 모두 치환", _display_project_name("A_B_C") == "A B C"),
        ("언더스코어 없으면 그대로", _display_project_name("강남지사") == "강남지사"),
        ("빈 문자열도 안전하게 처리", _display_project_name("") == ""),
    ]

    all_ok = True
    for name, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    print()
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
