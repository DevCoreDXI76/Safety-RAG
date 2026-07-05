"""
공통 함수 모음
- 텍스트 청킹
- 임베딩 저장/로드
- 코사인 유사도 검색
"""

import os
import json
import numpy as np
from dotenv import load_dotenv
import voyageai
from anthropic import Anthropic

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

EMBEDDINGS_FILE = "embeddings.json"
KNOWLEDGE_BASE_DIR = "knowledge_base"

voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)


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


def save_embeddings(data):
    with open(EMBEDDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_embeddings():
    if not os.path.exists(EMBEDDINGS_FILE):
        return None
    with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a)
    b = np.array(vec_b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def search_similar_chunks(query, top_k=5):
    """쿼리와 가장 유사한 청크 top_k개를 반환"""
    data = load_embeddings()
    if data is None:
        raise FileNotFoundError("embeddings.json이 없습니다. build_knowledge_base.py를 먼저 실행하세요.")

    query_embedding = voyage_client.embed(
        [query], model="voyage-3", input_type="query"
    ).embeddings[0]

    scored = []
    for item in data:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:top_k]]