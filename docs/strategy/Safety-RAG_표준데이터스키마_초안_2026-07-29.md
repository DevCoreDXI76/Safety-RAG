# Safety-RAG 표준 데이터 스키마 초안 (2026-07-29)

## 분석 대상

research 폴더에 넣어주신 서식 12종을 LibreOffice(+h2orestart HWP 필터)로 변환 후 텍스트/표 구조를 정밀 추출해서 분석했습니다.

| 파일 | 성격 |
|---|---|
| 위험성평가표-구내정보통신공사(예시).pdf | **KICA 공식 예시, 통신공사 위험성평가 — 가장 중요** (7개 공종, 40+개 위험요인 항목 실사례) |
| 위험성평가표-무선망_시설공사(예시).hwp | KICA 공식 예시, 무선망 시설공사 |
| 위험성평가표-양식.hwp / 위험성평가_위험성평가표양식.hwp | 빈 양식 2종 (거의 동일 구조) |
| 전기_작업계획서.hwp | KICA 공식 양식 — 산업안전보건기준에 관한 규칙 제38조 대응 |
| 중량물_취급_작업계획서(이동식크레인).hwp | KICA 공식 양식 |
| 차량계_건설기계_작업계획서(예시).hwp | KICA 공식 양식 (실사례 포함) |
| 협의체_회의록.hwp | TBM류 문서 (참석자명단+의결사항+회의사진) |
| 안전보건교육_일지·참석자명단·교육사진대지.hwp | 목업 4번 관련 실물 확인 |
| [별지1~3] 기본/설계/공사 안전보건대장.hwp | 법정 서식이지만 발주자/설계자용 — Safety-RAG 1차 스코프 밖으로 판단 (하단 참고) |

---

## 핵심 발견 — 표준 스키마 설계에 직접 영향을 주는 것들

### 1. 위험도 표기 방식이 두 갈래로 나뉜다

- **KRAS 표준(KOSHA 공식)**: 가능성(빈도, 1~3 또는 1~5) × 중대성(강도) = 위험성 점수(숫자). Safety-RAG가 **지금 이미 이 방식으로 구현**되어 있고, 지난 QA에서 검증 완료된 부분입니다.
- **KICA 실사용 현장 서식**: 빈도(1~3) × 강도(1~3)를 **3×3 매트릭스에 대입해서 A(매우위험)/B(위험)/C(주의관리요) 등급**으로 표기. 원청 보고·현장 게시용으로는 이쪽이 훨씬 많이 쓰입니다 (구내정보통신공사 예시 전체가 이 방식).

→ **결론**: 위험도는 내부적으로 숫자(빈도×강도)로 저장하고, 화면/출력 시 "숫자" 표기와 "A/B/C 등급" 표기를 **모드로 선택**할 수 있게 스키마를 설계하는 게 맞습니다. 계산 로직(빈도×강도)은 공유하고, 표시 레이어만 분기합니다.

### 2. "단위작업" 단위로 여러 위험요인이 묶인다

KICA 실사례를 보면 위험성평가표 한 장이 "공종"(예: 4층 바닥 배관) 밑에 여러 "단위작업"(자재반입, 구내운반, 슬라브 배관 등)을 담고, **하나의 단위작업 안에 위험요인이 1개~3개까지 반복**됩니다(예: "슬라브 배관"에 "철근 걸림 위험"과 "베임·찔림 위험" 2개가 같이 들어감). 지금 Safety-RAG가 위험요인 1개 = 행 1개로 플랫하게 저장하고 있다면, "단위작업"을 그룹 키로 하나 더 두는 게 실제 현장 서식과 맞습니다.

### 3. 안전대책은 항상 "여러 줄 불릿"이다

실사례 어디에도 안전대책이 한 문장으로 끝나는 경우가 없습니다. 항상 `·` 또는 `-`로 시작하는 2~5개의 하위 조치 목록입니다. 현재 XLSX 셀에 줄바꿈(wrap_text)으로 처리 중인 방식이 맞는 방향이고, 데이터 모델에서도 안전대책을 **문자열 1개가 아니라 리스트(array)**로 저장해야 렌더링 시 불릿을 깔끔하게 재현할 수 있습니다.

