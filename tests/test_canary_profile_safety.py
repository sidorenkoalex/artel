"""Границы постоянного профиля Codex канарейки."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, doctor
from orchestrator.providers import codex as codex_provider


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

    def test_commit_without_reference_only_clears_the_profile(self):
        """Коммит без референса дома Codex: история и доверие удалены,
        отказа нет.

        Ловит мутацию: отсутствие референса снова отказывает прогон — либо
        профиль при этом не очищается и история прошлого прогона доезжает
        до следующего.
        """
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            profile = base / "profile"
            (profile / "sessions").mkdir(parents=True)
            (profile / "history.jsonl").write_text("old session")
            (profile / "config.toml").write_text('[projects."/old"]\n')
            canary._restore_canary_profile(profile, base / "no-reference")
            self.assertEqual(list(profile.iterdir()), [])


class CanaryProfileRefusalTest(unittest.TestCase):
    """Два отказа входа отдельного профиля различаются адресатом."""

    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        base = Path(root.name)
        self.pult_home = base / "pult-home"
        self.clone_home = base / "clone-home"
        self.profile = base / ".artel-canary-codex" / ".codex"
        saved_home = config.ROLE_HOME
        saved_override = codex_provider.set_codex_home_override(self.profile)
        config.ROLE_HOME = self.clone_home

        def restore():
            config.ROLE_HOME = saved_home
            codex_provider.set_codex_home_override(saved_override)

        self.addCleanup(restore)
        self.seen = []

    def refuse(self, logged_in_homes):
        def check(role):
            pair = (config.ROLE_HOME, codex_provider.codex_home_override())
            self.seen.append(pair)
            status = "ok" if pair in logged_in_homes else "fail"
            return doctor.Check("codex-chatgpt-auth", status,
                                "выполните codex login")

        with mock.patch.object(doctor, "check_codex_chatgpt_auth", check):
            with self.assertRaises(SystemExit) as refused:
                canary._refuse_unless_profile_logged_in(
                    "developer", self.pult_home, self.profile)
        return str(refused.exception)

    def test_profile_confirmed_by_pult_but_not_clone_is_pult_defect(self):
        """Профиль подтверждён окружением пульта, клоном нет — отказ
        называет дефект пульта без рецепта входа, состояние восстановлено.

        Ловит мутацию: сравнение идёт с боевым CODEX_HOME (переопределение
        снято) или ветка дефекта удалена — отказ звучит рецептом
        `codex login`, который ничего не изменит.
        """
        text = self.refuse({(self.pult_home, self.profile)})
        self.assertIn("дефект пульта", text)
        self.assertNotIn("Оператору нужен `codex login`", text)
        self.assertEqual(self.seen, [(self.clone_home, self.profile),
                                     (self.pult_home, self.profile)])
        self.assertEqual(config.ROLE_HOME, self.clone_home)
        self.assertEqual(codex_provider.codex_home_override(), self.profile)

    def test_profile_without_login_gets_login_recipe(self):
        """Профиль не подтверждён ни клоном, ни пультом — рецепт входа.

        Ловит мутацию: ветка дефекта срабатывает без подтверждения пультом
        — несделанный вход Оператора выдаётся за дефект пульта.
        """
        text = self.refuse(set())
        self.assertIn("codex login", text)
        self.assertNotIn("дефект пульта", text)


if __name__ == "__main__":
    unittest.main()
