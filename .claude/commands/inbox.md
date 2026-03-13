---
description: INBOX 문서를 PARA 자동 분류하고 사용자 승인 후 파일 이동
allowed-tools: mcp__slotmachine__classify_inbox, mcp__slotmachine__apply_classification
---

# /slotmachine:inbox — INBOX PARA 자동 분류

## 실행 순서

### 1단계 — 문서 로드

`classify_inbox` 툴을 호출해 INBOX 문서 목록을 가져온다.

문서가 없으면 "INBOX가 비어 있습니다." 라고 알리고 중단한다.

### 2단계 — PARA 분류

각 문서의 title, tags, excerpt를 바탕으로 아래 PARA 기준에 따라 분류한다.

| 카테고리 | 기준 |
|----------|------|
| Projects | 마감 기한이 있거나 현재 진행 중인 구체적 작업 |
| Areas | 지속적으로 관리가 필요한 책임 영역 (건강, 재무, 커리어 등) |
| Resources | 미래에 참고할 수 있는 자료, 아티클, 책 요약 등 |
| Archives | 완료되었거나 더 이상 활성화되지 않은 항목 |
| Inbox | 내용이 모호해 판단하기 어려운 경우 (그대로 유지) |

### 3단계 — 결과 표시

아래 형식으로 분류 결과를 테이블로 출력한다.

```
INBOX에서 N개의 문서를 발견했습니다.

#  문서명                    분류          확신도  근거
─────────────────────────────────────────────────────
1  앱_출시_체크리스트.md     Projects      높음    마감 기한과 구체적 태스크 포함
2  독서노트_원칙.md           Resources     높음    참고 자료성 내용
3  아이디어_메모.md           Inbox         낮음    내용이 모호해 판단 보류

M개 자동 분류 완료. (Inbox 유지: K개)

이동할 문서 목록:
  Projects → 앱_출시_체크리스트.md
  Resources → 독서노트_원칙.md

승인하시겠습니까? [Y: 전체 승인 / 번호: 해당 문서 카테고리 변경 / N: 취소]
```

확신도 기준:
- 높음: 판단 근거가 명확한 경우
- 중간: 어느 정도 근거가 있으나 다른 카테고리도 가능한 경우
- 낮음: 내용이 모호하거나 판단이 어려운 경우 → Inbox 유지 권장

### 4단계 — 사용자 승인 처리

- **Y 입력**: `apply_classification` 툴 호출 (category가 Inbox인 항목 제외)
- **번호 입력**: 해당 문서의 카테고리를 사용자가 지정한 값으로 변경 후 재확인
- **N 입력**: "분류를 취소했습니다." 알리고 중단

### 5단계 — 완료 보고

```
✅ N개 문서 이동 완료.
커밋: abc12345 — chore: PARA classify N inbox items [SlotMachine]

변경 내역:
  Projects/ → 앱_출시_체크리스트.md
  Resources/ → 독서노트_원칙.md

다음 단계: /slotmachine:save 로 원격 저장소에 push하세요.
```

오류가 있으면 오류 목록을 함께 출력한다.
