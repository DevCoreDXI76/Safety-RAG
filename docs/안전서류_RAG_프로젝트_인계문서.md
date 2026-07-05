# 안전서류 AI 초안 생성 시스템 (RAG 학습 프로젝트) — 인계 문서

> 이 문서는 새 채팅창에서 이어서 작업하기 위한 맥락 요약입니다. 이 문서 전체를 새 대화 시작 시 첨부하고 "이어서 진행해줘"라고 요청하면 됩니다.

---

## 1. 프로젝트 배경 및 목적

**계기**: 정보통신공사 프로젝트 PM을 수행하면서, 안전 관련 서류들을 미리 준비하고 작성하고 검토받는 데 시간이 너무 오래 걸렸고, 무엇부터 어떻게 해야 할지 몰라서 힘들었던 실제 경험.

**아이디어**: AI 안전관리자가 (1) 미리 작성해야 할 문서 목록을 알려주고, (2) 템플릿을 제공하고, (3) 프로젝트 정보를 입력하면 초안을 작성해주는 시스템. 향후 위험성평가 등으로 확대 가능.

**목적 재설정**: 처음엔 "비즈니스" 목적으로 접근했으나, 이후 **"RAG 기술을 배워보는 사이드프로젝트/학습" 목적으로 전환**. 본인이 먼저 사용(dogfooding)하면서 검증하고, 이후 다른 사람도 사용할 수 있도록 확장하는 방향으로 진행 중.

**사용자 배경**: POSCO DX 20년 근무, IT기획/재무/구매/IT시스템운영/영상회의시스템구축/PM/정보통신공사PM/안전관리자 업무 경험. 골프 티칭프로 자격증 보유(별도 검토했으나 보류). 주당 20시간 작업 가능(회사 병행). 디자인/마케팅이 약점, 기획은 강점, PM 경력으로 협력사/벤더 네트워크 넓음.

**참고 사항 (앞선 프로젝트)**: 이전에 "1인 개발자 데일리 리추얼 봇"(텔레그램 + Claude API + Railway 배포)을 4주 워밍업 프로젝트로 완주함. 이 경험에서 Python, Claude API, 스케줄러, 클라우드 배포(Railway), Volume을 통한 영구 저장, 프롬프트 엔지니어링을 익힘. 골프 스윙 분석 앱 아이디어는 시장 조사 결과 이미 골프픽스(90만명 사용) 등 성숙한 경쟁자가 많고 컴퓨터 비전 기술이 필요해 보류함.

---

## 2. 시장 조사 결과

### 경쟁 서비스 발견: "안전해YOU" (safeyou365.com)
- 현장 정보(공종·작업·인원)를 채팅으로 입력하면 AI가 법적 기준에 맞춘 **위험성평가표**를 1분 만에 완성
- 18개국어 자동 번역, 모바일 서명 수집 기능 보유
- 다만 일반 건설현장(철근/콘크리트) 중심으로 보이며, **정보통신공사 특화 여부 불확실**, TBM 일지 커버 여부도 불명확

### 차별화 포인트
- **정보통신공사 특화**: 통신주 작업, 광케이블 매설, 국사 내 작업 등은 일반 건설과 위험요인이 다름
- **위험성평가 ↔ TBM 연계**: TBM의 "핵심 유해·위험요인"은 원래 그날의 위험성평가표에서 발췌하는 것 — 이 둘을 따로 만들지 않고 하나의 워크플로우로 연동하는 것이 차별점이 될 수 있음
- 기존 경쟁자(에스원, 포커스에이아이 등)는 AI CCTV + 하드웨어 기반 대기업/중견기업 대상 솔루션이라 1인개발자가 정면 승부할 영역이 아님. 반면 **50인 미만 소규모 사업장은 여전히 서류 위주 수작업 관리**에 머물러 있어 상대적으로 비어있는 영역

### 법적 배경
- 중대재해처벌법이 "서류상 대응"이 아닌 "실질적 이행 여부"를 보는 방향으로 강화되는 추세
- **주의사항**: 이 도구는 법률 자문이나 법적 인증을 대체하지 않는다는 점을 명시해야 하며, 최종 서류는 반드시 사람(안전관리자)이 검토/승인하는 구조로 설계해야 함

