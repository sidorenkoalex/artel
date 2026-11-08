"""Метка размера (ADR-0032 п. 2): модули песочниц при `sandbox_sources=None` — из `config.ROOT`, отбор путей модулей песочниц, нестроковое значение подполя `size_marks`.

Свойства сверх долгоживущих файлов задачи 01M6XHJH6EJ8D0BR5PRNGZAY8C:
исходники — строками в памяти и файлами во временном корне `tmp_root`.
"""
import pytest

from orchestrator import config, targets, test_lint
from scripts import guard

pytestmark = pytest.mark.size("small")

LABEL = "tests/test_01aaaaaaaaaaaaaaaaaaaaaaaa_sample.py"
TASK = "01AAAAAAAAAAAAAAAAAAAAAAAA"


def sample(base: str) -> str:
    return "\n".join([
        '"""Образец долгоживущего файла.', "",
        "Группа: " + guard.GROUP_LONG_LIVED, '"""', "import pytest", "",
        f"from tests.sandbox import {base}", "",
        "pytestmark = pytest.mark.size(\"small\")", "", "",
        f"class CaseTest({base}):", "",
        "    def test_ac1_sample(self):",
        '        """Образец.', "",
        "        Ловит " + "мутацию: образец.", '        """',
        "        assert self is not None", ""])


def write(root, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_none_sources_read_from_pult_root(tmp_root):
    """`sandbox_sources=None` — модули песочниц `config.ROOT`: подкласс корня из `tests/<имя>_sandbox.py` корня распознан, класс из файла не песочниц — нет.

    Сценарий: во временном `config.ROOT` — `tests/sandbox.py` с
    `RealGitSandbox`, `tests/extra_sandbox.py` с `ExtraBox(RealGitSandbox)`,
    `tests/helpers.py` с `HelperBox(RealGitSandbox)`. Малый файл,
    наследующий `ExtraBox`, — строка «размер —» с `ExtraBox`; наследующий
    `HelperBox` — без строк «размер —».

    Ловит мутацию: при `None` guard передаёт пустой перечень либо читает
    не `config.ROOT`; отбор модулей песочниц берёт любой `tests/*.py`.
    """
    root = config.ROOT
    write(root, "tests/sandbox.py",
          "class RealGitSandbox:\n    pass\n")
    write(root, "tests/extra_sandbox.py",
          "from tests.sandbox import RealGitSandbox\n\n\n"
          "class ExtraBox(RealGitSandbox):\n    pass\n")
    write(root, "tests/helpers.py",
          "from tests.sandbox import RealGitSandbox\n\n\n"
          "class HelperBox(RealGitSandbox):\n    pass\n")
    found = [e for e in guard.long_lived_errors_from_files(
        [(LABEL, sample("ExtraBox"))], TASK, size_marks=True)
        if "размер —" in e]
    assert any("ExtraBox" in e for e in found), found
    found = [e for e in guard.long_lived_errors_from_files(
        [(LABEL, sample("HelperBox"))], TASK, size_marks=True)
        if "размер —" in e]
    assert found == [], found


@pytest.mark.parametrize("rel, expected", [
    ("tests/sandbox.py", True),
    ("tests/outcome_gate_sandbox.py", True),
    ("tests/sandbox_helpers.py", False),
    ("tests/test_sandbox.py", True),
    ("tests/sub/sandbox.py", False),
    ("orchestrator/sandbox.py", False),
])
def test_sandbox_source_path(rel, expected):
    """Путь модуля песочниц — `tests/sandbox.py` и `tests/*_sandbox.py` без подкаталогов.

    Сценарий: каждый путь перечня сверяется `is_sandbox_source_path`.

    Ловит мутацию: шаблон пути принимает подкаталог `tests/`, иной корень
    или имя, лишь начинающееся с `sandbox`.
    """
    assert test_lint.is_sandbox_source_path(rel) is expected


@pytest.mark.parametrize("value", [True, 1, ["required"]])
def test_non_string_size_marks_named(tmp_root, value):
    """Нестроковое значение `test_profile.size_marks` — отказ, называющий подполе, значение и ожидаемое `required`.

    Сценарий: запись проекта с профилем тестов и `size_marks` — `True`,
    `1` или список; `targets.check` — `TargetsError` с
    `test_profile.size_marks` и `required`.

    Ловит мутацию: значение проверяется общим видом строки («не непустая
    строка») без ожидаемого `required` либо нестроковое значение проходит.
    """
    entry = {"forge": "github", "url": "file:///nonexistent/sizeval",
             "base": "main", "token_slot": "sizeval-token", "no_paths": [],
             "project_skills": [], "merge_gate": "operator",
             "test_profile": {"command": ["python3", "-m", "pytest"],
                              "long_lived_dir": "tests",
                              "long_lived_name": "test_<id>_<name>.py",
                              "weakening_scope": ["tests/**/*.py"],
                              "mutation_claim_scope": ["tests/test_*.py"],
                              "size_marks": value}}
    with pytest.raises(targets.TargetsError) as caught:
        targets.check("sizeval", entry)
    text = str(caught.value)
    assert "test_profile.size_marks" in text, text
    assert targets.SIZE_MARKS_REQUIRED in text, text
