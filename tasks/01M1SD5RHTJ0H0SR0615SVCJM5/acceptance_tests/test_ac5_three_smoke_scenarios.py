"""AC-5 (tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md): три записанных смоук-
сценария на песочнице с фейковым git — штатный мерж, отказ по
подтверждённо красному CI, отказ по конфликту merge на защищённом пути —
дают тот же журнал и вывод до и после рефакторинга.

Песочница — `tests.test_invariants.FsmTest` (та же фикстура, на которой
уже стоят `MergeOnlyFromMergeGateTest`/`MergeNeedsGreenCiTest`/
`test_merge_failure_leaves_the_task_in_the_gate` для этой же merge-
последовательности, «фейковый git» — `SpyRun`, тот же термин, что
`docs/roadmap.md` R8 использует для этого приёма): своя песочница с нуля
здесь дублировала бы catalog/ci/keychain-обвязку без содержательной
причины (тот же довод, что `tasks/T036/acceptance_tests/
test_merge_gitcmd.py`).

Каждый тест фиксирует буквальные строки журнала/печати и конечное
состояние задачи, наблюдаемые на СЕГОДНЯШНЕМ (до рефакторинга задачи)
`orchestrator/fsm_merge_gate.py` — прогнан на сегодняшнем коде. Это и
есть «запись» смоука требования 6 SPEC: после разбора `_cmd_approve_
merge_gate` на шаги эти же утверждения обязаны остаться зелёными без
единой правки ассертов (AC-6 этой же задачи).

Зелёный с рождения: все три сценария воспроизводят уже существующее
поведение гейта — рефакторинг обязан оставить его буквально нетронутым
(AC-4/AC-5), не создать заново, поэтому эти тесты зелёные уже сегодня и
обязаны остаться зелёными после.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import ci, fsm, gitcmd, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

# AC-6: manual — зелёность `tests/test_fsm_merge_gate*.py`,
# `tests/test_branch_freshness_gate.py` и приёмочных планок задач
# 01M1NBWPKNBXP9ZXXQDJM7AXPJ/01M1GS5HZ1JXFGKVR95HEW0AEZ/
# 01M1R9YEK08XEQWBFX0929WFVJ уже покрыта `.github/workflows/ci.yml`
# (`unittest discover -s tests -v` на каждый пуш в чистом раннере) — это
# и есть проверка критерия. Повтор той же проверки подпроцессом внутри
# acceptance_tests рисковал бы ложным красным от несвязанных с этой
# задачей экологических условий машины разработчика, а не от регресса
# декомпозиции (тот же довод и прецедент, что `tasks/T036/
# acceptance_tests/test_merge_gitcmd.py` AC-4 и `tasks/T035` AC-11).


def _plain_args(call: list) -> list:
    """argv git-вызова без ведущих пар `-C <путь>` (Stage0: плотницкий
    merge идёт в scratch-worktree `git -C <scratch> ...`) — та же
    нормализация, что уже несёт `tests.test_invariants.
    MergeOnlyFromMergeGateTest._plain_args`."""
    args = list(call)
    if args[:1] == ["git"]:
        args = args[1:]
    i = 0
    while i + 1 < len(args) and args[i] == "-C":
        i += 2
    return args[i:]


def _journal_rows(task_id: str) -> list:
    return store.db().execute(
        "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
        (task_id,)).fetchall()


class NormalMergeSmokeTest(FsmTest):
    """Сценарий 1: штатный мерж — CI зелёный (фикстура `FsmTest.setUp`
    сама держит зелёный CI по умолчанию), конфликтов нет."""

    def test_ac5_normal_merge_reaches_done_with_literal_journal(self):
        """Из `merge_gate` штатный approve мержит ветку задачи плотницки
        в scratch-worktree и закрывает задачу в `done` с буквальным
        текстом закрывающей записи журнала.

        Ловит мутацию: разработчик при выносе финального перехода в
        отдельный шаг меняет текст detail (например убирает двоеточие или
        имя ветки из «смержено: {branch}») — `assertEqual` на буквальной
        строке здесь покраснеет; либо порядок worktree/merge
        переставляется — `assertLess` на индексах подкоманд поймает и
        это.
        """
        self.set_state("merge_gate")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "done")

        subcommands = self.git_spy.git_subcommands()
        self.assertIn("merge", subcommands)
        self.assertLess(
            subcommands.index("worktree"), subcommands.index("merge"),
            "плотницкий merge обязан идти в scratch-worktree, заведённом "
            "до самого merge")
        merge_calls = [c for c in self.git_spy.calls
                      if _plain_args(c)[:1] == ["merge"]]
        self.assertTrue(merge_calls, "git merge не вызван")
        self.assertIn(self.branch, merge_calls[0])

        rows = _journal_rows(self.TASK)
        closing = [r for r in rows if r["action"] == "state -> done"]
        self.assertTrue(closing, "нет записи журнала о переходе в done")
        self.assertEqual(closing[-1]["detail"], f"смержено: {self.branch}")


class ConfirmedRedCiSmokeTest(FsmTest):
    """Сценарий 2: `approve` из `merge_gate`, но CI ветки подтверждённо
    красный (ре-ран того же самого красного статуса — не флейк)."""

    RED_NOTE = "CI коммита abc12345 не зелёный: python=failure"
    RERUN_NOTE = "CI коммита abc12345 не зелёный: python=failure"

    def test_ac5_confirmed_red_ci_refuses_and_keeps_the_gate(self):
        """Подтверждённо красный CI (ре-ран остаётся красным) отказывает
        именованно, задача остаётся на `merge_gate`, merge не вызывается
        ни разу.

        Ловит мутацию: разработчик при выносе ре-рана в отдельный шаг
        путает условие флейка (например засчитывает подтверждённый
        красный как зелёный) — merge оказался бы вызван, и
        `assertNotIn("merge", ...)` здесь покраснеет; либо текст отказа
        меняется — `assertIn` на буквальной подстроке поймает и это.
        """
        self.set_state("merge_gate")

        with mock.patch.object(ci, "branch_status",
                               lambda branch: (False, self.RED_NOTE)), \
             mock.patch.object(ci, "trigger_rerun",
                               lambda branch: "ре-ран CI запущен (тест)"):
            with self.assertRaises(SystemExit) as exit_:
                self.capture(fsm.cmd_approve, self.TASK)

        message = str(exit_.exception)
        self.assertIn(f"[{self.TASK}] merge отклонён: {self.RERUN_NOTE}",
                      message)
        self.assertIn("задача осталась на гейте merge", message)
        self.assertIn(f"artel.py approve {self.TASK}", message)

        self.assertEqual(self.state(), "merge_gate")
        self.assertNotIn("merge", self.git_spy.git_subcommands())

        rows = _journal_rows(self.TASK)
        details = "\n".join(r["detail"] for r in rows)
        self.assertIn("flake-rate", [r["action"] for r in rows])
        self.assertIn(
            f"подтверждённый красный: первый статус красный, ре-ран тоже "
            f"красный ({self.RED_NOTE} -> {self.RERUN_NOTE})", details)


class ProtectedPathConflictSmokeTest(FsmTest):
    """Сценарий 3: `git merge --no-ff` в scratch-worktree проваливается
    содержательным конфликтом, задевающим защищённый путь (`gates.yaml`,
    `config.PROTECTED_PATHS`)."""

    def test_ac5_protected_path_conflict_escalates_with_literal_detail(self):
        """Конфликт merge, затрагивающий `gates.yaml`, эскалирует задачу
        (не возвращает в `in_dev`, как незащищённый конфликт), scratch-
        дерево убирается `git merge --abort`.

        Ловит мутацию: разработчик при выносе разбора конфликта в
        отдельный шаг меняет ветвление «защищённый путь -> escalated» на
        то же самое `in_dev`, что и для обычного конфликта (например
        забывает передать `_touches_protected_path` в новый шаг) —
        `assertEqual(self.state(), "escalated")` здесь покраснеет.
        """
        self.set_state("merge_gate")

        def failing(cmd, *args, **kwargs):
            self.git_spy(cmd, *args, **kwargs)
            plain = _plain_args(cmd)
            if plain[:2] == ["merge", "--no-ff"]:
                return subprocess.CompletedProcess(list(cmd), 1, "", "конфликт")
            if plain[:3] == ["diff", "--name-only", "--diff-filter=U"]:
                return subprocess.CompletedProcess(list(cmd), 0, "gates.yaml\n", "")
            return subprocess.CompletedProcess(list(cmd), 0, "", "")

        with mock.patch.object(gitcmd.subprocess, "run", failing):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        self.assertIn("merge", self.git_spy.git_subcommands())
        merge_calls = [_plain_args(c) for c in self.git_spy.calls
                      if _plain_args(c)[:1] == ["merge"]]
        self.assertTrue(
            any(c[:2] == ["merge", "--abort"] for c in merge_calls),
            f"git merge --abort не вызван: {merge_calls}")

        rows = _journal_rows(self.TASK)
        escalation = [r for r in rows if r["action"] == "state -> escalated"]
        self.assertTrue(escalation, "нет записи журнала о переходе в escalated")
        self.assertEqual(
            escalation[-1]["detail"],
            "конфликт merge затрагивает защищённый путь (gates.yaml); "
            "конфликтующие файлы: gates.yaml")


if __name__ == "__main__":
    unittest.main()
