# -*- coding: utf-8 -*-
"""
export_pdf.py 스모크 테스트 — 실제 저장된 기록을 PDF로 변환해 파일 유효성·
한글 텍스트 보존·문서유형별 스타일(열비율/배경색/정렬) 적용을 확인한다.
텍스트 추출은 pypdf를 쓴다(런타임 의존성 아님 — 이 스크립트 실행 전
`pip install pypdf`로 별도 설치 필요, requirements.txt엔 넣지 않음).

사용 예:
  pip install pypdf   # 최초 1회
  python test_export_pdf.py
"""
import io
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pypdf
from reportlab.lib.pagesizes import A4, landscape, portrait

from reportlab.platypus import Indenter, Table
from export_pdf import (
    _BODY_STYLE, _BOX_TITLE_STYLE, _build_elements, _build_table_element, _CELL_STYLE_CENTER,
    _CELL_STYLE_LEFT, _center_x, _CONTENT_INDENT_PT, _hex_color, _PAGE_MARGIN_PT, _PDF_HEADER_FILL,
    _TitleFlowable, record_to_pdf_bytes,
)
from document_styles import STYLE_SPECS
from markdown_tables import parse_markdown_blocks, parse_markdown_tables

SAMPLE_RECORD = {
    "document_type": "위험성평가표",
    "draft": (
        "| 작업단계 | 유해위험요인 | 감소대책 | 위험성 |\n"
        "|------|------|------|------|\n"
        "| 사전조사 | 매설물 손상(가스·전력·상수도) | 매설물 관리기관 확인 및 이설·보호대책 수립, "
        "굴착 착수 전 관계 기관(한국가스공사, 한전, 상수도사업본부 등) 협의 후 착공계 제출 | 9 |\n"
        "| 굴착 | 토사 붕괴 | 흙막이 지보공 설치, 구배 기준 준수, 굴착 깊이 2m 이상 시 사다리 등 승강설비 설치 | 12 |\n"
        "| 되메우기 | 장비 협착 | 신호수 배치, 출입 통제, 후진 경고음 확인 | 6 |\n"
    ),
}

# 2026-08-04 베타1 실기기 테스트 중 실제로 발생한 LayoutError 재현 사례:
# "표준 작업계획서" 스타일 스펙(column_widths=[16,26,30,34], 4열 기준)에 없는
# 12열 표(작업유형별 법정 별표 형태)가 생성되면, 정의 안 된 8개 열은
# DEFAULT_COLUMN_WIDTH로 채워지고 1열(비중 16/282)이 극도로 좁아진다.
# 그 좁은 1열에 100자를 넘는 문장이 들어가면 셀 하나가 페이지 하나보다도
# 커져 reportlab이 LayoutError로 PDF 생성 자체를 실패시켰다(빈 파일이 아니라
# 예외 발생 → 다운로드 500 에러).
SAMPLE_RECORD_NARROW_COLUMN_LONG_TEXT = {
    "document_type": "표준 작업계획서",
    "draft": (
        "| 단위작업 | " + " | ".join(f"열{i}" for i in range(2, 13)) + " |\n"
        "|" + "---|" * 12 + "\n"
        "| " + ("사전조사 및 준비 작업 현장여건 확인 관계기관 협의 " * 8).strip()
        + " | " + " | ".join(["x"] * 11) + " |\n"
    ),
}

SAMPLE_RECORD_WITH_SCORE = {
    "document_type": "위험성평가표",
    "draft": (
        "| 위험요인 | 빈도 | 강도 | 위험등급 | 개선후 위험등급 |\n"
        "|----------|------|------|----------|------------------|\n"
        "| 지게차 충돌 | 3(AI 제안값, 현장 확인 필수) | 2(AI 제안값, 현장 확인 필수) | "
        "A(AI 제안값, 현장 확인 필수) | B(AI 제안값, 현장 확인 필수) |\n"
    ),
}

