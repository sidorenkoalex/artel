"""Запросы `gh` функций CI (`orchestrator/ci.py`) к репозиторию внешнего проекта.

Группа: долгоживущий
Красен до реализации: функции `ci` не принимают `repo=` клона проекта (`check_runs`, `failed_check_names`, `find_run_id`, `check_run_workflow_run`, `trigger_rerun` — TypeError), `gh api` идёт без `GH_REPO` проекта и подставной `gh` отвечает 422 «коммит не найден», вершина главной ветки проекта читается из локальной `main`, а разбора вида адреса проекта и его отказа нет.

Окружение каждого сценария: главная копия пульта — настоящий git-репозиторий
песочницы, он же клон артели; учебный внешний проект — запись `targets.yaml`
песочницы со своим `url`, `base` и `token_slot` и настоящий git-клон
`repo_context.clone_path(<имя>)`; `gh` — подставной исполняемый файл в начале
PATH, отвечающий по правилам сценария: `gh api` отвечает только при
ожидаемом `GH_REPO` (иначе — как GitHub на чужом репозитории, HTTP 422),
`gh run` — только при ожидаемом `--repo`. Каждый запуск `gh` записывается
перехватом `subprocess.run` (argv, `cwd`, `env` вызова), настоящий процесс
при этом исполняется. Токен слота — подмена связки ключей песочницы
(`keychain.token`), значение берётся тем же публичным вызовом. Сети нет:
адреса проекта — на `localhost`, `gh` подставной.

Имена, адреса и ветки — случайные на каждом запуске; зерно печатается и
входит в текст провала.
"""
import json
import os
import random
import string
import subprocess
import sys
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from orchestrator import ci, config, keychain, repo_context, targets
from tests.sandbox import RealGitSandbox, artel_target_entry

GhCall = namedtuple("GhCall", "argv cwd env")

FAKE_GH = r'''#!@PYTHON@
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
with open(os.path.join(here, "gh-rules.json"), encoding="utf-8") as f:
    rules = json.load(f)
joined = " ".join(argv)
flag = argv[argv.index("--repo") + 1] if "--repo" in argv[:-1] else None
for rule in rules:
    if rule["contains"] not in joined:
        continue
    if "gh_repo" in rule and rule["gh_repo"] != os.environ.get("GH_REPO"):
        continue
    if "repo_flag" in rule and rule["repo_flag"] != flag:
        continue
    sys.stdout.write(rule.get("stdout", ""))
    sys.stderr.write(rule.get("stderr", ""))
    sys.exit(rule.get("code", 0))
if argv[:1] == ["api"]:
    sys.stderr.write("gh: No commit found for SHA (HTTP 422)\n")
    sys.exit(1)
sys.stderr.write("gh: no fixture answer\n")
sys.exit(1)
'''

LETTERS = string.ascii_lowercase


