"""
공통 함수 모음
- 텍스트 청킹
- 임베딩 저장/로드 (모델별 분리: voyage / cohere / kure)
- 코사인 유사도 검색
"""

import os
import json
import numpy as np
from dotenv import load_dotenv
import voyageai
import cohere
from anthropic import Anthropic

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

KNOWLEDGE_BASE_DIR = "knowledge_base"

voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
cohere_client = cohere.Client(api_key=COHERE_API_KEY) if COHERE_API_KEY else None
claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# KURE-v1은 로컬 모델이라 처음 호출될 때만 로드 (지연 로딩 — 매번 로드하면 느림)
_kure_model = None


def get_kure_model():
    global _kure_model
    if _kure_model is None:
        from sentence_transformers import SentenceTransformer  # 여기로 이동
        print("KURE-v1 모델 로딩 중... (최초 1회, 다소 시간 소요)")
        _kure_model = SentenceTransformer("nlpai-lab/KURE-v1")
    return _kure_model


# 지원하는 임베딩 모델과 결과 저장 파일 매핑
EMBEDDING_MODELS = {
    "voyage": "embeddings_voyage.json",
    "cohere": "embeddings_cohere.json",
    "kure": "embeddings_kure.json",
}

DEFAULT_MODEL = "voyage"


def chunk_text(text, max_chunk_size=800):
    """
    문단(빈 줄) 단위로 텍스트를 나누고, 너무 짧은 문단은 합치고
    너무 긴 문단은 문장 단위로 다시 쪼갬.
    글자 수로 기계적으로 자르는 방식 대비 문장/항목 중간 절단을 최소화.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) <= max_chunk_size:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chunk_size:
                sentences = para.split(". ")
                sub_chunk = ""
                for sentence in sentences:
                    if len(sub_chunk) + len(sentence) <= max_chunk_size:
                        sub_chunk += sentence + ". "
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk.strip())
                        sub_chunk = sentence + ". "
                if sub_chunk:
                    chunks.append(sub_chunk.strip())
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


def load_all_documents():
    """knowledge_base 폴더의 모든 .txt 파일을 읽어서 청크 리스트로 반환"""
    all_chunks = []
    for filename in os.listdir(KNOWLEDGE_BASE_DIR):
        if not filename.endswith(".txt"):
            continue
        filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_text(text)
        for chunk in chunks:
            all_chunks.append({"source": filename, "text": chunk})
    return all_chunks


# ── 임베딩 함수 (모델별 구현) ──────────────────────────────

def embed_with_voyage(texts, input_type):
    """input_type: 'document' 또는 'query'"""
    result = voyage_client.embed(texts, model="voyage-3", input_type=input_type)
    return result.embeddings


def embed_with_cohere(texts, input_type):
    """input_type: 'document' 또는 'query' (Cohere는 search_document/search_query 사용)"""
    if cohere_client is None:
        raise ValueError("COHERE_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")
    cohere_input_type = "search_document" if input_type == "document" else "search_query"
    result = cohere_client.embed(
        texts=texts,
        model="embed-multilingual-v3.0",
        input_type=cohere_input_type,
    )
    return result.embeddings


def embed_with_kure(texts, input_type):
    """
    KURE-v1은 로컬 추론 모델. API처럼 document/query 구분이 필수는 아니지만,
    검색 성능을 높이기 위해 공식 권장 프리픽스(query: / passage:)를 사용한다.
    """
    model = get_kure_model()
    if input_type == "query":
        prefixed = [f"query: {t}" for t in texts]
    else:
        prefixed = [f"passage: {t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True)
    return embeddings.tolist()


def embed_texts(texts, input_type, model=DEFAULT_MODEL):
    """모델 이름에 따라 적절한 임베딩 함수로 라우팅"""
    if model == "voyage":
        return embed_with_voyage(texts, input_type)
    elif model == "cohere":
        return embed_with_cohere(texts, input_type)
    elif model == "kure":
        return embed_with_kure(texts, input_type)
    else:
        raise ValueError(f"지원하지 않는 모델: {model}. 지원 모델: {list(EMBEDDING_MODELS.keys())}")


# ── 저장/로드 (모델별 파일 분리) ──────────────────────────

def get_embeddings_filepath(model=DEFAULT_MODEL):
    if model not in EMBEDDING_MODELS:
        raise ValueError(f"지원하지 않는 모델: {model}. 지원 모델: {list(EMBEDDING_MODELS.keys())}")
    return EMBEDDING_MODELS[model]


def save_embeddings(data, model=DEFAULT_MODEL):
    filepath = get_embeddings_filepath(model)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_embeddings(model=DEFAULT_MODEL):
    filepath = get_embeddings_filepath(model)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a)
    b = np.array(vec_b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def search_similar_chunks(query, top_k=5, model=DEFAULT_MODEL):
    """쿼리와 가장 유사한 청크 top_k개를 반환 (모델 지정 가능)"""
    data = load_embeddings(model)
    if data is None:
        raise FileNotFoundError(
            f"{get_embeddings_filepath(model)}가 없습니다. "
            f"build_knowledge_base.py --model {model} 을 먼저 실행하세요."
        )

    query_embedding = embed_texts([query], input_type="query", model=model)[0]

    scored = []
    for item in data:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:top_k]]