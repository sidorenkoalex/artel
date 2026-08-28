"""AC-3 (tasks/T067/SPEC.md): конфликт подтяжки, где конфликтующие файлы
— `docs/codebase-map.md` и хотя бы один другой файл: оркестратор ведёт
себя как до этой задачи — `git merge --abort`, задача переходит в
`escalated` с диагностикой конфликта, ветка задачи остаётся в состоянии
до подтяжки, main не изменяется.

Требование 4 SPEC называет этот путь (карта + другой файл, либо карта
отсутствует вовсе) «поведением прежним (T051/T052 байт-в-байт)» —
буквально тем же кодом, что уже отрабатывает `_pull_main_or_escalate`
сегодня: сама диагностика («конфликт подтяжки …») не меняется этой
задачей, только РЕШЕНИЕ о том, эскалировать или разрешить самому. Тест
поэтому не пришивается к конкретному тексту перечня файлов (то, что
реально уходит в `git merge`, в stdout, а не в stderr, откуда сегодня
читает `_pull_main_or_escalate` — эмпирически проверено при написании
теста) — только к наблюдаемому исходу: эскалация, откат, сохранность
обеих веток.

Зелёный с рождения: сценарий «конфликт по нескольким файлам, включая
карту» сегодня (T051) уже безусловно эскалирует — этот тест фиксирует
существующее поведение как планку, которую T067 не имеет права сузить
(ADR-0002).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MapConflictRealGitTest, PASSING_ACCEPTANCE_TEST  # noqa: E402
from orchestrator import fsm  # noqa: E402


class MapPlusOtherFileConflictEscalatesTest(MapConflictRealGitTest):

    def test_ac3_map_plus_shared_txt_conflict_escalates_and_aborts(self):
        wt = self.make_worktree()
        self.advance_from_in_dev(wt)
        self.diverge_map_only(wt)
        self.diverge_shared_txt(wt)
        pre_branch_head = self.branch_head()
        pre_main_head = self.main_head()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "конфликт по нескольким файлам, включая карту, обязан "
            "эскалировать — не только конфликт-по-карте разрешается сам")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower(),
                     "эскалация обязана нести диагностику конфликта")

        self.assertEqual(self.branch_head(), pre_branch_head,
                         "ветка задачи обязана остаться в состоянии до "
                         "подтяжки (merge отменён)")
        self.assertEqual(self.main_head(), pre_main_head,
                         "main не должен измениться")
        self.assert_no_merge_in_progress(wt)


if __name__ == "__main__":
    import unittest
    unittest.main()
