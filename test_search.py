"""
검색 품질만 빠르게 테스트하는 스크립트.
--model 인자로 임베딩 모델을 선택할 수 있다.

사용 예:
  python test_search.py                → voyage로 검색
  python test_search.py --model cohere → cohere로 검색
"""

import sys
from common import search_similar_chunks, EMBEDDING_MODELS, DEFAULT_MODEL


def parse_model_arg():
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return DEFAULT_MODEL


if __name__ == "__main__":
    model = parse_model_arg()
    if model not in EMBEDDING_MODELS:
        print(f"지원하지 않는 모델입니다: {model}. 지원 모델: {list(EMBEDDING_MODELS.keys())}")
        sys.exit(1)

    print(f"=== 검색 품질 테스트 (모델: {model}) ===\n")

    while True:
        query = input("검색할 질의 입력 (종료하려면 그냥 엔터): ").strip()
        if not query:
            break

        results = search_similar_chunks(query, top_k=5, model=model)

        print(f"\n[질의: {query}] (모델: {model})")
        for i, item in enumerate(results, 1):
            print(f"{i}. 출처: {item['source']}")
            print(f"   내용: {item['text'][:100]}...")
        print()