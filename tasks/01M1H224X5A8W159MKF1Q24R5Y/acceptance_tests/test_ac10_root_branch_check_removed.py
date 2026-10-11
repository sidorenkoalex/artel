"""AC-10: Проверка `root_branch != config.MAIN_BRANCH`, сегодня отказывающая
`approve`, если главная копия пульта не на `main`
(`orchestrator/fsm_merge_gate.py`), убрана или заменена проверкой, не
зависящей от текущего чекаута `config.ROOT` — `approve` больше не требует,
чтобы главная копия стояла на `main`.

Красен до реализации: `_cmd_approve_merge_gate` (`orchestrator/
fsm_merge_gate.py`, строки ~186-196) буквально делает `root_branch =
gitcmd.current_branch(); if root_branch and root_branch !=
config.MAIN_BRANCH: ... return ("stopped",)` — прямая проверка ЧЕКАУТА
`config.ROOT`. Раз AC-8 переводит сам merge на плотницкую запись
(независимую от чекаута), этой проверке структурно нечего защищать —
чекаут `config.ROOT` для плотницкого merge не участвует вовсе; тест ниже
чекаутит `self.root` на постороннюю ветку (не `main`, не ветку задачи) и
падает потому, что сегодня `approve` в ЭТОЙ ситуации отказывает именно
этой проверкой (`return ("stopped",)`), не доходя до самого merge.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import ci, config, fsm_merge_gate, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402

TASK = "01ARTELROOTBRANCHCHK01"


class ApproveDoesNotRequireRootOnMainTest(ArtelSelfTargetSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.make_task_branch_in_root(
            self.branch, "feature.txt", "код фичи\n", f"{TASK}: код фичи")
        self.insert_task(TASK, self.branch, "merge_gate")
        self.ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.ci_patcher.start()
        self.addCleanup(self.ci_patcher.stop)
        # Главная копия пульта — на ПОСТОРОННЕЙ ветке (не main, не ветка
        # задачи): ручной чекаут Оператора вне цикла FSM, тот самый
        # случай, которым ANSWER-1/AC-10 явно жертвует старой проверкой.
        self.git("checkout", "-q", "-b", "operator-scratch")

    def test_ac10_approve_succeeds_even_though_root_is_on_a_foreign_branch(self):
        """`approve` из `merge_gate` доводит задачу до `done`, несмотря на
        то, что `config.ROOT` стоит на `operator-scratch` (не `main`) —
        проверка `root_branch != config.MAIN_BRANCH` не отказывает
        переход.

        Ловит мутацию: не тронутую проверку `root_branch != config.
        MAIN_BRANCH` в начале `_cmd_approve_merge_gate` — тогда результат
        останется `("stopped",)`, состояние задачи — по-прежнему
        `merge_gate`.
        """
        t = store.get_task(store.db(), TASK)

        result = fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t)

        self.assertEqual(result, ("done",))
        self.assertEqual(store.get_task(store.db(), TASK)["state"], "done")

    def test_ac10_no_refusal_journal_entry_naming_a_foreign_root_branch(self):
        """Журнал задачи не несёт отказа «главная копия не на main» —
        текст-маркер прежней проверки (`fsm_merge_gate.py`, «approve
        отклонён: главная копия не на main») отсутствует после успешного
        `approve` с посторонним чекаутом `config.ROOT`.

        Ловит мутацию: ту же непеределанную проверку — сегодня она пишет
        именно эту запись в журнал ПЕРЕД возвратом `("stopped",)`.
        """
        t = store.get_task(store.db(), TASK)

        fsm_merge_gate._cmd_approve_merge_gate(store.db(), TASK, "merge_gate", t)

        conn = store.db()
        rows = conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=?", (TASK,)).fetchall()
        combined = " ".join(f"{r['action']} {r['detail'] or ''}" for r in rows)
        self.assertNotIn("главная копия не на main", combined)


if __name__ == "__main__":
    unittest.main()
