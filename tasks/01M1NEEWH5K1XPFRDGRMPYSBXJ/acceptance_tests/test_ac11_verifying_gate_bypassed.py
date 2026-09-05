"""AC-11 (SPEC.md): прогон канареечной задачи не ждёт гейт `verifying`
(обходит ожидание CI ветки).

Требование 11/AC-11 называет это «как в v1» буквально (SPEC.md,
раздел «Требования», п.11) — v1 (`orchestrator/canary.py::
_kill_at_verifying`, `_drive_task`) не дожидается CI поллингом
(`config.VERIFYING_POLL_INTERVAL_SEC` = 90 секунд между попытками,
`orchestrator/config.py`, SPEC T086), а убивает задачу тем же приёмом,
что на `merge_gate`, — это и есть наблюдаемое свойство: если бы
верификация НЕ обходилась, законченный прогон синтетической задачи
физически не мог бы уложиться в разумное время теста (хотя бы одна
итерация опроса — уже 90 секунд). Тест меряет именно это: весь прогон
укладывается far ниже `config.VERIFYING_POLL_INTERVAL_SEC`.

Красен до реализации: `canary --k` падает на разборе аргументов
мгновенно — время прогона тривиально мало́ и эта часть теста ложно-
зелёная сама по себе, поэтому первой идёт содержательная проверка
исхода (`killed`), которая красна по отсутствию клона/задачи, не по
времени (см. первый `assertNotIn`/следующий за ним `assertGreaterEqual`
в теле теста).
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, _EphemeralDirTracker  # noqa: E402

from orchestrator import config  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
}


class VerifyingGateBypassedTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        self.tracker = _EphemeralDirTracker()
        self.tracker.start(self, deep=True)

    def test_ac11_run_finishes_fast_and_task_ends_up_killed_not_stuck_verifying(self):
        """Единственная задача пула доходит до `merge_gate`/`killed`
        (v1-семантика, `_kill_at_merge_gate`) без реального ожидания
        CI: весь прогон укладывается в разумный запас (30с — далеко
        меньше одной итерации опроса `VERIFYING_POLL_INTERVAL_SEC` =
        90с), а итоговое состояние задачи — `killed`, не `verifying`.

        Ловит мутацию: разработчик по ошибке пропускает
        `verifying`-гейт через штатный опрос `auto`/`fsm` вместо
        canary-специфичного мгновенного убийства (буквальный перенос
        генерик-цикла ожидания CI на канареечные задачи, у которых
        реального CI ветки нет и не будет, `github_adapter` их
        пропускает) — тест либо провисит явно дольше отведённого
        запаса (первая проверка), либо задача останется в `verifying`
        (вторая).
        """
        started = time.monotonic()
        out = self.run_canary_pool(1)
        elapsed = time.monotonic() - started
        self.assertNotIn("[SystemExit]", out, out)

        self.assertLess(
            elapsed, min(30.0, config.VERIFYING_POLL_INTERVAL_SEC / 2),
            f"прогон занял {elapsed:.1f}с — похоже на реальное ожидание "
            f"CI вместо обхода гейта verifying")

        clones = self.tracker.git_like_snapshots()
        self.assertGreaterEqual(len(clones), 1, self.tracker.snapshots)
        tasks = [t for s in clones for t in s.get("tasks", [])]
        self.assertEqual(len(tasks), 1, tasks)
        self.assertEqual(
            tasks[0]["state"], "killed",
            f"задача не убита в конце прогона (state={tasks[0]['state']!r}) "
            f"— возможно, застряла в verifying")


if __name__ == "__main__":
    unittest.main()
