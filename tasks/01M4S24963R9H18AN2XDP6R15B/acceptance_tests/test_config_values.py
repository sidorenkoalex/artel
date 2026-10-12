"""Значения констант справочника ядра в `orchestrator/config.py`, названные SPEC.

Группа: разовый
Красен до реализации: констант CORE_REFERENCE_* в orchestrator/config.py ещё нет — обращение к ним падает AttributeError.

Значения — крутилки Оператора: после мержа он вправе их менять, поэтому
проверка значений — факт этой задачи (разовая группа), а свойства кода,
читающего константы, проверяют долгоживущие файлы
`tests/test_<префикс задачи>_*.py` от `config`, не литералами.

Свойства критериев, проверенные долгоживущими файлами кодовой ветки:
AC-1, AC-3…AC-8 — `tests/test_01m4s24963r9h18an2xdp6r15b_generator.py`;
AC-2, AC-14 — `tests/test_01m4s24963r9h18an2xdp6r15b_cli.py`;
AC-9 — `tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py`;
AC-10…AC-13, AC-15 — `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`.
"""
import unittest

from orchestrator import config

MIB = 1024 * 1024


class CoreReferenceConfigValuesTest(unittest.TestCase):
    """Значения констант требования 4 SPEC."""

    def test_ac2_min_uses_default_is_three(self):
        """`config.CORE_REFERENCE_MIN_USES` равен 3 — умолчанию `--min-uses` по SPEC.

        Ловит мутацию: порог заведён другим значением (2 или 5) — справочник
        артели меняет состав записей против замера ТЗ.
        """
        self.assertEqual(3, config.CORE_REFERENCE_MIN_USES)

    def test_ac10_source_limits_and_deadline_have_spec_values(self):
        """Пределы чтения коммита и общий срок — значения требования 4 SPEC.

        Ловит мутацию: предел заведён в байтах вместо МиБ (`32` вместо
        `32 * 1024 * 1024`), перепутаны пределы blob и объёма или срок
        задан не 60 секунд.
        """
        expected = {
            "CORE_REFERENCE_MAX_FILES": 2000,
            "CORE_REFERENCE_MAX_SOURCE_BYTES": 32 * MIB,
            "CORE_REFERENCE_MAX_BLOB_BYTES": 1 * MIB,
            "CORE_REFERENCE_MAX_LISTING_BYTES": 64 * MIB,
            "CORE_REFERENCE_GIT_TIMEOUT_SEC": 60,
        }
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertEqual(value, getattr(config, name))


if __name__ == "__main__":
    unittest.main()
