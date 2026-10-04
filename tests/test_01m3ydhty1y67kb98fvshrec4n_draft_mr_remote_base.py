"""Черновик запроса на слияние сверяет ветку задачи с СВЕЖЕЙ удалённой базой.

`github_adapter.ensure_draft_mr` решает «у ветки нет своих коммитов —
черновик не заводить» по голове `<base>` удалённого `origin`, полученной
свежим fetch, а не по локальной ветке `<base>` и не по ранее записанному
`refs/remotes/origin/<base>`: оба по построению отстают. База не читается —
прежнее поведение (push и `gh pr create`, инцидент при отказе), «ноль
коммитов» не додумывается. Для внешнего target сверка идёт в его клоне.

Песочница — `tests.sandbox.RealGitSandbox`: настоящий git, `origin` —
bare-репозиторий во временном каталоге (fetch локальный, сети нет).
`git push` перехватывается подменой `subprocess.run` (она же записывает
все git-вызовы), `gh` — подменой `github_adapter.ci.gh`. Число коммитов,
на которое удалённая база ушла вперёд, и число своих коммитов ветки —
случайные; зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: ensure_draft_mr считает коммиты ветки над локальной main — при отставшем пине пустая ветка «имеет коммиты» и уходит в push/gh (AC-1, AC-4), а при нечитаемом origin ветка, совпавшая с локальной main, молча пропускается вместо попытки push (AC-3).
"""
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, github_adapter, store
from tests.sandbox import RealGitSandbox

EXTERNAL = "outer"

TARGETS_YAML = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: http://localhost/artel
    base: {config.MAIN_BRANCH}
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  {EXTERNAL}:
    forge: github
    url: http://localhost/outer
    base: {config.MAIN_BRANCH}
    token_slot: outer-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def git_subcommand(cmd) -> tuple[str, str | None]:
    """(подкоманда git, путь первого `-C` или None) — сквозь ведущие `-C`."""
    if not isinstance(cmd, (list, tuple)) or not cmd or cmd[0] != "git":
        return "", None
    i, where = 1, None
    while i + 1 < len(cmd) and cmd[i] == "-C":
        where = where or cmd[i + 1]
        i += 2
    return (cmd[i] if i < len(cmd) else ""), where


