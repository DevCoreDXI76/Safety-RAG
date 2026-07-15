"""관리자용 사용 통계 — 텔레그램 /stats 명령어에서 사용.

token_usage_log.jsonl(문서 생성 1건마다 기록되는 로그)을 그때그때 다시
집계하는 방식이라 별도 DB나 캐시가 필요 없다.
"""
import os
import sys
import json
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import TOKEN_USAGE_LOG_PATH
from api.cost_alert import _entry_cost_usd
from api.access_control import get_allowed_users


def build_stats_message():
    allowed_users = get_allowed_users()

    per_user = defaultdict(lambda: {"count": 0, "doc_types": defaultdict(int), "cost": 0.0})
    total_cost = 0.0
    total_requests = 0

    if os.path.exists(TOKEN_USAGE_LOG_PATH):
        with open(TOKEN_USAGE_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                uid = str(entry.get("user_id"))
                cost = _entry_cost_usd(entry)
                per_user[uid]["count"] += 1
                per_user[uid]["doc_types"][entry.get("document_type", "?")] += 1
                per_user[uid]["cost"] += cost
                total_cost += cost
                total_requests += 1

    lines = [
        "📊 사용 현황",
        f"승인된 사용자: {len(allowed_users)}명",
        f"전체 생성 건수: {total_requests}건",
        f"전체 API 비용(추정): ${total_cost:.2f}",
        "",
        "사용자별:",
    ]

    if not per_user:
        lines.append("(아직 생성 이력 없음)")
    else:
        for uid, data in sorted(per_user.items(), key=lambda kv: -kv[1]["count"]):
            username = allowed_users.get(uid, {}).get("username")
            label = f"{username} (id: {uid})" if username else f"id: {uid}"
            doc_summary = ", ".join(f"{k} {v}건" for k, v in data["doc_types"].items())
            lines.append(f"- {label}: {data['count']}건 (${data['cost']:.2f}) — {doc_summary}")

    return "\n".join(lines)
