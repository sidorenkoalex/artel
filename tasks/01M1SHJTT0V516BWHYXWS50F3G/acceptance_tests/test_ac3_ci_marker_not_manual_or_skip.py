"""AC-3: автогейт приёмки (`orchestrator/fsm_autogate.py`) не относит
критерий с пометкой `ci` к спискам `manual`/`skip`, которые сегодня
безусловно блокируют автогейт — наличие пометки `ci` само по себе
задачу на ручной гейт не отправляет (решение о ней принимает статус CI,
AC-4/AC-5, не сам факт присутствия пометки).

Красен до реализации: `_autogate_conditions` сегодня не знает про
пометку `ci` вовсе — `guard.scan_ac_content` (до реализации этой
задачи, см. AC-1) не распознаёт `ci` как валидный `kind`, и планка с
единственной пометкой `ci` читается как планка БЕЗ единой пометки —
условие «а» проходит автогейтом (`reason is None`), а не тем путём,
которого ждёт этот тест (отказ по статусу CI, но НЕ текстом
«критерии manual/skip»). Тест красный из-за отсутствия ветки CI-
проверки, не из-за случайной удачи «reason is None».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateCiMarkerSandbox, ci_only_planka  # noqa: E402


class Ac3CiMarkerNotManualOrSkipTest(AutogateCiMarkerSandbox):

    def test_ac3_ci_marker_alone_is_not_reported_as_manual_or_skip(self):
        """Планка несёт единственную пометку `# AC-2: ci` (без
        manual/skip), а CI кодовой ветки при этом недоступен (нет
        данных) — условие «а» отказывает по причине статуса CI
        (AC-5), но эта причина НЕ формулируется как «критерии manual —
        AC-2» / «критерии skip — AC-2»: пометка `ci` — отдельная
        категория, не синоним manual/skip (требование 3).

        Ловит мутацию: код, классифицирующий незнакомую/новую пометку
        как `manual` по умолчанию (например, `manual_ns = [n for n,
        (kind, _) in markers.items() if kind != "skip"]` — ловит и
        `ci` заодно) — reason содержал бы подстроку «критерии manual»,
        тест это поймает.
        """
        self.seed_planka(ci_only_planka(2))

        with self.gh_no_data():
            ok, reason = self.conditions()

        self.assertIsNotNone(
            reason, "нет данных CI — условие «а» обязано отказать")
        self.assertNotIn("критерии manual", reason)
        self.assertNotIn("критерии skip", reason)


if __name__ == "__main__":
    unittest.main()
