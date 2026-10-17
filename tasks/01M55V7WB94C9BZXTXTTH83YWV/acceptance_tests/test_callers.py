"""Вызывающие функции CI: `ci-rerun` и ре-ран гейта мержа у артели и у внешнего проекта.

Группа: разовый
Красен до реализации: `ci_rerun.py` и `fsm_merge_gate.py` не передают клон проекта в `check_run_workflow_run`/`failed_check_names`/`trigger_rerun`/`fsm._origin_main_sha` (их `gh` идёт в репозиторий артели, подставной `gh` отвечает 422), а запись `flake-rate` при незапущенном повторе называет красный «подтверждённым», зелёный — «флейком».

Файл разовый по вынужденной причине: критерии называют закрытые узлы
(`fsm._origin_main_sha`, `fsm_merge_gate._ci_confirm_red_or_flake`), а
долгоживущему файлу `tests/` закрытые имена недоступны; к тому же AC-1
здесь сверяет факт этой задачи — перечисленные в SPEC файлы подмен `tests/`
не тронуты её диффом (`changed_paths()` помощника пульта). Свойства самих
функций `ci` держит долгоживущий файл задачи в `tests/`.

Окружение: главная копия пульта — настоящий git-репозиторий песочницы
(`RealGitSandbox`), он же клон артели; учебный внешний проект — запись
`targets.yaml` песочницы (`url` на `localhost`, своя `base`, `token_slot`) и
настоящий git-клон `repo_context.clone_path(<имя>)`; `gh` — подставной
исполняемый файл в PATH: `gh api` отвечает только при ожидаемом `GH_REPO`,
`gh run` — только при ожидаемом `--repo` (иначе 422 / отказ). Запуски `gh`
перехватываются подменой `subprocess.run` (argv, `cwd`, `env`) и
исполняются как есть.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import changed_paths  # noqa: E402

from orchestrator import (ci, ci_rerun, config, fsm, fsm_merge_gate,  # noqa: E402
                          keychain, repo_context, store)
from tests.sandbox import RealGitSandbox, artel_target_entry  # noqa: E402

GhCall = namedtuple("GhCall", "argv cwd env")
LETTERS = string.ascii_lowercase
REASON = "флейк на прогоне push"

# Файлы с подменами функций перечня прежней формы (SPEC, требование 2).
SUBSTITUTE_FILES = (
    "tests/test_invariants.py",
    "tests/test_ci_status.py",
    "tests/test_main_ci_line.py",
    "tests/test_merge_gate_ci_wait.py",
    "tests/test_ci_rerun_command.py",
    "tests/test_ci_stuck_check_run.py",
    "tests/test_main_ci_fetched_repo.py",
    "tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py",
)

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
    sys.exit(rule.get("code", 0))
if argv[:1] == ["api"]:
    sys.stderr.write("gh: No commit found for SHA (HTTP 422)\n")
    sys.exit(1)
sys.stderr.write("gh: no fixture answer\n")
sys.exit(1)
'''


def page(sha: str) -> list:
    return ["api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs"
                   f"?per_page={config.CI_CHECKS_PER_PAGE}&page=1"]


def wruns(sha: str) -> list:
    return ["api", f"repos/{{owner}}/{{repo}}/actions/runs"
                   f"?head_sha={sha}&per_page={config.CI_RUNS_PER_PAGE}"]


def red_note(sha: str) -> str:
    return f"CI коммита {sha[:8]} не зелёный: py=failure"


class CallersSandbox(RealGitSandbox):
    """Артель и учебный внешний проект, задачи в БД, подставной `gh`."""

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

        entry = (f"  {self.name}:\n    forge: github\n    url: {self.url}\n"
                 f"    base: {self.base}\n    token_slot: {self.slot}\n"
                 f"    no_paths: []\n    project_skills: []\n"
                 f"    merge_gate: operator\n")
        config.TARGETS.write_text("targets:\n" + artel_target_entry() + entry,
                                  encoding="utf-8")
        self.clone = repo_context.clone_path(self.name)
        self.clone.mkdir(parents=True)
        self.cgit("init", "-q", "-b", self.base)
        self.cgit("config", "user.email", "artel@example.invalid")
        self.cgit("config", "user.name", "artel tests")
        self.cgit("commit", "-q", "--allow-empty", "-m", "A")
        self.sha_a = self.cgit("rev-parse", "HEAD").strip()
        self.cgit("update-ref", f"refs/remotes/origin/{self.base}", self.sha_a)
        self.artel_main = self.git("rev-parse", config.MAIN_BRANCH).strip()
        self.conn = store.db()

    # ------------------------------------------------------------ фикстура

    def word(self, n: int) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(n))

    def cgit(self, *args: str) -> str:
        return self.git("-C", str(self.clone), *args)

    def project_branch(self) -> tuple[str, str]:
        branch = f"task/{self.rng.randrange(10**6)}-{self.word(5)}"
        self.cgit("checkout", "-q", "-b", branch, self.base)
        self.cgit("commit", "-q", "--allow-empty", "-m", f"H {branch}")
        head = self.cgit("rev-parse", "HEAD").strip()
        self.cgit("checkout", "-q", self.base)
        return branch, head

    def artel_branch(self) -> tuple[str, str]:
        branch = f"task/{self.rng.randrange(10**6)}-artel"
        self.git("checkout", "-q", "-b", branch, config.MAIN_BRANCH)
        self.git("commit", "-q", "--allow-empty", "-m", f"artel H {branch}")
        head = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", config.MAIN_BRANCH)
        return branch, head

    def new_task(self, target: str, branch: str, state: str) -> str:
        task_id = "".join(self.rng.choice(string.ascii_uppercase + string.digits)
                          for _ in range(26))
        store.insert_task(self.conn, task_id, f"Задача {task_id[:6]}", state,
                          branch, target, 25.0)
        return task_id

    def gh_repo(self) -> str:
        return f"{self.owner}/{self.repo_name}"

    def token(self) -> str:
        return keychain.token(self.slot)

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # ------------------------------------------------------------- ответы gh

    def flush_rules(self) -> None:
        (self.bin / "gh-rules.json").write_text(json.dumps(self.rules),
                                                encoding="utf-8")

    def answer(self, contains: str, payload, *, artel: bool, run: bool = False):
        rule = {"contains": contains,
                "stdout": payload if isinstance(payload, str)
                else json.dumps(payload)}
        if run:
            rule["repo_flag"] = None if artel else self.url
        else:
            rule["gh_repo"] = None if artel else self.gh_repo()
        self.rules.append(rule)
        self.flush_rules()

    def checks(self, sha: str, runs: list, *, artel: bool) -> None:
        self.answer(f"commits/{sha}/check-runs",
                    {"total_count": len(runs), "check_runs": runs}, artel=artel)

    def failed(self, name: str) -> dict:
        return {"name": name, "status": "completed", "conclusion": "failure",
                "id": self.rng.randrange(10**6)}

    def stuck(self, cid: int) -> dict:
        return {"name": "py" + self.word(3), "status": "in_progress",
                "conclusion": None, "id": cid,
                "started_at": "2020-01-01T00:00:00Z"}

    def red_scenario(self, head: str, main_sha: str, run_id: int, *,
                     artel: bool) -> None:
        """Голова красна заданием `py`, вершина главной ветки — другим."""
        self.checks(head, [self.failed("py")], artel=artel)
        self.checks(main_sha, [self.failed("lint" + self.word(3))], artel=artel)
        self.answer(f"actions/runs?head_sha={head}", {"workflow_runs": [
            {"id": run_id, "status": "completed", "conclusion": "failure"}]},
            artel=artel)
        self.answer("run rerun", "", artel=artel, run=True)
        self.answer("run watch", "", artel=artel, run=True)

    # -------------------------------------------------------------- запись

    @contextmanager
    def recording(self):
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

    @contextmanager
    def origin_main(self, sha: str):
        """`fsm._origin_main_sha` — запись вызовов, ответ `sha`."""
        spy = mock.Mock(return_value=sha)
        with mock.patch.object(fsm, "_origin_main_sha", spy):
            yield spy

    def ci_rerun(self, task_id: str) -> str:
        try:
            ci_rerun.cmd_ci_rerun(task_id, REASON)
        except SystemExit as exc:
            return str(exc)
        return ""

    def journal_red(self, task_id: str, head: str) -> None:
        store.journal(self.conn, task_id, "orchestrator",
                      fsm.VERIFYING_STATUS_ACTION, red_note(head))

    def flake_rows(self, task_id: str) -> list[str]:
        return [s["detail"] or "" for s in store.task_steps(self.conn, task_id)
                if s["action"] == "flake-rate"]

    # ------------------------------------------------------------- сверки

    def assert_main_form(self, calls: list, expected: list, what: str) -> None:
        self.assertEqual([c.argv for c in calls], expected,
                         self.msg(f"{what}: argv gh артели"))
        for call in calls:
            self.assertIsNone(call.env, self.msg(
                f"{what}: у gh артели своё окружение {call.argv}"))
            self.assertEqual(Path(call.cwd).resolve(), Path(config.ROOT).resolve(),
                             self.msg(f"{what}: cwd gh артели"))

    def assert_project(self, calls: list, what: str) -> None:
        self.assertTrue(calls, self.msg(f"{what}: ни одного вызова gh"))
        for call in calls:
            env = dict(os.environ) if call.env is None else call.env
            self.assertEqual(env.get("GH_TOKEN"), self.token(),
                             self.msg(f"{what}: GH_TOKEN {call.argv}"))
            if call.argv[:1] == ["api"]:
                self.assertEqual(env.get("GH_REPO"), self.gh_repo(), self.msg(
                    f"{what}: GH_REPO {call.argv}"))
                self.assertNotIn("--repo", call.argv,
                                 self.msg(f"{what}: --repo у gh api"))
            else:
                self.assertIn("--repo", call.argv[:-1],
                              self.msg(f"{what}: нет --repo {call.argv}"))
                self.assertEqual(call.argv[call.argv.index("--repo") + 1],
                                 self.url, self.msg(f"{what}: {call.argv}"))

    def assert_called(self, calls: list, fragment: str, what: str) -> None:
        joined = [" ".join(c.argv) for c in calls]
        self.assertTrue(any(fragment in j for j in joined),
                        self.msg(f"{what}: нет вызова «{fragment}»: {joined}"))


class ArtelCallersTest(CallersSandbox):
    """У артели вызывающие зовут `gh` прежней формой."""

    def test_ac1_artel_callers_keep_main_form(self):
        """`ci-rerun` и ре-ран гейта мержа у артели — `gh` ровно как на main.

        Задача артели в `verifying`: красный путь `ci-rerun` (сверка имён
        упавших заданий головы и вершины, поиск прогона, `rerun --failed`,
        `watch`, повторное чтение статуса) и путь зависшей проверки
        (`check_run_workflow_run`, `rerun <id>`, `watch`). Задача артели на
        гейте мержа: `_ci_confirm_red_or_flake` (поиск прогона, `rerun`,
        `watch`). Последовательность argv `gh` — та, что даёт main, у каждого
        вызова нет своего `env` (ни `GH_REPO`, ни `GH_TOKEN`), `cwd` — корень
        пульта. Перечисленные в SPEC файлы подмен `tests/` дифф задачи не
        трогает.

        Ловит мутацию: вызывающий передаёт у артели `repo=` клона артели и
        функция строит по нему окружение `gh` (`GH_REPO` артели) либо
        `--repo`; лишний или пропавший вызов `gh` в пути `ci-rerun`; правка
        существующей подмены `tests/` под новую сигнатуру.
        """
        with self.subTest(путь="ci-rerun красный"):
            branch, head = self.artel_branch()
            run_id = self.rng.randrange(10**6)
            self.red_scenario(head, self.artel_main, run_id, artel=True)
            task = self.new_task(config.DEFAULT_TARGET, branch, "verifying")
            self.journal_red(task, head)
            with self.origin_main(self.artel_main), self.recording() as calls:
                self.ci_rerun(task)
            self.assert_main_form(calls, [
                page(head), page(self.artel_main),
                page(head), page(self.artel_main),
                wruns(head), ["run", "rerun", str(run_id), "--failed"],
                ["run", "watch", str(run_id), "--exit-status"],
                page(head), page(self.artel_main)], "ci-rerun красный")
        with self.subTest(путь="ci-rerun зависшая проверка"):
            branch, head = self.artel_branch()
            cid = self.rng.randrange(10**6)
            run_id = self.rng.randrange(10**6)
            self.checks(head, [self.stuck(cid)], artel=True)
            self.answer(f"actions/jobs/{cid}", {"run_id": run_id}, artel=True)
            self.answer("run rerun", "", artel=True, run=True)
            self.answer("run watch", "", artel=True, run=True)
            task = self.new_task(config.DEFAULT_TARGET, branch, "verifying")
            with self.recording() as calls:
                self.ci_rerun(task)
            self.assert_main_form(calls, [
                page(head), ["api", f"repos/{{owner}}/{{repo}}/actions/jobs/{cid}"],
                ["run", "rerun", str(run_id)],
                ["run", "watch", str(run_id), "--exit-status"],
                page(head)], "ci-rerun зависшая")
        with self.subTest(путь="гейт мержа"):
            branch, head = self.artel_branch()
            run_id = self.rng.randrange(10**6)
            self.red_scenario(head, self.artel_main, run_id, artel=True)
            task = self.new_task(config.DEFAULT_TARGET, branch, "merge_gate")
            green = (True, f"CI коммита {head[:8]} зелёный (1 проверок)")
            with mock.patch.object(ci, "branch_status",
                                   lambda b, repo=None: green), \
                    self.recording() as calls:
                fsm_merge_gate._ci_confirm_red_or_flake(
                    self.conn, task, branch, red_note(head))
            self.assert_main_form(calls, [
                wruns(head), ["run", "rerun", str(run_id), "--failed"],
                ["run", "watch", str(run_id), "--exit-status"]], "гейт мержа")
        with self.subTest(факт="подмены tests/ не тронуты"):
            touched = sorted(set(changed_paths()) & set(SUBSTITUTE_FILES))
            self.assertEqual(touched, [], "дифф задачи правит файлы подмен "
                                          f"tests/: {touched}")


class ProjectCallersTest(CallersSandbox):
    """У внешнего проекта вызывающие адресуют `gh` репозиторию проекта."""

    def test_ac7_ci_rerun_and_merge_gate_address_project(self):
        """`ci-rerun` и гейт мержа задачи проекта зовут `gh` к проекту.

        Красный путь `ci-rerun`: `failed_check_names` головы и вершины
        `origin/<base>`, поиск прогона и повтор `trigger_rerun`. Путь
        зависшей проверки: `check_run_workflow_run` и `trigger_rerun(…,
        run_id=…)`. Гейт мержа: `trigger_rerun` в `_ci_confirm_red_or_flake`.
        Каждый вызов `gh`: `gh api` — `GH_REPO=<владелец>/<имя>` и токен
        слота, `gh run` — `--repo <url>` и токен слота; ожидаемые запросы
        (проверки вершины, задание зависшей проверки, `run rerun`) сделаны.

        Ловит мутацию: `ci_rerun.py` зовёт `check_run_workflow_run(check_id)`
        или `failed_check_names(head)` без клона, либо `trigger_rerun(branch)`
        гейта мержа без клона — `gh api` без `GH_REPO` (ответ 422) или голова
        ветки читается в клоне артели и повтор не запущен вовсе.
        """
        with self.subTest(путь="ci-rerun красный"):
            branch, head = self.project_branch()
            run_id = self.rng.randrange(10**6)
            self.red_scenario(head, self.sha_a, run_id, artel=False)
            task = self.new_task(self.name, branch, "verifying")
            self.journal_red(task, head)
            with self.origin_main(self.sha_a), self.recording() as calls:
                out = self.ci_rerun(task)
            self.assert_called(calls, f"commits/{self.sha_a}/check-runs",
                               f"ci-rerun красный ({out})")
            self.assert_called(calls, f"run rerun {run_id}",
                               f"ci-rerun красный ({out})")
            self.assert_project(calls, "ci-rerun красный")
        with self.subTest(путь="ci-rerun зависшая проверка"):
            branch, head = self.project_branch()
            cid = self.rng.randrange(10**6)
            run_id = self.rng.randrange(10**6)
            self.checks(head, [self.stuck(cid)], artel=False)
            self.answer(f"actions/jobs/{cid}", {"run_id": run_id}, artel=False)
            self.answer("run rerun", "", artel=False, run=True)
            self.answer("run watch", "", artel=False, run=True)
            task = self.new_task(self.name, branch, "verifying")
            with self.recording() as calls:
                out = self.ci_rerun(task)
            self.assert_called(calls, f"actions/jobs/{cid}",
                               f"ci-rerun зависшая ({out})")
            self.assert_called(calls, f"run rerun {run_id}",
                               f"ci-rerun зависшая ({out})")
            self.assert_project(calls, "ci-rerun зависшая")
        with self.subTest(путь="гейт мержа"):
            branch, head = self.project_branch()
            run_id = self.rng.randrange(10**6)
            self.red_scenario(head, self.sha_a, run_id, artel=False)
            task = self.new_task(self.name, branch, "merge_gate")
            green = (True, f"CI коммита {head[:8]} зелёный (1 проверок)")
            with mock.patch.object(ci, "branch_status",
                                   lambda b, repo=None: green), \
                    self.recording() as calls:
                fsm_merge_gate._ci_confirm_red_or_flake(
                    self.conn, task, branch, red_note(head))
            self.assert_called(calls, f"run rerun {run_id}", "гейт мержа")
            self.assert_project(calls, "гейт мержа")


class OriginMainShaRepoTest(CallersSandbox):
    """`ci-rerun` зовёт `fsm._origin_main_sha` с клоном проекта задачи."""

    def test_ac10_origin_main_sha_gets_project_clone(self):
        """Проект — `repo=<клон проекта>`, артель — вызов без `repo=`.

        Функции `ci` подменены (статус красный, голова совпадает с журналом,
        имена упавших заданий головы и вершины не пересекаются, повтор
        запущен): сценарий доходит до сверки с вершиной главной ветки. У
        задачи проекта `fsm._origin_main_sha` вызван один раз с `repo`,
        равным `repo_context.clone_path(<имя>)`; у задачи артели — один раз
        без именованного `repo`.

        Ловит мутацию: строка `ci_rerun.py` оставлена `_origin_main_sha(target)`
        — у проекта `repo` не передан (fetch по адресу проекта в главной копии
        пульта); либо `repo=` передаётся и артели — вызов артели не прежний.
        """
        head = "c" * 40
        main_sha = "d" * 40

        def failed_names(sha, repo=None):
            return ({"py"} if sha == head else {"lint"}), ""

        patches = [
            mock.patch.object(ci, "verifying_status", lambda b, repo=None: (
                ci.VERIFYING_RED, red_note(head))),
            mock.patch.object(ci, "head_sha", lambda b, repo=None: (head, "")),
            mock.patch.object(ci, "failed_check_names", failed_names),
            mock.patch.object(ci, "trigger_rerun", lambda *a, **k: (
                "ре-ран прогона 1 запущен, ожидание завершения: ок")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        for target, expected in ((self.name, self.clone),
                                 (config.DEFAULT_TARGET, None)):
            with self.subTest(проект=target):
                task = self.new_task(target, f"task/{self.word(6)}", "verifying")
                self.journal_red(task, head)
                with self.origin_main(main_sha) as spy:
                    out = self.ci_rerun(task)
                self.assertEqual(spy.call_count, 1, self.msg(
                    f"{target}: _origin_main_sha вызван {spy.call_count} раз "
                    f"({out})"))
                args, kwargs = spy.call_args
                self.assertEqual(args[:1], (target,), self.msg(str(spy.call_args)))
                if expected is None:
                    self.assertNotIn("repo", kwargs, self.msg(
                        f"артель: вызов не прежний {spy.call_args}"))
                else:
                    self.assertIn("repo", kwargs, self.msg(
                        f"проект: нет repo= {spy.call_args}"))
                    self.assertEqual(Path(kwargs["repo"]).resolve(),
                                     Path(expected).resolve(),
                                     self.msg(f"проект: repo= не клон проекта "
                                              f"{spy.call_args}"))


class FlakeRateNotStartedTest(CallersSandbox):
    """Запись `flake-rate` гейта мержа при незапущенном повторе."""

    def confirm(self, rerun_note: str, status: tuple) -> list[str]:
        branch = f"task/{self.word(6)}"
        task = self.new_task(config.DEFAULT_TARGET, branch, "merge_gate")
        with mock.patch.object(ci, "trigger_rerun",
                               lambda *a, **k: rerun_note), \
                mock.patch.object(ci, "branch_status",
                                  lambda b, repo=None: status):
            try:
                fsm_merge_gate._ci_confirm_red_or_flake(
                    self.conn, task, branch, red_note("e" * 40))
            except SystemExit:
                pass
        return self.flake_rows(task)

    def test_ac11_not_started_rerun_is_named_in_flake_rate(self):
        """Незапущенный повтор: «повтор не запущен» с причиной, не «подтверждённый красный».

        `trigger_rerun` вернула отказ запуска («ре-ран CI не запущен: …» или
        «ре-ран прогона <id> не запущен: …» со случайной причиной). При
        красном последующем `branch_status` записи `flake-rate` этого прохода
        есть, одна несёт «повтор не запущен» и причину, ни одна не несёт «ре-ран
        тоже красный» и «подтверждённый красный»; при зелёном — то же, и ни
        одна не несёт «флейк». При запущенном повторе и красном статусе
        запись по-прежнему несёт «подтверждённый красный».

        Ловит мутацию: признак `ci.rerun_started` не проверяется (или
        проверяется только на красной ветке) — незапущенный повтор пишется
        «подтверждённым красным» либо зелёный — «флейком»; либо запись
        «повтор не запущен» не несёт `note` причины.
        """
        red = (False, f"CI коммита {'e' * 8} не зелёный: py=failure")
        green = (True, f"CI коммита {'e' * 8} зелёный (1 проверок)")
        for kind in ("ci", "run"):
            why = f"причина-{self.word(8)}"
            note = (f"ре-ран CI не запущен: {why}" if kind == "ci" else
                    f"ре-ран прогона {self.rng.randrange(10**6)} не запущен: "
                    f"{why}")
            for status in (red, green):
                with self.subTest(отказ=note, зелёный=status[0]):
                    rows = self.confirm(note, status)
                    self.assertTrue(rows, self.msg("нет записи flake-rate"))
                    self.assertTrue(
                        any("повтор не запущен" in r and why in r for r in rows),
                        self.msg(f"нет «повтор не запущен» с причиной: {rows}"))
                    for bad in ("ре-ран тоже красный", "подтверждённый красный"):
                        self.assertFalse(any(bad in r for r in rows),
                                         self.msg(f"«{bad}» при незапущенном "
                                                  f"повторе: {rows}"))
                    if status[0]:
                        self.assertFalse(any("флейк" in r for r in rows),
                                         self.msg(f"«флейк» при незапущенном "
                                                  f"повторе: {rows}"))
        with self.subTest(повтор="запущен, красный"):
            rows = self.confirm(
                f"ре-ран прогона {self.rng.randrange(10**6)} запущен, ожидание "
                f"завершения: gh run watch завершился", red)
            self.assertTrue(any("подтверждённый красный" in r for r in rows),
                            self.msg(f"запущенный повтор: {rows}"))