SAMPLE_RECORD_WITH_HEADING = {
    "document_type": "위험성평가표",
    "draft": (
        "# 위험성평가표 초안\n\n"
        "## ■ 기본 정보\n\n"
        "| 항목 | 내용 |\n"
        "|------|------|\n"
        "| 현장명 | 강남지사 |\n\n"
        "## ■ 중점(One Point) 위험요인\n\n"
        "| 위험요인 | 대책 |\n"
        "|------|------|\n"
        "| 붕괴 | 흙막이 설치 |\n"
    ),
}

SAMPLE_RECORD_MIXED_WIDTH = {
    "document_type": "TBM 일지",
    "draft": (
        "| 확인항목 | 이행여부 |\n"
        "|------|------|\n"
        "| 오늘 작업은 지중 굴착 및 광케이블 매설로, 굴착 깊이 2미터를 초과하는 구간이 "
        "포함되어 있어 흙막이 지보공 설치와 붕괴 위험 점검이 필수적으로 선행되어야 함 | 예 |\n"
    ),
}


def run():
    print("=== export_pdf.py 스모크 테스트 ===\n")

    checks = []

    # --- 문서 제목: 가운데정렬 + 밑줄 + 28pt + 굵게(faux-bold 2회 겹쳐 그리기) ---
    checks.append(("여백은 상하좌우 15pt로 통일", _PAGE_MARGIN_PT == 15))
    checks.append(("제목 폰트 크기 28pt", _TitleFlowable("위험성평가표").font_size == 28))
    checks.append(("박스 제목(서브 제목) 폰트 크기 18pt", _BOX_TITLE_STYLE.fontSize == 18))
    checks.append(("표 셀(왼쪽정렬) 폰트 크기 14pt", _CELL_STYLE_LEFT.fontSize == 14))
    checks.append(("표 셀(가운데정렬) 폰트 크기 14pt", _CELL_STYLE_CENTER.fontSize == 14))
    checks.append(("서술형 본문 폰트 크기 14pt", _BODY_STYLE.fontSize == 14))
    checks.append(("가운데정렬 계산: 텍스트 폭이 가용폭보다 작을 때 중앙 배치", _center_x(100, 300) == 100))
    checks.append(("가운데정렬 계산: 텍스트가 가용폭보다 크면 0에서 시작(음수 금지)", _center_x(400, 300) == 0))

    class _FakeCanvas:
        def __init__(self):
            self.draw_calls = []
            self.line_calls = []
        def setFont(self, *a, **k): pass
        def setLineWidth(self, *a, **k): pass
        def drawString(self, x, y, text): self.draw_calls.append((x, y, text))
        def line(self, *a, **k): self.line_calls.append(a)

    title_flowable = _TitleFlowable("표준 작업계획서")
    title_flowable.wrap(500, 1000)
    fake_canvas = _FakeCanvas()
    title_flowable.canv = fake_canvas
    title_flowable.draw()
    checks.append(("제목을 두 번 겹쳐 그려 굵게 보이게 함(faux-bold)", len(fake_canvas.draw_calls) == 2))
    checks.append((
        "두 번 그린 텍스트 내용이 같다(약간의 x 오프셋만 다름)",
        fake_canvas.draw_calls[0][2] == fake_canvas.draw_calls[1][2] == "표준 작업계획서",
    ))
    checks.append(("밑줄이 한 번 그려짐", len(fake_canvas.line_calls) == 1))

    pdf_bytes = record_to_pdf_bytes(SAMPLE_RECORD)
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)

    tables = parse_markdown_tables(SAMPLE_RECORD["draft"])
    frame_width = landscape(A4)[0] - 2 * _PAGE_MARGIN_PT
    fits = True
    for table in tables:
        table_flowable, _ = _build_table_element(table, frame_width, SAMPLE_RECORD["document_type"])
        w, h = table_flowable.wrap(frame_width, 10000)
        if w > frame_width + 1:  # +1pt: 부동소수점 오차 허용
            fits = False

    checks.append(("PDF 매직바이트", is_pdf))
    checks.append(("문서종류 제목 보존", SAMPLE_RECORD["document_type"] in full_text))
    checks.append(("표 내용(작업단계/감소대책) 보존", "작업단계" in full_text and "매설물 관리기관" in full_text))
    checks.append(("모든 표가 페이지 폭 안에 들어감(clipping 없음)", fits))

    # --- 스타일(열비율/배경색/AI 제안값 각주) 검증 ---
    score_tables = parse_markdown_tables(SAMPLE_RECORD_WITH_SCORE["draft"])
    score_table = score_tables[0]
    score_flowable, ai_present = _build_table_element(
        score_table, frame_width, SAMPLE_RECORD_WITH_SCORE["document_type"]
    )
    checks.append(("AI 제안값이 있는 표는 ai_value_present=True", ai_present is True))

    bg_commands = score_flowable._bkgrndcmds
    checks.append((
        "헤더 행에 header_fill 배경색 적용",
        any(cmd[1] == (0, 0) for cmd in bg_commands),
    ))
    checks.append((
        "PDF 헤더 행은 공유 스펙(진한 남색)이 아니라 PDF 전용 연한 톤을 씀",
        any(cmd[1] == (0, 0) and cmd[-1] == _hex_color(_PDF_HEADER_FILL) for cmd in bg_commands),
    ))
    checks.append((
        "PDF 전용 헤더색은 공유 스펙 header_fill과 다름(더 연해야 함)",
        _PDF_HEADER_FILL != STYLE_SPECS["위험성평가표"].header_fill,
    ))
    checks.append((
        "위험등급 'A' 셀에 A등급 배경색 적용 (열3=위험등급, 행1)",
        any(cmd[1] == (3, 1) for cmd in bg_commands),
    ))
    checks.append((
        "개선후 위험등급 'B' 셀에 B등급 배경색 적용 (열4=개선후 위험등급, 행1)",
        any(cmd[1] == (4, 1) for cmd in bg_commands),
    ))

    pdf_bytes_score = record_to_pdf_bytes(SAMPLE_RECORD_WITH_SCORE)
    reader_score = pypdf.PdfReader(io.BytesIO(pdf_bytes_score))
    full_text_score = "".join(page.extract_text() for page in reader_score.pages)
    checks.append((
        "AI 제안값 셀은 순수값만 표시(안내문구는 셀에 없음)",
        "AI 제안값" not in full_text_score.split("※")[0],
    ))
    checks.append(("AI 제안값 각주가 표 아래에 1회 표기됨", full_text_score.count("AI 제안값") == 1))

    # --- 좁은 열에 지나치게 긴 셀 텍스트가 들어와도 LayoutError 없이 생성됨 ---
    try:
        narrow_pdf = record_to_pdf_bytes(SAMPLE_RECORD_NARROW_COLUMN_LONG_TEXT)
        narrow_ok = narrow_pdf[:5] == b"%PDF-"
    except Exception as e:
        narrow_ok = False
        print(f"  (좁은 열 긴 텍스트 케이스에서 예외 발생: {type(e).__name__})")
    checks.append(("좁은 열(12열 표 1열)에 긴 텍스트가 와도 PDF 생성이 실패하지 않음", narrow_ok))

    # --- 열 너비가 실제 내용 길이에 비례해 배분됨(짧은 "예" 열은 좁고, 서술형 열은 넓음) ---
    mixed_tables = parse_markdown_tables(SAMPLE_RECORD_MIXED_WIDTH["draft"])
    mixed_flowable, _ = _build_table_element(
        mixed_tables[0], frame_width, SAMPLE_RECORD_MIXED_WIDTH["document_type"]
    )
    mixed_widths = mixed_flowable._colWidths
    checks.append((
        "서술형 열(0)이 짧은 '예/아니오' 열(1)보다 훨씬 넓다",
        mixed_widths[0] > mixed_widths[1] * 3,
    ))

    # --- 2026-08-04 재현된 버그: 짧은 열도 옆에 아주 긴 열이 있으면 자기
    # 자연폭보다 더 좁게 눌려서 줄바꿈됐다("작업단계" 4글자가 두 줄로 쪼개짐,
    # 폰트를 14pt로 키운 뒤 재발) ---
    from export_pdf import _measure_max_line_width
    narrow_vs_huge_flowable, _2 = _build_table_element(
        parse_markdown_tables(SAMPLE_RECORD["draft"])[0], frame_width, SAMPLE_RECORD["document_type"]
    )
    col0_natural = _measure_max_line_width("작업단계", _CELL_STYLE_LEFT.fontSize) + 10
    checks.append((
        "옆 열(감소대책)이 아주 길어도, 짧은 헤더 열은 자기 자연폭 이상을 받는다",
        narrow_vs_huge_flowable._colWidths[0] >= col0_natural - 1,
    ))

    checks.append((
        "열 너비 합이 frame_width와 같다(빈 공간 없이 꽉 참)",
        abs(sum(mixed_widths) - frame_width) < 1,
    ))

    # --- 박스 제목(헤딩)이 PDF에 실제로 그려짐 ---
    heading_pdf = record_to_pdf_bytes(SAMPLE_RECORD_WITH_HEADING)
    heading_reader = pypdf.PdfReader(io.BytesIO(heading_pdf))
    heading_text = "".join(page.extract_text() for page in heading_reader.pages)
    checks.append(("박스 제목 '■ 기본 정보'가 PDF 본문에 포함됨", "기본 정보" in heading_text))
    checks.append(("박스 제목 '■ 중점(One Point) 위험요인'이 PDF 본문에 포함됨", "중점" in heading_text and "위험요인" in heading_text))
    checks.append(("레벨1 제목('위험성평가표 초안')은 본문에 중복 삽입되지 않음(문서 제목에서만 1번)", heading_text.count("초안") == 0))

    # --- 2026-08-04 재현된 버그: 표가 아니라 서술형 문단인 섹션은 제목만 남고
    # 본문이 통째로 사라졌었다(parse_markdown_blocks가 heading/table만 인식) ---
    prose_record = {
        "document_type": "TBM 일지",
        "draft": (
            "## ■ 기본 정보\n\n"
            "| 항목 | 내용 |\n|------|------|\n| 현장명 | 강남지사 |\n\n"
            "---\n\n"
            "### 3. 중점(One Point) 위험요인\n\n"
            "오늘은 활선 근접 작업이 포함되어 있으므로 무전압 상태를 반드시 확인한다.\n"
        ),
    }
    prose_pdf = record_to_pdf_bytes(prose_record)
    prose_reader = pypdf.PdfReader(io.BytesIO(prose_pdf))
    prose_text = "".join(page.extract_text() for page in prose_reader.pages)
    checks.append(("표가 아닌 서술형 섹션의 본문 내용이 PDF에 실제로 그려짐", "무전압 상태" in prose_text))

    # --- 표는 명시적으로 좌측정렬(hAlign)됨, 박스 제목 아래 내용은 들여쓰기됨 ---
    indent_blocks = parse_markdown_blocks(SAMPLE_RECORD_WITH_HEADING["draft"])
    indent_elements = _build_elements(indent_blocks, SAMPLE_RECORD_WITH_HEADING["document_type"], frame_width)
    indenters = [e for e in indent_elements if isinstance(e, Indenter)]
    checks.append(("헤딩마다 Indenter(+)/Indenter(-) 쌍이 맞음", sum(i.left for i in indenters) == 0))
    checks.append(("들여쓰기 폭만큼(+_CONTENT_INDENT_PT)이 걸림", any(i.left == _CONTENT_INDENT_PT for i in indenters)))
    tables_in_elements = [e for e in indent_elements if isinstance(e, Table)]
    checks.append((
        "헤딩 아래 표의 열너비 합은 (frame_width - 들여쓰기)와 같음(들여쓰기만큼 좁아짐)",
        all(abs(sum(t._colWidths) - (frame_width - _CONTENT_INDENT_PT)) < 1 for t in tables_in_elements),
    ))
    checks.append(("헤딩 아래 표는 hAlign='LEFT'", all(t.hAlign == "LEFT" for t in tables_in_elements)))

    # --- 참석자 명단(서명 필수) 표는 최소 10행 확보 + 손글씨 서명 가능한 행 높이 ---
    roster_record = {
        "document_type": "TBM 일지",
        "draft": (
            "### 7. 참석자 명단 (서명 필수)\n\n"
            "| 소속 | 직책 | 성명 | 서명 |\n|------|------|------|------|\n"
            "|  |  |  |  |\n|  |  |  |  |\n"
        ),
    }
    roster_blocks = parse_markdown_blocks(roster_record["draft"])
    roster_table_rows = [b["rows"] for b in roster_blocks if b["type"] == "table"][0]
    roster_flowable, _ = _build_table_element(
        roster_table_rows, frame_width, roster_record["document_type"], is_signature_table=True
    )
    checks.append(("참석자 명단 표는 헤더 제외 최소 10행으로 패딩됨", len(roster_flowable._cellvalues) - 1 >= 10))
    checks.append(("_build_table_element이 만든 표는 hAlign='LEFT'", roster_flowable.hAlign == "LEFT"))
    checks.append((
        "참석자 명단 표의 데이터 행 높이가 서명 가능한 정도로 확대됨(>=24pt)",
        all(h >= 24 for h in roster_flowable._argH[1:]),
    ))
    checks.append((
        "일반 표(is_signature_table 기본값)는 패딩되지 않음",
        len(mixed_flowable._cellvalues) - 1 == 1,
    ))

    # --- record_to_pdf_bytes 전체 파이프라인에서도 "참석자"/"서명" 헤딩 뒤
    # 표가 자동으로 서명란 처리되는지(직전 헤딩 텍스트로 판정) ---
    roster_pdf = record_to_pdf_bytes(roster_record)
    checks.append(("참석자 명단 표 포함 PDF도 정상 생성됨", roster_pdf[:5] == b"%PDF-"))

    # --- 표가 여러 페이지에 걸치면 헤더 행(열 제목)이 각 페이지에 반복됨 ---
    many_rows_lines = ["| 번호 | 위험요인 | 감소대책 |", "|------|------|------|"]
    for i in range(80):
        many_rows_lines.append(f"| {i+1} | 위험요인 {i+1} | 감소대책 상세 설명 {i+1} |")
    many_rows_record = {
        "document_type": "위험성평가표",
        "draft": "\n".join(many_rows_lines),
    }
    many_rows_pdf = record_to_pdf_bytes(many_rows_record)
    many_rows_reader = pypdf.PdfReader(io.BytesIO(many_rows_pdf))
    checks.append(("80행 표는 여러 페이지로 분할됨", len(many_rows_reader.pages) > 1))
    pages_with_header = sum(
        1 for page in many_rows_reader.pages if "위험요인" in page.extract_text() and "감소대책" in page.extract_text()
    )
    checks.append(("헤더 행(열 제목)이 모든 페이지에 반복됨", pages_with_header == len(many_rows_reader.pages)))

    # --- 페이지 크기는 모두 A4, 방향만 문서유형별로 다름(2026-08-04 요청):
    # 위험성평가표는 열이 많아 가로형 유지, 표준작업계획서/TBM일지는 세로형 ---
    for doc_type, draft, expected_size in [
        ("위험성평가표", "| 항목 | 내용 |\n|------|------|\n| 현장명 | 강남 |\n", landscape(A4)),
        ("표준 작업계획서", "| 항목 | 내용 |\n|------|------|\n| 작업유형 | 굴착작업 |\n", portrait(A4)),
        ("TBM 일지", "| 항목 | 내용 |\n|------|------|\n| 일자 | 2026-08-04 |\n", portrait(A4)),
    ]:
        doc_pdf = record_to_pdf_bytes({"document_type": doc_type, "draft": draft})
        doc_reader = pypdf.PdfReader(io.BytesIO(doc_pdf))
        box = doc_reader.pages[0].mediabox
        size_ok = abs(float(box.width) - expected_size[0]) < 1 and abs(float(box.height) - expected_size[1]) < 1
        orientation = "세로형" if expected_size == portrait(A4) else "가로형"
        checks.append((f"{doc_type} PDF 페이지 크기가 A4({orientation})와 일치", size_ok))

    print()
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}")

    print("\n" + "=" * 50)
    print("전체 결과:", "PASS" if all_ok else "FAIL (위 로그 확인)")
    return all_ok


if __name__ == "__main__":
    run()
