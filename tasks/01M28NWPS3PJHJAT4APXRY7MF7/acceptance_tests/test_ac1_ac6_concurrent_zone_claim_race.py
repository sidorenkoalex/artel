"""Приёмочные тесты 01M28NWPS3PJHJAT4APXRY7MF7 — AC-1, AC-6 (SPEC.md).

Два независимых задача-кандидата (`self.TASK`, `self.TASK_B`), каждый —
настоящий `catalog.cmd_new` + `in_dev` + общая зона (`_sandbox.
ZoneClaimSandbox.ZONE`), запускают `runner.cmd_run` из двух РЕАЛЬНЫХ
потоков ОС с барьером синхронизации перед самим вызовом (тот же приём,
что `tests/test_lease.py::ConcurrentAcquireTest._run_concurrently` уже
применяет к гонке `lease.acquire()`): каждый поток открывает своё
подключение к БД самим вызовом `cmd_run` (внутри которого `store.db()`),
общий только файл БД — как у двух реальных CLI-процессов `auto`.

Красен до реализации: сегодня `runner._cmd_run` проверяет
`zone_lock.blocking_conflict` и полагается на то, что занятость появится
позже — отдельным `store.journal(..., "agent run started", ...)` глубоко
внутри `run_agent_once`, после сборки промпта/брифа/скилов (те самые
секунды разнесения — SPEC «Контекст»). Между проверкой и этой записью — большое
окно реального времени (workspace/preflight/fixation/skills/brief), в
котором ОБА потока успевают пройти проверку до того, как хоть один
записал что-либо о занятости: `kinds` ниже придут `["ok", "ok"]` вместо
`["exit", "ok"]`, `spawn.call_count == 2`, ассерты AC-1/AC-6 упадут.
"""
import io
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneClaimSandbox  # noqa: E402

from orchestrator import runner  # noqa: E402
from tests.sandbox import FakeProc  # noqa: E402


class ConcurrentZoneClaimRaceTest(ZoneClaimSandbox):
    """AC-1: захват зоны атомарен с проверкой конфликта — из двух
    одновременно стартующих `cmd_run` на общей зоне ровно один реально
    запускает агента. AC-6: второй получает именованный отказ занятости
    зоны, не тихо повисает и не падает нераспознанным исключением."""

    def setUp(self):
        super().setUp()
        self.TASK_B = self.spawn_second_real_task()

    def _run_concurrently(self):
        """Оба потока синхронизированы барьером НЕПОСРЕДСТВЕННО перед
        вызовом `cmd_run` — гонка бьёт именно по проверке+записи занятости,
        не по случайному опережению одного потока на подготовке."""
        barrier = threading.Barrier(2)
        results = {}
        errors = []

        def worker(task_id):
            buf = io.StringIO()
            try:
                barrier.wait(timeout=5)
                try:
                    with redirect_stdout(buf):
                        runner.cmd_run(task_id)
                    results[task_id] = ("ok", buf.getvalue())
                except SystemExit as exc:
                    results[task_id] = ("exit", buf.getvalue() + str(exc))
            except Exception as exc:  # pragma: no cover — диагностика гонки
                errors.append((task_id, repr(exc)))

        with mock.patch.object(
                runner, "spawn_agent",
                side_effect=lambda *a, **kw: FakeProc(["готово\n"], 0)) as spawn:
            threads = [threading.Thread(target=worker, args=(tid,))
                      for tid in (self.TASK, self.TASK_B)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)

        self.assertEqual(errors, [],
                         f"поток упал незапланированным исключением: {errors}")
        self.assertEqual(set(results), {self.TASK, self.TASK_B},
                         f"не оба потока успели завершиться: {results}")
        return results, spawn

    def test_ac1_exactly_one_of_two_simultaneous_starts_spawns_the_agent(self):
        """Два `cmd_run` одной общей зоны стартуют одновременно — ровно
        один реально спавнит агента (атомарность захвата), второй не
        успевает начать код вовсе.

        Ловит мутацию: см. докстринг модуля."""
        results, spawn = self._run_concurrently()

        kinds = sorted(kind for kind, _ in results.values())
        self.assertEqual(kinds, ["exit", "ok"],
                         f"ожидался ровно один старт и один отказ занятости "
                         f"зоны, получено: {results}")
        self.assertEqual(spawn.call_count, 1,
                         f"агент реально стартовал не ровно один раз: "
                         f"{spawn.call_count} вызовов")

    def test_ac6_the_losing_candidate_gets_a_named_zone_occupancy_refusal(self):
        """Проигравший гонку кандидат получает ИМЕНОВАННЫЙ отказ занятости
        зоны (путь/id/состояние занявшей задачи), не тихий зависший вызов
        и не нераспознанное исключение — то же наблюдаемое поведение, что
        уже даёт `zone_lock.refusal` для обычного (не гоночного) конфликта.

        Ловит мутацию: см. докстринг модуля — без атомарного захвата
        второй поток тоже получает `"ok"` (реально стартовавший агент)
        вместо `"exit"` с текстом отказа."""
        results, spawn = self._run_concurrently()

        losers = [tid for tid, (kind, _) in results.items() if kind == "exit"]
        winners = [tid for tid, (kind, _) in results.items() if kind == "ok"]
        self.assertEqual(len(losers), 1, f"нет ровно одного проигравшего: {results}")
        self.assertEqual(len(winners), 1, f"нет ровно одного победителя: {results}")
        loser, winner = losers[0], winners[0]
        text = results[loser][1].lower()
        self.assertIn("занята задачей", text,
                      f"отказ проигравшего не назван именованно: {text!r}")
        self.assertIn(winner.lower(), text,
                      f"отказ не называет реально занявшую зону задачу "
                      f"{winner}: {text!r}")
        self.assertIn("in_dev", text)


if __name__ == "__main__":
    import unittest
    unittest.main()