class RemoteBaseSandbox(RealGitSandbox):
    """Задача в настоящем git, github-target, `origin` — локальный bare."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        self.branch = f"task/{self.TASK.lower()}-svera"
        self.calls: list = []
        self.intercept = False
        self.push_returncode = 0
        self.gh_create_returncode = 0
        self.fetch_mode = "real"
        self.count_mode = "real"
        self.gh_calls: list = []
        self.real_run = subprocess.run
        patcher = mock.patch.object(subprocess, "run", self.recording_run)
        patcher.start()
        self.addCleanup(patcher.stop)
        gh = mock.patch.object(github_adapter.ci, "gh", self.spy_gh)
        gh.start()
        self.addCleanup(gh.stop)

    # ------------------------------------------------------------ подмены

    def recording_run(self, cmd, *args, **kwargs):
        if not self.intercept:
            return self.real_run(cmd, *args, **kwargs)
        sub, where = git_subcommand(cmd)
        if sub:
            self.calls.append((list(cmd), where, kwargs.get("cwd")))
        if sub == "push":
            stderr = "" if self.push_returncode == 0 else "permission denied"
            return subprocess.CompletedProcess(list(cmd), self.push_returncode,
                                               "", stderr)
        if sub == "fetch" and self.fetch_mode == "none":
            return None
        if sub == "fetch" and self.fetch_mode == "oserror":
            raise OSError("git: исполняемый файл недоступен")
        if sub == "rev-list" and "--count" in cmd and self.count_mode == "garbage":
            return subprocess.CompletedProcess(list(cmd), 0, "нечисло\n", "")
        return self.real_run(cmd, *args, **kwargs)

    def spy_gh(self, *args, **kwargs):
        self.gh_calls.append((list(args), dict(kwargs)))
        if args[:2] == ("pr", "create") and self.gh_create_returncode != 0:
            return subprocess.CompletedProcess(list(args), 1, "",
                                               "GraphQL: отказ форджа")
        return subprocess.CompletedProcess(
            list(args), 0, "http://localhost/artel/pull/1\n", "")

    # ------------------------------------------------------------ фикстуры

    def git_in(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def commit_in(self, repo: Path, name: str) -> None:
        (repo / name).write_text(f"{name}\n", encoding="utf-8")
        self.git_in(repo, "add", name)
        self.git_in(repo, "commit", "-q", "-m", name)

    def bare(self) -> str:
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        self.git("init", "-q", "--bare", path)
        return path

    def lagging_remote_base(self, repo: Path, *, ahead: int,
                            branch_ahead_of_base: int = 0,
                            branch_behind_remote: int = 0) -> dict:
        """`origin` клона `repo` ушёл на `ahead` коммитов вперёд локальной
        `<base>`; `refs/remotes/origin/<base>` возвращён на прежнюю голову
        (отстал так же, как пин). Ветка задачи растёт от свежей головы
        удалённой базы и несёт `branch_ahead_of_base` своих коммитов; затем
        удалённая база уходит ещё на `branch_behind_remote` коммитов вперёд."""
        base = config.MAIN_BRANCH
        self.git_in(repo, "remote", "add", "origin", self.bare())
        self.git_in(repo, "push", "-q", "origin", f"{base}:{base}")
        old = self.git_in(repo, "rev-parse", base).strip()
        self.git_in(repo, "checkout", "-q", "-b", "upstream")
        for i in range(ahead):
            self.commit_in(repo, f"upstream{i}.txt")
        self.git_in(repo, "checkout", "-q", "-b", self.branch)
        for i in range(branch_ahead_of_base):
            self.commit_in(repo, f"own{i}.txt")
        self.git_in(repo, "checkout", "-q", "upstream")
        for i in range(branch_behind_remote):
            self.commit_in(repo, f"later{i}.txt")
        self.git_in(repo, "push", "-q", "origin", f"upstream:{base}")
        self.git_in(repo, "checkout", "-q", base)
        self.git_in(repo, "branch", "-q", "-D", "upstream")
        self.git_in(repo, "update-ref", f"refs/remotes/origin/{base}", old)
        state = {
            "local": self.git_in(repo, "rev-parse", base).strip(),
            "tracking": self.git_in(repo, "rev-parse",
                                    f"refs/remotes/origin/{base}").strip(),
            "branch": self.git_in(repo, "rev-parse", self.branch).strip(),
            "remote": self.git_in(repo, "ls-remote", "origin",
                                  f"refs/heads/{base}").split()[0],
        }
        self.assertEqual(state["local"], old, f"зерно: {self.seed}; фикстура")
        self.assertEqual(state["tracking"], old, f"зерно: {self.seed}; фикстура")
        return state

    def insert_task(self, target: str) -> None:
        store.insert_task(self.conn, self.TASK, "Сверка с базой", "in_dev",
                          self.branch, target, config.DEFAULT_BUDGET_USD)

    def reset_observations(self) -> None:
        store.update_task(self.conn, self.TASK, draft_mr_created=0)
        self.conn.execute("DELETE FROM steps")
        self.conn.execute("DELETE FROM alerts")
        self.conn.commit()
        self.calls.clear()
        self.gh_calls.clear()

    def ensure_draft_mr(self) -> None:
        self.intercept = True
        try:
            github_adapter.ensure_draft_mr(
                self.conn, self.TASK, store.get_task(self.conn, self.TASK))
        finally:
            self.intercept = False

    # ---------------------------------------------------------- наблюдения

    def git_calls(self, sub: str) -> list:
        return [c for c in self.calls if git_subcommand(c[0])[0] == sub]

    def pr_creates(self) -> list:
        return [a for a, _kw in self.gh_calls if a[:2] == ["pr", "create"]]

    def steps(self) -> list:
        return [(r["action"], r["detail"] or "")
                for r in store.task_steps(self.conn, self.TASK)]

    def actions(self) -> list:
        return [action for action, _detail in self.steps()]

    def skip_records(self) -> list:
        return [f"{a} {d}" for a, d in self.steps()
                if a == github_adapter.DRAFT_MR_SKIPPED_ACTION]

    def adapter_alerts(self) -> list:
        return self.conn.execute(
            "SELECT * FROM alerts WHERE source='github_adapter'").fetchall()

    def flag(self) -> int:
        return store.get_task(self.conn, self.TASK)["draft_mr_created"]

    def assert_skipped(self, where: str) -> None:
        msg = f"зерно: {self.seed}; {where}"
        self.assertEqual(self.git_calls("push"), [], msg)
        self.assertEqual(self.gh_calls, [], msg)
        self.assertEqual(self.adapter_alerts(), [], msg)
        self.assertNotIn("Draft MR FAILED", self.actions(), msg)
        self.assertEqual(self.flag(), 0, msg)
        records = self.skip_records()
        self.assertEqual(len(records), 1, f"{msg}; журнал: {self.steps()}")
        self.assertIn(f"origin/{config.MAIN_BRANCH}", records[0],
                      f"{msg}; запись пропуска не называет базу сверки")


class SelfTargetRemoteBaseTest(RemoteBaseSandbox):

    def setUp(self):
        super().setUp()
        self.insert_task(config.DEFAULT_TARGET)

    def test_ac1_empty_branch_over_fresh_remote_base_is_skipped(self):
        """Пустая ветка при отставших пине и origin-ref — пропуск без форджа.

        Сценарий: удалённая `main` ушла на случайное число коммитов вперёд
        локальной `main`, ранее записанный `refs/remotes/origin/main`
        возвращён на старую голову; ветка задачи растёт от свежей удалённой
        базы без своих коммитов (на втором входе удалённая база ещё и ушла
        дальше головы ветки). После `ensure_draft_mr` — ни push, ни `gh`, ни
        алерта `github_adapter`, `draft_mr_created` не выставлен, в журнале
        ровно одна запись `DRAFT_MR_SKIPPED_ACTION`, называющая
        `origin/main`.

        Ловит мутацию: база сверки — локальная `main` (как до задачи) или
        `refs/remotes/origin/main` без свежего fetch — у ветки
        обнаруживаются «свои» коммиты отставания, адаптер делает push и
        `gh pr create`, в журнал не пишется запись пропуска.
        """
        ahead = self.rng.randint(1, 3)
        behind = self.rng.choice((0, self.rng.randint(1, 2)))
        state = self.lagging_remote_base(self.root, ahead=ahead,
                                         branch_behind_remote=behind)
        if behind == 0:
            self.assertEqual(state["branch"], state["remote"],
                             f"зерно: {self.seed}; фикстура")

        self.ensure_draft_mr()

        self.assert_skipped(f"удалённая база впереди пина на {ahead}, "
                            f"впереди ветки на {behind}")

    def test_ac2_branch_with_own_commit_gets_a_draft_mr(self):
        """Ветка со своими коммитами над удалённой базой — черновик заводится.

        Сценарий: на нескольких случайных конфигурациях (удалённая база
        впереди пина или нет, ушла ли она дальше точки ответвления) у ветки
        есть 1–3 своих коммита над свежей удалённой базой. После
        `ensure_draft_mr` push ветки вызван, `gh pr create --draft` вызван,
        `draft_mr_created` выставлен, записи пропуска нет.

        Ловит мутацию: в подсчёте переставлены база и ветка (`rev-list
        <ветка>..<база>`) — ветка, ответвлённая от свежей базы, «не имеет
        коммитов», черновик молча пропускается и не заводится никогда.
        """
        ahead = self.rng.randint(0, 3)
        own = self.rng.randint(1, 3)
        behind = self.rng.randint(0, 2)
        self.lagging_remote_base(self.root, ahead=ahead,
                                 branch_ahead_of_base=own,
                                 branch_behind_remote=behind)

        self.ensure_draft_mr()

        msg = (f"зерно: {self.seed}; своих коммитов {own}, база впереди пина "
               f"на {ahead}, ушла дальше ветки на {behind}")
        pushes = self.git_calls("push")
        self.assertEqual(len(pushes), 1, msg)
        self.assertIn(self.branch, pushes[0][0], msg)
        self.assertEqual(len(self.pr_creates()), 1, f"{msg}; gh: {self.gh_calls}")
        self.assertIn("--draft", self.pr_creates()[0], msg)
        self.assertEqual(self.flag(), 1, msg)
        self.assertEqual(self.skip_records(), [], msg)

    def test_ac3_unreadable_remote_base_keeps_the_old_behaviour(self):
        """Удалённая база не читается — push и `gh pr create`, как до проверки.

        Сценарий: ветка без своих коммитов совпадает и с локальной `main`, и
        с `refs/remotes/origin/main` (любой из них «доказал» бы ноль
        коммитов). Удалённая база не читается одним из способов: адрес
        `origin` ведёт в несуществующий каталог (fetch отказал), git на
        fetch не ответил (`None`), запуск git на fetch упал `OSError`;
        отдельно — fetch прошёл, но число коммитов не разбирается. Для
        каждого способа — три исхода форджа: всё прошло (push, `gh pr
        create`, признак выставлен), отказ push и отказ `gh pr create`
        (`Draft MR FAILED` и инцидент `github_adapter`). Записи пропуска нет
        ни в одном случае.

        Ловит мутацию: при отказе fetch код откатывается на локальную
        `main` или на `refs/remotes/origin/main` (либо приравнивает «нет
        ответа» к нулю) — ветка, совпавшая с ними, молча пропускается: ни
        push, ни `gh`, ни инцидента, хотя база так и не прочитана.
        """
        base = config.MAIN_BRANCH
        origin = self.bare()
        self.git("remote", "add", "origin", origin)
        self.git("push", "-q", "origin", f"{base}:{base}")
        self.git("branch", "-q", self.branch, base)
        missing = f"/nonexistent/origin-{self.rng.randrange(1 << 30):x}"
        modes = [("адрес origin не существует", "url", "real"),
                 ("git на fetch не ответил", "none", "real"),
                 ("запуск git на fetch упал", "oserror", "real"),
                 ("число коммитов не читается", "real", "garbage")]
        self.rng.shuffle(modes)
        for title, fetch_mode, count_mode in modes:
            for outcome in ("ok", "push", "gh"):
                with self.subTest(base_unreadable=title, outcome=outcome):
                    self.reset_observations()
                    url = missing if fetch_mode == "url" else None
                    if url:
                        self.git("remote", "set-url", "origin", url)
                    self.fetch_mode = "real" if fetch_mode == "url" else fetch_mode
                    self.count_mode = count_mode
                    self.push_returncode = 1 if outcome == "push" else 0
                    self.gh_create_returncode = 1 if outcome == "gh" else 0
                    try:
                        self.ensure_draft_mr()
                    finally:
                        self.fetch_mode = self.count_mode = "real"
                        if url:
                            self.git("remote", "set-url", "origin", origin)
                    self.check_degraded(title, outcome)

    def check_degraded(self, title: str, outcome: str) -> None:
        msg = f"зерно: {self.seed}; {title}; исход {outcome}"
        self.assertEqual(len(self.git_calls("push")), 1,
                         f"{msg}; push не вызван: {self.steps()}")
        self.assertEqual(self.skip_records(), [], msg)
        if outcome == "push":
            self.assertEqual(self.pr_creates(), [], msg)
        else:
            self.assertEqual(len(self.pr_creates()), 1, msg)
        if outcome == "ok":
            self.assertEqual(self.flag(), 1, msg)
            self.assertEqual(self.adapter_alerts(), [], msg)
        else:
            self.assertIn("Draft MR FAILED", self.actions(), msg)
            self.assertTrue(self.adapter_alerts(), msg)
            self.assertEqual(self.flag(), 0, msg)


class ExternalTargetRemoteBaseTest(RemoteBaseSandbox):

    def test_ac4_external_target_checks_its_own_clone(self):
        """Внешний target: fetch базы и подсчёт коммитов — в его клоне.

        Сценарий: клон target'а `outer` лежит там, куда указывает
        `repo_context` (`config.PROJECTS/outer/repo`), со своим bare
        `origin`; удалённая база ушла вперёд пина клона, его
        `refs/remotes/origin/main` отстал, ветка задачи без своих коммитов
        существует только в клоне. После `ensure_draft_mr` — пропуск как в
        AC-1 (ни push, ни `gh`, ни алерта, признак не выставлен, запись
        пропуска с `origin/main`), а каждый fetch шёл с `-C <клон>`, ни один
        — в `config.ROOT`.

        Ловит мутацию: свежий fetch и подсчёт идут без `repo=` клона, то
        есть в `config.ROOT` — там нет ни `origin`, ни ветки задачи, база
        «не читается», адаптер уходит в push и `gh pr create` вместо
        пропуска, а fetch записан без `-C <клон>`.
        """
        # Клон проекта — `repo/` области проекта (ADR-0021 п.1, этап 2).
        clone = config.PROJECTS / EXTERNAL / "repo"
        clone.mkdir(parents=True)
        self.git_in(clone, "init", "-q", "-b", config.MAIN_BRANCH)
        self.git_in(clone, "config", "user.email", "artel@example.invalid")
        self.git_in(clone, "config", "user.name", "artel tests")
        self.commit_in(clone, "outer.txt")
        ahead = self.rng.randint(1, 3)
        self.lagging_remote_base(clone, ahead=ahead)
        self.insert_task(EXTERNAL)

        self.ensure_draft_mr()

        self.assert_skipped(f"внешний target, база впереди пина на {ahead}")
        fetches = self.git_calls("fetch")
        msg = f"зерно: {self.seed}; fetch-вызовы: {fetches}"
        self.assertTrue(fetches, msg)
        for cmd, where, _cwd in fetches:
            self.assertEqual(where, str(clone), msg)


if __name__ == "__main__":
    unittest.main()
