"""AC-2, AC-3 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md, требование 1):
список исключений манифеста несёт три записи с причиной, и инвариант
«только стандартная библиотека» (S1, 01M1RDCAFENSW2VVAPECHCVGMM) их
пропускает, по-прежнему ловя посторонние импорты вне списка.

Красен до реализации: `orchestrator.stack` (ветка S1) ещё не смержена в
этом дереве — импорт падает `ModuleNotFoundError` для обоих тестов.

`_util.find_foreign_imports` — точная копия сканера
`tests/test_invariants.py::StdlibOnlyImportsInvariantTest._foreign_imports`
(ветка S1) на момент написания этой планки: AC-3 испытывает СОСТОЯТЕЛЬНОСТЬ
уже одобренной, СМЕЖНОЙ задачей S1 механики на конкретных новых записях
этой задачи, не переизобретает саму механику (её приёмочно испытала S1).
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from _util import find_foreign_imports  # noqa: E402

# Пакет pip -> допустимые написания ИМПОРТИРУЕМОГО имени модуля: хайфен
# в имени пакета pip никогда не бывает валидным идентификатором Python
# (`import pytest-timeout` — SyntaxError), поэтому запись манифеста
# обязана нести один из вариантов справа, не буквальное имя пакета слева.
IMPORT_NAME_CANDIDATES = {
    "pytest": {"pytest"},
    "pytest-timeout": {"pytest_timeout", "pytest-timeout"},
    "pytest-xdist": {"pytest_xdist", "pytest-xdist", "xdist"},
}


def _exceptions_by_package():
    """{пакет pip: (запись_имени, причина)} — сверка не по буквальному
    написанию (не зафиксировано SPEC однозначно), а по СМЫСЛУ: находит,
    какая запись THIRD_PARTY_EXCEPTIONS относится к какому пакету, среди
    правдоподобных написаний импортируемого имени."""
    from orchestrator import stack  # noqa: E402
    found = {}
    for name, reason in stack.THIRD_PARTY_EXCEPTIONS:
        for package, candidates in IMPORT_NAME_CANDIDATES.items():
            if name in candidates or name.replace("-", "_") in candidates:
                found[package] = (name, reason)
    return found


class ManifestExceptionsTest(unittest.TestCase):

    def test_ac2_each_of_the_three_packages_is_declared_with_a_reason(self):
        """Требование 1/AC-2: `pytest`, `pytest-timeout`, `pytest-xdist`
        — каждый присутствует в THIRD_PARTY_EXCEPTIONS с непустой
        причиной.

        Ловит мутацию: один из трёх пакетов не добавлен в список
        исключений (например разработчик забыл `pytest-xdist`) —
        `assertIn` на найденных пакетах откажет; либо запись добавлена
        БЕЗ причины (пустая строка вторым элементом пары) —
        `assertTrue(reason.strip())` откажет.
        """
        found = _exceptions_by_package()

        for package in IMPORT_NAME_CANDIDATES:
            self.assertIn(
                package, found,
                f"{package} не найден в orchestrator.stack."
                f"THIRD_PARTY_EXCEPTIONS (искались написания "
                f"{IMPORT_NAME_CANDIDATES[package]}): {found}")
            _name, reason = found[package]
            self.assertTrue(
                reason.strip(),
                f"запись исключения для {package} ({_name!r}) не несёт "
                f"причины")

    def test_ac3_scanner_exempts_declared_names_but_still_catches_others(self):
        """Требование 1/AC-3: инвариант «только стандартная библиотека»
        (`tests/test_invariants.py`, S1) — пропускает `import <имя из
        THIRD_PARTY_EXCEPTIONS>` на синтетическом дереве, но по-прежнему
        падает на импорте пакета, которого в списке нет.

        Ловит мутацию: разработчик расширил THIRD_PARTY_EXCEPTIONS новой
        записью, чьё имя НЕ совпадает буквально с тем, что реально
        встретится в `import`-операторе (например записал
        `"pytest-timeout"` с дефисом вместо `"pytest_timeout"`) —
        синтетический файл с `import pytest_timeout` по-прежнему попал бы
        в нарушения, `assertEqual([], ...)` для «чистого» дерева откажет.
        """
        from orchestrator import stack  # noqa: E402

        exceptions = tuple(name for name, _reason in stack.THIRD_PARTY_EXCEPTIONS)

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orchestrator").mkdir()
            body = "\n".join(f"import {name}" for name in exceptions) + "\n"
            (root / "orchestrator" / "uses_exceptions.py").write_text(
                body, encoding="utf-8")

            exempted_violations = find_foreign_imports(
                root, exceptions=exceptions)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orchestrator").mkdir()
            (root / "orchestrator" / "dirty.py").write_text(
                "import totally_fake_third_party_package_xyz\n",
                encoding="utf-8")

            still_caught = find_foreign_imports(root, exceptions=exceptions)

        self.assertEqual(
            [], exempted_violations,
            f"дерево, импортирующее ровно объявленные исключения "
            f"({exceptions}), ошибочно помечено нарушением: "
            f"{exempted_violations}")
        self.assertTrue(
            still_caught,
            "импорт пакета вне списка исключений не пойман сканером "
            "даже при непустом списке исключений")


if __name__ == "__main__":
    unittest.main()
