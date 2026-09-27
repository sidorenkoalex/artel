"""AC-12 — 01M3GKJ84XM5QPC6TK5EE307Q9: недоказуемая аддитивность
эскалирует как прежде (нет базовой стадии; git не ответил успешно).

Источник — SPEC.md, «Критерии приёмки»:

AC-12. Аддитивность недоказуема — эскалация как прежде: файл добавлен
обеими сторонами (базовой стадии нет) и случай, когда git не ответил
успешно на сверку стадий или на слияние, дают тот же исход, что AC-9.

Сбой git вносится подменой `subprocess.run` (единственный настоящий
запуск процесса под всеми git-вызовами пульта — и `gitcmd.git`/
`gitcmd.in_repo`, и прямой запуск, если реализация выберет его):
ненулевым кодом отвечают ровно те примитивы, которыми SPEC требование 5
предписывает доказывать аддитивность и сливать (`git diff --no-index`,
`git merge-file`, чтение стадий индекса `:1:`/`:2:`/`:3:`); всё
остальное — merge, `merge --abort`, чтение конфликтных файлов — идёт
настоящим git.

Красен до реализации: сегодня сверки стадий нет вовсе, и подменённый
`subprocess.run` не перехватывает ни одного вызова — ассерт «хотя бы
один примитив сверки был позван» падает, честно сообщая, что fail-closed
проверять пока не на чем. Сценарий «файл добавлен обеими сторонами»
сегодня эскалирует сам по себе (второй метод зелёный с рождения — он
фиксирует поведение, которое обязано пережить задачу).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

ADDED_BY_BOTH = "docs/novyy-dokument.md"


class UndecidableAdditivityEscalatesTest(_sandbox.AdditivePullSandbox):

    def test_ac12_file_added_by_both_sides_escalates(self):
        """Документа нет в базе слияния вовсе — обе стороны завели его
        сами, с разным содержимым: «относительно базы» не определено, и
        подтяжка эскалирует прежним путём.

        Ловит мутацию: отсутствующая стадия `:1:` трактуется как пустая
        база (обе стороны «только добавили строки» относительно пустоты)
        — пульт склеил бы два независимых документа в один, выдав это за
        разрешённый аддитивный конфликт.
        """
        self.seed_base({_sandbox.DOC_A: _sandbox.BASE_LINES})
        self.seed_branch_side({ADDED_BY_BOTH: ["- версия ветки задачи"]})
        self.seed_main_side({ADDED_BY_BOTH: ["- версия main"]})

        outcome = self.evaluate()

        self.assert_escalated_as_before(outcome, [ADDED_BY_BOTH])

    def test_ac12_git_failure_on_additivity_check_escalates(self):
        """Тот же аддитивный конфликт, что сливается в AC-6, но каждый
        примитив сверки стадий и union-слияния отвечает ненулевым кодом:
        исход — прежняя эскалация, не «слили на всякий случай».

        Ловит мутацию: код возврата git не проверяется (или пустой
        `stdout` сверки читается как «удалённых строк ноль») — сбой
        сверки прошёл бы за доказанную аддитивность, и пульт склеил бы
        файлы вслепую; fail-closed, который требует SPEC требование 8,
        перестал бы работать.
        """
        self.seed_additive_conflict(_sandbox.DOC_A)

        outcome, probes = self.evaluate_with_broken_git()

        self.assertTrue(
            probes,
            "ни один примитив сверки аддитивности/union-слияния не был "
            "позван — проверить fail-closed не на чем (SPEC требование 5 "
            "называет `git diff --no-index --numstat`, `git merge-file "
            "-p --union` и стадии индекса :1:/:2:/:3:)")
        self.assert_escalated_as_before(outcome, [_sandbox.DOC_A])


if __name__ == "__main__":
    unittest.main()
