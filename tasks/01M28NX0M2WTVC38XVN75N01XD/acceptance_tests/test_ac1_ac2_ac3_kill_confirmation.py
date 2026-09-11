"""Приёмочные тесты 01M28NX0M2WTVC38XVN75N01XD — AC-1, AC-2, AC-3 (SPEC.md).

Красен до реализации: отказ и журнал AC-1 (`test_ac1_*`) и журнал
подтверждения AC-2 (`test_ac2_journal_names_the_yes_confirmation`) не
производятся сегодняшним `kill` — диспетчер `"kill"` в `orchestrator/
artel.py::main` не знает флага `--yes`, `cleanup.cmd_kill`/`_cmd_kill`
не различают живой/мёртвый lease перед ликвидацией вовсе.
`test_ac2_yes_flag_performs_full_kill_and_signals_holder` и оба
`test_ac3_*` зелены уже сегодня — они кроют поведение, которое эта
задача сознательно НЕ меняет (полный kill при живом lease независимо
от подтверждения, полный kill без флага при мёртвом/отсутствующем
lease) — их зелёность здесь и есть регрессионная защита требования 3
SPEC («работает как раньше»), не дефект теста.

Живой lease — тем же приёмом, что уже используют `tests/
test_detached_cycle.py::KillSignalsDetachedHolderTest`/`CmdStopTest`:
держатель — pid ЭТОГО ЖЕ тестового процесса (безопасно проверять
живость `os.kill(pid, 0)` и одновременно гарантированно не даёт
случайно убить сам тестовый процесс благодаря `_signal_only_kill`,
которая пропускает к настоящему `os.kill` только сигнал 0).
"""
import os
import re
import signal
import socket
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artel, cleanup, config, runner, store, workspace  # noqa: E402
from tests.sandbox import _ts_ago  # noqa: E402
from tests.test_detached_cycle import _signal_only_kill, _terminating_calls  # noqa: E402
from tests.test_kill_cleanup import TmpRepoTest  # noqa: E402

_REFUSAL_ACTION = "kill отклонён: цикл жив"
_CONFIRM_ACTION = "kill подтверждён флагом --yes при живом цикле"


class KillConfirmationSandbox(TmpRepoTest):
    """Задача с worktree/кодовой веткой, форсированная в `in_dev` (роль
    `developer` — однословная, без пробелов, удобна для regex AC-1),
    lease живого отвязанного цикла — та же сессия/pid во всех сценариях,
    сеет каждый тест сам (мёртвый/отсутствующий вариант нужен только
    AC-3)."""

    def setUp(self):
        super().setUp()
        self.ensure_worktree()
        conn = store.db()
        current = store.get_task(conn, self.TASK)["state"]
        store.set_state(conn, self.TASK, "in_dev", "operator",
                        expected_state=current, detail="тест: подготовка")

    def seed_live_lease(self) -> None:
        store.insert_lease(store.db(), self.TASK, "cycle-session",
                           os.getpid(), socket.gethostname(), store.now())

    def seed_stale_lease(self) -> None:
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        store.insert_lease(store.db(), self.TASK, "cycle-session",
                           os.getpid(), socket.gethostname(), stale_ts)

    def cli_kill(self, *flags: str) -> str:
        with mock.patch.object(sys, "argv",
                               ["artel.py", "kill", self.TASK, *flags]):
            return self.capture(artel.main)

    def journal_actions(self) -> list:
        return [s["action"] for s in store.task_steps(store.db(), self.TASK)]


class Ac1KillWithoutYesRefusesLiveLeaseTest(KillConfirmationSandbox):
    """AC-1: `kill <id>` без `--yes` при живом lease отказывает точным
    текстом; состояние, ветка, worktree и lease не меняются, держатель
    не получает сигнала, отказ журналируется."""

    def setUp(self):
        super().setUp()
        self.seed_live_lease()

    def test_ac1_refuses_with_named_text_naming_stop_and_kill_yes(self):
        """Отказ печатает названный SPEC текст целиком: pid и роль
        держателя, обе следующие команды (`stop` без аргументов и `kill
        --yes`) — и не меняет ничего в задаче.

        Ловит мутацию: проверка живости lease перед отказом убрана (или
        считает лизу мёртвой безусловно) — kill проходит целиком без
        `SystemExit`; либо текст отказа называет только одну из команд
        `stop`/`kill --yes`, либо теряет pid/роль — `assertRegex` не
        совпадёт ни с одной такой урезанной версией текста.
        """
        role = runner.step_role(store.get_task(store.db(), self.TASK))
        pid = os.getpid()
        pattern = (
            rf"\[{re.escape(self.TASK)}\] цикл жив \(pid {pid}, "
            rf"шаг {re.escape(role)} с \S.*?\) — остановить цикл: "
            rf"artel\.py stop {re.escape(self.TASK)}; ликвидировать "
            rf"задачу \(ветка и worktree будут удалены\): artel\.py kill "
            rf"{re.escape(self.TASK)} --yes"
        )

        with _signal_only_kill(cleanup) as kill:
            with self.assertRaises(SystemExit) as ctx:
                self.cli_kill()

        text = str(ctx.exception)
        self.assertRegex(text, pattern, f"текст отказа не совпал: {text!r}")
        self.assertEqual(_terminating_calls(kill), [],
                         "держатель lease не должен получать сигнал")
        self.assertEqual(self.task_row()["state"], "in_dev")
        row = store.lease_row(store.db(), self.TASK)
        self.assertEqual(row["session_id"], "cycle-session",
                         "lease не должен быть перехвачен отказанным kill")
        self.assertTrue(workspace.path(self.TASK).exists())
        self.assertIn(self.branch, self.branches())

    def test_ac1_journal_names_the_refusal(self):
        """Отказ пишет отдельную запись действия «kill отклонён: цикл
        жив» — по ней Оператор отличит осознанный отказ от того, что
        команда просто не сработала по другой причине.

        Ловит мутацию: текст отказа печатается, но нигде не
        журналируется — тест красен, если ни одна запись действия
        журнала не совпадает буквально.
        """
        with _signal_only_kill(cleanup):
            with self.assertRaises(SystemExit):
                self.cli_kill()

        self.assertIn(_REFUSAL_ACTION, self.journal_actions(),
                     f"журнал: {self.journal_actions()}")


