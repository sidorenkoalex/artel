"""AC-2, AC-3, AC-5 (tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/SPEC.md): прочие
незакоммиченные изменения worktree задачи (кроме `docs/codebase-map.md`)
фиксируются WIP-чекпоинтом по мандату роли `developer` — той же
механикой, что `orchestrator/checkpoint.py::commit_timeout_checkpoint` —
до вызова `git merge`; сам факт чекпоинта не отказывает переходу, подтяжка
main продолжается штатно.

Красен до реализации: `_pull_main_or_escalate` сегодня не коммитит ничего
в worktree задачи вовсе — фейковый git ниже симулирует WIP-файл вне
`tasks/<id>/`, который main тоже поменял (`WIP_FILE`): пока этот WIP не
закоммичен чекпоинтом, `git merge` отвечает реальным текстом git «would
be overwritten by merge», называющим `WIP_FILE` (та же механика отказа,
что и у карты в AC-1/AC-4, только источник дирта — не карта, а прочий
код). Без чекпоинта ни один `commit`-вызов не появится, `merge` продолжит
отказывать, и все три теста файла падают на `escalated` вместо `review`.
"""
import subprocess
import unittest
from unittest import mock

from _sandbox import PullCleanupSandbox  # noqa: E402
from orchestrator import acceptance, gitcmd  # noqa: E402

WIP_FILE = "orchestrator/wip_module.py"


class NonMapWipCheckpointTest(PullCleanupSandbox):

    def _side_effect(self):
        """Фейковый git: worktree задачи несёт WIP вне `tasks/<id>/` (не
        карту) — `git diff --cached --quiet` после `add -A` отвечает
        «есть застейдженный дифф» (rc=1), пока чекпоинт не закоммитит его.
        `git merge` до этого коммита отказывает реальным текстом git
        «would be overwritten by merge», называющим `WIP_FILE` (main
        тоже поменял этот путь — тот же довод, что и в сценарии карты:
        без цели, которую merge обязан переписать, дирт не мешает
        реальному git вовсе, поэтому WIP тоже должен быть «на пути»
        слияния, а не посторонним файлом)."""
        calls = []
        state = {"wip_committed": False}

        def side_effect(repo, *args):
            calls.append((repo, args))
            if repo != self.wt_path:
                resp = self._fixation_response(repo, *args)
                if resp is not None:
                    return resp
                raise AssertionError(f"неожиданный вызов вне worktree "
                                     f"задачи: repo={repo} args={args}")
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                if state["wip_committed"]:
                    return self._ok(repo, *args)
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    "error: Your local changes to the following files "
                    f"would be overwritten by merge:\n\t{WIP_FILE}\n"
                    "Please commit your changes or stash them before you "
                    "merge.\nAborting\n")
            if args[:2] == ("diff", "--name-only"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:2] == ("diff", "--cached"):
                rc = 0 if state["wip_committed"] else 1
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), rc, "", "")
            if "commit" in args:
                state["wip_committed"] = True
                return self._ok(repo, *args)
            if args == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "f" * 40 + "\n", "")
            if args[:2] == ("status", "--porcelain"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("init",):
                return self._ok(repo, *args)
            if args[:1] in (("add",), ("reset",), ("checkout",)):
                return self._ok(repo, *args)
            raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

        return calls, side_effect

    def test_ac2_non_map_wip_committed_as_checkpoint_before_pull(self):
        """Незакоммиченный WIP вне `tasks/<id>/` и вне `docs/codebase-
        map.md` обязан зафиксироваться WIP-чекпоинтом (реальным `commit`
        в worktree задачи) по мандату роли `developer`; журнал обязан
        называть чекпоинт.

        Ловит мутацию: реализация просто игнорирует прочий WIP (не
        реализует требование 2 вовсе, ограничившись только очисткой
        карты из AC-1) — в `calls` не появится ни одного `commit`-вызова
        на `self.wt_path`, и журнал не назовёт «чекпоинт».
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        wt_commit_calls = [args for repo, args in calls
                           if repo == self.wt_path and "commit" in args]
        self.assertTrue(
            wt_commit_calls,
            "нет ни одного commit-вызова в worktree задачи — WIP не "
            "зафиксирован чекпоинтом")
        journal_text = " ".join(self.journal_details()).lower()
        self.assertIn(
            "чекпоинт", journal_text,
            f"журнал обязан называть WIP-чекпоинт: {self.journal_details()}")

    def test_ac3_checkpoint_alone_does_not_escalate_the_transition(self):
        """Сам факт WIP-чекпоинта — не отказ перехода: задача с ТОЛЬКО
        таким WIP в worktree не уходит в `escalated`, подтяжка main
        продолжается обычным путём дальше (переход `in_dev -> review`
        состоится).

        Ловит мутацию: реализация ошибочно трактует непустой чекпоинт как
        причину для эскалации (например, ранний `return "escalated"`
        сразу после коммита WIP) — итоговое состояние осталось бы
        `escalated`/`in_dev`, не `review`, и вывод содержал бы
        «эскалац».
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=6), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            out = self.advance_from_in_dev()

        self.assertEqual(
            self.state(), "review",
            "сам факт WIP-чекпоинта не имеет права отказать переходу")
        combined = (out + " ".join(self.journal_details())).lower()
        self.assertNotIn("эскалац", combined)
        abort_calls = [args for repo, args in calls
                      if repo == self.wt_path and args[:1] == ("merge",)
                      and "--abort" in args]
        self.assertEqual(
            abort_calls, [],
            "подтяжка после чистого чекпоинта не должна откатывать merge")

    def test_ac5_non_map_wip_worktree_pulls_main_after_checkpoint(self):
        """Worktree с незакоммиченными изменениями кода роли `developer`
        вне `tasks/<id>/` (не считая карты) получает WIP-чекпоинт и после
        этого успешно подтягивает main без эскалации задачи — полный
        сквозной сценарий AC-5, не только сам факт коммита (AC-2) или
        отсутствие эскалации (AC-3) по отдельности.

        Ловит мутацию: чекпоинт коммитит WIP, но код после этого не
        продолжает штатную подтяжку (например, забытый ранний `return` до
        вызова `git merge`/`acceptance.run`) — `acc_run` не был бы вызван
        ровно с worktree задачи, хотя сам commit уже случился.
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.advance_from_in_dev()

        wt_commit_calls = [args for repo, args in calls
                           if repo == self.wt_path and "commit" in args]
        self.assertTrue(wt_commit_calls, "WIP обязан быть закоммичен чекпоинтом")
        self.assertEqual(
            self.state(), "review",
            "после чекпоинта подтяжка main обязана состояться штатно")
        # Правка Оператора 06.09 (amend-tests): после hotfix регрессии №14
        # (ADR-0013) контракт — `acceptance.run(tdir, code_root=<worktree>)`;
        # проверяем и каталог планки, и код ветки, как
        # tests/test_branch_freshness_gate.py.
        acc_run.assert_called_once()
        self.assertEqual(acc_run.call_args.args[0], self.wt_path / "tasks" / self.TASK)
        self.assertEqual(acc_run.call_args.kwargs.get("code_root"), self.wt_path)


if __name__ == "__main__":
    unittest.main()
