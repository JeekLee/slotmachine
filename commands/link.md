---
description: 문서의 관련 문서를 탐색하고 Obsidian 위키링크를 자동 제안·삽입
allowed-tools: mcp__slotmachine__suggest_links, mcp__slotmachine__apply_links
---

# /slotmachine:link — 위키링크 자동 제안 및 삽입

## 실행 순서

### 1단계 — 대상 문서 확인

사용자가 문서 경로를 제공하지 않은 경우, 현재 작업 중인 파일 또는 최근 언급된 파일을 확인한다.
경로를 특정할 수 없으면 사용자에게 vault 기준 상대 경로를 물어본다.

예: `Projects/my_project.md`

### 2단계 — 관련 문서 탐색

`suggest_links` 툴을 호출한다.

```json
{
  "path": "대상 문서 상대 경로",
  "top_k": 10,
  "threshold": 0.5
}
```

반환값:
- `candidates`: 관련 문서 후보 목록 (title / final_score / vector_score / proximity_boost / para_category / excerpt)
- `found`: 후보 수

후보가 없으면 "관련 문서를 찾지 못했습니다." 라고 알리고 중단한다.

### 3단계 — 후보 목록 표시

후보 목록을 사용자에게 표시한다.

```
"[대상 문서명]"의 관련 문서 후보 N개:

#   제목                       카테고리    점수   근거
────────────────────────────────────────────────────────
1   클린코드_요약               Resources  0.87   벡터 0.82 + 근접성 +0.05
2   아키텍처_패턴_노트           Resources  0.81   벡터 0.81 + 근접성 +0.00
3   2024_리팩토링_프로젝트       Projects   0.76   벡터 0.71 + 근접성 +0.05
...

삽입할 항목을 선택하세요.
[Enter: 전체 삽입 / 번호: 선택 삽입 (예: 1 3) / N: 취소]
```

- **Enter 또는 "전체"**: 전체 후보 삽입
- **번호 입력** (예: `1 3`): 해당 항목만 삽입
- **N**: 취소

### 4단계 — apply_links 호출

사용자가 승인한 항목의 title 목록을 전달한다.

```json
{
  "path": "대상 문서 상대 경로",
  "link_titles": ["클린코드_요약", "아키텍처_패턴_노트"]
}
```

### 5단계 — 완료 보고

```
✅ N개 위키링크 삽입 완료.
커밋: abc12345 — chore: add N wiki links to [문서명] [SlotMachine]

삽입된 링크:
  - [[클린코드_요약]]
  - [[아키텍처_패턴_노트]]

다음 단계: /slotmachine:save 로 원격 저장소에 push하세요.
```

오류가 있으면 오류 내용을 함께 출력한다.