class Ac2KillWithYesConfirmsLiveLeaseTest(KillConfirmationSandbox):
    """AC-2: `kill <id> --yes` при живом lease выполняет прежнее полное
    поведение kill целиком и журналирует подтверждение флагом."""

    def setUp(self):
        super().setUp()
        self.seed_live_lease()

    def test_ac2_yes_flag_performs_full_kill_and_signals_holder(self):
        """С флагом `--yes` живой lease больше не блокирует ликвидацию:
        состояние переходит в `killed`, ветка и worktree убираются,
        держатель получает `SIGKILL` — байт-в-байт прежнее поведение
        `cmd_kill` (SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P, AC-10), закреплённое
        в `tests/test_detached_cycle.py::KillSignalsDetachedHolderTest`.

        Ловит мутацию: `--yes` разбирается CLI, но не долетает до
        `cmd_kill` (например, застревает в разборе argv или проверяется
        только присутствие любого третьего аргумента) — тест красен,
        если lease/ветка/worktree остаются нетронутыми либо держатель
        не получает `SIGKILL`.
        """
        with _signal_only_kill(cleanup) as kill:
            self.cli_kill("--yes")

        self.assertEqual(_terminating_calls(kill),
                         [mock.call(os.getpid(), signal.SIGKILL)])
        self.assertEqual(self.task_row()["state"], "killed")
        self.assertFalse(workspace.path(self.TASK).exists())
        self.assertNotIn(self.branch, self.branches())

    def test_ac2_journal_names_the_yes_confirmation(self):
        """Отдельная запись журнала отличает kill, подтверждённый флагом
        при живом lease, от обычного kill без него (AC-3 требует, чтобы
        та же фраза НЕ появлялась там).

        Ловит мутацию: подтверждённый `--yes` kill идёт тем же путём,
        что и kill без живого lease, без отдельной пометки в журнале —
        тест красен, если фраза не найдена ни в одной записи.
        """
        with _signal_only_kill(cleanup):
            self.cli_kill("--yes")

        self.assertIn(_CONFIRM_ACTION, self.journal_actions(),
                     f"журнал: {self.journal_actions()}")


class Ac3KillWithoutYesWorksAsBeforeWithoutLiveLeaseTest(KillConfirmationSandbox):
    """AC-3: без живого lease `kill <id>` без флага работает как раньше
    — без текста отказа AC-1 и без новой записи в журнал."""

    def test_ac3_stale_lease_kills_normally_without_new_journal_entries(self):
        """Протухший lease того же держателя (heartbeat старше
        `config.LEASE_STALE_AFTER_SEC`) — kill без `--yes` доводит
        ликвидацию до конца, не упоминая «цикл жив» ни в выводе, ни в
        журнале.

        Ловит мутацию: проверка живости lease перед отказом слишком
        широкая (считает живым любой lease, а не только свежий по
        heartbeat) — тест красен, если kill без живого lease вдруг
        начинает требовать `--yes` (`SystemExit` вместо обычной
        ликвидации).
        """
        self.seed_stale_lease()

        with _signal_only_kill(cleanup):
            out = self.cli_kill()

        self.assertEqual(self.task_row()["state"], "killed")
        self.assertFalse(workspace.path(self.TASK).exists())
        self.assertNotIn(self.branch, self.branches())
        self.assertNotIn("цикл жив", out)
        self.assertNotIn(_REFUSAL_ACTION, self.journal_actions())
        self.assertNotIn(_CONFIRM_ACTION, self.journal_actions())

    def test_ac3_no_lease_at_all_kills_normally(self):
        """Отсутствие lease вовсе — тот же нормальный путь, что и
        сегодня (`tests/test_kill_cleanup.py::KillCleanupTest::
        test_task_killed_before_commit_leaves_no_trace`).

        Ловит мутацию: отказ AC-1 срабатывает даже без единой строки
        lease (например, `None`-строка ошибочно трактуется как «жива»)
        — тест красен на `SystemExit` там, где раньше kill просто
        завершал задачу.
        """
        with _signal_only_kill(cleanup):
            out = self.cli_kill()

        self.assertEqual(self.task_row()["state"], "killed")
        self.assertNotIn(self.branch, self.branches())
        self.assertNotIn("цикл жив", out)
        self.assertNotIn(_REFUSAL_ACTION, self.journal_actions())
        self.assertNotIn(_CONFIRM_ACTION, self.journal_actions())


if __name__ == "__main__":
    import unittest
    unittest.main()
