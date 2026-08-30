"""AC-11 (tasks/T073/SPEC.md): существующие тесты, включая
`tests/test_invariants.py`, после изменений остаются зелёными;
`docs/invariants.md` и тексты инвариантов этой задачей не отредактированы.

Критерий несёт два самостоятельных утверждения:

1. «существующие тесты остаются зелёными» — см. маркер `skip` ниже.
2. «docs/invariants.md ... не отредактированы» — тест ниже: реальный
   дифф ветки относительно `main`, тем же приёмом, что и
   `tasks/T063/acceptance_tests/test_retro_suite_and_docs_untouched.py`
   AC-5 и `tasks/T049/acceptance_tests/test_ac6_ac7_regression_and_
   protected_paths.py` AC-7. `tests/test_invariants.py` — та же
   проверка: «тексты инвариантов» (docs/invariants.md) относятся и к
   его тестовому коду, раз задача не вправе ослаблять неослабляемые
   тесты (скил conventions-core, ADR-0002).
"""

# AC-11: skip — «существующий набор тестов (tests/) остаётся зелёным»
# уже исполняется штатным CI-гейтом (`.github/workflows/ci.yml`, джоб
# `python`, `unittest discover -s tests -v`) на каждый коммит ветки
# задачи и требуется `merge_gate` (orchestrator/fsm.py, cmd_approve при
# state == "merge_gate") — тот же довод, что и в tasks/T049/
# acceptance_tests/test_ac6_ac7_regression_and_protected_paths.py (AC-6
# там) и tasks/T064/acceptance_tests/test_ac4_existing_checks_not_
# weakened.py (AC-4 там). Повторный subprocess-прогон здесь ловил бы
# окружение машины разработчика, а не дефект этой задачи. Вторая
# половина критерия («docs/invariants.md/tests/test_invariants.py не
# отредактированы») покрыта тестом ниже.

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

PROTECTED_FILES = ("docs/invariants.md", "tests/test_invariants.py")


class InvariantsUntouchedTest(unittest.TestCase):

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac11_branch_diff_does_not_touch_invariants_doc_or_its_tests(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed if p in PROTECTED_FILES]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main правит {offending} "
            f"(SPEC T073, AC-11: инварианты и их тесты этой задачей не "
            f"ослабляются и не правятся, ADR-0002)")


if __name__ == "__main__":
    unittest.main()
