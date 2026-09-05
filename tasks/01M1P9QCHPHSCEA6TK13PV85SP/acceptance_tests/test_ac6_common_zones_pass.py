"""AC-6 (tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md): пересечение диффа с
путями из общего списка зон (`orchestrator/config.COMMON_ZONES`) не
считается нарушением по AC-1 — переход проходит, даже если этот путь
не входит в `zones` задачи.

Зелёный с рождения: сегодня гейта нет вовсе — любой дифф проходит
переход `in_dev -> review` без сверки с зонами, значит и этот сценарий
проходит уже сейчас, но по отсутствию кода, не по намеренному
поведению AC-6. После появления гейта (AC-1) тест обязан остаться
зелёным ИМЕННО потому, что COMMON_ZONES учтены как исключение (см.
«Ловит мутацию» ниже) — то же «сохранение поведения», что AC-16 в
tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/
test_ac12_ac16_capacity_gate.py.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZonesGateSandbox  # noqa: E402


class Ac6CommonZonePathIsNotAViolationTest(ZonesGateSandbox):

    def test_ac6_diff_touching_only_a_common_zone_path_passes_the_gate(self):
        """`zones` задачи не покрывает `tests/`, дифф трогает только
        файл под `tests/` (директория-маска из COMMON_ZONES) — переход
        обязан пройти в `review`, а не отказать как «вне зон».

        Ловит мутацию: сверка забыла про исключение COMMON_ZONES
        (сравнивает дифф только с `zones` задачи, не объединяя с
        общим списком) — файл под `tests/` ошибочно посчитался бы вне
        зон, и переход отказал бы вопреки AC-6. Путь под директорией
        `tests/`, не листинг `tests/` буквально, — та же семантика
        префикса «путь == зона или начинается с неё», что уже несёт
        `orchestrator/fsm_merge_gate.py` для `PROTECTED_PATHS`: тест
        ловит и упрощение до точного сравнения строк вместо префикса."""
        self.set_zones("orchestrator/store.py")

        self.advance_with_diff_files(["tests/test_added_by_developer.py"])

        self.assertEqual(
            self.state(), "review",
            "tests/test_added_by_developer.py вне объявленных zones, но "
            "внутри COMMON_ZONES ('tests/') — не нарушение (AC-6), "
            "переход обязан пройти")


if __name__ == "__main__":
    unittest.main()
