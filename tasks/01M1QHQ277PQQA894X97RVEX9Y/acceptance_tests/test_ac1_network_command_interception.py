"""AC-1 (tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md): «`TmpRootTest`-
песочница (`tests/sandbox.py`) перехватывает вызовы `fetch`/`push`/
`ls-remote`/`clone` с адресом, не являющимся локальным путём (`file://`
или абсолютный путь), и возвращает мгновенный отказ (rc≠0, stderr «сеть
в тестах запрещена: <команда> <адрес>») без обращения к сети.»

Красен до реализации: `TmpRootTest.setUp` сегодня заводит `SpyRun(
passthrough_unknown=True)` (`tests/sandbox.py:476`), который для команд
`fetch`/`push`/`ls-remote`/`clone` (не входящих в список плотницких
примитивов `SpyRun._PLUMBING_SHA`/`_PLUMBING_OK`/`rev-parse --verify`)
уходит в РЕАЛЬНЫЙ `subprocess.run` — перехвата сетевых адресов ещё нет,
так что мок `_REAL_RUN` ниже (страховка от реального сетевого вызова,
см. докстринг класса) фиксирует попытку такого вызова, и rc/stderr-
ассерты падают на пустом успешном ответе подложенного мока вместо
ожидаемого именованного отказа.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import gitcmd  # noqa: E402
from tests import sandbox  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class NetworkGitCommandsAreBlockedTest(TmpRootTest):
    """Каждая из четырёх сетевых git-подкоманд с DNS-адресом обязана
    быть перехвачена ДО реального `subprocess.run`.

    `_REAL_RUN` (`tests/sandbox.py`, страховка `SpyRun.passthrough_
    unknown`) подменяется здесь моком: если перехват ещё не реализован,
    песочница уходит в passthrough и позвала бы РЕАЛЬНЫЙ git-процесс с
    адресом, у которого нет надежды на ответ (DNS не резолвится, домен
    из зарезервированного `.example`) — подмена не даёт тесту застрять
    на реальном сетевом обращении независимо от того, реализован
    перехват или нет.
    """

    HOST = "no-such-host-ac1.invalid.example"
    URL = f"https://{HOST}/repo.git"

    CASES = (
        ("fetch", ("fetch", "-q", URL, "main")),
        ("push", ("push", "-q", URL, "refs/heads/main:refs/heads/main")),
        ("ls-remote", ("ls-remote", URL, "refs/heads/main")),
        ("clone", ("clone", URL, "/tmp/ac1-clone-dest")),
    )

    def test_ac1_fetch_push_ls_remote_clone_with_dns_address_are_blocked(self):
        """Каждая из команд fetch/push/ls-remote/clone с адресом-URL на
        DNS-имя (не `file://`, не абсолютный путь) обязана вернуться
        мгновенным именованным отказом, а не уйти в реальный git-процесс.

        Ловит мутацию: перехват фильтрует только по имени команды без
        проверки адреса (заблокировал бы и локальные адреса — регрессия
        к AC-2, которую ловит соседний файл) — здесь же проверяется, что
        КАЖДАЯ из четырёх команд именно с DNS-адресом даёт rc≠0 и точный
        текст «сеть в тестах запрещена: <команда> <адрес>»; реализация,
        отвечающая любым другим текстом или общим отказом без команды/
        адреса, эти ассерты не пройдёт.
        """
        with mock.patch.object(sandbox, "_REAL_RUN") as real_run:
            for label, args in self.CASES:
                with self.subTest(command=label):
                    res = gitcmd.git(*args)
                    self.assertNotEqual(
                        0, res.returncode,
                        f"{label}: сетевой адрес обязан отклоняться (rc≠0)")
                    self.assertIn(
                        f"сеть в тестах запрещена: {args[0]}", res.stderr,
                        f"{label}: stderr обязан называть команду и адрес")
                    self.assertIn(
                        self.URL, res.stderr,
                        f"{label}: stderr обязан включать сам адрес")
            real_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