---

## 3. 관련 안전서류 정보 (조사 결과)

### 확인된 핵심 서류 카테고리
1. 선임 관련: 안전보건관리책임자(20억 이상 공사 시), 안전관리자/보건관리자 선임보고서(선임 후 14일 이내 고용노동부 제출)
2. 위험성평가 관련: 위험성평가표, 위험성평가 실시규정
3. 작업계획 및 현장점검: 표준 작업계획서, TBM 일지
4. 교육 관련: 연간 산업안전보건교육계획표, 안전보건교육일지
5. 비용 관련: 산업안전보건관리비 사용명세서
6. 대형공사 특화: 건설공사 안전보건대장

### 참고 출처
- 한국산업안전보건공단(KOSHA): kosha.or.kr, portal.kosha.or.kr
- 고용노동부: moel.go.kr
- 대한안전보건교육원: kshec.co.kr (서식다운로드 페이지)
- 국가법령정보센터: law.go.kr

### 위험성평가표 구조
- 공종별 작업 단위로 세분화하여 위험요인 도출
- 위험성 = 가능성(빈도 1~5) × 중대성(강도 1~5)
- 감소대책 우선순위: ① 제거 → ② 대체 → ③ 공학적 대책 → ④ 관리적 대책 → ⑤ 개인보호구
- 근로자 참여 필수 (누락 시 부적합 판정 가능)
- 결재 순서: 담당자 작성 → 검토자 검토 → 근로자대표 확인 → 안전보건관리책임자 승인

### TBM 일지(작업 전 안전점검회의) 구조
- 회의일시, 회의장소
- 회의내용: 작업일 현재 핵심 유해·위험요인(위험성평가에서 발췌), 준수사항/유의사항, 최근 동종업계 재해사례
- 참석자 명단(소속/직책/성명/서명) 필수
- **TBM 미실시 또는 형식적 실시는 중대재해 발생 시 안전관리 소홀 판단 근거가 될 수 있음**

---

## 4. 기술 방향 — RAG (Retrieval-Augmented Generation)

### 선택 이유
- 안전서류는 정확한 법 조항/표준 서식에 근거해야 하므로, Claude가 일반 지식으로 초안을 쓰면 부정확할 위험 → RAG로 관련 규정/서식을 검색해서 근거로 삼아 생성하면 신뢰도 향상
- 사용자가 명시적으로 "RAG 기술을 배워보고 싶다"는 학습 목적을 밝힘

### 임베딩 모델 선택: Voyage AI
- Anthropic은 자체 임베딩 모델이 없고 **Voyage AI를 공식 추천 파트너**로 안내
- 비교 검토 결과:

| 모델 | 가격(백만토큰) | 특징 |
|---|---|---|
| Voyage voyage-3-large | $0.18 | Anthropic 공식 추천, 법률 특화 모델(voyage-law-2)도 있음, 최대 32K 토큰 |
| OpenAI text-embedding-3-large | ~$0.13 | 생태계 넓음, 구현 쉬움 |
| Google text-embedding-005 | $0.006 | 가장 저렴하나 최대 2K토큰, Vertex AI 설정 복잡 |
| Cohere embed-multilingual-v3 | 중간 | 한국어 등 비영어권에서 OpenAI 대비 우수하다는 평가 있음 |
| 오픈소스(KURE-v1 등 한국어 특화) | 무료(직접호스팅) | 실제 국내 RAG 사례에서 한국어 뉘앙스 검색 정확도가 OpenAI 최상위 모델보다 높게 나온 사례 있음 |

**중요 발견**: 한국어 문서(이 프로젝트의 핵심 데이터)에서는 영어 기준 벤치마크 1위 모델(OpenAI, Voyage)이 반드시 한국어에서도 최고는 아님. 이 부분은 **Phase 3 고도화 단계에서 실험해볼 소재로 남겨둠**.

**현재 결정**: Phase 1 MVP는 **Voyage AI(voyage-3)**로 시작 (Anthropic 생태계 일관성, 학습 목적에 충분).

