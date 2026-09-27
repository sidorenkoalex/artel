"""Юнит-тесты предусловия «в кодовой ветке есть коммит» для черновика
запроса на слияние (SPEC 01M3HP7WAXKFK3GYZ3T6HX08M0, требования 8-10).

Постоянная копия покрытия приёмочной планки задачи (`tasks/
01M3HP7WAXKFK3GYZ3T6HX08M0/acceptance_tests/`) — та планка уходит при
уборке каталога задачи, этот файл остаётся регрессией `tests/`.

Песочница — `tests/sandbox.py::RealGitSandbox`: НАСТОЯЩИЙ git-репозиторий
во временном каталоге. Заглушкой не обойтись — «есть ли в ветке коммит
относительно базы» спрашивается у локального git, и фейк отвечал бы только
заранее угаданному примитиву. Наружу не уходит ничего: `git push`
перехватывается подменой `subprocess.run` (она же считает попытки), `gh` —
подменой `github_adapter.ci.gh`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, github_adapter, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

# Адреса фикстур — loopback: инвариант 35 (docs/invariants.md) держит
# `tests/**/*.py` без DNS-имён, а проверяемое свойство (черновик заводится
# либо законно пропускается) от хоста не зависит — `url` target'а адаптер
# только хранит, а адрес запроса на слияние приходит из вывода `gh`.
TARGETS_YAML = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: http://localhost/artel
    base: {config.MAIN_BRANCH}
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class _DraftMrSandbox(RealGitSandbox):
    """Задача с кодовой веткой в настоящем git, github-target, без сети."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        self.push_calls: list = []
        self.push_returncode = 0
        self.gh_calls: list = []
        self._real_run = subprocess.run
        self.patch(gitcmd.subprocess, "run", self._recording_run)
        self.patch(github_adapter.ci, "gh", self._spy_gh)
        self.branch = f"task/{self.TASK.lower()}-shum"
        self.checkout(config.MAIN_BRANCH)
        self.checkout(self.branch, create=True)
        self.checkout(config.MAIN_BRANCH)
        store.insert_task(self.conn, self.TASK, "Шум журнала", "in_dev",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _subcommand(cmd) -> str:
        """Подкоманда git сквозь ведущие пары `-C <путь>` — тот же разбор,
        что `tests.sandbox.SpyRun.git_subcommands`."""
        if not cmd or cmd[0] != "git":
            return ""
        i = 1
        while i + 1 < len(cmd) and cmd[i] == "-C":
            i += 2
        return cmd[i] if i < len(cmd) else ""

    def _recording_run(self, cmd, *args, **kwargs):
        if self._subcommand(cmd) == "push":
            self.push_calls.append(list(cmd))
            stderr = "" if self.push_returncode == 0 else "permission denied"
            return subprocess.CompletedProcess(list(cmd),
                                              self.push_returncode, "", stderr)
        return self._real_run(cmd, *args, **kwargs)

    def _spy_gh(self, *args, **kwargs):
        self.gh_calls.append(list(args))
        return subprocess.CompletedProcess(
            list(args), 0, "http://localhost/artel/pull/1\n", "")

    # ------------------------------------------------------------ фикстуры

    def commit_on_branch(self) -> None:
        """Один коммит в кодовой ветке; рабочая копия возвращается на базу —
        сценарии не зависят от того, какая ветка под HEAD."""
        self.checkout(self.branch)
        (self.root / f"{self.TASK}.txt").write_text("работа\n", encoding="utf-8")
        self.git("add", f"{self.TASK}.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: правка")
        self.checkout(config.MAIN_BRANCH)

    def ensure_draft_mr(self) -> None:
        github_adapter.ensure_draft_mr(self.conn, self.TASK,
                                       store.get_task(self.conn, self.TASK))

    # ---------------------------------------------------------- наблюдения

    def actions(self) -> list:
        return [r["action"] for r in store.task_steps(self.conn, self.TASK)]

    def flag(self) -> int:
        return store.get_task(self.conn, self.TASK)["draft_mr_created"]

    def adapter_alerts(self) -> list:
        return [r["message"] for r in store.open_alerts(self.conn)
                if r["source"] == "github_adapter"]

    def pr_creates(self) -> list:
        return [call for call in self.gh_calls if call[:2] == ["pr", "create"]]


class EnsureDraftMrOnAnEmptyBranchTest(_DraftMrSandbox):
    """Требование 8: локальная проверка коммитов ДО обращения к GitHub."""

    def test_empty_branch_skips_github_without_an_incident(self):
        """Ветка заведена от базы и пуста: ни push, ни `gh`, ни алерта —
        запись журнала обычного уровня, признак «черновик заведён» не
        выставлен (следующий переход попробует снова).

        Ловит мутацию: проверка коммитов стоит ПОСЛЕ публикации ветки или
        после `gh pr create` — push на пустой ветке всё равно случится,
        GitHub ответит «No commits between», и вместо тихого пропуска в
        журнале снова окажется `Draft MR FAILED` с открытым инцидентом.
        """
        self.ensure_draft_mr()

        self.assertEqual(self.push_calls, [])
        self.assertEqual(self.gh_calls, [])
        self.assertEqual(self.adapter_alerts(), [])
        self.assertIn(github_adapter.DRAFT_MR_SKIPPED_ACTION, self.actions())
        self.assertNotIn("Draft MR FAILED", self.actions())
        self.assertEqual(self.flag(), 0)

    def test_a_commit_makes_the_draft_mr_appear(self):
        """Тот же узел на той же ветке после первого коммита заводит
        черновик — пропуск отложил заведение, а не отменил его.

        Ловит мутацию: пропуск выставляет `draft_mr_created` (или ставит
        крест на ветке иначе) — черновик не завёлся бы уже никогда.
        """
        self.ensure_draft_mr()
        self.commit_on_branch()

        self.ensure_draft_mr()

        self.assertEqual(len(self.pr_creates()), 1, self.gh_calls)
        self.assertIn("--draft", self.pr_creates()[0])
        self.assertEqual(self.flag(), 1)
        self.assertIn("Draft MR заведён", self.actions())

    def test_a_failing_push_with_a_commit_is_still_an_incident(self):
        """Требование 10: отказ push при НАЛИЧИИ коммита остаётся
        инцидентом `github_adapter`, как сегодня.

        Ловит мутацию: пропуск написан шире критерия «нет коммитов» (любой
        отказ, git не ответил, база не прочитана) — настоящие сбои сети и
        прав превратились бы в тихую запись о пропуске, и пульт ослеп бы к
        отказам публикации.
        """
        self.commit_on_branch()
        self.push_returncode = 1

        self.ensure_draft_mr()

        self.assertEqual(len(self.push_calls), 1, self.push_calls)
        self.assertIn("Draft MR FAILED", self.actions())
        self.assertTrue(self.adapter_alerts())
        self.assertEqual(self.flag(), 0)

    def test_git_without_an_answer_keeps_the_pre_task_behaviour(self):
        """Локальный git не ответил числом — прежнее поведение (попытка
        публикации), не пропуск: «нет ответа» не значит «нет коммитов».

        Ловит мутацию: `None` приравнен к нулю — на любой машине/песочнице,
        где `rev-list` не отвечает разборчиво, черновики перестали бы
        заводиться вовсе, и отказ был бы молчаливым.
        """
        self.commit_on_branch()

        with mock.patch.object(github_adapter.gitcmd, "commits_behind",
                               lambda *a, **kw: None):
            self.ensure_draft_mr()

        self.assertEqual(len(self.push_calls), 1, self.push_calls)
        self.assertEqual(self.flag(), 1)


class DraftMrAtTheVerifyingRubiconTest(_DraftMrSandbox):
    """Требование 9: рубеж `in_dev -> verifying` (`ensure_head_in_origin`,
    его зовёт `advance_gates/tests_writing.py::_origin_push_gate`) не
    оставляет задачу без запроса на слияние."""

    def test_publishing_the_head_opens_the_draft_mr(self):
        """Ветка на входе в `in_dev` была пуста (черновик законно
        пропущен), коммит появился позже — публикация головы на рубеже
        заводит черновик.

        Ловит мутацию: заведение черновика подключено только к входу в
        `in_dev` — на прямом пути без возвратов задача уходила бы в
        `verifying` вовсе без запроса на слияние, при этом запись перехода
        обещала бы «MR готов» (наблюдение 27.09).
        """
        self.ensure_draft_mr()
        self.assertEqual(self.flag(), 0, "фикстура: на пустой ветке пропуск")
        self.commit_on_branch()
        self.gh_calls.clear()

        ok, detail = github_adapter.ensure_head_in_origin(
            self.conn, self.TASK, self.branch)

        self.assertTrue(ok, detail)
        self.assertEqual(len(self.pr_creates()), 1, self.gh_calls)
        self.assertEqual(self.flag(), 1)
        self.assertEqual(self.adapter_alerts(), [])

    def test_a_branch_identical_to_the_base_wakes_nobody(self):
        """Голова ветки совпала с головой базы — будить адаптер незачем, и
        рубеж не трогает ни `gh`, ни признак задачи, ни журнал.

        Ловит мутацию: сверка `head == база` в хуке снята, и узел черновика
        зовётся на каждой успешной публикации без разбора. До форджа дело
        и тогда не дойдёт — авторитетную сверку несёт сама
        `ensure_draft_mr`, — но каждый approve `merge_gate`, куда
        `ensure_head_in_origin` приходит на КАЖДЫЙ визит, начнёт дописывать
        в журнал `Draft MR пропущен: в ветке нет коммитов`: ровно тот
        механический повтор, который эта задача и лечит.
        """
        ok, detail = github_adapter.ensure_head_in_origin(
            self.conn, self.TASK, self.branch)

        self.assertTrue(ok, detail)
        self.assertEqual(self.gh_calls, [])
        self.assertEqual(self.flag(), 0)
        self.assertNotIn(github_adapter.DRAFT_MR_SKIPPED_ACTION,
                         self.actions())

    def test_an_already_created_draft_mr_is_not_created_twice(self):
        """Идемпотентность колонки `draft_mr_created` рубежом не нарушена.

        Ловит мутацию: новый вызов обходит проверку признака (например
        зовёт `gh pr create` напрямую) — каждый approve `merge_gate` плодил
        бы новый запрос на слияние.
        """
        self.commit_on_branch()
        store.update_task(self.conn, self.TASK, draft_mr_created=1)

        github_adapter.ensure_head_in_origin(self.conn, self.TASK, self.branch)

        self.assertEqual(self.pr_creates(), [])


if __name__ == "__main__":
    unittest.main()
