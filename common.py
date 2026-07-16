"""
공통 함수 모음
- 텍스트 청킹
- 임베딩 저장/로드 (모델별 분리: voyage / cohere / kure)
- 코사인 유사도 검색
"""

import os
import re
import json
import threading
from datetime import datetime, timezone, timedelta
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

# Railway Volume 마운트 경로(자동 주입) 또는 로컬 개발용 폴백 경로
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

KST = timezone(timedelta(hours=9))

# 문서 생성 1건마다 토큰 사용량을 한 줄씩 append하는 JSON Lines 로그.
# 전체 사용자가 하나의 파일을 공유하고(user_id 필드로 구분), 매 요청마다
# 파일 전체를 다시 쓰지 않도록(allowed_users.json류의 read-modify-write와
# 다르게) append 전용으로 설계했다.
TOKEN_USAGE_LOG_PATH = os.path.join(DATA_DIR, "token_usage_log.jsonl")
_token_usage_lock = threading.Lock()


def log_token_usage(document_type, user_id, usage, generation_seconds=None):
    """
    usage는 Anthropic 응답의 .usage 객체(input_tokens/output_tokens/
    cache_creation_input_tokens/cache_read_input_tokens 속성을 가짐).
    generation_seconds는 API 호출 시작~끝까지 걸린 실제 시간(초) — 캐시
    적중률·토큰량과 같은 레코드에 저장해야 "어떤 최적화가 실제로 생성
    시간을 줄였는지" 사후 비교가 가능하다.
    """
    entry = {
        "timestamp": datetime.now(KST).isoformat(),
        "document_type": document_type,
        "user_id": user_id,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        "cache_read_input_tokens": usage.cache_read_input_tokens,
        "generation_seconds": generation_seconds,
    }
    with _token_usage_lock:
        with open(TOKEN_USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

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

# document_type(문서종류 label) → 우선 검색할 knowledge_base 파일 1:1 매핑
# generate_draft.py의 DOCUMENT_TYPES 라벨과 knowledge_base/ 파일명 기준
DOCUMENT_TYPE_KB_MAP = {
    "위험성평가표": "위험성평가_실시규정.txt",
    "TBM 일지": "TBM_서식.txt",
    "안전보건교육일지": "안전보건교육_가이드.txt",
    "산업안전보건관리비 사용명세서": "산업안전보건관리비_가이드.txt",
    "표준 작업계획서": "표준작업계획서_가이드.txt",
}

# 유사도 검색 랭킹이 아니라 매핑된 knowledge_base 파일 전체를 프롬프트에 통째로
# 포함시켜야 하는 document_type. "3. 위험성 추정 기준", "4. 위험성 감소대책
# 우선순위" 같은 정의/규정 섹션은 현장 쿼리와 문장 구조가 안 맞아 유사도
# 랭킹으로는 안정적으로 뽑히지 않아서 도입함. 5개 파일 모두 크기가 작아
# (각 2~3천 자) 전체 포함해도 컨텍스트 부담이 없어 5개 문서종류 전부 적용.
FULL_INCLUDE_DOCUMENT_TYPES = {
    "위험성평가표",
    "TBM 일지",
    "안전보건교육일지",
    "산업안전보건관리비 사용명세서",
    "표준 작업계획서",
}

# 표준 작업계획서 - 작업유형별 법정 별표 보완자료 (직접 주입 전용, RAG 검색 대상 아님)
WORK_TYPE_KB_FILE = "표준작업계획서_법정별표.txt"

# 작업유형 라벨 → (시작 마커, 종료 마커). 마커는 WORK_TYPE_KB_FILE 원문의 헤더
# 문자열을 그대로 사용한다. 종료 마커는 다음 섹션의 시작 지점(또는 다음 챕터
# 제목)이며, 마지막 항목은 뒤이어 나오는 "3. 향후 확장 후보..." 챕터 제목까지를
# 종료 마커로 사용해 해당 작업유형 블록만 정확히 잘라낸다.
WORK_TYPE_SECTION_MARKERS = {
    "굴착작업": (
        "[작업유형: 굴착작업] (13종 중 6번)",
        "[작업유형: 차량계 건설기계를 사용하는 작업] (13종 중 3번)",
    ),
    "차량계 건설기계를 사용하는 작업": (
        "[작업유형: 차량계 건설기계를 사용하는 작업] (13종 중 3번)",
        "[작업유형: 전기작업] (13종 중 5번, 안전보건규칙 제318조 관련)",
    ),
    "전기작업": (
        "[작업유형: 전기작업] (13종 중 5번, 안전보건규칙 제318조 관련)",
        "[작업유형: 중량물의 취급 작업] (13종 중 11번)",
    ),
    "중량물의 취급 작업": (
        "[작업유형: 중량물의 취급 작업] (13종 중 11번)",
        "[작업유형: 차량계 하역운반기계등을 사용하는 작업] (13종 중 2번)",
    ),
    "차량계 하역운반기계등을 사용하는 작업": (
        "[작업유형: 차량계 하역운반기계등을 사용하는 작업] (13종 중 2번)",
        "3. 위험성평가·TBM과의 연계",
    ),
}


def read_kb_file(filename):
    """knowledge_base/ 내 특정 파일의 전체 텍스트를 그대로 읽어 반환"""
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def extract_kb_section(text, start_marker, end_marker=None):
    """
    start_marker부터 (end_marker가 있으면) 그 직전까지 잘라내 반환.
    구분용으로만 쓰인 순수 대시(-) 줄은 결과에서 제거한다.
    start_marker를 찾지 못하면 빈 문자열을 반환한다.
    """
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker)) if end_marker else len(text)
    if end == -1:
        end = len(text)
    section = text[start:end]
    lines = [
        line for line in section.split("\n")
        if not (line.strip() and set(line.strip()) == {"-"})
    ]
    return "\n".join(lines).strip()


