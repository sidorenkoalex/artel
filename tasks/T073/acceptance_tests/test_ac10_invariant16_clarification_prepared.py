"""AC-10 (tasks/T073/SPEC.md): в артефактах задачи подготовлен текст
уточнения инварианта 16 («история переживает задачу, не эпоху») для
последующего принятия Оператором отдельным ADR; сама задача не создаёт
и не правит файл в `docs/adr/`.

Критерий несёт два самостоятельных утверждения:

1. «текст уточнения ... подготовлен» — см. маркер `manual` ниже:
   ПРИСУТСТВИЕ каких-то слов про «инвариант 16» в SPEC/PLAN/REVIEW можно
   найти grep'ом (и это было бы тавтологией — прошло бы при любой
   болтовне на эту тему), но ДОСТАТОЧНОСТЬ текста как основы для ADR —
   снимает ли он видимое противоречие «инвариант 16 не трогает
   .artel/logs/» vs «команда prune трогает» — решает Оператор при
   принятии ADR (сам SPEC формулирует это правом Оператора, не
   проверкой кода): «Принятие ADR с этим текстом — право Оператора,
   вне объёма этой задачи».
2. «сама задача не создаёт и не правит файл в docs/adr/» — тест ниже:
   реальный дифф текущей ветки относительно `main`, тем же приёмом, что
   `tasks/T063/acceptance_tests/test_retro_suite_and_docs_untouched.py`
   AC-5 и `tasks/T049/acceptance_tests/test_ac6_ac7_regression_and_
   protected_paths.py` AC-7.
"""

# AC-10: manual — «текст уточнения инварианта 16 подготовлен (и годится
# как основа ADR)» проверяет Оператор при чтении артефактов задачи на
# приёмке/при рассмотрении ADR: unittest не умеет судить, снимает ли
# конкретная формулировка видимое противоречие с текущим текстом
# инварианта 16 (docs/invariants.md, пункт 16) — это ровно то решение,
# которое SPEC называет правом Оператора («Принятие ADR ... — право
# Оператора, вне объёма этой задачи»). Автоматическая часть критерия
# («docs/adr/ не создан и не правлен этой задачей») — тест ниже.

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class AdrDirUntouchedTest(unittest.TestCase):

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac10_branch_diff_does_not_touch_docs_adr(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed if p.startswith("docs/adr/")]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main создаёт/правит файл "
            f"в docs/adr/: {offending} — SPEC T073 требование 4/AC-10 "
            f"явно исключает это из объёма задачи (принятие ADR — право "
            f"Оператора)")


if __name__ == "__main__":
    unittest.main()
