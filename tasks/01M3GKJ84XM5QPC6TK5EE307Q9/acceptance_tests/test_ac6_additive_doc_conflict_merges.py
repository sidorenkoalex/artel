"""AC-6 — 01M3GKJ84XM5QPC6TK5EE307Q9: конфликт по двум аддитивным
документам подтяжка сливает сама, не теряя ни одной строки.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Подтяжка main, конфликтующая по двум документам (`docs/*.md`),
где каждая сторона только добавила строки, завершает merge без
эскалации: задача остаётся в состоянии, из которого шла подтяжка, а в
каждом из двух файлов присутствуют ВСЕ строки базы слияния и ВСЕ добавки
обеих сторон (ни одна строка не потеряна).

Проверка идёт против НАСТОЯЩЕГО git (`tests/sandbox.py::RealGitSandbox`,
требование 11 SPEC): аддитивность читается со стадий индекса, которые
оставляет неудачный `git merge`, — заглушкой это не изобразить.

Красен до реализации: сегодня `pull._handle_merge_failure`
авторазрешает ровно один набор конфликтов — `[docs/codebase-map.md]`;
любой другой уходит в `git merge --abort` и `store.set_state(...,
"escalated")`. Задача окажется в `escalated`, а файлы — в состоянии
базы, без добавок сторон.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import pull  # noqa: E402


class AdditiveDocConflictMergesTest(_sandbox.AdditivePullSandbox):

    def setUp(self):
        super().setUp()
        self.seed_additive_conflict(_sandbox.DOC_A, _sandbox.DOC_B)

    def test_ac6_two_additive_docs_merge_without_escalation(self):
        """Подтяжка main, конфликтующая по двум документам, где обе
        стороны только дописали строки, возвращает `Pulled`, оставляет
        задачу в `in_dev` и не оставляет незавершённого merge.

        Ловит мутацию: условие авторазрешения расширено на документы, но
        осталось «ровно один файл» (`len(files) == 1`) — набор из двух
        документов снова эскалировал бы, и состояние стало бы
        `escalated`.
        """
        outcome = self.evaluate()

        self.assertIsInstance(
            outcome, pull.Pulled,
            f"аддитивный конфликт двух документов обязан слиться "
            f"подтяжкой, получено: {outcome!r}")
        self.assertEqual(
            "in_dev", self.state(),
            "задача обязана остаться в состоянии, из которого шла подтяжка")
        self.assertFalse(self.merge_in_progress(),
                         "merge обязан быть завершён, а не оставлен "
                         "незакрытым в worktree")
        self.assertEqual("", self.worktree_dirty(),
                         "после слияния рабочее дерево обязано быть чистым")

    def test_ac6_no_line_of_either_side_is_lost(self):
        """В каждом из двух файлов присутствуют все три строки базы
        слияния, добавка main и добавка ветки, и не осталось маркеров
        конфликта.

        Ловит мутацию: слияние написано собственным склейщиком «база +
        хвост одной стороны» вместо `git merge-file -p --union` — добавка
        второй стороны (или сама база) потерялась бы молча, merge при
        этом завершился бы успешно.
        """
        self.evaluate()

        self.assert_all_lines_present(_sandbox.DOC_A)
        self.assert_all_lines_present(_sandbox.DOC_B)


if __name__ == "__main__":
    unittest.main()