### 전체 로드맵
- **Phase 1 (진행 중)**: 기본 RAG 파이프라인 구축 — 지식베이스 청킹 → Voyage 임베딩 → 코사인 유사도 검색 → Claude 생성
- **Phase 2**: 본인 검증 — 실제 시나리오로 테스트
- **Phase 3 (고도화 실험, 학습 포인트)**: Contextual Retrieval, Reranking(Cohere 등), 하이브리드 검색(벡터+키워드), 임베딩 모델 비교실험(Voyage vs Cohere multilingual vs 한국어 특화 오픈소스)
- **Phase 4**: 검증되면 웹/봇 인터페이스로 감싸서 타인도 사용 가능하게 확장

---

## 5. 현재까지 구축한 것 (프로젝트: `safety-rag`)

### 개발 환경
- Windows, Python 3.11.9, VS Code
- 경로: `C:\MyProjects\03_Study\safety-rag`
- 가상환경(`venv`) 사용 중
- **참고**: `pip` 명령어가 PowerShell에서 직접 인식 안 되는 이슈가 있었음 → `py -m pip install ...`로 해결
- VS Code Pylance의 "Import could not be resolved" 경고는 인터프리터를 가상환경으로 재선택(`Ctrl+Shift+P` → `Python: Select Interpreter` → `venv\Scripts\python.exe`)하여 해결

### 폴더 구조
```
safety-rag/
├── .env
├── requirements.txt
├── knowledge_base/
│   ├── 위험성평가_실시규정.txt
│   └── TBM_서식.txt
├── common.py
├── build_knowledge_base.py
├── generate_draft.py
└── embeddings.json          ← build_knowledge_base.py 실행 후 자동 생성됨
```

### `requirements.txt`
```
anthropic
voyageai
numpy
python-dotenv
```

### `.env` (실제 값은 본인이 채움)
```
ANTHROPIC_API_KEY=여기에_클로드_API_키
VOYAGE_API_KEY=여기에_보이지_API_키
```

### `common.py` (현재 상태 — 청킹 방식 개선 전 버전)
```python
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


def chunk_text(text, chunk_size=500, overlap=50):
    """
    텍스트를 chunk_size 글자 단위로 쪼갬 (overlap만큼 겹치게 해서 문맥 손실 최소화)
    ⚠️ 알려진 문제: 문장/항목 중간에서 끊기는 경우가 있음 (아래 6번 섹션 "개선 제안" 참고)
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
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
```

### `build_knowledge_base.py`
```python
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

result = voyage_client.embed(texts, model="voyage-3", input_type="document")

for chunk, embedding in zip(chunks, result.embeddings):
    chunk["embedding"] = embedding

save_embeddings(chunks)
print(f"완료! embeddings.json에 {len(chunks)}개 청크의 임베딩을 저장했습니다.")
```

### `generate_draft.py` (현재 상태 — max_tokens 및 디버그 출력 개선 전 버전)
```python
"""
실제 사용 스크립트
프로젝트 정보를 입력하면, 관련 근거를 검색해서 Claude가 문서 초안을 작성합니다.
"""

from common import search_similar_chunks, claude_client

def generate_document_draft(document_type, project_info):
    query = f"{document_type} 작성 관련 {project_info}"
    relevant_chunks = search_similar_chunks(query, top_k=5)

    context = "\n\n---\n\n".join(
        f"[출처: {c['source']}]\n{c['text']}" for c in relevant_chunks
    )

    system_prompt = (
        "너는 정보통신공사 현장의 안전서류 작성을 돕는 보조 도구야. "
        "제공된 참고 자료(법령, 표준 서식)를 근거로 문서 초안을 작성해. "
        "참고 자료에 없는 내용은 추측해서 만들어내지 말고, "
        "실제 서류처럼 항목과 형식을 갖춰서 작성해. "
        "마지막에 반드시 '※ 이 초안은 참고용이며, 최종 검토 및 승인은 안전관리자가 직접 수행해야 합니다'라는 문구를 포함해."
    )

    user_prompt = (
        f"다음은 {document_type} 작성에 참고할 자료입니다:\n\n{context}\n\n"
        f"---\n\n"
        f"이 프로젝트 정보를 바탕으로 {document_type} 초안을 작성해줘:\n{project_info}"
    )

    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,   # ⚠️ 개선 필요: 4000 정도로 늘려야 함 (아래 6번 참고)
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text.strip()


if __name__ == "__main__":
    print("=== 안전서류 초안 생성기 (MVP) ===\n")
    document_type = input("문서 종류 (예: 위험성평가표 / TBM 일지): ").strip()
    project_info = input("프로젝트/작업 정보를 입력하세요: ").strip()

    print("\n초안 생성 중...\n")
    draft = generate_document_draft(document_type, project_info)

    print("=" * 50)
    print(draft)
    print("=" * 50)
```

