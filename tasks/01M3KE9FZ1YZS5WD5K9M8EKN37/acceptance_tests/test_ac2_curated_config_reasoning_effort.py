"""AC-2: глубина рассуждения в образце настроек дома роли.

Красен до реализации: `docs/reference/role-home/codex/config.toml` не
несёт ключа `model_reasoning_effort` вовсе — записи с таким именем в
разборе образца нет.
"""
import unittest

import _util


class Ac2CuratedConfigTest(unittest.TestCase):
    """Образец `docs/reference/role-home/codex/config.toml`."""

    def test_ac2_reasoning_effort_is_a_top_level_key_of_the_curated_config(self):
        """Образец настроек дома роли несёт ту же глубину рассуждения,
        что и команда шага, — ключом ВЕРХНЕГО УРОВНЯ файла, а не внутри
        секции.

        Ловит мутацию: ключ записан внутри секции (дописан в конец файла
        под `[shell_environment_policy]` или заведён своей `[model]`) —
        сверка половин сличает ПОЛНЫЕ ключи с префиксом секции, и
        `model.model_reasoning_effort` образца не совпадёт с
        `model_reasoning_effort` `-c`-пары команды шага: половины
        разъезжаются, а дом роли молча остаётся без настройки.
        Наблюдаемо: у найденной записи непустое имя секции.
        """
        entries = _util.toml_entries(_util.curated_config_text())

        found = [(section, value) for section, key, value in entries
                 if key == _util.REASONING_KEY]

        self.assertTrue(
            found,
            f"ключа {_util.REASONING_KEY!r} нет в образце "
            f"{_util.curated_config_path()}")
        for section, value in found:
            with self.subTest(section=section):
                self.assertEqual(section, "", found)
                self.assertEqual(value, _util.REASONING_VALUE, found)


if __name__ == "__main__":
    unittest.main()
