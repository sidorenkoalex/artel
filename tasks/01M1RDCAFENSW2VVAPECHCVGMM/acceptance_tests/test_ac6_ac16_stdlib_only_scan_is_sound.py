"""AC-6, AC-16 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md, требования 2/3):
состоятельность правила «только стандартная библиотека» — пропускает
сегодняшнее дерево репозитория (AC-6) и ловит подсаженный сторонний
импорт на синтетическом дереве, не трогая чистое (AC-16).

Зелёный с рождения: `_util.find_foreign_imports` — код этой же
приёмочной планки (независимая реализация правила требования 3, по его
буквальной формулировке), не код задачи; его поведение не зависит от
того, реализован ли инвариант в `tests/test_invariants.py`, — тем же
приёмом, что `_util.find_dns_addresses` в
tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/
test_ac6_ac10_dns_scan_structural_logic.py.
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from _util import find_foreign_imports  # noqa: E402


class ReferenceScanIsSoundTest(unittest.TestCase):

    def test_ac6_current_tree_has_no_foreign_imports(self):
        """Требование 3/AC-6: сегодняшнее дерево `orchestrator/`,
        `scripts/`, `tests/` не содержит сторонних импортов — прогон
        независимой копии правила ПРЯМО СЕЙЧАС, на настоящем дереве
        репозитория, без исключений (список манифеста пуст, AC-3).

        Ловит мутацию: в дереве репозитория появился настоящий сторонний
        импорт (например, кто-то по ошибке добавил `import requests` в
        `orchestrator/`) — эта строка перестанет быть пустой уже сейчас,
        до всякой реализации задачи, и `assertEqual([], ...)` откажет.
        """
        violations = find_foreign_imports(REPO_ROOT)
        self.assertEqual(
            [], violations,
            f"в дереве репозитория найдены импорты вне stdlib/пакетов "
            f"репозитория: {violations}")

    def test_ac16_planted_foreign_import_is_caught_on_a_synthetic_tree(self):
        """AC-16: временное дерево с подсаженным сторонним импортом —
        падение (обнаружение); чистое временное дерево — нет.

        Ловит мутацию: правило проверяет модуль целиком без разбиения на
        вершину пути (`import foo.bar` не сведён к `foo`), либо не видит
        импорт под `if`/`try` (нужен `ast.walk`, не только `tree.body`)
        — синтетическая фикстура ниже кладёт нарушение простым `import`
        верхнего уровня, а чистая — только stdlib и относительный
        внутрипакетный импорт.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orchestrator").mkdir()
            (root / "orchestrator" / "dirty.py").write_text(
                "import totally_fake_third_party_package_xyz\n",
                encoding="utf-8")

            dirty_violations = find_foreign_imports(root)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orchestrator").mkdir()
            (root / "orchestrator" / "clean.py").write_text(
                "import os\nfrom . import config\n", encoding="utf-8")

            clean_violations = find_foreign_imports(root)

        self.assertTrue(
            dirty_violations,
            "подсаженный сторонний импорт на синтетическом дереве не "
            "пойман")
        self.assertEqual(
            [], clean_violations,
            f"чистое синтетическое дерево ошибочно помечено нарушением: "
            f"{clean_violations}")


if __name__ == "__main__":
    unittest.main()
