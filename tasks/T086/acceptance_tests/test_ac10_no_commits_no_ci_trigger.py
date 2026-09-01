"""AC-10 (tasks/T086/SPEC.md): опрос CI в цикле `verifying` не создаёт
коммитов в ветке задачи и не запускает/не перезапускает CI-проверки.

Два независимых наблюдения за одним и тем же прогоном (несколько
опросов внутри `auto`, остановленных губернатором, — не одиночный
опрос, потому что именно повторный опрос — новая механика этой задачи,
и именно она рискует «разбудить» CI лишний раз, если реализация решит
дёрнуть что-то write-приёма на каждой итерации):

- `git_spy` (`FsmTest`, наследуется через `VerifyingTest`) перехватывает
  ЛЮБОЙ `subprocess.run` git-процесса — ни один опрос не имеет права
  породить `git commit`/`git push`/любую git-подкоманду вовсе, раз
  `ci.verifying_status` только читает GitHub API (SPEC T079, требование
  5, AC-12, не тронуто этой задачей).
- `self.gh_calls` (`set_ci_dual`, `_sandbox.py`) — сырые argv каждого
  вызова `gh`; ни один опрос не имеет права содержать `rerun`/`dispatch`
  (единственные write-подкоманды `gh`, которые «будят» CI повторным
  прогоном).

Красен до реализации: `verifying` не в `STATE_ROLE` сегодня — цикл не
делает опросов вовсе, `LoopGoverned` не бросается, `assertRaises` падает
первым (то же основание, что у AC-1/AC-2/AC-5 этого набора).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto  # noqa: E402
from _sandbox import LoopGoverned, RUNNING_RUNS, VerifyingTest  # noqa: E402


class VerifyingPollDoesNotCommitOrTriggerCiTest(VerifyingTest):

    def test_ac10_repeated_polls_create_no_commits_and_no_ci_trigger(self):
        self.enter_verifying(RUNNING_RUNS, "[]")
        since_git = len(self.git_spy.calls)
        self.install_sleep_pause_governor(3)

        with self.assertRaises(LoopGoverned):
            auto.cmd_auto(self.TASK)

        self.assertEqual(
            self.git_subcommands_since(since_git), [],
            "опрос CI в verifying не имеет права звать git вовсе (не "
            "только commit/push) — ci.verifying_status только читает")

        write_verbs = [call for call in self.gh_calls
                      if "rerun" in call or "dispatch" in call]
        self.assertEqual(
            write_verbs, [],
            f"опрос CI не имеет права перезапускать проверки — среди "
            f"вызовов gh нашлись write-подкоманды: {write_verbs}")


if __name__ == "__main__":
    unittest.main()