WORK_TYPE_PREAMBLE_START_MARKER = "1. 작업계획서 작성 대상 작업"
# 프리앰블("법정 전체 목록")의 끝은 항상 이 챕터 제목이어야 한다. 예전에는
# 끝 마커로 markers[0](요청받은 work_type 자신의 시작 마커)을 썼는데, 그러면
# 파일 안에서 나중에 나오는 work_type(전기작업·중량물)을 요청할 때 그 사이에
# 있는 다른 work_type 섹션(굴착작업·차량계건설기계)까지 통째로 딸려 들어가는
# 버그가 있었다(2026-07-11 발견 — 전기작업 컨텍스트에 굴착작업 사전조사
# 내용까지 포함되고 있었음). 섹션 2 제목을 고정 끝 마커로 써서 프리앰블
# 범위를 "법정 전체 목록" 하나로 못박는다.
WORK_TYPE_PREAMBLE_END_MARKER = "2. 정보통신공사 현장 우선 적용 작업유형"

# 안전보건교육 특별교육 항목 - RAG 검색으로만 끌려오면 매 생성마다 top-k
# 순위에 따라 등장 여부가 달라질 수 있다(실제로 맨홀/밀폐공간 혼동 사례
# 발생, 2026-07-11). 작업유형과 명확히 연결되는 특별교육 항목은 work_type
# 법정별표와 동일하게 직접 주입해 매번 안정적으로 등장하도록 한다.
EDUCATION_KB_FILE = "안전보건교육_법정시간및내용.txt"

# 작업유형 라벨 → [(시작 마커, 종료 마커), ...] 리스트. 여러 항목을 연달아
# 주입할 수 있도록 리스트로 관리한다 (예: 굴착작업은 굴착 특별교육이 필수,
# 맨홀작업 특별교육은 광케이블 지중매설 현장에서 맨홀 진입이 흔해 참고용으로
# 함께 제공).
WORK_TYPE_EDUCATION_REFS = {
    "굴착작업": [
        ("[제19호] 굴착면의 높이가 2미터 이상이 되는 지반 굴착작업",
         "[제27호] 건축물의 골조, 다리의 상부구조 또는 탑의 금속제 부재로"),
        ("[제34호] 맨홀작업", "[제35호] 밀폐공간에서의 작업"),
    ],
    "전기작업": [
        ("[제17호] 전압이 75볼트 이상인 정전 및 활선작업",
         "[제19호] 굴착면의 높이가 2미터 이상이 되는 지반 굴착작업"),
    ],
}


def get_work_type_context(work_type):
    """
    작업유형에 해당하는 법정 별표 섹션을 추출. 매칭 실패 시 빈 문자열.
    "법정 전체 목록"(제38조제1항 근거, 13종 목록, 굴착 2m 기준 등 이미
    검증된 문장)을 앞에 함께 붙여서, 모델이 그 목록에 없는 세부 기준을
    스스로 추측해 지어내는 걸 줄인다. WORK_TYPE_EDUCATION_REFS에 매핑이
    있으면 관련 안전보건교육 특별교육 항목도 함께 직접 주입한다(RAG
    검색에 맡기지 않음 — top-k 순위 변동으로 매번 다르게 나오는 문제 방지).
    """
    markers = WORK_TYPE_SECTION_MARKERS.get(work_type)
    if not markers:
        return ""
    full_text = read_kb_file(WORK_TYPE_KB_FILE)
    preamble = extract_kb_section(full_text, WORK_TYPE_PREAMBLE_START_MARKER, WORK_TYPE_PREAMBLE_END_MARKER)
    work_type_section = extract_kb_section(full_text, markers[0], markers[1])
    parts = [preamble, work_type_section]

    education_markers = WORK_TYPE_EDUCATION_REFS.get(work_type)
    if education_markers:
        education_text = read_kb_file(EDUCATION_KB_FILE)
        education_parts = [
            extract_kb_section(education_text, start, end)
            for start, end in education_markers
        ]
        education_parts = [p for p in education_parts if p]
        if education_parts:
            parts.append(
                f"[관련 안전보건교육 특별교육 항목 - {EDUCATION_KB_FILE}]\n\n"
                + "\n\n---\n\n".join(education_parts)
            )

    return "\n\n".join(p for p in parts if p).strip()