### `knowledge_base/위험성평가_실시규정.txt` (전체 내용)
```
[위험성평가 실시규정 및 작성 가이드]

1. 위험성평가 개요
위험성평가란 사업장의 유해·위험요인을 파악하고, 해당 요인으로 인한 부상 또는 
질병의 가능성(빈도)과 중대성(강도)을 추정·결정하여 감소대책을 수립·실행하는 
일련의 과정을 말한다. 산업안전보건법에 따라 사업주는 위험성평가를 실시할 
의무가 있다.

2. 위험성평가 절차
(1) 사전준비: 평가 대상 공정 및 작업 확인, 평가 담당자 지정
(2) 유해·위험요인 파악: 공종별·작업단위별로 세분화하여 위험요인 도출
(3) 위험성 추정: 가능성(빈도) × 중대성(강도)로 위험성 수준 계산
(4) 위험성 결정: 허용 가능한 위험인지 여부 판단
(5) 위험성 감소대책 수립 및 실행: 우선순위에 따라 대책 적용
(6) 기록 및 보존: 평가 결과와 대책 이행 여부를 문서화

3. 위험성 추정 기준
가능성(빈도) 척도: 1(거의 발생하지 않음) ~ 5(매우 자주 발생)
중대성(강도) 척도: 1(경미) ~ 5(치명적, 사망 등)
위험성 = 가능성 × 중대성으로 계산하며, 점수가 높을수록 우선 개선 대상이 된다.
예: 가능성 3 × 중대성 4 = 12 (높은 위험, 즉시 개선 필요)

4. 위험성 감소대책 우선순위
(1) 제거: 위험요인 자체를 없애는 방법 (가장 우선)
(2) 대체: 덜 위험한 방법이나 물질로 교체
(3) 공학적 대책: 방호장치, 격리, 환기 등 설비적 개선
(4) 관리적 대책: 작업절차 개선, 교육, 표지판 설치 등
(5) 개인보호구: 안전모, 안전대, 보호안경 등 (최후 수단)

5. 근로자 참여
위험성평가는 반드시 해당 작업을 수행하는 근로자를 참여시켜야 한다. 
근로자가 직접 겪는 현장의 위험을 가장 잘 알기 때문이며, 근로자 참여가 
누락된 위험성평가는 부적합 판정을 받을 수 있다.

6. 승인 체계
위험성평가서는 다음 순서로 결재를 거쳐야 한다:
담당자 작성 → 검토자 검토 → 근로자대표 확인 → 안전보건관리책임자(승인자) 최종 승인

7. 정보통신공사 현장 특화 위험요인 예시
- 통신주 승주 작업: 추락, 감전 위험
- 광케이블 지중 매설 작업: 굴착 중 붕괴, 타 매설물(가스관, 전력선) 손상 위험
- 국사/통신실 내 작업: 밀폐공간 질식, 고전압 감전 위험
- 고소 작업(안테나, 기지국 설치 등): 추락, 낙하물 위험
- 맨홀/핸드홀 내 작업: 유해가스 중독, 질식 위험

8. 위험성평가표 필수 기재 항목
- 평가일자 / 평가 담당자 / 참여 근로자
- 공종 및 세부 작업명
- 유해·위험요인 (구체적으로 기술)
- 가능성 점수 / 중대성 점수 / 위험성 점수
- 위험성 감소대책 (우선순위 원칙에 따라)
- 대책 이행 여부 및 확인일
- 재평가 필요 여부
```

