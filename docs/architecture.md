# 치아보험 보장분석표 생성기 아키텍처

## 1. 목표와 안전 원칙

이 애플리케이션은 Windows에서 완전히 로컬로 동작한다. PDF나 개인정보를 외부 API, 분석 도구, 텔레메트리로 전송하지 않는다. 최우선 목표는 추출량이 아니라 **근거 없는 보험정보를 만들지 않는 것**이다. 원문에서 확인되지 않는 필드는 `null`로 유지하고, 낮은 신뢰도의 결과는 자동 확정하지 않는다. 권장금액과 가입금액을 별도 필드로 보존하며 서로 대체하지 않는다.

## 2. 모듈 경계와 처리 Pipeline

각 단계는 입력과 출력을 명시한 독립 모듈이며 중간 결과를 디버그 JSON으로 직렬화할 수 있게 한다.

1. PDF metadata 확인 및 암호화/페이지 수 검사
2. PyMuPDF Text Layer 추출 (`text`, `words`, `blocks`, `dict`와 좌표 보존)
3. 페이지별 Text Quality 분석
4. `TEXT_PARTIAL`, `TEXT_GARBLED`, `IMAGE_ONLY` 페이지만 로컬 OCR 후보로 전달
5. OCR 결과와 원본 Text Layer를 별도 provenance로 유지
6. 여러 제목/레이아웃 특징을 이용한 페이지 유형 분류
7. 좌표 기반 행·열 및 인접 셀 분석
8. 보험계약 추출
9. 전체 치아보장(`AggregateCoverage`) 추출
10. 상품별 치과담보(`DentalRider`) 추출
11. 정규화, level 내부 중복 제거, 계약 연결 및 교차 검증
12. 사용자 검토·수정, 원본 좌표 하이라이트
13. 확정 데이터로 HTML 보고서 생성 및 로컬 PDF 출력

계획된 패키지 경계는 `core/pdf`, `core/parsers`, `core/dental`, `core/processing`, `ui`, `reports`이다. `GenericParser`가 기본이며 provider adapter는 증거가 있는 형식 특성만 보강한다. 알 수 없는 문서는 오류 종료 대신 Generic 결과와 지원 수준을 표시한다.

## 3. 데이터 Level과 provenance

### Level 1 — AggregateCoverage

고객 전체 보험의 집계 분석이다. 원본/정규화 담보명, 카테고리, 권장·가입·부족·초과 금액, 원문 차액, 보고/계산 보장률, 상태, 모든 출처 페이지, 대표 출처 및 confidence를 보존한다.

### Level 2 — DentalRider

특정 계약/상품의 실제 개별 담보다. 보험사와 상품명은 확인된 연결만 기록한다. 원본/정규화/신용정보원 담보명, 카테고리, 가입금액, 지급단위·한도, 원인 구분, 페이지·bbox·원문 및 confidence를 보존한다.

두 level은 의미가 다르므로 상호 중복 제거하거나 금액을 합산하지 않는다. 모든 금액은 숫자 값과 `raw` 문자열을 함께 보존한다. 모든 추출 객체는 페이지(1-base), bbox `(x0,y0,x1,y1)`, 원문과 confidence 이유를 가질 수 있다.

## 4. Text Quality와 OCR fallback

공백을 제외한 전체 문자 수, 한글/숫자 비율, 의미 있는 단어 수, 보험 핵심어 탐지율, replacement/control 문자 비율, 글자 사이 과도한 공백 패턴을 측정한다.

- `IMAGE_ONLY`: 공백 제외 문자가 없거나 극소수이고 의미 정보가 없음
- `TEXT_GARBLED`: 숫자는 충분하지만 한글과 보험 단어가 거의 없거나, 깨진 문자/이상 공백이 심함
- `TEXT_PARTIAL`: 일부 의미 정보는 있으나 길이·한글·핵심어 지표가 안정 기준 미달
- `TEXT_OK`: 충분한 길이와 한글 문맥 및 의미 단어가 확인됨

임계치는 보수적인 초기값이며 분석 결과에 metrics와 reason을 남긴다. `TEXT_OK` 외 상태는 OCR 후보지만 실행 여부는 정책/로컬 엔진 가용성에 따른다. OCR은 한국어+영어+숫자를 로컬에서만 처리하고, OCR confidence가 낮으면 결과를 `LOW`와 검토 대상으로 둔다. Text Layer와 OCR이 충돌하면 원문을 임의 선택하지 않고 검토 항목을 만든다.

## 5. 금액과 비율 정책

