"""AC-5 (tasks/T073/SPEC.md): команда `prune` с явным флагом реального
исполнения удаляет из `.artel/logs/` только то, что ОДНОВРЕМЕННО старше
90 дней И выходит за пределы N последних задач, где N = 20, значение
читается из именованной константы конфига.

Интерфейс, который тест фиксирует разработчику (SPEC не называет
конкретных имён — команда `prune` называна текстом критериев, дальше
выбор реализации): модуль `orchestrator/prune.py`, функция
`cmd_prune(execute: bool = False)` (по образцу `doctor.cmd_doctor
(restore: bool = False)`, `canary.cmd_canary(tz_dir, *,
rewrite_baseline: bool = False)` — тот же стиль булева kwarg на команду
без обязательных аргументов), константа `config.LOG_RETENTION_KEEP_TASKS`
= 20 (N последних задач).

N читается ДИНАМИЧЕСКИ из `config.LOG_RETENTION_KEEP_TASKS`, не
литералом 20 (скил test-authoring, «Предпосылки о значениях
конфигурации»): фикстура строит ровно `N` задач-заполнителей в зоне
«последние N», сколько бы Оператор ни поднял N в будущем.

Порог в 90 дней в самом критерии — фиксированное число SPEC (не
«крутилка Оператора» из требования 1), поэтому взят литералом.

Красен до реализации: `orchestrator/prune.py` не существует —
`ImportError`. Это ожидаемая краснота «нет кода задачи», не дефект
теста.
"""
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

OLD_DAYS = 200  # заведомо старше 90-дневного порога критерия
RECENT_DAYS = 5  # заведомо младше порога


def _ts(days_ago: int) -> str:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%d %H:%M:%SZ")


class PruneLogsRetentionTest(TmpRootTest):
    """Полная таблица истинности условия «старше 90 дней И вне
    последних N задач» — по одной задаче на комбинацию, плюс N задач-
    заполнителей, занимающих «последние N» местами с заведомо БОЛЬШИМИ
    номерами задач, чем у задач комбинации (см. докстринг модуля)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        from orchestrator import prune  # noqa: E402  (после патчей TmpRootTest)
        self.prune = prune
        self.n = config.LOG_RETENTION_KEEP_TASKS

        # Задачи комбинации — заведомо МЕНЬШИЕ номера, чем у любого
        # заполнителя ниже, поэтому они вне «последних N» без заполнителей.
        self.old_outside = self._make_task(1, OLD_DAYS)
        self.recent_outside = self._make_task(2, RECENT_DAYS)
        # Заполнители — самые БОЛЬШИЕ номера: гарантированно вытесняют
        # old_outside/recent_outside из «последних N», не вытесняя друг
        # друга наружу (их ровно N, и это единственные N задач с
        # номерами больше filler-диапазона задач комбинации).
        filler_base = 1000
        for i in range(self.n):
            self._make_task(filler_base + i, OLD_DAYS)
        # "Последние N" по номеру задачи — старая и свежая, каждая
        # обязана уцелеть, невзирая на возраст (старая — потому что она
        # ВНУТРИ последних N, свежая — вдвойне защищена).
        self.old_inside = self._make_task(filler_base + self.n, OLD_DAYS)
        self.recent_inside = self._make_task(filler_base + self.n + 1, RECENT_DAYS)

    def _make_task(self, number: int, age_days: int):
        task_id = f"T{number:05d}"
        branch = f"task/{task_id.lower()}-x"
        store.insert_task(store.db(), task_id, f"Задача {task_id}",
                          "done", branch, config.DEFAULT_TARGET, 25.0)
        log_path = config.LOGS / f"{task_id}-analyst-1.log"
        config.LOGS.mkdir(parents=True, exist_ok=True)
        log_path.write_text("лог прогона\n", encoding="utf-8")
        mtime = time.time() - age_days * 86400
        import os
        os.utime(log_path, (mtime, mtime))
        return task_id, log_path

    def test_ac5_deletes_only_old_logs_outside_last_n_tasks(self):
        capture(self.prune.cmd_prune, True)

        old_outside_id, old_outside_path = self.old_outside
        recent_outside_id, recent_outside_path = self.recent_outside
        old_inside_id, old_inside_path = self.old_inside
        recent_inside_id, recent_inside_path = self.recent_inside

        self.assertFalse(
            old_outside_path.exists(),
            f"{old_outside_id}: лог старше 90 дней И вне последних "
            f"{self.n} задач обязан быть удалён")
        self.assertTrue(
            recent_outside_path.exists(),
            f"{recent_outside_id}: лог младше 90 дней не удаляется, "
            f"даже если задача вне последних {self.n}")
        self.assertTrue(
            old_inside_path.exists(),
            f"{old_inside_id}: лог задачи из последних {self.n} не "
            f"удаляется, даже если он старше 90 дней")
        self.assertTrue(
            recent_inside_path.exists(),
            f"{recent_inside_id}: лог младше 90 дней и внутри последних "
            f"{self.n} — защищён вдвойне")

    def test_ac5_dry_run_deletes_nothing_from_this_fixture(self):
        """Перекрёстная проверка с AC-4 на этой же требовательной
        фикстуре: dry-run (без execute) не трогает даже кандидата на
        удаление."""
        capture(self.prune.cmd_prune)

        _, old_outside_path = self.old_outside
        self.assertTrue(
            old_outside_path.exists(),
            "prune без execute не обязан ничего удалять (AC-4), даже "
            "заведомого кандидата на удаление")


if __name__ == "__main__":
    unittest.main()
