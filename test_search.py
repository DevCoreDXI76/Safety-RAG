"""
검색 품질만 빠르게 테스트하는 스크립트.
문서 생성 없이, 질의에 대해 어떤 청크가 검색되는지만 확인한다.
지식베이스에 문서를 추가/변경했을 때 검색이 잘 되는지 확인하는 용도.
"""

from common import search_similar_chunks

if __name__ == "__main__":
    print("=== 검색 품질 테스트 ===\n")
    while True:
        query = input("검색할 질의 입력 (종료하려면 그냥 엔터): ").strip()
        if not query:
            break

        results = search_similar_chunks(query, top_k=5)

        print(f"\n[질의: {query}]")
        for i, item in enumerate(results, 1):
            print(f"{i}. 출처: {item['source']}")
            print(f"   내용: {item['text'][:100]}...")
        print()