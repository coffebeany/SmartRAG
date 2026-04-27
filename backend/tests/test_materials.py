from app.models.entities import MaterialFile
from app.services.materials import active_snapshot, file_ext, safe_filename, supported_file_exts


def test_safe_filename_removes_paths_and_unsafe_chars() -> None:
    assert safe_filename("../运维 报告?.pdf") == "运维_报告_.pdf"
    assert safe_filename("") == "uploaded_file"


def test_file_ext_is_normalized() -> None:
    assert file_ext("Report.PDF") == ".pdf"
    assert file_ext("README") == ""


def test_active_snapshot_only_contains_active_files() -> None:
    active = MaterialFile(file_id="b", status="active")
    removed = MaterialFile(file_id="a", status="removed")
    assert active_snapshot([removed, active]) == ["b"]


def test_supported_file_exts_come_from_parser_registry() -> None:
    assert ".pdf" in supported_file_exts()
    assert ".docx" in supported_file_exts()
    assert ".exe" not in supported_file_exts()
