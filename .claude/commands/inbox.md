---
description: INBOX 문서를 PARA 자동 분류하고 사용자 승인 후 파일 이동
allowed-tools: mcp__slotmachine__classify_inbox, mcp__slotmachine__get_document_contents, mcp__slotmachine__get_templates, mcp__slotmachine__apply_classification, mcp__slotmachine__suggest_links
---

# /slotmachine:inbox — INBOX PARA 자동 분류

## 실행 순서

### 1단계 — 문서 및 vault 구조 로드

`classify_inbox` 툴을 호출한다.

반환값:
- `documents`: INBOX 문서 목록 (path / title / tags / excerpt)
- `vault_structure`: 카테고리별 하위 디렉토리 및 기존 문서 제목

문서가 없으면 "INBOX가 비어 있습니다." 라고 알리고 중단한다.

### 2단계 — 문서 목록 표시 및 처리 범위 선택

INBOX 문서 목록을 번호와 함께 출력한다.

```
INBOX에 N개의 문서가 있습니다.

#   문서명
──────────────────────────────
1   앱_출시_체크리스트.md
2   독서노트_원칙.md
3   아이디어_메모.md
4   회의록_2026.md
5   클린코드_요약.md

전체 분류: [Enter] / 특정 문서 선택: 번호 입력 (예: 1 3 5) / 취소: N
```

- **Enter 또는 "전체"**: 전체 문서 분류 진행
- **번호 입력** (예: `1 3 5`): 해당 번호 문서만 분류 진행
- **N**: 중단

### 3단계 — PARA 분류 및 배치 위치 결정 (excerpt 기반)

선택된 문서 각각에 대해 excerpt와 메타데이터만으로 다음을 판단한다.

#### 3-1. PARA 카테고리 결정

| 카테고리 | 기준 |
|----------|------|
| Projects | 마감 기한이 있거나 현재 진행 중인 구체적 작업 |
| Areas | 지속적으로 관리가 필요한 책임 영역 |
| Resources | 미래에 참고할 수 있는 자료, 아티클, 책 요약 등 |
| Archives | 완료되었거나 더 이상 활성화되지 않은 항목 |
| Inbox | 내용이 모호해 판단하기 어려운 경우 |

#### 3-2. 하위 디렉토리 결정

`vault_structure[category].subdirs` 목록을 참고해 문서 내용과 가장 관련 있는 하위 디렉토리를 선택한다.

- 적합한 하위 디렉토리가 있으면 → `target_folder`로 지정 (예: `20_Projects/CryptoLab/Rocky`)
- 없으면 → category 루트 폴더 사용 (target_folder 생략)

### 4단계 — 분류 결과 표시 및 승인 요청

```
N개 문서 분류 결과:

#  문서명                    카테고리   배치 위치                       확신도  근거
────────────────────────────────────────────────────────────────────────────
1  앱_출시_체크리스트.md     Projects  20_Projects/Obsidian            높음    마감 기한과 구체적 태스크 포함
2  독서노트_원칙.md           Resources 40_Resources/Documentation      높음    참고 자료성 내용
3  아이디어_메모.md           Inbox     (유지)                          낮음    내용이 모호해 판단 보류

승인하시겠습니까? [Y: 전체 승인 / 번호: 해당 문서 수정 / N: 취소]
```

- **Y**: 5단계로 진행
- **번호 입력**: 해당 문서의 카테고리/위치를 사용자가 수정 후 재확인
- **N**: 취소

### 5단계 — 관련 문서 탐색 (벡터 기반)

이동 대상 문서(Inbox 유지 제외)마다 `suggest_links` 툴을 호출한다.

```json
{ "path": "INBOX/앱_출시_체크리스트.md", "top_k": 5, "threshold": 0.5 }
```

- 후보가 반환되면 → 해당 문서의 링크 후보로 메모한다.
- 후보가 없으면 (GraphDB에 미등록된 신규 문서 등) → `vault_structure[category].doc_titles` 기반 LLM 판단으로 폴백한다.

> `suggest_links`는 vault 전체를 대상으로 벡터 유사도 + 그래프 근접성 점수를 계산하므로,
> 단순 제목 목록 기반 판단보다 정확한 관련 문서를 찾아낸다.

### 5.5단계 — 파일명 제안

5단계 결과를 바탕으로 각 이동 대상 문서의 새 파일명을 제안한다.

#### 파일명 제안 기준 (우선순위)