### 4. 실시자(담당자)는 종종 복수 인원·역할이다

"현장소장000 / 반장000 / 근로자000" 처럼 역할+이름이 여러 명 들어갑니다. 문자열 하나로 뭉쳐 저장하면 나중에 역할별 필터링(예: "이 항목은 누가 확인해야 하지?")이 불가능해집니다.

### 5. 작업계획서는 공종별로 필요한 필드가 완전히 다르다

- **전기_작업계획서**: 발주처/시공사/NO, 작업책임자·입회자, 위험성평가 결과(위험성크기+관리계획), 절연용보호구/방호구 체크리스트, 작업순서-내용-안전조치사항-비고 표
- **중량물(이동식크레인)**: 크레인 현황(기종/규격/운전원면허), 작업일자별(최대 3일치) 작업장 현황, 인양물 규격/중량/작업반경/붐길이, 줄걸이 하중 계산(절단하중/안전계수/장력계수), 지반강도/아웃트리거, 풍속 작업중지 기준
- **차량계 건설기계**: 장비 최대 3대 동시 등록(장비명/제조사모델/장비능력/장비폭/조종원), 운행경로(시점~종점), 제한속도, 지형·지반상태, 투입시 점검사항(등록증/면허증/보험증명서)

→ 세 양식을 억지로 하나의 플랫 테이블에 넣으면 안 쓰는 필드가 절반 이상 생깁니다. **"공통 헤더 + 작업유형별 확장 블록(polymorphic)"** 구조가 맞습니다.

### 6. TBM류 문서(협의체 회의록)는 위험성평가와 구조가 다르다

참석자명단(업체명/성명/서명, 최대 인원 가변) + 의결사항(자유서술) + 회의사진(첨부) 이 전부입니다. 이전 세션에서 확인한 "TBM(Tool Box Meeting) 회의록" 형태(TBM일시/작업명/TBM장소/잠재위험요인/대책/중점위험 선정)와는 별개 문서 종류로, **TBM일지**는 그날의 위험성평가 요약을 끌어와 보여주는 문서이고 **협의체 회의록**은 순수 회의록입니다. 지금 Safety-RAG의 "TBM일지"가 어느 쪽을 구현했는지 확인이 필요합니다 — 아마 전자(위험성평가 연동형)가 맞을 겁니다.

---

## 표준 데이터 스키마 (JSON Schema 초안)

### 공통 헤더 (모든 문서가 공유)

```json
{
  "project": {
    "project_id": "string (내부 PK)",
    "company_name": "string (공사명 앞에 붙는 발주/시공사명, 예: 00 정보통신(주))",
    "site_name": "string (현장명)",
    "construction_name": "string (공사명, 예: '00 정보통신공사')",
    "period_start": "date",
    "period_end": "date",
    "site_manager": "string (현장소장)",
    "site_address": "string"
  }
}
```

### A. 위험성평가표 (risk_assessment)

