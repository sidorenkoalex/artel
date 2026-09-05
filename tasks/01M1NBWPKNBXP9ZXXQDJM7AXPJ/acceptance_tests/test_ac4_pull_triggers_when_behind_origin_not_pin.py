"""AC-4 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Юнит-тест: ветка
задачи отстаёт от main артели на origin, но совпадает с (не отстаёт от)
локальным `config.MAIN_BRANCH` — подтяжка всё равно выполняется
(отставание обнаруживается по origin, не по пину).

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-4 (сценарий процитирован дословно).

Красен до реализации: тот же сценарий, что и test_ac1/test_ac2 — здесь
проверяется ТОЛЬКО конечный исход (`outcome == "pulled"`), без привязки
к конкретному механизму (`fetch`/аргументы merge — предмет AC-1/AC-2).
Проверено прогоном на немодифицированном коде при подготовке файла:
`outcome == "fresh"`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import OriginDivergedSandbox  # noqa: E402


class Ac4PullTriggersWhenBehindOriginNotPinTest(OriginDivergedSandbox):

    def test_ac4_behind_origin_even_with_matching_pin_still_pulls(self):
        """Ветка задачи форкнута от текущего пина (совпадает с ним);
        после этого main артели на origin уходит на один коммит вперёд
        БЕЗ движения локального пина. Отставание обязано обнаружиться
        от origin — исход сверки обязан быть `"pulled"`, не `"fresh"`.

        Ловит мутацию: `commits_behind` зовётся БЕЗ `base` (дефолт —
        локальный `config.MAIN_BRANCH`) — при совпадении ветки задачи с
        пином `behind` посчитается нулём, и исход останется `"fresh"`
        вместо `"pulled"`, хотя origin явно ушёл вперёд.
        """
        pin_before = self.local_pin_sha()
        self.advance_origin_only()
        self.assertEqual(
            self.local_pin_sha(), pin_before,
            "предпосылка теста: локальный пин не сдвинут расхождением origin")

        outcome = self.pull()

        self.assertEqual(
            outcome, "pulled",
            "ветка задачи отстаёт от origin — подтяжка обязана "
            "произойти, даже когда локальный пин её отставшей не видит")


if __name__ == "__main__":
    import unittest
    unittest.main()