| 우선순위 | 조건 | 참고 데이터 |
|---------|------|------------|
| 1 | `suggest_links` 결과가 1개 이상 | 관련 문서 상위 3개의 파일명 stem 패턴 |
| 2 | 관련 문서 없음 (threshold 미달 / GraphDB 미등록) | `vault_structure[category].doc_titles` (목적지 폴더 파일명 목록) |
| 3 | 목적지 폴더가 비어있거나 패턴 파악 불가 | 기존 파일명 유지 ("변경 불필요") |

#### 파일명 생성 규칙

참고 문서들의 파일명에서 **네이밍 패턴** (구분자, 날짜 접두사, 언어 혼용 스타일 등)을 파악해 일관성 있는 파일명을 제안한다.
현재 파일명이 이미 패턴에 맞으면 "변경 불필요"로 표시한다.

#### 파일명 제안 결과 표시 및 승인

```
파일명 제안:

#  현재 파일명                제안 파일명                       참고 기준
────────────────────────────────────────────────────────────────────────
1  앱_출시_체크리스트.md     2024_앱출시_체크리스트.md          동일폴더 패턴
2  독서노트_원칙.md           원칙_Principles_독서노트.md        관련문서 패턴
3  아이디어_메모.md           (Inbox 유지 — 건너뜀)             -
4  건강관리_루틴.md           (변경 불필요)                     -

파일명을 수정하시겠습니까? [Y: 제안 적용 / E: 개별 편집 / S: 현재 파일명 유지]
```

- **Y**: 제안된 파일명을 모두 적용해 6단계로 진행
- **E**: 개별 편집 — 번호를 입력하면 해당 파일명을 사용자가 직접 입력, 완료 후 6단계 진행
- **S**: 파일명 변경 없이 원본 파일명을 유지한 채 6단계로 진행

### 6단계 — 필요한 템플릿 로드

이동 대상 문서에서 사용된 카테고리를 중복 없이 추출한다.

`get_templates(categories)` 를 한 번 호출한다.

예: Projects, Resources 두 카테고리가 사용되면 → `get_templates(["Projects", "Resources"])`

템플릿이 없는 카테고리(Archives 등)는 원본 그대로 유지한다.

### 7단계 — 배치 단위 문서 재작성

이동 대상 문서를 **5개 단위 배치**로 나눠 처리한다.

각 배치마다:

1. `get_document_contents(batch_paths)` 를 호출해 해당 배치 문서의 full_content를 가져온다.
2. 각 문서에 대해:
   - `full_content`(원본)와 해당 카테고리의 템플릿을 참조한다.
   - 원본 내용을 최대한 보존하면서 템플릿 구조로 재작성한다.
     - 템플릿 frontmatter 필드 포함 (원본 값 우선)
     - 템플릿 섹션 구조 준수
     - **5단계에서 탐색한 관련 문서**를 적절한 위치에 `[[문서명]]`으로 연결 (폴백 시 vault_structure 기반)
   - 템플릿이 없는 카테고리(Archives 등)는 content 생략 (원본 유지).

모든 배치 처리가 완료되면 8단계로 진행한다.

### 8단계 — apply_classification 호출

5.5단계에서 확정된 파일명을 `new_filename` 필드에 포함한다.
파일명 변경이 없는 문서는 `new_filename` 필드를 생략한다.

```json
{
  "classifications": [
    {
      "path": "00_Inbox/앱_출시_체크리스트.md",
      "category": "Projects",
      "target_folder": "20_Projects/Obsidian",
      "content": "재작성된 전체 문서 내용 (관련 문서 위키링크 포함)",
      "new_filename": "2024_앱출시_체크리스트.md"
    },
    {
      "path": "00_Inbox/독서노트_원칙.md",
      "category": "Resources",
      "target_folder": "40_Resources/Documentation",
      "content": "재작성된 전체 문서 내용 (관련 문서 위키링크 포함)",
      "new_filename": "원칙_Principles_독서노트.md"
    }
  ]
}
```

### 9단계 — 완료 보고

```
✅ N개 문서 이동 완료.
커밋: abc12345 — chore: PARA classify N inbox items [SlotMachine]

변경 내역:
  20_Projects/Obsidian/ → 2024_앱출시_체크리스트.md  (관련 문서 3개 연결, 파일명 변경)
  40_Resources/Documentation/ → 원칙_Principles_독서노트.md  (관련 문서 1개 연결, 파일명 변경)

다음 단계: /slotmachine:save 로 원격 저장소에 push하세요.
```

오류가 있으면 오류 목록을 함께 출력한다.