```json
{
  "risk_assessment": {
    "assessment_id": "string",
    "project_id": "string (FK)",
    "process_name": "string (공종, 예: '4층 바닥 배관', '입선작업', '케이블 풀링작업')",
    "assessment_date": "date",
    "risk_display_mode": "enum ['numeric_product', 'matrix_abc']  // 숫자곱셈 vs A/B/C 매트릭스, 문서 종류/제출처별로 선택",
    "matrix_scale": "enum [3, 5]  // 빈도·강도 척도, 기본 3 (KICA 관행), KRAS 제출용은 5도 지원",
    "unit_tasks": [
      {
        "unit_task_id": "string",
        "unit_task_name": "string (단위작업, 예: '자재반입', '슬라브 배관')",
        "hazards": [
          {
            "hazard_id": "string",
            "description": "string (위험요인 — 상황+결과 서술형 1~2문장)",
            "legal_basis": "string | null (관련근거/법적기준 — KRAS 표준 제출시만 필수, KICA 실무형은 생략 가능)",
            "current_measures": "string | null (현재의 안전보건조치 — KRAS 표준형만)",
            "frequency": "integer (빈도, 1~matrix_scale)",
            "severity": "integer (강도, 1~matrix_scale)",
            "risk_score": "integer (frequency * severity, 항상 계산)",
            "risk_grade": "enum ['A','B','C'] | null (risk_display_mode=matrix_abc일 때 매트릭스 조회로 산출)",
            "responsible_parties": [
              {"role": "string (예: 반장/현장소장/근로자)", "name": "string | null"}
            ],
            "safety_measures": ["string (불릿 1줄씩, 배열)"],
            "improved_risk_score": "integer | null (개선후 위험성 — KRAS 표준형만)",
            "target_date": "date | null (개선예정일)",
            "completed_date": "date | null (완료일)",
            "owner": "string | null (담당자)"
          }
        ]
      }
    ],
    "matrix_legend": {
      "note": "risk_display_mode=matrix_abc일 때만 사용. 예: 3x3 기준 빈도1×강도1=C ... 빈도3×강도3=A",
      "grade_map": "{ '1-1':'C', '1-2':'C', '1-3':'B', '2-1':'C', '2-2':'B', '2-3':'A', '3-1':'B', '3-2':'A', '3-3':'A' }"
    }
  }
}
```

### B. 표준작업계획서 (work_plan) — 공통 + 작업유형별 확장

```json
{
  "work_plan": {
    "plan_id": "string",
    "project_id": "string (FK)",
    "work_type": "enum ['electric', 'heavy_lifting_crane', 'vehicle_construction_machinery', 'general']",
    "work_number": "string (작업번호)",
    "work_name": "string (작업명)",
    "work_location": "string (작업개소)",
    "author": "string (작성자)",
    "reviewer": "string | null (검토자)",
    "prepared_date": "date",
    "work_responsible": "string (작업책임자)",
    "witness": "string | null (입회자)",
    "work_schedule": {"date": "date", "note": "string | null"},
    "linked_risk_assessment_id": "string | null (해당 위험성평가표 참조 — 위험성평가 결과 섹션에 요약 표시)",
    "work_steps": [
      {"order": "integer", "content": "string (작업내용)", "safety_measures": "string", "note": "string | null"}
    ],

    "electric_ext": {
      "_applies_when": "work_type == 'electric'",
      "owner_company": "string (발주처)",
      "contractor": "string (시공사)",
      "checklist": {
        "site_safety_check": "boolean",
        "insulation_gear": "boolean",
        "insulation_barrier": "boolean",
        "responsible_confirm": "boolean",
        "qualified_person_confirm": "boolean",
        "work_standard_used": "boolean"
      }
    },

    "crane_ext": {
      "_applies_when": "work_type == 'heavy_lifting_crane'",
      "crane_model": "string",
      "crane_capacity": "string (정격하중)",
      "registration_number": "string",
      "operator_name": "string",
      "operator_license_valid_until": "date",
      "safety_inspection_valid_until": "date",
      "daily_sessions": [
        {
          "session_no": "integer (최대 3)",
          "date": "date",
          "time_range": "string",
          "location": "string",
          "area_sqm": "number",
          "ground_obstacle": "boolean",
          "underground_obstacle": "boolean",
          "work_content": "string",
          "supervisor": "string",
          "director": "string",
          "operator": "string",
          "rigger": "string",
          "rigger_assistant": "string",
          "signal_person": "string",
          "signal_method": "enum ['hand','radio','other']",
          "lift_object_spec": "string",
          "lift_object_weight_kg": "number",
          "total_lift_weight_kg": "number",
          "work_radius_m": "number",
          "boom_length_m": "number",
          "lift_capacity_check": "string (제원표 확인 결과)",
          "max_lift_load_percent": "number (85% 이내 검토결과)",
          "ground_strength": "enum ['견고','보통','연약']",
          "outrigger_extendable": "boolean",
          "wind_stop_criteria_ms": "number"
        }
      ]
    },

    "vehicle_machinery_ext": {
      "_applies_when": "work_type == 'vehicle_construction_machinery'",
      "company_name": "string",
      "manager": "string",
      "work_process": "string (공종, 예: 가시설공사)",
      "total_workload": "string",
      "speed_limit_kmh": "number",
      "commander": "string (작업지휘자)",
      "signal_method": "string",
      "guide_positions": [{"position": "string", "route_start": "string", "route_end": "string"}],
      "ppe_issued": ["string"],
      "equipment_list": [
        {
          "equipment_name": "string",
          "manufacturer_model": "string",
          "capacity": "string",
          "width_m": "number",
          "purpose": "string",
          "operator_name": "string",
          "operator_license": "string | null"
        }
      ],
      "site_terrain": {"slope_flat_pct": "number", "slope_incline_pct": "number"},
      "ground_condition": {"type": "string", "compaction": "string", "bearing_capacity": "string", "groundwater": "string", "drainage": "string"},
      "pre_deployment_checks": {"registration_copy": "boolean", "license_copy": "boolean", "insurance_proof": "boolean"}
    }
  }
}
```