### `knowledge_base/TBM_서식.txt` (전체 내용)
```
[TBM(Tool Box Meeting, 작업 전 안전점검회의) 작성 가이드]

1. TBM 개요
TBM은 매일 작업 시작 전, 현장 근로자들이 모여 그날 수행할 작업의 위험요인과 
주의사항을 공유하는 짧은 안전점검회의다. 정식 명칭은 "작업 전 안전점검회의"이며, 
현장에서는 하루 업무를 반드시 TBM으로 시작해야 한다.

2. TBM과 위험성평가의 관계
TBM에서 다루는 "핵심 유해·위험요인"은 별도로 새로 만드는 것이 아니라, 
사전에 작성된 위험성평가표에서 그날 작업에 해당하는 항목을 추려서 
공유하는 것이다. 즉 위험성평가가 먼저 있고, TBM은 그 내용을 매일 
현장에 전달하는 실행 단계로 볼 수 있다.

3. TBM 필수 기재 항목
(1) 회의일시: TBM을 실시한 날짜와 시각
(2) 회의장소: 작업 현장 위치
(3) 회의내용
    - 작업일 현재 핵심 유해·위험요인 (해당일 작업의 위험성평가 항목 중 발췌)
    - 위 위험요인에 대한 근로자 준수사항 및 유의사항
    - 최근 동종업계 재해사례 공유 (있는 경우)
(4) 사진 및 회의자료: 현장 사진, 관련 자료 첨부
(5) 참석자 명단: 소속/직책, 성명, 서명 (전원 서명 필수)

4. 정보통신공사 현장 TBM 예시 시나리오
작업 유형에 따라 아래와 같은 위험요인을 우선 공유해야 한다:
- 통신주 작업일: 승주 시 안전대 체결 확인, 감전 위험 구간 사전 확인
- 지중 매설 작업일: 굴착 전 매설물 위치 확인(전력/가스), 붕괴 방지 조치 확인
- 맨홀 작업일: 유해가스 측정 결과 확인, 환기 여부, 감시인 배치 여부
- 고소 작업일: 안전대 착용 및 체결 상태, 낙하물 방지망 설치 여부

5. TBM 운영 시 유의사항
- 형식적으로 서명만 받고 끝내지 말고, 실제로 위험요인을 구두로 설명하고 
  근로자의 이해 여부를 확인해야 한다
- TBM 미실시 또는 형식적 실시는 중대재해 발생 시 안전관리 소홀로 
  판단되는 근거가 될 수 있다
- TBM 일지는 위험성평가서와 함께 현장에 비치하고, 감독기관 점검 시 
  제시할 수 있어야 한다

6. TBM 일지 양식 구성
- 일자 / 현장명 / 작성자
- 참여 공종 및 작업 내용
- 오늘의 핵심 위험요인 (위험성평가 연계)
- 준수사항 및 유의사항
- 최근 재해사례 (선택)
- 참석자 서명란 (소속, 직책, 성명, 서명)
```

---

## 6. 테스트 결과 및 발견된 이슈

### 테스트 1: 위험성평가표 생성 — 성공
입력: "정보통신공사, 광케이블 지중 매설 작업, 인원 5명, 굴착 작업 포함"
- 지식베이스의 굴착 붕괴, 매설물 손상 등 위험요인이 정확히 반영됨
- 제거→대체→공학적→관리적→보호구 우선순위 구조 정확히 재현
- 결재란 구조도 정확히 반영
- **문제**: `max_tokens=1500` 제한으로 "도로 또는" 에서 답변이 중간에 끊김

### 테스트 2: TBM 일지 생성 — 성공
같은 입력으로 테스트, 위험성평가표와 다른 형식(회의일시/장소/참석자 서명란)으로 정확히 생성됨. "위험성평가표 해당 항목에서 발췌"라고 명시하고, 점수가 없으면 추측하지 않고 "위험성평가표 점수 기재"로 빈칸 처리한 점이 좋았음(프롬프트의 "추측 금지" 지시가 잘 작동).

### 발견된 이슈 1: max_tokens 부족 (해결 방법 제시함, 적용 여부 미확인)
`generate_draft.py`의 `max_tokens=1500` → `4000`으로 변경 필요