금액 파서는 `원`, `만/만원`, `억`의 조합과 소수를 정수 원 단위로 변환하고 원문을 보존한다. 문맥 라벨이 `권장`, `가입`, `부족`, `초과` 중 무엇인지 확인된 후에만 대응 필드에 배치한다. 권장·가입이 모두 있고 권장이 0보다 클 때만 계산 보장률을 만든다. PDF 보고 비율과 허용 오차 밖에서 다르면 검토 대상으로 둔다. 차액 부호는 제공사마다 달라 원문 차액과 정규화 부족/초과를 분리한다.

## 6. 중복 제거 정책

Aggregate 키는 정규화 담보명과 확인된 금액/상태 의미를 사용한다. 반복 행은 합산하지 않고 `source_pages`만 합친다. 값이 충돌하면 임의 병합하지 않고 별도 후보 또는 확인 필요로 남긴다. DentalRider 키에는 계약 식별자, 원인 구분, 지급단위, 담보명, 금액을 포함한다. 질병/상해 또는 지급단위가 다르면 별도 담보다. Rider끼리도 합계 보장액을 계산하지 않는다.

## 7. 보험상품 연결 전략

동일 페이지/표의 명시적 계약 식별자와 좌표상 포함 관계를 우선한다. 이어 연속된 product-detail 페이지의 검증된 헤더를 사용한다. 상품명에 `치아보험`, `치과보험`, `Dental`이 있으면 상품 후보 confidence를 높이지만 모든 담보를 치과담보로 확정하지 않는다. 보험사나 상품 연결이 불확실하면 `null`, `LOW`, 연결 실패 이유로 유지한다. 판별 우선순위는 보험사 원본 담보명, 상품명, 신용정보원명, 주변 문맥이다.

## 8. Confidence 정책

- `HIGH`: 명확한 구조화 행에서 필드와 좌표가 일치하고 Text Layer 품질이 정상
- `MEDIUM`: 문맥과 레이아웃은 일치하지만 일부 필드 누락, 부분 Text 또는 양호한 OCR
- `LOW`: OCR 불확실, 계약 연결 모호, 값 충돌 또는 약한 문맥

confidence에는 반드시 사람이 읽을 수 있는 `confidence_reason`을 함께 둔다. `LOW`와 validation issue는 확인 필요 화면으로 보낸다. 자동 규칙은 확인되지 않은 필드를 채우지 않는다.

## 9. 설정과 확장

치아 포함/제외 키워드는 `config/dental_keywords.json`, 카테고리는 `config/dental_categories.json`에서 로드한다. 이후 페이지/보험사 패턴도 JSON 설정으로 추가한다. 단일 글자 `치`는 키워드로 사용하지 않는다. provider adapter는 공통 모델과 parser protocol을 구현하므로 새 보험사 추가가 pipeline 변경을 요구하지 않는다.

## 10. 테스트 전략과 단계

현재 단계는 모델 불변조건, 한국식 금액 변환, 정상/부분/숫자 위주 깨짐/이미지 페이지 품질 판정, 좌표 추출, 페이지 분류, 후보 탐지, JSON/CLI를 테스트한다. PDF fixture는 저장소에 넣지 않고 PyMuPDF로 실행 중 생성한다.

후속 단계는 순서대로 (1) 로컬 OCR adapter 구현, (2) Meritz/Samsung Aggregate parser, (3) 계약/Product parser, (4) 치아 상품·Rider detector, (5) normalization/dedup/cross-reference/validation을 구현하며 각 단계에서 회귀 테스트를 통과한 뒤 진행한다. Parser 검증 후에만 한국어 GUI, source highlight viewer, 보고서, PyInstaller 패키징을 구현한다.

## 11. PDF Parsing Foundation 구현 상태

`PDFLoader`가 경로·metadata·암호화·페이지 수와 1-base 페이지 접근을 관리하고,
`LayoutExtractor`가 plain text와 word/block bbox를 보존한다. 각 페이지는 기존
Text Quality 분석 직후 설정 기반 `PageClassifier` 및 치아/보험사/상품 후보 탐지를
거쳐 `PDFPageData`가 된다. `analyze_pdf(path)`는 이 결과와 품질/유형 집계를
`PDFAnalysisResult`로 반환하며, 로컬 debug JSON 내보내기와 CLI를 제공한다.

OCR은 이번 단계에서 adapter protocol과 명시적인 `NOT_CONFIGURED` 구현만 제공한다.
OCR 필요 페이지를 숨기거나 Text Layer를 정상으로 가장하지 않으며, 다음 단계에서
로컬 OCR 구현을 이 interface에 연결한다. 이후 Aggregate/Contract/Rider parser는
페이지 원문과 좌표 및 후보 confidence를 그대로 입력으로 사용한다.

## 12. Generic Parsing Engine