# 법령 조문/별표 인용 검증 (소프트 체크): 생성된 초안이 참고자료에 없는
# 조/별표 번호를 지어내지 않았는지 정규식으로 대조한다. 국가법령정보센터
# 원문도 "별표 4"처럼 띄어 쓰는 경우가 흔해 숫자 앞뒤 공백을 허용한다.
CITATION_PATTERN = re.compile(
    r"제\s*\d+\s*조(?:의\s*\d+)?(?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?|별표\s*\d+"
)


def extract_citations(text):
    """텍스트에서 조/항/호/별표 인용을 있는 그대로(정규화 없이) 추출."""
    return CITATION_PATTERN.findall(text)


def _normalize_citation(citation):
    """
    인용 문자열의 공백만 제거한다. 조/항/호 구성요소는 그대로 유지한다 —
    예전에는 "제○조(의○)?"만 남기고 항·호를 잘라냈지만, 그러면 "제38조제1항제6호"
    (모델이 목록 순서를 보고 "제6호"를 스스로 지어붙인 경우)가 KB의 "제38조제1항"과
    같은 걸로 취급돼 경고 없이 통과해버리는 구멍이 실제로 발견됐다(항·호까지
    포함해서 지어낸 세부 번호를 놓침). 항·호까지 그대로 비교하면 "제345조"(KB)
    vs "제345조제1항"(draft) 같은 사소한 표기 차이도 걸릴 수 있지만, 이 체크는
    소프트 경고(사람이 확인하는 용도)라 과잉 경고가 누락보다 안전하다는 원칙에
    따라 세부 유지 쪽을 택한다.
    """
    return re.sub(r"\s+", "", citation)


def find_unverified_citations(draft, reference_context):
    """
    draft에 등장하는 조/항/호/별표 인용 중, reference_context(생성에 실제
    사용된 전체 참고자료)에 그대로 등장하지 않는 것만 반환. 컨텍스트에 없다고
    해서 반드시 틀린 인용은 아니므로(오탐 가능) 이 결과는 생성을 막는 용도가
    아니라 사람이 확인할 수 있도록 경고를 붙이는 용도로만 사용한다.
    """
    draft_citations = {_normalize_citation(c) for c in extract_citations(draft)}
    context_citations = {_normalize_citation(c) for c in extract_citations(reference_context)}
    return sorted(draft_citations - context_citations)


# 이격거리/간격 등 "일반 수치" 가드레일. find_unverified_citations와 반대
# 방향인 위험성 구간표 체커(find_broken_risk_score_ranges)와 달리, 이격거리는
# KB마다 값이 상황에 따라 달라 고정된 정답 목록을 만들 수 없다. 그래서 조문
# 인용 체커와 동일하게 "초안에 있는데 참고자료에 없으면 미검증"이라는
# 방향으로 설계한다. 감시 대상을 이격거리/간격 계열로 좁혀 오탐을 줄인다 —
# 앵커 키워드가 없는 수치(예: 지게차 포크 높이 15~20cm)는 애초에 스코프 밖이라
# 검사하지 않는다.
CLEARANCE_KEYWORDS = ["이격거리", "이격", "간격", "여유 공간", "안전거리", "접근 한계거리"]

# 단위 알터네이션 순서는 센티미터↔센티 사이에서 중요하다 (더 긴 것을 먼저 매칭).
# 부분 매칭(예: "m"이 다른 단어 안에 포함됨)은 뒤의 부정 전방탐색(?![a-zA-Z가-힣])이 방지한다.
DISTANCE_VALUE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:cm|mm|m|미터|센티미터|센티)(?![a-zA-Z가-힣])"
)


