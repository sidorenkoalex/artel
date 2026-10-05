"""Юнит-тесты замка полных прогонов машины `orchestrator/suite_lock.py` и
исхода «прогон не начат» (SPEC 01M46D5T8SZ9D6S34TZFX8S46V).

Очередь прогонов разными процессами, ожидание, мёртвый держатель, снятие
на каждом исходе и отказы гейта мержа держит долгоживущий файл задачи
`tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py`. Здесь — углы,
которых он не бьёт: запись об ожидании на смене держателя, прогон внутри
уже взятого замка, исход «не начат» узла гейтов без лога и без прогона,
вина пульта у автогейта и `--accept-red` на приёмке.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, fsm, models, store, suite_lock
from tests.sandbox import TaskSeededTmpRootTest, TmpRootTest
from tests.test_approve_acceptance_full_suite import ApproveAcceptanceSandbox

HOLDER_TASK = "01MHOLDERHOLDERHOLDERHOLD"


def foreign_lock(task_id: str = HOLDER_TASK, kind: str = suite_lock.KIND_GATE,
                 pid: int | None = None) -> None:
    """Замок за живым чужим процессом (родитель процесса теста)."""
    path = suite_lock.path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"task_id": task_id,
                                "pid": pid or os.getppid(), "run": None,
                                "kind": kind}), encoding="utf-8")


class WaitAcquireTest(TmpRootTest):

    def test_wait_reports_holder_once_per_holder_and_gives_up_at_limit(self):
        """Ожидание называет держателя один раз на держателя и сдаётся на
        пределе, не трогая чужой замок.

        Сценарий: замок за живым чужим процессом весь предел ожидания —
        `on_wait` позван один раз; после смены держателя (другая задача)
        новое ожидание позвано снова с новым держателем; исход — держатель,
        файл замка тот же.

        Ловит мутацию: `on_wait` зовётся на каждом опросе (журнал задачи
        забит записями раз в секунду на полчаса ожидания); предел ожидания
        не соблюдается (замок берётся поверх живого держателя — исход
        `None`, файл переписан); ожидание без предела — вызов не вернётся.
        """
        patcher = mock.patch.object(suite_lock, "POLL_SEC", 0.01)
        patcher.start()
        self.addCleanup(patcher.stop)
        foreign_lock()
        seen = []

        holder = suite_lock.wait_acquire("T1", suite_lock.KIND_GATE, 0.2,
                                         seen.append)

        self.assertEqual(holder["task_id"], HOLDER_TASK)
        self.assertEqual([h["task_id"] for h in seen], [HOLDER_TASK])
        self.assertEqual(json.loads(suite_lock.path().read_text())["task_id"],
                         HOLDER_TASK)

        calls = []

        def on_wait(busy):
            calls.append(busy["task_id"])
            if len(calls) == 1:
                foreign_lock("01MSECONDSECONDSECONDSECO")

        suite_lock.wait_acquire("T1", suite_lock.KIND_GATE, 0.2, on_wait)
        self.assertEqual(calls, [HOLDER_TASK, "01MSECONDSECONDSECONDSECO"])

    def test_describe_names_kind_task_and_pid(self):
        """Держатель словами различает гейт, `suite-run` и `notes`.

        Ловит мутацию: вид держателя не читается — прогон гейта назван
        «suite-run», и Оператор ищет команду роли, которой не было; pid
        выпал из текста.
        """
        self.assertEqual(suite_lock.describe(
            {"task_id": "A", "pid": 11, "kind": suite_lock.KIND_GATE}),
            "гейта задачи A (pid 11)")
        self.assertEqual(suite_lock.describe({"task_id": "B", "pid": 12}),
                         "suite-run задачи B (pid 12)")
        self.assertEqual(suite_lock.describe(
            {"task_id": None, "pid": 13, "kind": suite_lock.KIND_NOTES}),
            "notes (pid 13)")


class ReentrantRunTest(TmpRootTest):

    def test_run_inside_own_lock_neither_waits_nor_releases(self):
        """Прогон процесса, уже держащего замок, идёт без ожидания и замок
        не снимает.

        Сценарий: замок взят текущим процессом (как фоновым процессом
        `suite-run`); предел ожидания — ноль; `run_full_suite` с подменённым
        зелёным pytest — зелёный, pytest позван, замок по-прежнему за
        текущим процессом.

        Ловит мутацию: проверки «замок уже мой» нет — прогон ждёт сам себя
        и даёт «прогон не начат» (фоновый `suite-run` никогда не гонит
        набор); внутренний прогон снимает замок внешнего — следующий гейт
        пошёл бы параллельно ещё идущему прогону базы `suite-run`.
        """
        (self.root / "work" / "tests").mkdir(parents=True)
        self.assertIsNone(suite_lock.acquire("T1", 3))
        self.addCleanup(suite_lock.release)
        done = subprocess.CompletedProcess([], 0, "1 passed in 0.01s\n", "")
        with mock.patch.object(config, "FULL_SUITE_LOCK_WAIT_SEC", 0), \
                mock.patch.object(acceptance.subprocess, "run",
                                  return_value=done) as run:
            green, output = acceptance.run_full_suite(self.root / "work")

        self.assertTrue(green, output)
        self.assertTrue([c for c in run.call_args_list
                         if "pytest" in c.args[0]], run.call_args_list)
        self.assertTrue(suite_lock.held_by_me())


class NotStartedOutcomeTest(TaskSeededTmpRootTest):

    def test_gate_node_gives_not_started_without_pytest_and_log(self):
        """Занятый сверх предела замок — исход «прогон не начат» узла гейтов:
        pytest не позван, лога и сохранённого итога нет, деталь и журнал
        задачи называют держателя.

        Ловит мутацию: «не начат» разбирается как красный прогон (исход
        `FULL_SUITE_RED`, заведён пустой лог «прогона»); прогон после
        предела всё равно запускается; деталь без держателя; ожидание не
        записано в журнал задачи.
        """
        (self.root / "work" / "tests").mkdir(parents=True)
        foreign_lock()
        with mock.patch.object(config, "FULL_SUITE_LOCK_WAIT_SEC", 0), \
                mock.patch.object(acceptance, "run_full_suite") as run:
            result = acceptance.full_suite(self.root / "work", self.TASK)

        run.assert_not_called()
        self.assertFalse(result.green)
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_NOT_STARTED)
        self.assertIsNone(result.log_path)
        self.assertIn(HOLDER_TASK, result.detail)
        self.assertEqual(list(Path(config.LOGS).glob("*fullsuite*")), [])
        journal = [f"{r['action']} {r['detail']}"
                   for r in store.task_steps(store.db(), self.TASK)]
        self.assertTrue([j for j in journal
                         if acceptance.FULL_SUITE_LOCK_WAIT_ACTION in j
                         and HOLDER_TASK in j], journal)

    def test_not_started_refusal_of_autogate_blames_pult(self):
        """Отказ автогейта «прогон не начат» — вина пульта, не роли.

        Сценарий: деталь исхода собрана производителем
        (`acceptance._full_suite_detail` над `_not_started_note`) с
        префиксом автогейта.

        Ловит мутацию: начало текста исхода не в перечне пульта — занятая
        машина уходит в «не установлена», и прогон канарейки, испорченный
        очередью прогонов, перестаёт засчитываться в допуск пары.
        """
        note = acceptance._not_started_note(
            {"task_id": HOLDER_TASK, "pid": 1, "kind": suite_lock.KIND_GATE})
        detail = acceptance._full_suite_detail(
            acceptance.FULL_SUITE_NOT_STARTED, "", None, note)
        self.assertEqual(models.autogate_refusal_blame(f"автогейт: {detail}"),
                         models.BLAME_PULT)


class ApproveNotStartedTest(ApproveAcceptanceSandbox):

    def test_accept_red_does_not_pass_a_run_that_never_started(self):
        """`--accept-red` не проводит приёмку, если прогона не было.

        Сценарий: узел гейтов отдаёт «прогон не начат» (замок машины занят);
        `approve --accept-red` — отказ, задача в `acceptance`, записи о
        принятой красноте нет, держатель назван в выводе.

        Ловит мутацию: «не начат» идёт общей веткой не-зелёного исхода —
        основание красноты принимает непроверенный набор, и задача уходит на
        `merge_gate` без единого прогона.
        """
        self.full_suite_result = (False, acceptance._not_started_note(
            {"task_id": HOLDER_TASK, "pid": 1, "kind": suite_lock.KIND_GATE}))

        out = self.approve(accept_red="красный main")

        self.assertEqual(self.state(), "acceptance")
        self.assertIn(HOLDER_TASK, out)
        self.assertNotIn(fsm.ACCEPTANCE_RED_ACCEPTED_ACTION,
                         self.journal_blob())


if __name__ == "__main__":
    unittest.main()
