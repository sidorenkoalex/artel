"""AC-3, AC-4 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): `config.py`
несёт три именованные константы — потолок размера одного включённого
файла (131072 байт), потолок размера части пакета/diff (65536 байт,
AC-3) и потолок гейта ёмкости diff снимка (262144 байт, AC-4).

SPEC называет только ЗНАЧЕНИЯ, не имена констант (в отличие, например,
от tasks/T060/SPEC.md, требование 1, буквально называющего
`config.MAX_PARALLEL_TASKS` — здесь такой буквальной привязки нет, тот
же вырожденный случай, что разобран в tasks/T079/acceptance_tests/
test_ac9_verifying_wait_ceiling_escalates.py). Тест поэтому не хардкодит
ИМЯ константы — сканирует `config` на публичный атрибут верхнего
регистра с нужным целым значением, а имя оставляет на решение
исполнителя.

Красен до реализации: test_ac3_config_has_a_named_constant_for_the_file_cap,
..._for_the_part_cap и test_ac4_..._for_the_gate_cap — ни одна из трёх
констант в `orchestrator/config.py` сегодня не существует.

Зелёный с рождения: test_ac3_file_and_part_caps_are_distinct_constants —
сегодня оба множества имён пусты и пересечение пустых множеств пусто по
построению, тест проходит не потому что константы уже различны, а
потому что обеих ещё нет; после реализации это станет содержательной
проверкой «131072 и 65536 не могут разрешиться в одно и то же имя», и
переписывать тест под сегодняшнюю вырожденность не нужно.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

FILE_CAP_BYTES = 131072       # AC-2/AC-3 — 128 КиБ
PART_CAP_BYTES = 65536        # AC-3/AC-5/AC-9 — 64 КиБ
GATE_CAP_BYTES = 262144       # AC-4/AC-12 — 256 КиБ


def _named_int_constants(value: int) -> list[str]:
    """Имена публичных атрибутов config верхнего регистра, чьё значение —
    именно `value` и именно `int` (не `bool` — `True == 1` не в счёт)."""
    return [name for name in dir(config)
           if name.isupper() and type(getattr(config, name)) is int
           and getattr(config, name) == value]


class Ac3FileCapConstantTest(unittest.TestCase):

    def test_ac3_config_has_a_named_constant_for_the_file_cap(self):
        names = _named_int_constants(FILE_CAP_BYTES)

        self.assertTrue(names,
                        f"в config.py нет именованной константы со "
                        f"значением {FILE_CAP_BYTES} (потолок одного "
                        f"включённого файла)")


class Ac3PartCapConstantTest(unittest.TestCase):

    def test_ac3_config_has_a_named_constant_for_the_part_cap(self):
        names = _named_int_constants(PART_CAP_BYTES)

        self.assertTrue(names,
                        f"в config.py нет именованной константы со "
                        f"значением {PART_CAP_BYTES} (потолок части "
                        f"пакета/diff)")

    def test_ac3_file_and_part_caps_are_distinct_constants(self):
        file_names = set(_named_int_constants(FILE_CAP_BYTES))
        part_names = set(_named_int_constants(PART_CAP_BYTES))

        self.assertFalse(file_names & part_names,
                         "потолок файла и потолок части — два разных "
                         "числа (131072 != 65536), не могут совпасть в "
                         "одном имени")


class Ac4GateCapConstantTest(unittest.TestCase):

    def test_ac4_config_has_a_named_constant_for_the_gate_cap(self):
        names = _named_int_constants(GATE_CAP_BYTES)

        self.assertTrue(names,
                        f"в config.py нет именованной константы со "
                        f"значением {GATE_CAP_BYTES} (потолок гейта "
                        f"ёмкости diff снимка)")


if __name__ == "__main__":
    unittest.main()
