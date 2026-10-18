"""Запуск процесса места `pytest-own` (`acceptance._launch`, SPEC
01M56KCVCTW5BV9TWTH54TW9Q9, требование 3): отказ «команда профиля <имя> не
найдена» — только об отсутствующем `argv[0]`, не о несуществующем `cwd`."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import acceptance


class OwnLaunchTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="artel-launch-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_missing_cwd_is_not_a_missing_command(self):
        """Несуществующий `cwd` при существующей команде — `FileNotFoundError` как есть.

        Ловит мутацию: `_launch` переводит в `CommandNotFound` любой
        `FileNotFoundError` запуска, не сверив `exc.filename` с `argv[0]` —
        несуществующий каталог прогона назван «команда профиля … не найдена».
        """
        absent = self.tmp / "absent-dir"
        with self.assertRaises(FileNotFoundError) as caught:
            acceptance._launch([sys.executable, "-c", "pass"], absent, True)
        self.assertNotIsInstance(caught.exception, acceptance.CommandNotFound)

    def test_missing_command_named_only_for_own(self):
        """Нет `argv[0]`: у `pytest-own` — `CommandNotFound` с именем, иначе `FileNotFoundError`.

        Ловит мутацию: перевод сделан без признака `own` (у `pult-pytest`
        отказ вместо исключения) или текст отказа называет не `argv[0]` —
        тип исключения или текст расходится.
        """
        head = str(self.tmp / "absent-command")
        with self.assertRaises(acceptance.CommandNotFound) as caught:
            acceptance._launch([head], self.tmp, True)
        self.assertEqual(str(caught.exception),
                         f"команда профиля {head} не найдена")
        with self.assertRaises(FileNotFoundError):
            acceptance._launch([head], self.tmp, False)


if __name__ == "__main__":
    unittest.main()
