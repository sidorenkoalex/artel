"""AC-2 (SPEC 01M2ARQGY51B99YNP9PY806AN1) — примитив принимает параметр
`repo` для работы в клоне target'а (по образцу `gitcmd.in_repo`) и
убирает приватную ссылку (`git update-ref -d`) даже когда `rev-parse`
приватной ссылки отказал (`try`/`finally`) — не только на успехе.

Вход — `fsm._origin_main_sha(target_name, repo=...)` (AC-4: одно из
трёх мест, переведённых на примитив; единственное из трёх, чья
СУЩЕСТВУЮЩАЯ сигнатура уже несёт параметр `repo`, docstring
orchestrator/fsm.py:129-139) с `target_name=config.DEFAULT_TARGET` —
для self-target `_origin_main_source` не читает git/`targets.yaml`
вовсе (orchestrator/fsm.py:96-97), так что весь git-трафик теста идёт
исключительно через примитив, вызванный этим узлом. `gitcmd.in_repo`
полностью подменена: настоящего `repo` на диске нет, вызовы — только
`fetch`/`rev-parse`/`update-ref`, а `gitcmd.git` (без `-C`) обязана
остаться незвонной — `repo` задан, весь трафик обязан идти именно через
`in_repo`, не мимо него.

Красен до реализации: сегодня `_origin_main_sha` с `repo=` делает
`gitcmd.in_repo(repo, "fetch", "-q", "origin", branch)` и следом
`gitcmd.in_repo(repo, "rev-parse", "FETCH_HEAD")` — ни один из этих
вызовов не несёт рефспека `+refs/heads/<ref>:refs/artel/fetch/...`
(требуемого AC-1/AC-2), поэтому поиск такого рефспека среди аргументов
fetch-вызова не найдёт ни одного совпадения и тест упадёт именно на
этом месте, до того как дело дойдёт до проверки уборки.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, gitcmd  # noqa: E402


class Ac2RepoParamAndFinallyCleanupTest(unittest.TestCase):

    def test_ac2_repo_dispatches_via_in_repo_and_cleans_up_after_rev_parse_failure(self):
        """`repo=<клон>` обязан провести КАЖДЫЙ git-вызов примитива через
        `gitcmd.in_repo(repo, ...)`, а не `gitcmd.git`; когда `rev-parse`
        приватной ссылки отказал, ссылка всё равно убирается —
        `git update-ref -d <та же ссылка>` обязан прозвучать несмотря на
        отказ.

        Ловит мутацию: уборка ссылки написана ТОЛЬКО на успешной ветке
        (не в `finally`) — при отказе `rev-parse` вызов `update-ref -d`
        с этой же ссылкой не прозвучит, и `assertTrue(any(...))` внизу
        не найдёт его среди записанных вызовов.
        """
        target_repo = Path("/nonexistent/private-fetch-ac2-target-clone")
        calls: list[tuple] = []

        def fake_in_repo(repo, *args) -> subprocess.CompletedProcess:
            calls.append((repo, args))
            if args and args[0] == "fetch":
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args and args[0] == "rev-parse":
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    "не разрешилось (симуляция отказа)")
            if args and args[0] == "update-ref":
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

        with mock.patch.object(gitcmd, "in_repo",
                               side_effect=fake_in_repo) as in_repo_mock, \
             mock.patch.object(gitcmd, "git") as git_mock:
            sha = fsm._origin_main_sha(config.DEFAULT_TARGET, repo=target_repo)

        self.assertIsNone(sha, "rev-parse приватной ссылки отказал — "
                          "вырожденный случай, тот же, что и «git не ответил»")
        git_mock.assert_not_called()
        self.assertTrue(in_repo_mock.called)

        repos_used = {repo for repo, _ in calls}
        self.assertEqual(repos_used, {target_repo},
                         "repo обязан дойти до КАЖДОГО git-вызова примитива, "
                         "не только до fetch")

        fetch_calls = [args for repo, args in calls if args and args[0] == "fetch"]
        self.assertEqual(len(fetch_calls), 1, f"ровно один fetch: {fetch_calls}")
        refspec_candidates = [
            a for a in fetch_calls[0] if a.startswith("+refs/heads/")]
        self.assertEqual(
            len(refspec_candidates), 1,
            f"fetch обязан адресовать ветку рефспеком "
            f"+refs/heads/<ref>:refs/artel/fetch/<pid>-<uuid> "
            f"(вызов: {fetch_calls[0]})")
        private_ref = refspec_candidates[0].split(":", 1)[1]

        cleanup_calls = [args for repo, args in calls
                        if args[:1] == ("update-ref",) and "-d" in args]
        self.assertTrue(
            any(private_ref in args for args in cleanup_calls),
            f"уборка приватной ссылки {private_ref!r} обязана произойти "
            f"даже когда rev-parse отказал (try/finally); записанные "
            f"вызовы update-ref: {cleanup_calls}")


if __name__ == "__main__":
    unittest.main()