### 발견된 이슈 2: 청킹(chunking) 문제 (해결 코드 제시함, 적용 여부 미확인)
현재 `chunk_text()`가 글자 수(500자) 기준으로 기계적으로 잘라서, 문장/항목 중간에서 끊기는 문제 발견 (디버그 출력에서 "의 위험성평가 항목 중 발췌)"처럼 문장 중간부터 시작하는 청크 확인됨).

**제안된 개선 코드** (아직 `common.py`에 미적용 상태):
```python
def chunk_text(text, max_chunk_size=800):
    """
    문단(빈 줄) 단위로 텍스트를 나누고, 너무 짧은 문단은 합치고
    너무 긴 문단은 다시 쪼갬. 문장/항목 중간에서 끊기는 걸 최소화.
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
```
적용 시 `common.py`의 기존 `chunk_text()` 교체 후, **반드시 `python build_knowledge_base.py` 재실행 필요** (청킹이 바뀌면 임베딩도 다시 만들어야 함).

### 추가 제안된 디버그 코드 (아직 미적용)
`generate_draft.py`의 `generate_document_draft()` 함수 안, `context` 조합 전에 검색된 청크를 출력하는 코드:
```python
print("\n[검색된 근거 청크]")
for i, c in enumerate(relevant_chunks, 1):
    print(f"{i}. 출처: {c['source']}")
    print(f"   내용 일부: {c['text'][:80]}...")
print()
```

### 발견된 구조적 이슈: 위험성평가 ↔ TBM 실제 연동 미비
현재는 TBM 생성 시 지식베이스(일반 가이드)에서만 근거를 가져오고 있어, 매번 일반론적인 위험요인이 나옴. 원래 의도대로라면 "오늘 이 프로젝트에서 실제로 생성한 위험성평가표"의 구체적 항목/점수를 TBM이 가져와야 함.

**해결 방향(미착수)**: 위험성평가표 생성 결과를 `projects/현장명.json` 형태로 저장해두고, TBM 생성 시 지식베이스 검색과 별개로 그 프로젝트 파일을 직접 참조하도록 구조 확장 필요.

---

## 7. 다음 단계 (우선순위)

1. **청킹 개선 적용** — 위 6번의 개선 코드를 `common.py`에 반영 → `build_knowledge_base.py` 재실행 → 재테스트
2. **max_tokens 늘리기** — `generate_draft.py`에서 1500 → 4000
3. **디버그 출력 추가** — 검색된 근거를 눈으로 확인할 수 있도록
4. **위험성평가 ↔ TBM 실제 연동 구조 설계** — 프로젝트별 JSON 저장 방식 도입
5. **(Phase 3, 추후)** 임베딩 모델 비교 실험 — Voyage vs Cohere multilingual vs 한국어 특화 오픈소스(KURE-v1 등), Contextual Retrieval, Reranking 적용
6. **(Phase 4, 추후)** 검증되면 인터페이스 확장 (웹/봇 형태로 타인도 사용 가능하게)

---

## 8. 참고: 1인개발 10원칙 (사용자가 반복 참조하는 원칙, 이북 "1인개발을 시작하려는 당신께" 요약)

1. 목적을 명확히 정하라 (사이드프로젝트 vs 비즈니스)
2. 런웨이를 계산하라 (전업 시 생활비/플랜B)
3. "유틸" 서비스부터 시작하라 (플랫폼은 콜드스타트 문제)
4. 빠르게 MVP를 출시하라
5. 부족한 부분은 과감히 아웃소싱하라 (디자인 등)
6. 개발보다 마케팅에 최소 동일한 노력을 쏟아라
7. 유저 이벤트 분석 SDK를 처음부터 장착하라
8. 리텐션 관리에 집중하라 (특히 푸시/이메일)
9. 커뮤니티를 통해 의지를 유지하라 (단, 본업 균형 유지)
10. '1인개발'이 아닌 '1인사업'으로 접근하라 (기획/디자인/개발/마케팅/CS 전부)

---

## 새 채팅에서 이어갈 때 안내

이 문서를 새 대화창에 첨부한 뒤 "위 문서 내용 이어서 진행해줘. 다음 단계는 [7번의 항목 중 원하는 것]부터 시작하고 싶어" 라고 요청하면 바로 이어서 진행할 수 있습니다.