### C. TBM일지 / 협의체 회의록 (tbm_log)

```json
{
  "tbm_log": {
    "log_id": "string",
    "project_id": "string (FK)",
    "log_type": "enum ['tbm', 'council_meeting']  // TBM일지 vs 협의체 회의록 — 서로 다른 문서",
    "date": "date",
    "location": "string",
    "work_name": "string | null (TBM: 당일 작업명)",
    "work_content": "string | null (TBM: 당일 작업내용)",
    "linked_risk_assessment_id": "string | null (그날의 위험성평가표 연동 — TBM은 이걸 요약해서 보여줌)",
    "risk_assessment_done": "boolean | null (위험성평가 실시여부, TBM 전용)",
    "key_hazards_selected": ["string (그날 중점위험으로 선정된 항목, hazard_id 참조 또는 자유서술)"],
    "attendees": [
      {"company": "string (업체명)", "name": "string (성명)", "signed": "boolean (서명 여부)"}
    ],
    "resolutions": "string | null (의결사항, 협의체 회의록 전용)",
    "photos": ["string (첨부 이미지 경로/URL, 여러 장)"]
  }
}
```

---

## 렌더러 매핑 원칙 (3-포맷 공통)

브레인스토밍에서 나온 "표준 데이터 → PDF/HWPX/XLSX 3-포맷 렌더러" 구조를 이 스키마 기준으로 정리하면:

1. **PDF/HWPX 렌더러**: `unit_tasks[].hazards[]`를 순서대로 순회하며 표 행(row)으로 그리고, 표가 페이지를 넘어가면 헤더 행을 반복 출력(HWPX의 `repeatHeader` 버그가 바로 이 지점 — 표준 스키마에서 "표 헤더는 페이지마다 반복"을 렌더러 공통 규칙으로 명시해야 함).
2. **XLSX 렌더러**: 같은 데이터를 셀에 매핑하되 `safety_measures` 배열은 줄바꿈(`\n`)으로 합쳐 하나의 wrap_text 셀에 넣음(현재 방식 유지).
3. **위험도 표시**: `risk_display_mode`에 따라 렌더러가 숫자 또는 A/B/C 배지 중 하나를 그림 — 데이터는 항상 `frequency`/`severity`/`risk_score`를 갖고 있고, `risk_grade`는 파생값(뷰 전용)으로 취급.
4. **문서 메타데이터**: 이전 QA에서 지적된 "PDF 메타데이터 공란(Author/Title/Creator)" 문제는 렌더러가 `project.company_name` + `risk_assessment.assessment_date`를 PDF 메타데이터에 채우도록 스키마-렌더러 계약에 명시.

---

## Safety-RAG 기존 구현과의 차이점 (검토 필요)

