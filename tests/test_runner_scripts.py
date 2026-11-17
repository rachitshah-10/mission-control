import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_start_and_test_scripts_exist_and_are_executable():
    start_script = ROOT / "start.sh"
    test_script = ROOT / "test.sh"

    assert start_script.is_file(), "start.sh is missing"
    assert test_script.is_file(), "test.sh is missing"
    assert os.access(start_script, os.X_OK), "start.sh must be executable"
    assert os.access(test_script, os.X_OK), "test.sh must be executable"


def test_readme_documents_single_start_and_test_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "./start.sh" in readme
    assert "./test.sh" in readme
    assert "TOOL_CHOICES.md" in readme
