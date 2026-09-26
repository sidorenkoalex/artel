"""AC-1, AC-2: пары авторизации подписки стоят в ОБЕИХ половинах
изоляции — в команде шага роли на Codex и в курируемом `config.toml`
дома роли, — и сверка половин дословная и двусторонняя.

Красен до реализации: `CodexProvider.CONFIG_OVERRIDES` несёт сегодня
ровно две пары (сеть песочницы и политика подтверждений), а
`docs/reference/role-home/codex/config.toml` — ровно их же; пар
`cli_auth_credentials_store=keyring` и `forced_login_method=chatgpt`
нет ни в одной половине, поэтому оба теста ниже падают на их
отсутствии.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402


class AuthorizationOverridesTest(unittest.TestCase):
    """Обе половины одной изоляции: argv шага и курируемый конфиг."""

    def setUp(self):
        _util.stub_tool_path(self)
        self.argv = _util.codex_command("gpt-5.6-terra")
        self.overrides = _util.config_overrides(self.argv)

    def test_ac1_both_authorization_overrides_stand_before_exec_and_keep_the_old_ones(self):
        """Команда шага несёт обе пары авторизации подписки глобальными
        флагами (до `exec`), сохраняя прежние переопределения и все
        одиннадцать `--disable`.

        Ловит мутацию: пары авторизации дописаны в список флагов ПОСЛЕ
        подкоманды (там, где стоят `--json`/`--sandbox`) — 0.155.1
        разбирает глобальные флаги только до подкоманды, и шаг либо
        падает разбором аргументов, либо молча идёт с дефолтным способом
        авторизации: ключом API, которого шагу больше никто не передаёт.
        Вторая мутация того же теста: пары авторизации ДОБАВЛЕНЫ, а
        прежние (выключенная сеть песочницы, `approval_policy = never`)
        или часть `--disable` при этом вытеснены из списка.
        """
        at = self.argv.index("exec")

        for key, value in _util.AUTH_OVERRIDES:
            with self.subTest(key=key):
                self.assertTrue(_util.carries_pair(self.argv, key, value),
                                self.argv)
                self.assertEqual(self.overrides.get(key), value, self.argv)
                position = max(index for index, item in enumerate(self.argv)
                               if f"{key}={value}" in item)
                self.assertLess(position, at, self.argv)

        for key, value in _util.LEGACY_OVERRIDES:
            with self.subTest(legacy=key):
                self.assertEqual(self.overrides.get(key), value, self.argv)

        pairs = [(self.argv[i], self.argv[i + 1])
                 for i in range(len(self.argv) - 1)]
        missing = [feature for feature in _util.DISABLED_FEATURES
                   if ("--disable", feature) not in pairs]
        self.assertEqual(missing, [], self.argv)
        self.assertEqual(self.argv.count("--disable"), 11, self.argv)

    def test_ac2_curated_config_repeats_the_command_overrides_pair_for_pair_both_ways(self):
        """Курируемый `config.toml` дома роли несёт значения `keyring` и
        `chatgpt`, и множество его пар вне раздела `[features]` дословно
        совпадает с множеством `-c`-пар команды шага — в обе стороны и
        по числу пар.

        Ловит мутацию: пара дописана в одну половину и забыта (или
        переименована) в другой — например `forced_login_method` попал в
        команду шага, а `config.toml` оставлен прежним. Односторонняя
        сверка «каждая пара команды есть в файле» такую правку файла
        пропустила бы, и дом роли обещал бы вход ключом API там, где
        команда шага требует вход ChatGPT: два рубежа одной изоляции
        разъезжаются молча.
        """
        text = _util.codex_reference("config.toml").read_text(encoding="utf-8")
        pairs = _util.toml_pairs(text)

        for key, value in _util.AUTH_OVERRIDES:
            with self.subTest(key=key):
                self.assertEqual(pairs.get(key), value, pairs)

        curated = {key: value for key, value in pairs.items()
                   if not key.startswith("features.")}

        # Прямая сторона: каждая пара команды шага есть в файле.
        for key, value in sorted(self.overrides.items()):
            with self.subTest(direction="команда->файл", key=key):
                self.assertEqual(curated.get(key), value, curated)
        # Обратная сторона: каждая пара файла вне `[features]` есть в
        # команде шага, и числа пар равны.
        for key, value in sorted(curated.items()):
            with self.subTest(direction="файл->команда", key=key):
                self.assertEqual(self.overrides.get(key), value,
                                 self.overrides)
        self.assertEqual(len(self.overrides), len(curated),
                         (self.overrides, curated))


if __name__ == "__main__":
    unittest.main()
