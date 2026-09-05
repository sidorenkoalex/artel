"""Красен до реализации: сегодня `acceptance.materialize_from_branch`
пишет ВСЕГДА в свежий `tempfile.mkdtemp()` — устаревшая копия планки,
осевшая на штатном пути рабочего каталога кода задачи (например, от
предыдущего ручного прогона Оператора по протоколу на время бага, SPEC
«Не входит») никогда не встречается материализацией и продолжает
портить прогон. После правки (AC-1: материализация НА МЕСТЕ, поверх
устаревшей копии — тот же приём, что `artifact_branch.materialize_task_dir`
уже применяет к `tasks/<id>/` целиком) устаревший файл заменяется
содержимым текущей головы артефактной ветки, и прогон после подтяжки
(AC-4) видит только актуальную планку — путь тот же самый, что использует
любая другая точка (AC-1/AC-2/AC-4 общий узел).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (MARKER_TEST_VIA_FILE, MarkerPullSandbox,  # noqa: E402
                      STALE_TEST)
from orchestrator import workspace  # noqa: E402


class Ac8StaleOverlayTest(MarkerPullSandbox):

    def seed_stale_copy_on_disk(self) -> None:
        """Кладёт `test_stale.py` (заведомо падающий) прямо на диск по
        штатному пути `tasks/<id>/acceptance_tests/` рабочего каталога
        кода задачи — ДО подтяжки, без коммита ни в одну ветку: симулирует
        осевший от предыдущего прогона файл, которого артефактная ветка
        уже не несёт (реальный источник — SPEC «Не входит»: протокол
        ручного прогона планки Оператором в worktree до мержа этой
        задачи; здесь важен только сам факт «стухшая копия на диске»,
        не то, откуда она взялась)."""
        wt_path, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error, f"worktree не заведён: {error}")
        stale_dir = wt_path / "tasks" / self.TASK / "acceptance_tests"
        stale_dir.mkdir(parents=True, exist_ok=True)
        (stale_dir / "test_stale.py").write_text(STALE_TEST, encoding="utf-8")

    def test_ac8_stale_copy_is_replaced_and_pull_uses_the_same_materialized_path(self):
        """Устаревшая копия (`test_stale.py`, заведомо падающая) на диске —
        артефактная ветка несёт ДРУГОЕ содержимое (только зелёный
        `test_via_file.py`, маркер кода ветки задачи). Подтяжка main
        (AC-4) обязана: (1) заменить содержимое по штатному пути стухшим
        файлом больше не пахнет — `test_stale.py` убран; (2) прогнать
        актуальную планку зелёным, не запнувшись о стухший файл.

        Ловит мутацию: материализация продолжает писать в `tempfile.
        mkdtemp()` (или иначе игнорирует уже существующий каталог на
        штатном пути) — устаревший `test_stale.py` никогда не убирается
        (файл остаётся на диске после прогона) и/или продолжает
        участвовать в СЛЕДУЮЩЕМ прогоне того же пути, если материализация
        когда-нибудь начнёт писать туда же, не заменяя.
        """
        self.seed_stale_copy_on_disk()
        self.commit_marker_plank({"test_via_file.py": MARKER_TEST_VIA_FILE})

        outcome = self.pull()

        self.assertEqual(
            outcome, "pulled",
            f"актуальная (зелёная) планка обязана перевесить устаревшую "
            f"стухшую копию; журнал: {self.journal_details()}")
        stale_path = self.materialized_acceptance_dir() / "test_stale.py"
        self.assertFalse(
            stale_path.exists(),
            f"устаревший файл {stale_path}, отсутствующий в текущей "
            f"голове артефактной ветки, обязан быть убран материализацией")
        fresh_path = self.materialized_acceptance_dir() / "test_via_file.py"
        self.assertTrue(
            fresh_path.is_file(),
            f"актуальный файл ветки обязан оказаться по тому же "
            f"материализованному пути: {fresh_path}")


if __name__ == "__main__":
    unittest.main()
