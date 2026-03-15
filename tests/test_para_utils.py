"""para_utils.resolve_para_category 단위 테스트."""
from pathlib import Path

import pytest

from slotmachine.sync.para_utils import resolve_para_category

PARA_MAP = {
    "Projects": "20_Projects",
    "Areas": "30_Areas",
    "Resources": "40_Resources",
    "Archives": "50_Archives",
}
INBOX = "00_Inbox"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path


class TestResolveParaCategory:
    def test_projects_folder(self, vault):
        path = vault / "20_Projects" / "my_project.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Projects"

    def test_areas_folder(self, vault):
        path = vault / "30_Areas" / "health.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Areas"

    def test_resources_folder(self, vault):
        path = vault / "40_Resources" / "book_summary.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Resources"

    def test_archives_folder(self, vault):
        path = vault / "50_Archives" / "old_project.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Archives"

    def test_inbox_folder(self, vault):
        path = vault / "00_Inbox" / "new_note.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Inbox"

    def test_nested_path_uses_top_folder(self, vault):
        path = vault / "20_Projects" / "SubTeam" / "Rocky" / "task.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Projects"

    def test_unknown_folder_returns_inbox(self, vault):
        path = vault / "90_Settings" / "config.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Inbox"

    def test_root_level_file_returns_inbox(self, vault):
        path = vault / "readme.md"
        assert resolve_para_category(path, vault, PARA_MAP, INBOX) == "Inbox"

    def test_path_outside_vault_returns_inbox(self, vault, tmp_path):
        other = tmp_path / "other" / "file.md"
        assert resolve_para_category(other, vault / "sub", PARA_MAP, INBOX) == "Inbox"

    def test_custom_folder_names(self, vault):
        custom_map = {"Projects": "Projects", "Areas": "Areas",
                      "Resources": "Resources", "Archives": "Archives"}
        path = vault / "Projects" / "task.md"
        assert resolve_para_category(path, vault, custom_map, "INBOX") == "Projects"

    def test_default_inbox_folder_name(self, vault):
        """inbox_folder 기본값이 "INBOX"임을 확인한다."""
        path = vault / "INBOX" / "note.md"
        assert resolve_para_category(path, vault, PARA_MAP) == "Inbox"
