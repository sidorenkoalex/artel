"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-8(а) (SPEC.md).

AC-8 явно перечисляет сценарии, которые обязаны покрыть новые тесты
(«...после `done`/`killed` держателя стартует developer тем же вызовом,
журнал несёт вход и выход с длительностью ожидания») — этот файл кроет
ОБА исхода держателя (`done` и `killed`) отдельными подтестами;
`test_ac1_ac2_ac3_wait_zone_cycle.py` уже кроет тот же механизм для
`done` в отдельности (AC-1..AC-3) — здесь предмет именно то, что
разработчик не забыл `killed` как СИМВОЛ РАВНОЗНАЧНОГО освобождения (оба
уже сегодня вне `zone_lock.BLOCKING_STATES`, но НОВЫЙ код цикла ожидания
мог бы ошибочно проверять только `state == "done"` буквально).

Допущения интерфейса — см. `_sandbox.py`.

Красен до реализации: как и соседние файлы этой задачи — `wait_zone` у
`auto.cmd_auto` ещё не существует.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (ZoneWaitSandbox, fake_now_sequence,  # noqa: E402
                      only_on_poll_interval)

from orchestrator import auto, config, store  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"


class Ac8aResumeAfterHolderDoneOrKilledTest(ZoneWaitSandbox):

    def _scenario(self, holder_final_state: str) -> tuple[str, mock.Mock, int, str]:
        self.reset_task()
        # `reset_task` не чистит СОБСТВЕННЫЙ журнал `self.TASK` (только
        # таблицу `tasks` конкурентов) — без этого второй прогон того же
        # `self.TASK` внутри одного теста (два подтеста `done`/`killed`)
        # унаследовал бы запись `"agent run started"` актором `developer`
        # от ПЕРВОГО прогона: `zone_lock._occupies(self.TASK)` увидела бы
        # её и решила, что `self.TASK` уже занимает СВОЮ зону, — конфликт
        # не проверялся бы вовсе, и второй подтест ложно проходил бы мимо
        # ожидания зоны (найдено валидацией стабом).
        conn = store.db()
        conn.execute("DELETE FROM steps WHERE task_id=?", (self.TASK,))
        conn.commit()
        self.set_own_zones(CONFLICT_PATH)
        # Отдельный id держателя на каждый исход (`reset_task` чистит
        # ТАБЛИЦУ `tasks` других задач, но не их историю `steps` — общий
        # id между подтестами дал бы держателю ЭТОГО прогона накопленную
        # историю ПРЕДЫДУЩЕГО подтеста и ложно считался бы уже занявшим
        # ДО собственного `mark_already_started` этого прогона; найдено
        # валидацией стабом).
        occupier = f"T9{holder_final_state[:2].upper()}"
        self.seed_task(occupier, "Занявшая зону", "in_dev", CONFLICT_PATH)
        self.mark_already_started(occupier)
        since = self.journal_len()

        def fake_sleep(seconds):
            self.set_task_state(occupier, holder_final_state)

        with mock.patch.object(config, "ZONE_WAIT_POLL_SEC", 0.001,
                              create=True), \
             mock.patch.object(config, "ZONE_WAIT_MAX_SEC", 3600,
                              create=True), \
             mock.patch.object(auto.time, "sleep",
                              side_effect=only_on_poll_interval(fake_sleep)), \
             mock.patch.object(store, "now", side_effect=fake_now_sequence()):
            out, popen = self.run_with_fake_agent(
                lambda: auto.cmd_auto(self.TASK,
                                      session_id=self.CALLER_SESSION,
                                      wait_zone=True))
        return out, popen, since, occupier

    def test_ac8_a_developer_starts_after_holder_reaches_done_or_killed(self):
        """`done` и `killed` — оба СИМВОЛ ухода держателя из блокирующего
        диапазона (уже сегодня оба вне `zone_lock.BLOCKING_STATES`,
        симметрично) — цикл `--wait-zone` обязан завершить ожидание и
        стартовать роль developer ТЕМ ЖЕ вызовом для КАЖДОГО из них, не
        только для `done`.

        Ловит мутацию: код ожидания сверяет освобождение зоны буквальным
        `holder_state == "done"` вместо переиспользования `zone_lock.
        blocking_conflict` целиком — держатель, ушедший через `kill`
        (`killed`), навсегда завис бы в ожидании (потолок остановил бы
        цикл вместо немедленного продолжения), хотя зона объективно уже
        свободна.
        """
        for holder_final_state in ("done", "killed"):
            with self.subTest(holder_final_state=holder_final_state):
                out, popen, since, occupier = self._scenario(holder_final_state)

                self.assertTrue(
                    popen.called,
                    f"развернуться после освобождения зоны обязан тем же "
                    f"вызовом: spawn_agent ни разу не вызван для "
                    f"{holder_final_state}: {out!r}")

                rows = store.task_steps(store.db(), self.TASK)[since:]
                joined = "\n".join(
                    f"{r['actor']} {r['action']} {r['detail']}"
                    for r in rows).lower()
                self.assertIn(
                    f"ждёт зоны {CONFLICT_PATH.lower()}: держит "
                    f"{occupier.lower()} (in_dev)", joined,
                    f"вход в ожидание не журналирован для держателя "
                    f"{holder_final_state}: {out!r}")
                self.assertIn(
                    "зона свободна через", joined,
                    f"выход из ожидания не журналирован для держателя "
                    f"{holder_final_state}: {out!r}")
                self.assertIn(
                    "мин", joined,
                    f"выход из ожидания не несёт длительности для "
                    f"держателя {holder_final_state}: {out!r}")
                self.assertIn(
                    "держал", joined,
                    f"выход из ожидания не называет держателя ({occupier}) "
                    f"для {holder_final_state}: {out!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
