"""Границы постоянного профиля Codex канарейки."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary


class CanaryProfileSafetyTest(unittest.TestCase):
    def test_profile_symlink_is_refused_before_lock_file(self):
        """Ссылка на боевой каталог не получает побочных записей.

        Ловит мутацию: проверка ссылки снята — замок создаётся по адресу
        каталога, на который указывает профиль канарейки.
        """
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            pult = base / "pult-home"
            pult.mkdir()
            (base / ".artel-canary-codex").symlink_to(pult, target_is_directory=True)
            with mock.patch.object(Path, "home", return_value=base):
                with self.assertRaises(SystemExit):
                    with canary._locked_canary_profile():
                        pass
            self.assertEqual(list(pult.iterdir()), [])

    def test_file_credentials_are_preserved_and_refused(self):
        """Подготовка не читает и не удаляет файл учётных данных.

        Ловит мутацию: проверка auth.json снята — очистка профиля удаляет
        файл с токеном, и вход молча переходит на другое хранилище.
        """
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            curated = base / "reference"
            curated.mkdir()
            (curated / "config.toml").write_text("forced_login_method = 'chatgpt'")
            profile = base / "profile"
            profile.mkdir()
            credentials = profile / "auth.json"
            credentials.write_bytes(b"fixture-secret")
            with self.assertRaises(SystemExit) as refused:
                canary._restore_canary_profile(profile, curated)
            self.assertIn("auth.json", str(refused.exception))
            self.assertEqual(credentials.read_bytes(), b"fixture-secret")


if __name__ == "__main__":
    unittest.main()
