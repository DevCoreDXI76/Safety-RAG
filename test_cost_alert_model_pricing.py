# -*- coding: utf-8 -*-
"""_entry_cost_usd()가 document_type에 따라 실제 배포 모델(Sonnet 5 vs
Haiku 4.5) 단가를 구분해서 적용하는지 검증한다. 기존 코드는 document_type을
무시하고 모든 항목에 Sonnet 5 단가를 적용해, 실제로는 Haiku 4.5를 쓰는
안전보건교육일지 항목의 원가를 과대 계상하고 있었다(2026-08-07 실측원가
집계 중 발견).

사용 예:
  python test_cost_alert_model_pricing.py
"""
import os
import sys
import json
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api.cost_alert as cost_alert
import api.admin_stats as admin_stats


def run():
    checks = []

    # 모든 항목이 동일한 토큰 수를 쓰도록 맞춰서, 모델별 단가 차이만으로
    # 원가 차이가 나는지 명확히 확인한다.
    common_tokens = {
        "input_tokens": 1000,
        "output_tokens": 1000,
        "cache_creation_input_tokens": 1000,
        "cache_read_input_tokens": 1000,
    }

    haiku_entry = {"document_type": "안전보건교육일지", **common_tokens}
    sonnet_entry = {"document_type": "표준 작업계획서", **common_tokens}
    unmapped_entry = {"document_type": "위험성평가표", **common_tokens}  # 매핑 없음 -> 기본값(Sonnet)
    no_type_entry = {**common_tokens}  # document_type 키 자체가 없는 옛 로그도 안전해야 함

    haiku_cost = cost_alert._entry_cost_usd(haiku_entry)
    sonnet_cost = cost_alert._entry_cost_usd(sonnet_entry)
    unmapped_cost = cost_alert._entry_cost_usd(unmapped_entry)
    no_type_cost = cost_alert._entry_cost_usd(no_type_entry)

    # 손으로 계산한 기대값 (Haiku $1/$5, Sonnet $2/$10 per MTok, 캐시쓰기 x2, 캐시읽기 x0.1)
    expected_haiku = 0.001 + 0.005 + 0.002 + 0.0001  # 0.0081
    expected_sonnet = 0.002 + 0.010 + 0.004 + 0.0002  # 0.0162

    checks.append(("안전보건교육일지(Haiku)는 Haiku 단가로 계산됨",
                    abs(haiku_cost - expected_haiku) < 1e-9))
    checks.append(("표준 작업계획서(Sonnet)는 Sonnet 단가로 계산됨",
                    abs(sonnet_cost - expected_sonnet) < 1e-9))
    checks.append(("Haiku 원가가 Sonnet 원가의 정확히 절반",
                    abs(haiku_cost - sonnet_cost / 2) < 1e-9))
    checks.append(("매핑 없는 문서유형(위험성평가표)은 기본값인 Sonnet 단가로 계산됨",
                    abs(unmapped_cost - expected_sonnet) < 1e-9))
    checks.append(("document_type 키 자체가 없어도 예외 없이 Sonnet 단가로 폴백",
                    abs(no_type_cost - expected_sonnet) < 1e-9))

    # --- 통합 지점: build_stats_message()도 같은 결과를 반영해야 한다 ---
    original_token_log = admin_stats.TOKEN_USAGE_LOG_PATH
    with tempfile.TemporaryDirectory() as tmp_dir:
        admin_stats.TOKEN_USAGE_LOG_PATH = os.path.join(tmp_dir, "token_usage_log.jsonl")
        try:
            with open(admin_stats.TOKEN_USAGE_LOG_PATH, "w", encoding="utf-8") as f:
                f.write(json.dumps({"user_id": "u1", **haiku_entry}, ensure_ascii=False) + "\n")
                f.write(json.dumps({"user_id": "u1", **sonnet_entry}, ensure_ascii=False) + "\n")

            message = admin_stats.build_stats_message()
            # 두 건 합산 비용 = Haiku 1건 + Sonnet 1건 = 0.0081 + 0.0162 = 0.0243
            checks.append(("/stats 합산 비용에도 문서유형별 단가가 반영됨", "$0.02" in message))
        finally:
            admin_stats.TOKEN_USAGE_LOG_PATH = original_token_log

    print()
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 50)
    print("전체 결과:", "PASS" if all(ok for _, ok in checks) else "FAIL (위 로그 확인)")


if __name__ == "__main__":
    run()
