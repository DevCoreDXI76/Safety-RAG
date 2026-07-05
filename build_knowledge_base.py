"""
지식 베이스 구축 스크립트
knowledge_base 폴더의 모든 문서를 청크로 쪼개고 임베딩해서 embeddings.json에 저장
문서를 추가/수정할 때마다 다시 실행하면 됩니다.
"""

from common import load_all_documents, save_embeddings, voyage_client

print("문서 로딩 중...")
chunks = load_all_documents()
print(f"총 {len(chunks)}개의 청크를 찾았습니다.")

if len(chunks) == 0:
    print("[경고] knowledge_base 폴더에 .txt 파일이 없습니다. 먼저 파일을 넣어주세요.")
    exit(1)

print("임베딩 생성 중... (Voyage AI 호출)")
texts = [c["text"] for c in chunks]

# Voyage API는 한 번에 여러 텍스트를 배치로 처리 가능
result = voyage_client.embed(texts, model="voyage-3", input_type="document")

for chunk, embedding in zip(chunks, result.embeddings):
    chunk["embedding"] = embedding

save_embeddings(chunks)
print(f"완료! embeddings.json에 {len(chunks)}개 청크의 임베딩을 저장했습니다.")