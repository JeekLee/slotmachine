"""PARA 카테고리 추론 유틸리티.

파일 경로 기반으로 PARA 카테고리를 결정한다.
full_sync, incremental_sync에서 공통으로 사용한다.
"""
from __future__ import annotations

from pathlib import Path


def resolve_para_category(
    path: Path,
    vault_path: Path,
    para_folder_map: dict[str, str],
    inbox_folder: str = "INBOX",
) -> str:
    """파일 경로에서 PARA 카테고리를 추론한다.

    vault 기준 상대 경로의 최상위 폴더를 para_folder_map과 비교해 카테고리를 반환한다.

    Args:
        path: 파일 절대 경로
        vault_path: vault 루트 절대 경로
        para_folder_map: {"Projects": "20_Projects", "Areas": "30_Areas", ...}
        inbox_folder: INBOX 폴더명 (예: "00_Inbox")
    Returns:
        "Projects" / "Areas" / "Resources" / "Archives" / "Inbox" 중 하나.
        매칭되지 않으면 "Inbox" 반환.
    """
    try:
        rel = path.relative_to(vault_path)
    except ValueError:
        return "Inbox"

    top_folder = rel.parts[0] if rel.parts else ""

    if top_folder == inbox_folder:
        return "Inbox"

    # para_folder_map의 값(폴더명) → 키(카테고리) 역방향 매핑
    folder_to_category = {folder: category for category, folder in para_folder_map.items()}
    return folder_to_category.get(top_folder, "Inbox")
