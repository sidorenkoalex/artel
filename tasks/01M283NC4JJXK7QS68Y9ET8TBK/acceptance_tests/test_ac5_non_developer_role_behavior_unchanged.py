"""Приёмочный тест AC-5 — 01M283NC4JJXK7QS68Y9ET8TBK.

Источник — tasks/01M283NC4JJXK7QS68Y9ET8TBK/SPEC.md, «Критерии приёмки»:

AC-5. Шаг роли без мандата кода (не `developer`) с `rc=0` и грязным
деревом вне `tasks/<id>/` — прежнее поведение сохранено: откат WIP вне
мандата, как до этой задачи.

«Как до этой задачи» — проверено чтением `orchestrator/runner.py`/
`orchestrator/checkpoint.py` на голове ветки задачи ДО реализации:
`_discard_out_of_mandate_changes` сегодня вызывается ТОЛЬКО тремя
WIP-чекпоинтами аварийных путей (`commit_timeout_checkpoint`/
`commit_abnormal_checkpoint`/`commit_pause_now_checkpoint`) — ни один из
них не срабатывает на обычном успешном (`rc=0`, без таймаута/провала/
обрыва потока) завершении шага. Значит РЕАЛЬНОЕ «прежнее поведение» для
сценария этого критерия (rc=0, роль `reviewer`, грязное дерево вне
`tasks/<id>/`) — не «файл откатывается», а «ничего его не трогает»: ни
код-коммита, ни отката, ни записи журнала. Новый механизм (AC-1/AC-2/
AC-3) — мандат ТОЛЬКО `developer` (сам текст AC-1) — обязан не менять
именно это отсутствие эффекта для прочих ролей, что и проверяет тест
ниже: файл остаётся на диске ровно таким, каким его оставила роль.

Зелёный с рождения: до реализации задачи новый механизм не существует
вовсе, поэтому он и сегодня не касается пути `reviewer` — тест фиксирует
это отсутствие эффекта как критерий (не как деталь реализации AC-1) и
останется зелёным после того, как AC-1 подключит механизм для
`developer`, потому что мандат `developer` этой правки её не касается.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DeveloperWipCommitSandbox  # noqa: E402


class NonDeveloperRoleBehaviorUnchangedTest(DeveloperWipCommitSandbox):

    def test_ac5_reviewer_role_dirty_tree_outside_task_dir_is_left_untouched(self):
        """Шаг `reviewer` (роль без мандата кода) завершается `rc=0` с
        незакоммиченным файлом вне `tasks/<id>/` — код-ветка задачи не
        сдвигается новым механизмом, файл остаётся на диске неизменным,
        запись журнала «код закоммичен пультом за роль» не появляется.

        Ловит мутацию: проверка мандата (`role == "developer"`) снята или
        инвертирована — новый код-коммит захватил бы правку `reviewer`
        наравне с `developer`, HEAD кодовой ветки сдвинулся бы там, где
        AC-5 требует no-op.
        """
        self.enter_review()
        marker_path = self.write_code_file(
            "orchestrator/reviewer_note.md", "заметка не по мандату\n")
        before = self.worktree_head()

        self.run_faked()

        self.assertEqual(
            self.worktree_head(), before,
            "AC-5: новый механизм — только для роли developer, "
            "код-ветка не должна сдвинуться на шаге reviewer")
        self.assertTrue(marker_path.exists(),
                        "AC-5: файл вне мандата не должен быть убран с диска")
        self.assertEqual(marker_path.read_text(encoding="utf-8"),
                         "заметка не по мандату\n",
                         "AC-5: содержимое файла вне мандата не должно "
                         "измениться")
        self.assertEqual(
            self.code_commit_journal_entries(), [],
            "AC-5: запись журнала «код закоммичен пультом за роль» — "
            "только для роли developer")


if __name__ == "__main__":
    import unittest
    unittest.main()
