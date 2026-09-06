"""AC-9 (SPEC.md), вторая половина: `prune` применяет к содержимому
`.artel/canary/` тот же порог давности (`config.LOG_RETENTION_DAYS`,
`docs/retention.md`), что и к `.artel/logs/`.

Использует `tests/sandbox.py::TmpRootTest` — общую песочницу путей
`config` (уже используемую юнит-тестами `orchestrator/prune.py`,
`tests/test_prune.py`), не копию: этот файл только читает её, не
правит.

Красен до реализации: `orchestrator/prune.py` сегодня знает только про
`config.LOGS` (`_log_candidates`) — старый файл под `.artel/canary/`
после `prune --execute` остаётся на месте, `assertFalse(old_file.
exists())` падает.
"""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, prune  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


def _age_file(path: Path, age_days: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("диагностика канарейки\n", encoding="utf-8")
    mtime = time.time() - age_days * 86400
    os.utime(path, (mtime, mtime))


class PruneCanaryDiagRetentionTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

    def _diag_file(self, run_stamp: str, task_id: str) -> Path:
        return (config.ROOT / ".artel" / "canary" / run_stamp / task_id
               / "steps.txt")

    def test_ac9_old_canary_diagnostics_are_removed_by_execute(self):
        """Файл диагностики старше `config.LOG_RETENTION_DAYS` (динамически
        от config, не литералом 90 — тот же принцип, что и у `.artel/
        logs/`) убирается `prune --execute`, ровно как убрался бы
        одноимённо старый файл `.artel/logs/`.

        Ловит мутацию: `prune._log_candidates`/`cmd_prune` остаются
        нетронутыми, зная только про `config.LOGS` — старый файл под
        `.artel/canary/` переживает `prune --execute` без единого
        предупреждения об этом в отчёте.
        """
        old = self._diag_file("20200101T000000Z", "T00001")
        _age_file(old, config.LOG_RETENTION_DAYS + 1)

        capture(prune.cmd_prune, True)

        self.assertFalse(
            old.exists(),
            f"старая диагностика канарейки не убрана prune --execute: {old}")

    def test_ac9_fresh_canary_diagnostics_survive_execute(self):
        """Свежий файл диагностики (моложе порога) переживает `prune
        --execute` — тот же принцип двойного порога, что и у `.artel/
        logs/` (докстринг `orchestrator/prune.py`): свежий не удаляется
        никогда.

        Ловит мутацию: разработчик убирает ВЕСЬ каталог `.artel/
        canary/` безусловно (по аналогии с «раз в принципе можно
        убирать — убираем всё»), не проверяя возраст, — свежий файл
        пропал бы вместе со старым.
        """
        fresh = self._diag_file("20260101T000000Z", "T00002")
        _age_file(fresh, 1)

        capture(prune.cmd_prune, True)

        self.assertTrue(
            fresh.exists(),
            f"свежая диагностика канарейки убрана prune --execute "
            f"вопреки порогу давности: {fresh}")

    def test_ac9_dry_run_does_not_remove_old_canary_diagnostics(self):
        """Без `--execute` (dry-run, поведение по умолчанию) старая
        диагностика канарейки остаётся на месте — план, не исполнение,
        тот же принцип, что и у `.artel/logs/`.

        Ловит мутацию: разработчик подключает `.artel/canary/` к
        исполнению задом наперёд (удаляет уже на dry-run, не дожидаясь
        `execute=True`).
        """
        old = self._diag_file("20200101T000000Z", "T00003")
        _age_file(old, config.LOG_RETENTION_DAYS + 1)

        capture(prune.cmd_prune)

        self.assertTrue(
            old.exists(),
            f"dry-run prune удалил диагностику канарейки без --execute: {old}")


if __name__ == "__main__":
    unittest.main()