class ProjectGhSandbox(RealGitSandbox):
    """Учебный внешний проект с клоном, подставной `gh`, запись вызовов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.name = "ucheb" + self.word(5)
        self.owner = "own" + self.word(4)
        self.repo_name = "proj" + self.word(4)
        self.slot = f"{self.name}-slot-{self.rng.randrange(100, 999)}"
        self.base = "trunk" + self.word(3)
        self.url = f"https://localhost/{self.owner}/{self.repo_name}.git"
        self.has_slot = True

        self.bin = self.root / ".artel" / "fake-bin"
        self.bin.mkdir(parents=True, exist_ok=True)
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH.replace("@PYTHON@", sys.executable),
                      encoding="utf-8")
        gh.chmod(0o755)
        self.rules: list = []
        self.flush_rules()
        os.environ["PATH"] = f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}"
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO"):
            os.environ.pop(name, None)

        self.write_targets()
        self.build_clone()
        self.artel_main = self.git("rev-parse", config.MAIN_BRANCH).strip()

    # ------------------------------------------------------------ фикстура

    def word(self, n: int) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(n))

    def sha_of(self, repo: Path, ref: str) -> str:
        return self.git("-C", str(repo), "rev-parse", ref).strip()

    def write_targets(self, url: str | None = None) -> None:
        if url is not None:
            self.url = url
        entry = (f"  {self.name}:\n    forge: github\n    url: {self.url}\n"
                 f"    base: {self.base}\n    token_slot: {self.slot}\n"
                 f"    no_paths: []\n    project_skills: []\n"
                 f"    merge_gate: operator\n")
        config.TARGETS.write_text("targets:\n" + artel_target_entry() + entry,
                                  encoding="utf-8")

    def build_clone(self) -> None:
        """Клон: `origin/<base>` на коммите A, локальные `<base>` и `main` —
        на коммите B, ветка задачи с головой H поверх B."""
        self.clone = repo_context.clone_path(self.name)
        self.clone.mkdir(parents=True)
        c = str(self.clone)
        self.git("-C", c, "init", "-q", "-b", self.base)
        self.git("-C", c, "config", "user.email", "artel@example.invalid")
        self.git("-C", c, "config", "user.name", "artel tests")
        self.git("-C", c, "commit", "-q", "--allow-empty", "-m", "A")
        self.sha_a = self.sha_of(self.clone, "HEAD")
        self.git("-C", c, "update-ref", f"refs/remotes/origin/{self.base}",
                 self.sha_a)
        self.git("-C", c, "commit", "-q", "--allow-empty", "-m", "B")
        self.sha_b = self.sha_of(self.clone, "HEAD")
        self.git("-C", c, "branch", config.MAIN_BRANCH)
        self.branch = f"task/{self.rng.randrange(10**6)}-{self.word(6)}"
        self.git("-C", c, "checkout", "-q", "-b", self.branch)
        self.git("-C", c, "commit", "-q", "--allow-empty", "-m", "H")
        self.head = self.sha_of(self.clone, "HEAD")
        self.git("-C", c, "checkout", "-q", self.base)

    def artel_branch(self) -> tuple[str, str]:
        """Ветка задачи артели в её клоне (корень песочницы) и её голова."""
        branch = f"task/{self.rng.randrange(10**6)}-artel"
        self.git("checkout", "-q", "-b", branch)
        # Своё сообщение у каждой ветки: пустые коммиты одной секунды с
        # одним текстом совпали бы по sha.
        self.git("commit", "-q", "--allow-empty", "-m", f"artel H {branch}")
        head = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)
        return branch, head

    def gh_repo(self) -> str:
        return f"{self.owner}/{self.repo_name}"

    def token(self) -> str:
        return keychain.token(self.slot)

    @contextmanager
    def without_token_slot(self):
        """`targets.load` отдаёт запись проекта без поля `token_slot`
        (поле обязательно для `targets.check`, поэтому — обёрткой чтения)."""
        real_load = targets.load

        def load():
            out = {}
            for name, entry in real_load().items():
                entry = dict(entry)
                if name == self.name:
                    entry.pop("token_slot", None)
                out[name] = entry
            return out

        with mock.patch.object(targets, "load", side_effect=load):
            yield

    # ------------------------------------------------------------- ответы gh

    def flush_rules(self) -> None:
        (self.bin / "gh-rules.json").write_text(json.dumps(self.rules),
                                                encoding="utf-8")

    def answer(self, contains: str, payload, *, artel: bool = False,
               run: bool = False) -> None:
        """Правило ответа `gh`: проект — только при `GH_REPO` проекта (`gh
        api`) либо `--repo <url>` проекта (`gh run`); артель — только без
        `GH_REPO` и без `--repo`."""
        rule = {"contains": contains,
                "stdout": payload if isinstance(payload, str)
                else json.dumps(payload)}
        if run:
            rule["repo_flag"] = None if artel else self.url
        else:
            rule["gh_repo"] = None if artel else self.gh_repo()
        self.rules.append(rule)
        self.flush_rules()

    def checks(self, sha: str, runs: list, **kw) -> None:
        self.answer(f"commits/{sha}/check-runs",
                    {"total_count": len(runs), "check_runs": runs}, **kw)

    def workflow_runs(self, sha: str, runs: list, **kw) -> None:
        self.answer(f"actions/runs?head_sha={sha}", {"workflow_runs": runs}, **kw)

    def check(self, name: str, conclusion: str = "success", suite=None,
              status: str = "completed", cid=None) -> dict:
        run = {"name": name, "status": status, "conclusion": conclusion,
               "id": cid if cid is not None else self.rng.randrange(10**6)}
        if suite is not None:
            run["check_suite"] = {"id": suite}
        return run

    # -------------------------------------------------------------- запись

    @contextmanager
    def recording(self):
        """Перехват `subprocess.run`: вызовы `gh` записываются с `cwd` и
        `env` вызова; исполняются все вызовы, как без перехвата."""
        calls: list[GhCall] = []
        real_run = subprocess.run

        def run(cmd, *args, **kwargs):
            argv = [str(a) for a in cmd] if isinstance(cmd, (list, tuple)) \
                else [str(cmd)]
            if argv and Path(argv[0]).name == "gh":
                calls.append(GhCall(argv[1:], kwargs.get("cwd"),
                                    kwargs.get("env")))
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(subprocess, "run", side_effect=run):
            yield calls

    def effective(self, call: GhCall) -> dict:
        return dict(os.environ) if call.env is None else call.env

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def assert_project_api(self, calls: list, token: str | None = "slot",
                           what: str = "") -> None:
        """Каждый `gh api`: `GH_REPO` проекта, `GH_TOKEN` — токен слота
        (или не выставлен при `token=None`), без `--repo` в argv."""
        expected_token = self.token() if token == "slot" else None
        api = [c for c in calls if c.argv[:1] == ["api"]]
        self.assertTrue(api, self.msg(f"{what}: ни одного gh api: {calls}"))
        for call in api:
            env = self.effective(call)
            self.assertEqual(env.get("GH_REPO"), self.gh_repo(), self.msg(
                f"{what}: GH_REPO вызова {call.argv} — не проект "
                f"(url {self.url})"))
            self.assertEqual(env.get("GH_TOKEN"), expected_token, self.msg(
                f"{what}: GH_TOKEN вызова {call.argv}"))
            self.assertNotIn("--repo", call.argv, self.msg(
                f"{what}: --repo в argv gh api {call.argv}"))

    def assert_project_run(self, calls: list, what: str = "") -> None:
        """Каждый `gh run`/`gh pr`: `--repo <url>` проекта и токен слота."""
        runs = [c for c in calls if c.argv[:1] in (["run"], ["pr"])]
        self.assertTrue(runs, self.msg(f"{what}: ни одного gh run/pr: {calls}"))
        for call in runs:
            self.assertIn("--repo", call.argv[:-1], self.msg(
                f"{what}: нет --repo в {call.argv}"))
            self.assertEqual(call.argv[call.argv.index("--repo") + 1], self.url,
                             self.msg(f"{what}: --repo не url проекта: "
                                      f"{call.argv}"))
            self.assertEqual(self.effective(call).get("GH_TOKEN"), self.token(),
                             self.msg(f"{what}: GH_TOKEN {call.argv}"))

    def endpoints(self, calls: list) -> list[str]:
        return [" ".join(c.argv) for c in calls]

    def assert_called(self, calls: list, fragment: str, what: str) -> None:
        self.assertTrue(any(fragment in e for e in self.endpoints(calls)),
                        self.msg(f"{what}: нет вызова «{fragment}»: "
                                 f"{self.endpoints(calls)}"))

    def url_variants(self) -> list[str]:
        path = f"{self.owner}/{self.repo_name}"
        return [f"https://localhost/{path}.git", f"https://localhost/{path}/",
                f"git@localhost:{path}.git"]


class ArtelGhUnchangedTest(ProjectGhSandbox):
    """У артели `gh` функций CI — прежние argv, окружение и `cwd`."""

    def assert_main_form(self, calls: list, expected: list, what: str) -> None:
        self.assertEqual([c.argv for c in calls], expected,
                         self.msg(f"{what}: argv gh артели"))
        for call in calls:
            self.assertIsNone(call.env, self.msg(
                f"{what}: у gh артели появилось своё окружение {call.argv}"))
            self.assertEqual(Path(call.cwd).resolve(),
                             Path(config.ROOT).resolve(),
                             self.msg(f"{what}: cwd gh артели"))
            self.assertNotIn("GH_REPO", os.environ, self.msg(what))

    def test_ac1_artel_gh_calls_keep_main_form(self):
        """Функции перечня у артели зовут `gh` ровно как на main.

        Запись внешнего проекта рядом в `targets.yaml`. Сценарии артели:
        красный `verifying_status`/`branch_status` со сверкой с вершиной
        `main` и связкой проверки с прогоном; ветка без проверок (`gh run
        list`); `accepted_full_suite`; `failed_check_names`; `find_run_id`
        при двух красных прогонах; `check_run_workflow_run`;
        `trigger_rerun` с `run_id` и с поиском прогона; `main_line_status`
        без `repo` и с `repo=config.ROOT`. Каждый вызов `gh` — argv той же
        формы, что на main (`gh api repos/{owner}/{repo}/…`, `gh run …` без
        `--repo`), без своего `env` (нет ни `GH_REPO`, ни `GH_TOKEN`) и с
        `cwd` — корнем пульта.

        Ловит мутацию: признак внешнего проекта ставится любому пути (или
        `config.ROOT` сопоставляется записи проекта) — у артели появляется
        `GH_REPO`/`GH_TOKEN` в `env` или `--repo` в argv; либо `gh api` теперь
        зовётся с другим адресом вместо `repos/{owner}/{repo}/…`.
        """
        branch, head = self.artel_branch()
        main = self.artel_main
        per = config.CI_CHECKS_PER_PAGE
        runs_per = config.CI_RUNS_PER_PAGE
        suite = self.rng.randrange(10**6)
        failed_name = "lint" + self.word(3)

        def page(sha):
            return ["api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs"
                           f"?per_page={per}&page=1"]

        def wruns(sha):
            return ["api", f"repos/{{owner}}/{{repo}}/actions/runs"
                           f"?head_sha={sha}&per_page={runs_per}"]

        self.checks(head, [self.check(failed_name, "failure", suite)], artel=True)
        self.workflow_runs(head, [
            {"id": 5001, "check_suite_id": suite, "event": "push",
             "head_branch": branch, "status": "completed",
             "conclusion": "failure"},
            {"id": 5002, "event": "pull_request", "head_branch": branch,
             "status": "completed", "conclusion": "failure"}], artel=True)
        self.checks(main, [self.check(failed_name, "failure", suite + 1)],
                    artel=True)
        self.workflow_runs(main, [{"id": 6001, "check_suite_id": suite + 1,
                                   "event": "push",
                                   "head_branch": config.MAIN_BRANCH}],
                           artel=True)
        cid = str(self.rng.randrange(10**6))
        self.answer(f"actions/jobs/{cid}", {"run_id": 7001}, artel=True)
        self.answer("run rerun", "", artel=True, run=True)
        self.answer("run watch", "", artel=True, run=True)

        scenarios = [
            ("verifying_status красный", lambda: ci.verifying_status(branch),
             [page(head), wruns(head), page(main)]),
            ("branch_status красный", lambda: ci.branch_status(branch),
             [page(head), wruns(head), page(main)]),
            ("failed_check_names", lambda: ci.failed_check_names(head),
             [page(head)]),
            ("find_run_id", lambda: ci.find_run_id(head),
             [wruns(head), page(head)]),
            ("check_run_workflow_run", lambda: ci.check_run_workflow_run(cid),
             [["api", f"repos/{{owner}}/{{repo}}/actions/jobs/{cid}"]]),
            ("trigger_rerun run_id", lambda: ci.trigger_rerun(branch, "7001"),
             [["run", "rerun", "7001"],
              ["run", "watch", "7001", "--exit-status"]]),
            ("trigger_rerun поиск", lambda: ci.trigger_rerun(branch),
             [wruns(head), page(head), ["run", "rerun", "5001", "--failed"],
              ["run", "watch", "5001", "--exit-status"]]),
            ("main_line_status", lambda: ci.main_line_status(main),
             [page(main), wruns(main)]),
            ("main_line_status repo=config.ROOT",
             lambda: ci.main_line_status(main, repo=config.ROOT),
             [page(main), wruns(main)]),
        ]
        for what, call, expected in scenarios:
            with self.subTest(сценарий=what):
                with self.recording() as calls:
                    call()
                self.assert_main_form(calls, expected, what)

        with self.subTest(сценарий="без проверок — gh run list"):
            bare_branch, bare_head = self.artel_branch()
            self.checks(bare_head, [], artel=True)
            self.answer(f"run list --branch {bare_branch}", "[]", artel=True,
                        run=True)
            with self.recording() as calls:
                ci.verifying_status(bare_branch)
            self.assert_main_form(calls, [
                page(bare_head),
                ["run", "list", "--branch", bare_branch, "--json",
                 "headBranch,status,conclusion", "--limit",
                 str(config.CI_RUN_LIST_LIMIT)]], "gh run list")

        with self.subTest(сценарий="accepted_full_suite"):
            green_branch, green_head = self.artel_branch()
            self.checks(green_head, [self.check(ci.FULL_SUITE_JOB, "success",
                                                suite + 2)], artel=True)
            self.workflow_runs(green_head, [{"id": 8001,
                                             "check_suite_id": suite + 2,
                                             "event": "push",
                                             "head_branch": green_branch}],
                               artel=True)
            with self.recording() as calls:
                ci.accepted_full_suite(green_head)
            self.assert_main_form(calls, [page(green_head), wruns(green_head)],
                                  "accepted_full_suite")

    def test_ac1_artel_calls_keep_old_substitute_form(self):
        """Подмены функций перечня прежней формы работают у артели без правки.

        Функции `ci` подменены сигнатурами, которыми их подменяют тесты
        пульта: `head_sha` как `lambda branch:`, `check_runs`/
        `failed_check_names`/`find_run_id` как `lambda sha:`, `run_list` как
        `lambda branch:`, `gh` как `(*args, timeout=None)`. Красный
        `verifying_status`/`branch_status` артели, ветка без проверок,
        `trigger_rerun` с поиском прогона и `main_line_status(…,
        repo=config.ROOT)` отрабатывают без `TypeError` и возвращают
        ожидаемый исход.

        Ловит мутацию: функции модуля зовут друг друга с явным `repo=None`
        (или `repo=` клона артели) вместо прежней формы — подмена прежней
        сигнатуры падает `TypeError: unexpected keyword argument 'repo'`.
        """
        sha = "a" * 40
        main_sha = "b" * 40
        name = "lint" + self.word(3)
        red = [{"name": name, "status": "completed", "conclusion": "failure"}]
        green = [{"name": name, "status": "completed", "conclusion": "success"}]
        state = {"runs": red}
        gh_calls = []

        def gh(*args, timeout=None):
            gh_calls.append(args)
            if args[:1] == ("api",) and "actions/runs" in args[1]:
                return subprocess.CompletedProcess(args, 0, json.dumps(
                    {"workflow_runs": [{"id": 4242, "status": "completed",
                                        "conclusion": "failure"}]}), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        patches = [
            mock.patch.object(ci, "head_sha", lambda branch: (
                main_sha if branch == config.MAIN_BRANCH else sha, "")),
            mock.patch.object(ci, "check_runs", lambda s: (
                state["runs"] if s == sha else red, "")),
            mock.patch.object(ci, "run_list", lambda branch: ([], "")),
            mock.patch.object(ci, "gh", gh),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        branch = f"task/{self.word(6)}"
        with self.subTest(функция="verifying_status"):
            outcome, note = ci.verifying_status(branch)
            self.assertEqual(outcome, ci.VERIFYING_RED, self.msg(note))
            self.assertIn("унаследован", note, self.msg(note))
        with self.subTest(функция="branch_status"):
            ok, note = ci.branch_status(branch)
            self.assertFalse(ok, self.msg(note))
        with self.subTest(функция="verifying_status без проверок"):
            state["runs"] = []
            outcome, note = ci.verifying_status(branch)
            self.assertEqual(outcome, ci.VERIFYING_NONE, self.msg(note))
            state["runs"] = red
        with self.subTest(функция="trigger_rerun"):
            with mock.patch.object(ci, "find_run_id", lambda s: ("4242", "")):
                note = ci.trigger_rerun(branch)
            self.assertTrue(ci.rerun_started(note), self.msg(note))
        with self.subTest(функция="main_line_status repo=config.ROOT"):
            with mock.patch.object(ci, "check_runs",
                                   lambda s: (green, "")):
                status = ci.main_line_status(self.artel_main, repo=config.ROOT)
            self.assertEqual(status.kind, ci.MAIN_GREEN,
                             self.msg(status.note))
        with self.subTest(функция="failed_check_names как lambda sha"):
            with mock.patch.object(ci, "failed_check_names",
                                   lambda s: ({name}, "")):
                outcome, note = ci.verifying_status(branch)
            self.assertEqual(outcome, ci.VERIFYING_RED, self.msg(note))


class ProjectGhApiTest(ProjectGhSandbox):
    """`gh api` функций перечня у внешнего проекта — `GH_REPO` и токен."""

    def scenarios(self):
        """(что, вызов, обязательный фрагмент вызова gh) — все места `gh api`."""
        clone, head, a = self.clone, self.head, self.sha_a
        suite = self.rng.randrange(10**6)
        name = "py" + self.word(4)
        self.checks(head, [self.check(name, "failure", suite)])
        self.workflow_runs(head, [
            {"id": 5101, "check_suite_id": suite, "event": "push",
             "head_branch": self.branch, "status": "completed",
             "conclusion": "failure"},
            {"id": 5102, "event": "pull_request", "head_branch": self.branch,
             "status": "completed", "conclusion": "failure"}])
        self.checks(a, [self.check(name, "failure", suite + 1)])
        self.workflow_runs(a, [{"id": 6101, "check_suite_id": suite + 1,
                                "event": "push", "head_branch": self.base}])
        cid = str(self.rng.randrange(10**6))
        self.answer(f"actions/jobs/{cid}", {"run_id": 7101})
        return [
            ("verifying_status красный",
             lambda: ci.verifying_status(self.branch, repo=clone),
             [f"commits/{head}/check-runs", f"head_sha={head}",
              f"commits/{a}/check-runs"]),
            ("branch_status красный",
             lambda: ci.branch_status(self.branch, repo=clone),
             [f"commits/{head}/check-runs", f"head_sha={head}",
              f"commits/{a}/check-runs"]),
            ("find_run_id", lambda: ci.find_run_id(head, repo=clone),
             [f"head_sha={head}", f"commits/{head}/check-runs"]),
            ("check_run_workflow_run",
             lambda: ci.check_run_workflow_run(cid, repo=clone),
             [f"actions/jobs/{cid}"]),
            ("main_line_status", lambda: ci.main_line_status(a, repo=clone),
             [f"commits/{a}/check-runs", f"head_sha={a}"]),
        ]

    def test_ac2_every_gh_api_call_carries_project_repo(self):
        """Каждый `gh api` проекта несёт `GH_REPO=<владелец>/<имя>` и токен слота.

        Три вида `url` записи: https с `.git`, https с завершающей `/`, scp
        `git@<хост>:<владелец>/<имя>.git`. Сценарии доходят до всех мест
        `gh api`: красный `verifying_status`/`branch_status` со сверкой с
        вершиной `origin/<base>` и связкой проверки с прогоном
        (`_commit_workflow_runs`), `find_run_id` при двух красных прогонах,
        `check_run_workflow_run`, `main_line_status(<sha>, repo=<клон>)` с
        упавшей проверкой. Каждый `gh api` — `GH_REPO` ровно `<владелец>/
        <имя>` (без `.git` и `/`), `GH_TOKEN` — токен слота, `--repo` в argv
        нет; каждый ожидаемый запрос сделан.

        Ловит мутацию: `GH_REPO` выводится `url_key`-ом целиком (с хостом)
        или не снимает `.git`/`/`; scp-вид не разобран; одна из функций
        (`_commit_workflow_runs`, `failed_check_names` вершины, запрос
        прогонов `find_run_id`) не получает репозиторий — у её `gh api` нет
        `GH_REPO` или он не тот; `--repo` по-прежнему дописывается к `gh api`.
        """
        for url in self.url_variants():
            self.write_targets(url)
            self.rules = []
            for what, call, fragments in self.scenarios():
                with self.subTest(url=url, сценарий=what):
                    with self.recording() as calls:
                        call()
                    for fragment in fragments:
                        self.assert_called(calls, fragment, what)
                    self.assert_project_api(calls, what=f"{url}: {what}")


class ProjectGhRunTest(ProjectGhSandbox):
    """`gh run`/`gh pr` у внешнего проекта — `--repo <url>` и токен."""

    def test_ac3_gh_run_and_pr_carry_project_url(self):
        """`gh run list`/`rerun`/`watch` и `gh pr` проекта — с `--repo <url>`.

        Ветка без проверок (`verifying_status` → `gh run list` по ветке);
        `trigger_rerun` с `run_id` (`gh run rerun`, `gh run watch`);
        `ci.gh("pr", …, repo=<url>)`. Каждый такой вызов несёт `--repo` с
        `url` записи проекта и `GH_TOKEN` — токен слота; `gh run list`
        действительно сделан.

        Ловит мутацию: `_no_checks_by_branch` зовёт `run_list(branch)` без
        адреса проекта либо `trigger_rerun` зовёт `gh run rerun/watch` без
        `--repo` — вызов идёт в репозиторий артели, `--repo` в argv нет.
        """
        self.checks(self.head, [])
        self.answer(f"run list --branch {self.branch}", "[]", run=True)
        self.answer("run rerun", "", run=True)
        self.answer("run watch", "", run=True)
        self.answer("pr view", "", run=True)
        run_id = str(self.rng.randrange(10**6))
        with self.recording() as calls:
            ci.verifying_status(self.branch, repo=self.clone)
        self.assert_called(calls, f"run list --branch {self.branch}",
                           "без проверок")
        self.assert_project_run(calls, "gh run list")
        with self.recording() as calls:
            ci.trigger_rerun(self.branch, run_id, repo=self.clone)
        self.assert_called(calls, f"run rerun {run_id}", "trigger_rerun")
        self.assert_called(calls, f"run watch {run_id}", "trigger_rerun")
        self.assert_project_run(calls, "trigger_rerun")
        with self.recording() as calls:
            ci.gh("pr", "view", self.branch, repo=self.url)
        self.assert_project_run(calls, "gh pr")


class ProjectGreenStatusTest(ProjectGhSandbox):
    """Зелёные проверки головы ветки проекта читаются у репозитория проекта."""

    def green_head(self) -> None:
        self.checks(self.head, [self.check("py" + self.word(3), "success"),
                                self.check("lint" + self.word(3), "success")])

    def test_ac4_verifying_status_green_from_project_repo(self):
        """`verifying_status` ветки проекта с зелёными проверками — `VERIFYING_GREEN`.

        Подставной `gh` знает головной коммит только при `GH_REPO` проекта
        (иначе отвечает 422, как GitHub артели на чужой коммит). Исход —
        `ci.VERIFYING_GREEN`, `note` не начинается с «голова ветки не в
        origin», запрос проверок коммита ушёл с `GH_REPO` проекта.

        Ловит мутацию: `verifying_status` не передаёт клон в `check_runs` —
        запрос идёт без `GH_REPO`, ответ 422, исход `VERIFYING_NONE` с
        «голова ветки не в origin» (инцидент sled).
        """
        self.green_head()
        with self.recording() as calls:
            outcome, note = ci.verifying_status(self.branch, repo=self.clone)
        self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))
        self.assertFalse(note.startswith(ci.HEAD_NOT_IN_ORIGIN_NOTE),
                         self.msg(note))
        self.assert_called(calls, f"commits/{self.head}/check-runs",
                           "verifying_status")
        self.assert_project_api(calls, what="verifying_status зелёный")

    def test_ac5_branch_status_green_from_project_repo(self):
        """`branch_status` ветки проекта с зелёными проверками — `True`.

        Ловит мутацию: `branch_status` спрашивает `check_runs(sha)` без
        репозитория проекта — 422, исход `False` «статус неизвестен».
        """
        self.green_head()
        with self.recording() as calls:
            ok, note = ci.branch_status(self.branch, repo=self.clone)
        self.assertTrue(ok, self.msg(note))
        self.assert_called(calls, f"commits/{self.head}/check-runs",
                           "branch_status")
        self.assert_project_api(calls, what="branch_status зелёный")


class ProjectTriggerRerunTest(ProjectGhSandbox):
    """`trigger_rerun` ветки проекта — голова в клоне, `gh` к проекту."""

    def test_ac6_trigger_rerun_addresses_project(self):
        """Повтор с `run_id` и с поиском прогона адресован репозиторию проекта.

        Ветка задачи есть только в клоне проекта (в клоне артели её нет).
        С `run_id`: `gh run rerun <id>`/`gh run watch <id>` с `--repo <url>`.
        Поиск: голова ветки — коммит клона проекта (запрос прогонов по нему,
        `gh api` с `GH_REPO` проекта), затем `rerun --failed`/`watch` с
        `--repo <url>`; итог — повтор запущен (`ci.rerun_started`).

        Ловит мутацию: `trigger_rerun` читает голову `head_sha(branch)` без
        клона — ветки нет в клоне артели, повтор «не запущен», ни одного
        вызова `gh`; либо поиск прогона (`find_run_id`) идёт без `GH_REPO`.
        """
        run_id = str(self.rng.randrange(10**6))
        self.answer("run rerun", "", run=True)
        self.answer("run watch", "", run=True)
        with self.subTest(вид="run_id задан"):
            with self.recording() as calls:
                note = ci.trigger_rerun(self.branch, run_id, repo=self.clone)
            self.assertTrue(ci.rerun_started(note), self.msg(note))
            self.assert_called(calls, f"run rerun {run_id}", "run_id")
            self.assert_project_run(calls, "run_id")
            self.assertFalse([c for c in calls if c.argv[:1] == ["api"]],
                             self.msg("поиск прогона при заданном run_id"))
        with self.subTest(вид="поиск по голове"):
            found = self.rng.randrange(10**6)
            self.workflow_runs(self.head, [{"id": found, "status": "completed",
                                            "conclusion": "failure"}])
            with self.recording() as calls:
                note = ci.trigger_rerun(self.branch, repo=self.clone)
            self.assertTrue(ci.rerun_started(note), self.msg(note))
            self.assert_called(calls, f"head_sha={self.head}", "поиск")
            self.assert_called(calls, f"run rerun {found} --failed", "поиск")
            self.assert_project_api(calls, what="поиск прогона")
            self.assert_project_run(calls, "поиск прогона")


class ProjectWithoutSlotTest(ProjectGhSandbox):
    """Запись проекта без `token_slot`: `GH_REPO` есть, `GH_TOKEN` нет."""

    def test_ac8_no_token_slot_still_sets_gh_repo(self):
        """Без `token_slot` `gh api` проекта несёт `GH_REPO`, но не `GH_TOKEN`.

        `targets.load` отдаёт запись проекта без поля. `verifying_status`
        ветки проекта (зелёные проверки): `check_runs` уходит с `GH_REPO`
        проекта, `GH_TOKEN` в окружении вызова не выставлен, `--repo` нет.

        Ловит мутацию: `GH_REPO` ставится только вместе с токеном (окружение
        вызова собирается лишь при найденном токене) — у записи без слота
        `gh api` идёт без `GH_REPO`, ответ 422.
        """
        self.checks(self.head, [self.check("py" + self.word(3), "success")])
        with self.without_token_slot():
            self.assertNotIn("token_slot", targets.target(self.name))
            with self.recording() as calls:
                outcome, note = ci.verifying_status(self.branch,
                                                    repo=self.clone)
        self.assert_called(calls, f"commits/{self.head}/check-runs",
                           "без слота")
        self.assert_project_api(calls, token=None, what="без token_slot")
        self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))


class ProjectBaseTipTest(ProjectGhSandbox):
    """Сверка с главной веткой проекта — вершина `origin/<base>` клона."""

    def test_ac9_inherited_red_uses_origin_base_tip(self):
        """Красный путь спрашивает проверки коммита A `origin/<base>`, не B.

        `base` записи — не `main`; в клоне `origin/<base>` на коммите A,
        локальные `<base>` и `main` — на коммите B. Упавшая проверка ветки
        упала и на A, и на B. `verifying_status` и `branch_status`: запрос
        `commits/<A>/check-runs` с `GH_REPO` проекта сделан, `commits/<B>/…`
        — нет; фраза «красный унаследован от …» называет sha A.

        Ловит мутацию: вершина берётся `head_sha("main", repo=клон)` или
        `head_sha(base, repo=клон)` (локальная ветка) — спрошен B, фраза
        называет B; либо литерал `main` оставлен — сверка идёт с локальной
        `main` клона.
        """
        name = "py" + self.word(4)
        self.checks(self.head, [self.check(name, "failure")])
        self.checks(self.sha_a, [self.check(name, "failure")])
        self.checks(self.sha_b, [self.check(name, "failure")])
        for what, call in (
                ("verifying_status",
                 lambda: ci.verifying_status(self.branch, repo=self.clone)[1]),
                ("branch_status",
                 lambda: ci.branch_status(self.branch, repo=self.clone)[1])):
            with self.subTest(функция=what):
                with self.recording() as calls:
                    note = call()
                self.assert_called(calls, f"commits/{self.sha_a}/check-runs", what)
                self.assertFalse(
                    any(f"commits/{self.sha_b}/" in e
                        for e in self.endpoints(calls)),
                    self.msg(f"{what}: спрошен локальный B: "
                             f"{self.endpoints(calls)}"))
                self.assert_project_api(calls, what=what)
                inherited = note.partition("красный унаследован от")[2]
                self.assertTrue(inherited, self.msg(f"{what}: нет фразы: {note}"))
                self.assertIn(self.sha_a[:8], inherited.split(";")[0],
                              self.msg(f"{what}: фраза не про A: {note}"))
                self.assertNotIn(self.sha_b[:8], note, self.msg(note))


class ProjectUrlRefusalTest(ProjectGhSandbox):
    """Адрес проекта иного вида — именованный отказ без запуска `gh`."""

    def test_ac12_unparsed_url_refuses_without_gh(self):
        """`url` не https- и не scp-вида: `gh` не запущен, отказ называет адрес.

        Виды: `ssh://git@<хост>/<владелец>/<имя>.git`, https с одним
        сегментом пути, с тремя сегментами, с пустым сегментом.
        `check_runs(sha, repo=<клон>)` возвращает `(None, причина)` — «статуса
        нет», причина называет `url` записи; подставной `gh` не запускался.

        Ловит мутацию: неразобранный адрес молча даёт вызов без `GH_REPO`
        (запрос уходит в репозиторий артели) или `GH_REPO` из первых двух
        сегментов любого адреса — `gh` запущен; либо отказ не называет адрес.
        """
        bad = [f"ssh://git@localhost/{self.owner}/{self.repo_name}.git",
               f"https://localhost/{self.repo_name}",
               f"https://localhost/{self.owner}/{self.repo_name}/{self.word(3)}",
               f"https://localhost//{self.repo_name}"]
        self.checks(self.head, [self.check("py", "success")])
        for url in bad:
            with self.subTest(url=url):
                self.write_targets(url)
                with self.recording() as calls:
                    runs, why = ci.check_runs(self.head, repo=self.clone)
                self.assertIsNone(runs, self.msg(f"{url}: статус есть: {runs}"))
                self.assertEqual(calls, [], self.msg(f"{url}: gh запущен"))
                self.assertIn(url, why, self.msg(f"{url}: отказ без адреса: "
                                                 f"{why}"))
