"""Мелкие свойства механизма токена хостинга (SPEC 01M545EDTHS47HSB59AKC1EZ9C),
не покрытые долгоживущим файлом задачи: дописывание `GIT_CONFIG_*` к уже
заданным в окружении, разбор ключа `on:` workflow, сравнение адресов."""
import unittest

from orchestrator import gitcmd
from orchestrator.doctor import project_checks


class HostingEnvTest(unittest.TestCase):

    def test_appends_after_existing_git_config_entries(self):
        """`GIT_CONFIG_*` окружения Оператора сохраняются, сброс и помощник
        пульта встают следом за ними.

        Ловит мутацию: индексы помощника начинаются с 0 независимо от
        `GIT_CONFIG_COUNT` окружения — запись Оператора `KEY_0` затёрта.
        """
        base = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.pager",
                "GIT_CONFIG_VALUE_0": "cat"}
        env = gitcmd.hosting_env(base, "sekret-42")
        self.assertEqual(env["GIT_CONFIG_COUNT"], "3")
        self.assertEqual((env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]),
                         ("core.pager", "cat"))
        self.assertEqual((env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]),
                         ("credential.helper", ""))
        self.assertEqual(env["GIT_CONFIG_KEY_2"], "credential.helper")
        self.assertNotIn("sekret-42", env["GIT_CONFIG_VALUE_2"])
        self.assertEqual(env[gitcmd.HOSTING_TOKEN_ENV], "sekret-42")
        self.assertEqual(base["GIT_CONFIG_COUNT"], "1")

    def test_url_key_ignores_trailing_slash_and_git_suffix(self):
        """Адрес `origin` с `.git`/завершающей чертой — тот же проект.

        Ловит мутацию: адреса сравниваются побайтно — `…/repo.git` и
        `…/repo/` не совпадают с `…/repo` записи.
        """
        self.assertEqual(gitcmd.url_key("file:///srv/o/repo.git"),
                         gitcmd.url_key("file:///srv/o/repo/"))
        self.assertNotEqual(gitcmd.url_key("file:///srv/o/repo"),
                            gitcmd.url_key("file:///srv/o/repo2"))


class DeclaresPullRequestTest(unittest.TestCase):

    def test_exact_trigger_name_only(self):
        """`pull_request_target` и вложенный ключ `pull_request` под другим
        событием — не триггер `pull_request`; комментарий и кавычки — не
        помеха.

        Ловит мутацию: поиск подстроки `pull_request` вместо имени ключа
        первого уровня под `on:` — `pull_request_target` или вложенный ключ
        дают ok.
        """
        no = ["on: pull_request_target\n",
              "on: [push, pull_request_target]\n",
              "on:\n  push:\n    pull_request:\n      x: 1\n",
              "jobs:\n  pull_request:\n    runs-on: x\n"]
        yes = ["on: pull_request  # PR\n",
               "'on': ['push', 'pull_request']\n",
               "on:\n  push:\n    branches: [main]\n  pull_request:\n",
               "on:\n  - push\n  - pull_request\n"]
        for text in no:
            with self.subTest(text=text):
                self.assertFalse(project_checks.declares_pull_request(text))
        for text in yes:
            with self.subTest(text=text):
                self.assertTrue(project_checks.declares_pull_request(text))


if __name__ == "__main__":
    unittest.main()
