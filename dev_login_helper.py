"""
로컬 개발 중 텔레그램 앱 없이 브라우저에서 webapp/index.html을 열어 테스트하기 위한 헬퍼.
api/telegram_auth.py의 verify_init_data()와 동일한 서명 알고리즘으로 유효한
X-Telegram-Init-Data 값을 만들고, 테스트 계정을 승인 목록에 추가한다.

실행: python dev_login_helper.py
출력된 JS 코드를 브라우저 devtools 콘솔에 붙여넣고 실행하면 인증을 통과한다.
"""

import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import urlencode

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from api.access_control import add_allowed_user

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TEST_USER_ID = 999999001
TEST_USERNAME = "dev_local_tester"


def build_init_data():
    user_json = json.dumps(
        {"id": TEST_USER_ID, "username": TEST_USERNAME, "first_name": "로컬테스트"},
        ensure_ascii=False, separators=(",", ":"),
    )
    fields = {
        "user": user_json,
        "auth_date": str(int(time.time())),
        "query_id": "dev_local_query",
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    fields["hash"] = computed_hash
    return urlencode(fields)


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN이 .env에 없습니다.")
        return

    add_allowed_user(TEST_USER_ID, username=TEST_USERNAME)
    init_data = build_init_data()

    print("아래 두 줄을 브라우저 devtools 콘솔에 붙여넣고 실행하세요")
    print("(webapp/index.html이 이미 로드되어 401 에러가 뜬 상태에서 실행):\n")
    print(f'window.Telegram.WebApp.initData = "{init_data}";')
    print("loadDocumentTypes();")


if __name__ == "__main__":
    main()
