"""AC-5 задачи 01M1TKP08PKB87K8772H69GCXJ: существующие тесты, подменяющие
имена через `mock.patch.object(fsm, "...")` на именах, перенесённых в
`pull.py`, продолжают работать — `fsm.py` реэкспортирует нужные имена.

Единственное такое имя, реально подменяемое СНАРУЖИ через
`mock.patch.object(fsm, "_origin_main_sha", ...)` в существующих тестах
(`tests/test_branch_freshness_gate.py`, `tests/test_fsm_map_conflict_
autoresolve.py` — их `setUp`), — `_origin_main_sha`: если перенос
логики в `pull.py` заставит внутренний код читать сам себя из
модуля `pull` напрямую (не через `fsm`), патч `fsm._origin_main_sha`
перестанет долетать до реального `git merge`, хотя `fsm.py` формально
всё ещё несёт атрибут с этим именем (реэкспорт «для галочки», не для
поведения).

Зелёный с рождения: сегодняшний `_pull_main_or_escalate` уже читает
`_origin_main_sha` из СВОЕГО модуля `fsm` (той же функции, что этот
тест патчит) — задача обязана сохранить это байт-в-байт (требование
4), поэтому поведенческая проверка не меняется рефакторингом.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PullNodeSandbox  # noqa: E402
from orchestrator import acceptance, fsm, gitcmd  # noqa: E402

MARKER_SHA = "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee0"


class Ac5ReexportTest(PullNodeSandbox):

    def test_ac5_patching_fsm_origin_main_sha_still_drives_merge_argument(self):
        """Патч `mock.patch.object(fsm, "_origin_main_sha", ...)` обязан
        долетать до реального аргумента `git merge` — тем же способом,
        каким сегодня на нём держатся `tests/test_branch_freshness_
        gate.py`/`tests/test_fsm_map_conflict_autoresolve.py`.

        Ловит мутацию: логика подтяжки, перенесённая в `pull.py`, читает
        собственную копию `_origin_main_sha` (или дублирует функцию
        внутри `pull.py` без реэкспорта в `fsm`) — маркерный sha,
        подставленный патчем на `fsm`, не долетит до аргументов `git
        merge`, и `assertIn` ниже это поймает.
        """
        self.write_acceptance_plank()
        side_effect = self.in_repo_side_effect()
        with mock.patch.object(fsm, "_origin_main_sha",
                               return_value=MARKER_SHA), \
             mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self.pull()

        self.assertEqual(outcome, "pulled")
        self.assertEqual(len(self.merge_calls), 1)
        _, merge_args = self.merge_calls[0]
        self.assertIn(
            MARKER_SHA, merge_args,
            "AC-5: патч fsm._origin_main_sha обязан долетать до реального "
            "git merge — иначе существующие тесты, подменяющие это имя "
            "через mock.patch.object(fsm, ...), перестанут работать после "
            "переноса логики подтяжки в pull.py")


if __name__ == "__main__":
    unittest.main()