def find_unverified_clearance_values(draft, reference_context):
    """
    draft를 <br>/줄바꿈 단위로 나눠, 이격거리 관련 앵커 키워드가 포함된
    조각에서만 수치+단위 패턴을 추출한다. 그 값이 reference_context에
    그대로 등장하지 않으면 미검증으로 반환한다 (find_unverified_citations와
    동일하게 소프트 경고 용도 — 생성을 막지 않고 사람이 확인하도록 표시만 함).
    """
    chunks = re.split(r"<br\s*/?>|\n", draft)
    draft_values = set()
    for chunk in chunks:
        if any(kw in chunk for kw in CLEARANCE_KEYWORDS):
            draft_values.update(
                _normalize_citation(m.group())
                for m in DISTANCE_VALUE_PATTERN.finditer(chunk)
            )
    if not draft_values:
        return []
    context_values = {
        _normalize_citation(m.group())
        for m in DISTANCE_VALUE_PATTERN.finditer(reference_context)
    }
    return sorted(draft_values - context_values)


# 위험성평가_실시규정.txt에 명시된 위험성 추정 기준의 정확한 표기 — 가능성·
# 중대성 척도("1~5", 18~19행)와 위험성 점수 구간("1~4"/"5~9"/"10~25", 24~26행).
# 물결표(~)가 생성 과정에서 누락되는 재발성 표기 오류("1~4"→"14", "1~5"→"15")를
# 감지하기 위한 기준값 — 조번호 인용 환각이 프롬프트 지시만으로는 100% 막히지
# 않았던 것과 동일한 성격의 문제라 코드 레벨 체크가 필요하다는 게 이 프로젝트의
# 반복된 관찰이다. "14"·"15" 같은 깨진 형태 자체를 찾으면 "14명"·"15일" 같은
# 정상 문맥과 구분이 안 돼 오탐 위험이 크므로, find_unverified_citations와
# 동일하게 "정확한 형태가 그대로 있는지"만 확인하는 방향으로 뒤집었다.
RISK_ESTIMATION_LABELS = ["1~5", "1~4", "5~9", "10~25"]


def find_broken_risk_score_ranges(draft):
    """
    _finalize_draft에서 document_type == "위험성평가표"일 때만 호출된다.
    이 문서 유형은 system_prompt 지시상 위험성 추정 기준(척도·구간)을 항상
    KB 그대로 따라야 하므로, 트리거 단어 없이 라벨 존재 여부를 바로 확인한다.
    (예전엔 draft에 "위험성 점수"+"구간" 단어가 함께 있어야만 검사했는데,
    모델이 "판정구간" 대신 "위험성 수준" 등으로 표현을 바꾸면 트리거가 안
    걸려 깨진 표기를 놓치는 반대 방향 오류가 있었음 — 2026-07 실사용
    테스트에서 발견.)
    """
    return [label for label in RISK_ESTIMATION_LABELS if label not in draft]


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


def search_similar_chunks(query, top_k=5, model=DEFAULT_MODEL, document_type=None, exclude_source=None):
    """
    쿼리와 가장 유사한 청크 top_k개를 반환 (모델 지정 가능).
    document_type이 주어지고 DOCUMENT_TYPE_KB_MAP에 매핑이 있으면, 매핑된
    knowledge_base 파일의 청크를 전부 우선 포함시키고 남은 자리만 나머지
    파일에서 top_k로 채운다. document_type이 없거나 매핑이 없으면 기존처럼
    전체 청크 대상 top_k 검색을 유지한다.
    exclude_source가 주어지면(문자열 또는 문자열 컬렉션) 해당 파일(들)의 청크는
    검색 대상에서 아예 제외한다 (해당 파일을 별도로 전체/부분 원문 포함시키는
    경우, 중복을 막기 위함).
    """
    data = load_embeddings(model)
    if data is None:
        raise FileNotFoundError(
            f"{get_embeddings_filepath(model)}가 없습니다. "
            f"build_knowledge_base.py --model {model} 을 먼저 실행하세요."
        )

    if exclude_source is None:
        excluded_sources = set()
    elif isinstance(exclude_source, str):
        excluded_sources = {exclude_source}
    else:
        excluded_sources = set(exclude_source)

    query_embedding = embed_texts([query], input_type="query", model=model)[0]

    scored = []
    for item in data:
        if item["source"] in excluded_sources:
            continue
        score = cosine_similarity(query_embedding, item["embedding"])
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    priority_file = DOCUMENT_TYPE_KB_MAP.get(document_type) if document_type else None

    if priority_file:
        priority = [(s, i) for s, i in scored if i["source"] == priority_file]
        others = [(s, i) for s, i in scored if i["source"] != priority_file]
        remaining = max(0, top_k - len(priority))
        top = priority + others[:remaining]
    else:
        top = scored[:top_k]

    for score, item in top:
        print(f"[search] {item['source']} ({score:.4f}) | {item['text'][:100]!r}")

    return [item for score, item in top]