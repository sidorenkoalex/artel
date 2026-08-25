"""Приёмочные тесты T034: AC-12 — шапка-маркер у модулей инварианта 28.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 9
(ревью T031): `tests/test_gitcmd_branch_reads.py` и
`tasks/T031/acceptance_tests/test_branch_correct_reads.py` кодируют
инвариант 28 реестра (docs/invariants.md, строка 28), но их докстринг
модуля не несёт шапки-маркера «НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002)» с явным
номером — по образцу `tests/test_acceptance_tests_flow.py`
(«НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): ... инварианты 26 и 27 реестра»).

Разбор — статический (`ast.get_docstring`), без импорта файлов: те же
основания, что у `scripts/guard.py` (докстринг модуля) — содержимое
чужого дерева здесь не исполняется.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

MARKER = "НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002)"
INVARIANT_28 = re.compile(r"\b28\b")

FILES = (
    "tests/test_gitcmd_branch_reads.py",
    "tasks/T031/acceptance_tests/test_branch_correct_reads.py",
)


def module_docstring(rel_path: str) -> str:
    path = REPO_ROOT / rel_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
    return ast.get_docstring(tree) or ""


class Ac12Invariant28MarkerTest(unittest.TestCase):
    """AC-12: докстринг модуля несёт маркер и номер 28."""

    def test_ac12_both_modules_carry_the_marker_and_the_invariant_number(self):
        missing = []
        for rel_path in FILES:
            doc = module_docstring(rel_path)
            has_marker = MARKER in doc
            has_number = bool(INVARIANT_28.search(doc))
            if not (has_marker and has_number):
                missing.append((rel_path, has_marker, has_number))

        self.assertEqual(
            missing, [],
            f"докстринг модуля без маркера/номера 28 "
            f"(файл, есть_маркер, есть_28): {missing}")

    def test_ac12_marker_and_number_appear_together_not_far_apart(self):
        """Маркер называет ИМЕННО инвариант 28, а не просто содержит обе
        подстроки где-то порознь: номер — в пределах того же абзаца."""
        for rel_path in FILES:
            with self.subTest(файл=rel_path):
                doc = module_docstring(rel_path)
                idx = doc.find(MARKER)
                self.assertNotEqual(idx, -1, f"{rel_path}: маркер не найден")
                paragraph_end = doc.find("\n\n", idx)
                if paragraph_end == -1:
                    paragraph_end = len(doc)
                paragraph = doc[idx:paragraph_end]
                self.assertRegex(
                    paragraph, INVARIANT_28,
                    f"{rel_path}: номер 28 не упомянут в абзаце с маркером")


if __name__ == "__main__":
    unittest.main()
