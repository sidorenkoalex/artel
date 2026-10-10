"""Отказ коммита подтяжки при авторазрешении конфликта карты пишет запись журнала до эскалации (SPEC 01M4JMMH70NWJG72G422BFY1KC, требование 2).

Долгоживущие тесты задачи покрывают регенерацию, `checkout --theirs` и
`add` карты; здесь — завершающий `commit` того же пути авторазрешения,
тот же сценарий песочницы.
"""
import unittest

from tests.test_01m4jmmh70nwjg72g422bfy1kc_pull_map_interpreter import (
    MAP_REL, STUB_OK, PullMapConflictSandbox)


class PullCommitStepFailureTest(PullMapConflictSandbox):

    def test_commit_failure_journals_step_code_and_tail(self):
        """Отказ `git commit` подтяжки после разрешённой карты — запись журнала с шагом, кодом и хвостом stderr до прежней эскалации.

        Ловит мутацию: отказ коммита по-прежнему молча возвращает `False`
        из `pull._auto_resolve_conflict` — записи с хвостом stderr до
        эскалации нет; запись не называет шаг `commit` или код возврата.
        """
        self.write_regenerator(STUB_OK.format(text="карта\n"))
        code = self.rng.randint(2, 120)
        self.fail_step = (("commit",), code, self.failing_stderr())
        since = self.max_step_id()

        outcome = self.pull()

        # Помощник сверяет «коммита нет»; здесь попытка коммита была ровно
        # одна и отказала — merge не завершён, её и убираем из сверки.
        commits = [c for c in self.calls if c[:1] == ("commit",)]
        self.assertEqual(len(commits), 1, self.note(repr(self.calls)))
        self.calls.remove(commits[0])
        self.assert_escalated_with_step_record(
            since, outcome, code, r"\bcommit\b",
            f"git commit отказал кодом {code} после карты {MAP_REL}")


if __name__ == "__main__":
    unittest.main()
