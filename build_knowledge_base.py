"""
지식베이스 문서를 청킹하고 임베딩하여 저장하는 스크립트.
--model 인자로 임베딩 모델을 선택할 수 있다 (기본값: voyage).

사용 예:
  python build_knowledge_base.py              → voyage로 빌드
  python build_knowledge_base.py --model cohere → cohere로 빌드
"""

import sys
from common import load_all_documents, embed_texts, save_embeddings, EMBEDDING_MODELS, DEFAULT_MODEL


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

    print(f"=== 지식베이스 빌드 (모델: {model}) ===\n")

    chunks = load_all_documents()
    print(f"총 {len(chunks)}개 청크 로드 완료")

    texts = [c["text"] for c in chunks]
    print("임베딩 생성 중...")
    embeddings = embed_texts(texts, input_type="document", model=model)

    data = []
    for chunk, embedding in zip(chunks, embeddings):
        data.append({
            "source": chunk["source"],
            "text": chunk["text"],
            "embedding": embedding,
        })

    save_embeddings(data, model=model)
    print(f"\n완료: {EMBEDDING_MODELS[model]}에 {len(data)}개 청크 임베딩 저장됨")