이전 QA(송파지사/분당지사/일산지사 테스트)에서 확인된 실제 구현과 비교하면:

- 기존: 위험요인 1건 = 1행 플랫 구조로 보임 → **"단위작업" 그룹핑 레이어 추가 검토 필요**
- 기존: 위험도 = 숫자(가능성×중대성) + 색상밴드 → **KICA 실무 관행인 A/B/C 등급 표시 모드 추가 여부는 베타 사용자 피드백(엑셀 선호, 원청 제출용 서식 등)에 따라 결정**. 급하게 바꿀 필요는 없고, 스키마에 "표시 모드" 필드로 여지만 남겨두면 됨.
- 기존: 작업유형(법정분류) 오류 사례(차량계 건설기계 vs 하역운반기계등)가 있었는데, 이번 `vehicle_machinery_ext`/`crane_ext` 분리 설계가 이 문제의 근본 해결책이 될 수 있음 — 작업유형을 스키마 레벨에서 명시적으로 선택하게 하면 법정 분류 매핑 오류가 구조적으로 줄어듦.
- 안전보건교육일지/산업안전보건관리비 사용명세서(목업 4·5번)는 이번 조사에서 안전보건교육일지 실물을 확보했으니, 다음 단계에서 이 스키마 체계에 편입할 수 있음. 산업안전보건관리비는 이번에 실물을 못 구했습니다 — 필요하시면 추가 조사하겠습니다.

---

## 다음 단계 제안

1. 이 JSON Schema 초안을 Claude Code에 전달해서 실제 DB 스키마(테이블 또는 문서 구조)로 변환
2. ✅ **완료 (2026-07-31, 커밋 `7c7feb6`)**: `risk_display_mode`(A/B/C 등급 표시)·"단위작업 그룹핑" 모두 반영 결정·구현됨 — 단, 스키마/DB 레벨 변경이 아니라 프롬프트+KB 직접주입 방식으로 구현(1번 항목의 "B안" 전면 전환과는 별개). 위험성평가표가 곱셈법(숫자 1~25)에서 KICA·KRAS 표준 행렬법(빈도×강도→A/B/C)으로 전환됐고, 위험성평가 실시규정 KB에 단위작업 그룹핑 지침이 추가됨.
3. ✅ **완료 (2026-07-31)**: TBM일지 구조 확인 — **"위험성평가 연동형"으로 이미 구현되어 있음** (문서 분리 불필요). `TBM_서식.txt` 가이드 자체가 위험성평가표에서 발췌하는 구조를 전제하고, CLI(`generate_draft.py`)·API(`api/routes.py`)·웹 UI(`webapp/index.html`) 3곳 모두 같은 현장의 위험성평가 회차를 선택해 연동하는 로직이 이미 있음. 단 연동은 선택적(optional) — 위험성평가 기록이 없는 현장이면 연동 없이 일반 가이드만으로 생성되는 폴백도 있음.
4. ✅ **완료**: 렌더러 3종(PDF/HWPX/XLSX) 모두 "표 헤더 반복" 반영됨 — PDF(`export_pdf.py` `repeatRows=1`), HWPX(표 XML `repeatHeader="1"`, 커밋 `01cae18`), XLSX(`export_xlsx.py` `print_title_rows`).
5. 🆕 **2026-07-31 QA 완료, 남은 항목**: 오늘 커밋(`7c7feb6`)의 대형 변경(행렬법 전환·KRAS 컬럼·TBM 중점위험요인·안전보건교육일지 3부구조·협의체 회의록)을 실제 생성 테스트로 QA 완료 — A/B/C 등급 산정 로직, 개선후 위험등급 대소관계, TBM 연동, XLSX 셀 타입(숫자/문자)·조건부서식 모두 정상 확인. 이제 남은 건 **1번(B안: 구조화 JSON 스키마 전면 전환)** 뿐이며, 이건 스코프가 크므로 착수 시 별도 브레인스토밍 세션으로 진행 권장.