`GenericParser`는 계약을 먼저 추출하고 그 결과를 Rider parser에 명시적으로 전달한다.
Aggregate parser는 필드 label을 우선하며, label이 없을 때에는 table header와 동일 행
bbox 열 관계 또는 명시적인 표 단위가 있는 경우만 값을 대응한다. 권장/가입금액에서
계산한 부족·초과·보장률과 PDF 원문 값을 별도로 보존하며 충돌은 수정하지 않고
`ValidationIssue`로 기록한다.

동일 이름과 동일 권장/가입금액의 Aggregate 반복은 금액을 합산하지 않고 출처 페이지만
병합한다. 값이 다른 후보는 모두 유지하고 `AGGREGATE_AMOUNT_CONFLICT`를 만든다.
Rider는 보험사 원본 담보명으로 치아 여부와 category를 판단하며 신용정보원 이름은 별도
필드로 보존한다. 질병/상해 및 지급단위도 별도 필드이므로 서로 다른 담보를 합치지 않는다.
동일 페이지에 계약이 여러 개이거나 OCR이 필요한 등 연결 근거가 부족한 경우 보험사와
상품명을 추측하지 않고 LOW confidence 및 확인 필요 항목으로 남긴다.

## 13. Local OCR 및 provenance

`analyze_pdf`는 Text Quality가 OCR 필요로 판정한 페이지만 250 DPI PNG로 한 번
렌더링한다. 픽셀 상한을 넘으면 DPI를 낮춘다. Tesseract backend는 bundle, 명시 경로,
시스템 PATH 순으로 실행 파일을 찾으며 자동 다운로드나 네트워크 통신을 하지 않는다.
실행 파일·언어 데이터 부재와 실행 실패를 각각 `NOT_CONFIGURED`, `FAILED`로 반환한다.

`PDFPageData`는 `text_layer_text`, `ocr_text`, `effective_text` 및
`TEXT_LAYER`/`OCR`/`MERGED` provenance를 독립 보존한다. OCR 성공 후 Text Quality를
다시 평가하고 더 나은 경우에만 parser 입력으로 채택한다. 핵심 보험 용어가 크게
충돌하면 두 원문을 보존하고 `TEXT_OCR_CONFLICT`를 생성한다. 낮은 OCR confidence의
parser 결과는 HIGH가 될 수 없다.

## 14. Provider와 adapter

Provider는 파일명이 아닌 전체 effective text의 회사명·제목·layout 신호를 score화해
`MERITZ`, `SAMSUNG`, `LOTTE`, `GENERIC`, `UNKNOWN`으로 판정한다. Provider adapter는
Generic Parser 이전에 page type, 연속 product-detail context, OCR 필요 hint만 제공한다.
메리츠 반복 Aggregate는 기존 dedup 정책으로 출처만 병합하고, 삼성 연속 상세는 새
보험사/상품 header가 없는 바로 다음 페이지에서만 계약 context를 상속한다. 롯데
adapter는 깨진 Text Layer에서 값을 복원하지 않고 OCR 필요 상태만 명시한다.

## 15. 좌표 행 복원과 중복 정책

Row reconstruction은 word 높이 중앙값과 페이지 높이로 y tolerance를 계산해 미세하게
어긋난 word를 같은 시각 행으로 묶고 좌→우 정렬한다. 행 bbox와 column 후보를 debug
JSON에 기록하며 Aggregate와 계약표 parser가 header-cell bbox 관계를 우선 사용한다.

계약 identity는 확인된 보험사, 상품명, 가입일, 보험기간, 피보험자로 구성한다. Rider
중복 키는 계약 identity, 정규화 담보명, 질병/상해, 지급단위, 가입금액이므로 지급조건이
다른 담보는 합치지 않는다. 완전히 동일한 반복 Rider는 금액을 합산하지 않고 source만
병합하며 금액 충돌은 `RIDER_DUPLICATE_CONFLICT`로 남긴다.

## 16. 지원 수준 및 실행 제어

분석 결과는 provider confidence, Text Layer 페이지 수, OCR 시도/성공/실패 수,
계약·Aggregate·Rider 수, 검토 항목 수와 `FULL`, `PARTIAL`, `REVIEW_REQUIRED`,
`UNSUPPORTED` 지원 수준을 제공한다. `on_progress(current, total, stage)`와
`is_cancelled()` dependency injection으로 향후 GUI 진행률·취소 기능을 연결할 수 있다.

설정 JSON은 `dental_coverage_analyzer.resources.config` package data에 포함하고
`importlib.resources`로 읽는다. PyInstaller에서는 `_MEIPASS`, 개발 checkout에서는
루트 `config/`를 호환 fallback으로 사용하므로 설정 위치 때문에 parser 구조를 다시
변경하지 않는다.
