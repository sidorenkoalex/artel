"""Приёмочные тесты 01M1VBEAWZW4EBZHKMGNBBK648 — AC-1, AC-2, AC-3 (SPEC.md).

Допущения интерфейса — см. докстринг `_sandbox.py`: `auto.cmd_auto(...,
wait_zone=True)`, `config.ZONE_WAIT_POLL_SEC`/`ZONE_WAIT_MAX_SEC`,
перехват реального `time.sleep` цикла ожидания (через `only_on_poll_
interval` — глобальный патч `time.sleep` иначе ловит и посторонние
вызовы, например ретрай спавна агента внутри `runner._cmd_run`, что
подтвердила валидация стабом), продление heartbeat lease наблюдаемым
фактом изменения `leases.heartbeat_ts`.

Красен до реализации: `auto.cmd_auto` сегодня не принимает параметр
`wait_zone` вовсе (`_run_zone_wait_refusal` всегда останавливает цикл
через `config.AUTO_STOP_ZONE_WAIT` — см. `orchestrator/auto.py::
_role_run_step`) — вызов ниже с `wait_zone=True` падает
`TypeError: cmd_auto() got an unexpected keyword argument 'wait_zone'`
до появления этого параметра.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (ZoneWaitSandbox, fake_now_sequence,  # noqa: E402
                      only_on_poll_interval)

from orchestrator import auto, config, store  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class WaitZoneCycleTest(ZoneWaitSandbox):

    def setUp(self):
        super().setUp()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "in_dev", CONFLICT_PATH)
        self.mark_already_started(OCCUPIER)

    def _run(self, fake_sleep):
        with mock.patch.object(config, "ZONE_WAIT_POLL_SEC", 0.001,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 3600,
                              create=True), \
             mock.patch.object(auto.time, "sleep",
                              side_effect=only_on_poll_interval(fake_sleep)), \
             mock.patch.object(store, "now", side_effect=fake_now_sequence()):
            return self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION,
                                      wait_zone=True))

    # --------------------------------------------------------------- AC-1

    def test_ac1_wait_zone_polls_at_configured_interval_and_renews_heartbeat(self):
        """`--wait-zone` не останавливает цикл на первом же отказе «ждёт
        зоны»: опрашивает несколько раз подряд с интервалом
        `config.ZONE_WAIT_POLL_SEC`, продлевая heartbeat lease задачи на
        каждом опросе, пока держатель зоны не освободит её.

        Ловит мутацию: цикл ожидания не продлевает heartbeat lease на
        опросах (heartbeat остаётся значением самого первого захвата,
        взятого `lease.run_locked` до входа в ожидание, — при реальном
        многочасовом ожидании такой lease протух бы и был бы перехвачен
        конкурентной сессией, требование 1 стало бы фикцией).
        """
        heartbeats = []
        calls = {"n": 0}

        def fake_sleep(seconds):
            # `only_on_poll_interval` (см. `_sandbox.py`) уже гарантирует
            # `seconds == config.ZONE_WAIT_POLL_SEC` — сюда доходят ТОЛЬКО
            # опросы ожидания зоны, не посторонние `time.sleep` (например
            # ретрай спавна агента внутри `runner._cmd_run`).
            calls["n"] += 1
            heartbeats.append(self.lease_heartbeat())
            if calls["n"] >= 3:
                self.set_task_state(OCCUPIER, "done")

        out, popen = self._run(fake_sleep)

        self.assertGreaterEqual(
            calls["n"], 3,
            f"цикл остановился раньше 3 опросов ({calls['n']}), хотя "
            f"держатель зоны не освобождал её: {out!r}")
        self.assertTrue(
            any(h != heartbeats[0] for h in heartbeats),
            "heartbeat lease не менялся между опросами ожидания — "
            "renewal требования 1 не происходит")

    # --------------------------------------------------------------- AC-2

    def test_ac2_entering_wait_journals_exactly_one_entry_line(self):
        """Вход в ожидание пишет РОВНО одну запись журнала «ждёт зоны
        <путь>: держит <id> (<state>)» — не ноль (тихий вход) и не по
        записи на каждый опрос (спам при долгом ожидании).

        Ловит мутацию: запись входа пишется на КАЖДОМ опросе `blocking_
        conflict` вместо одного раза при первом обнаружении конфликта —
        журнал разросся бы на одну строку за каждый `config.
        ZONE_WAIT_POLL_SEC`, что при боевом многочасовом ожидании
        превратило бы журнал задачи в шум.
        """
        since = self.journal_len()
        poll_count = {"n": 0}

        def fake_sleep(seconds):
            poll_count["n"] += 1
            if poll_count["n"] >= 2:
                self.set_task_state(OCCUPIER, "done")

        self._run(fake_sleep)

        rows = store.task_steps(store.db(), self.TASK)[since:]
        entry_text = f"ждёт зоны {CONFLICT_PATH}: держит {OCCUPIER} (in_dev)"
        matches = [r for r in rows
                  if entry_text in f"{r['actor']} {r['action']} {r['detail']}"]
        self.assertEqual(
            len(matches), 1,
            f"вход в ожидание обязан журналироваться РОВНО один раз, "
            f"найдено {len(matches)}: {[dict(r) for r in matches]}")

    # --------------------------------------------------------------- AC-3

    def test_ac3_release_journals_exit_once_and_role_runs_without_restart(self):
        """Освобождение зоны (держатель ушёл из блокирующей фазы) пишет
        РОВНО одну запись «зона свободна через N мин, держал <id>», и
        цикл `auto` продолжает ТЕМ ЖЕ вызовом — стартует роль developer
        без ручного перезапуска (требование, которое и закрывает 9
        обходов внешнего `zone_wait_auto.sh` за 05-06.09, SPEC
        «Контекст»).

        Ловит мутацию: после освобождения зоны `auto` останавливается
        (как раньше делал `_run_zone_wait_refusal`/`AUTO_STOP_ZONE_WAIT`)
        вместо того, чтобы продолжить и реально запустить агента —
        `popen.assert_called()` ниже не выполнился бы, а Оператору
        снова понадобился бы ручной `artel.py auto <id>`.
        """
        since = self.journal_len()

        def fake_sleep(seconds):
            self.set_task_state(OCCUPIER, "done")

        out, popen = self._run(fake_sleep)

        rows = store.task_steps(store.db(), self.TASK)[since:]
        exit_rows = [r for r in rows
                    if "зона свободна через" in r["detail"].lower()
                    or "зона свободна через" in r["action"].lower()]
        exit_rows = [r for r in exit_rows
                    if "мин" in f"{r['action']} {r['detail']}".lower()
                    and "держал" in f"{r['action']} {r['detail']}".lower()
                    and OCCUPIER in f"{r['action']} {r['detail']}"]
        self.assertEqual(
            len(exit_rows), 1,
            f"выход из ожидания обязан журналироваться РОВНО один раз в "
            f"формате «зона свободна через N мин, держал {OCCUPIER}»: "
            f"{out!r}")
        popen.assert_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
