"""Токен хостинга внешнего проекта и проверки `doctor` по записи проекта.

Группа: долгоживущий
Красен до реализации: пульт не читает слот `token_slot` записи проекта — `gh` внешнего проекта идёт без `GH_TOKEN` проекта, git-вызовы с `origin` клона идут без помощника учётных данных пульта (`git credential fill` в их окружении отдаёт чужой пароль), пустой слот не даёт отказа, а у `doctor` нет проверок клона, пуша, CI, защиты ветки, токена и `no_paths` записи проекта и подмены `keychain.token` в песочнице.

Окружение каждого сценария (требование 9 SPEC): `origin` внешнего проекта —
второй настоящий git-репозиторий (bare, адрес `file://…`), `gh` — подставной
исполняемый файл в начале PATH, слот связки ключей — подмена
`keychain.token`, которая отдаёт значение тестового словаря слотов и не
трогает настоящую связку. Системный gitconfig машины не читается
(`GIT_CONFIG_NOSYSTEM=1`): в нём бывает `osxkeychain` Оператора.
Конкурирующие помощники учётных данных (глобальный `credential.helper` и с
областью URL проекта `credential.<URL>.helper`) лежат в глобальном конфиге
песочницы (`GIT_CONFIG_GLOBAL`), который пульт не подменяет.

«Помощник пульта отдаёт токен» проверяется наблюдаемо: окружение, с которым
пульт запустил git, перехватывается подменой `subprocess.run`, и в этом
окружении исполняется `git credential fill` по URL проекта.

Строки проверок `doctor` SPEC не называет по имени: строка ищется по тексту,
который называет критерий, либо сравнением `doctor.all_checks` двух
подготовленных состояний — проверка с тем же `Check.name`, чей исход
сменился (например ok → fail), и есть проверка этого состояния.

Запись внешнего проекта без поля `token_slot` (AC-10, AC-15) не проходит
`targets.check` (поле обязательно, `orchestrator/targets.py` вне зоны
задачи), поэтому сценарий подменяет публичную `targets.load` обёрткой,
которая убирает поле у записи проекта.
"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
from collections import Counter, namedtuple
from pathlib import Path
from unittest import mock

from orchestrator import (ci, config, doctor, github_adapter, keychain,
                          repo_context, runner, stack, store, targets)
from tests.sandbox import (RealGitSandbox, TmpRootTest, _stub_check_stack,
                           artel_target_entry, init_bare_origin,
                           network_guarded_real_run)

Call = namedtuple("Call", "argv env")

# Подкоманды git, говорящие с remote (требование 1 SPEC).
REMOTE_SUBCOMMANDS = ("fetch", "push", "pull", "ls-remote")
PULT_MARKER = ("ARTEL_PULT_GIT", "1")

FAKE_GH = """#!{python}
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
with open(os.path.join(here, "gh-calls.jsonl"), "a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": argv,
                           "gh_token": os.environ.get("GH_TOKEN")}}) + "\\n")

def answer(name):
    path = os.path.join(here, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()

if argv[:2] == ["auth", "token"]:
    token = answer("auth-token.txt")
    if not token:
        sys.stderr.write("You are not logged into any GitHub hosts\\n")
        sys.exit(1)
    print(token)
    sys.exit(0)
if argv and argv[0] == "api" and any(a.endswith("/protection") for a in argv):
    data = answer("protection.json")
    if data is None:
        sys.stderr.write("gh: Branch not protected (HTTP 404)\\n")
        sys.exit(1)
    print(data)
    sys.exit(0)
if argv[:2] == ["repo", "view"]:
    print(answer("base.txt") or "main")
    sys.exit(0)
print("ok")
sys.exit(0)
"""


def git_subcommand(argv: list) -> list:
    """Аргументы git-вызова после ведущих `-C <путь>`/`-c <ключ=знач>`."""
    args = list(argv[1:])
    while len(args) >= 2 and args[0] in ("-C", "-c"):
        args = args[2:]
    return args


def is_git(argv: list) -> bool:
    return bool(argv) and Path(str(argv[0])).name == "git"


def is_gh(argv: list) -> bool:
    return bool(argv) and Path(str(argv[0])).name == "gh"


class Recorder:
    """Подмена `subprocess.run`/`Popen` на время операции: запоминает argv и
    окружение каждого вызова; исполняет только git и `gh` (подставной),
    прочие процессы (CLI ролей, `security`) не запускает. `fail` — список
    предикатов argv: подходящий вызов получает отказ без исполнения
    (`origin` отказал)."""

    def __init__(self):
        self.calls: list[Call] = []
        self.fail: list = []
        self._real_popen = subprocess.Popen

    def run(self, cmd, *args, **kwargs):
        argv = ([str(cmd)] if isinstance(cmd, (str, Path))
                else [str(a) for a in cmd])
        env = kwargs.get("env")
        self.calls.append(Call(argv, dict(os.environ if env is None else env)))
        if not (is_git(argv) or is_gh(argv)):
            raise FileNotFoundError("песочница: внешний процесс не запускается")
        want_text = bool(kwargs.get("text") or kwargs.get("universal_newlines")
                         or kwargs.get("encoding"))
        for refuse in self.fail:
            if refuse(argv):
                err = "отказ песочницы: origin не принял операцию\n"
                return subprocess.CompletedProcess(
                    argv, 1, "" if want_text else b"",
                    err if want_text else err.encode())
        return network_guarded_real_run(cmd, *args, **kwargs)

    def popen(self, cmd, *args, **kwargs):
        argv = ([str(cmd)] if isinstance(cmd, (str, Path))
                else [str(a) for a in cmd])
        if not (is_git(argv) or is_gh(argv)):
            raise FileNotFoundError("песочница: внешний процесс не запускается")
        return self._real_popen(cmd, *args, **kwargs)

    def git_calls(self, subcommand: str | None = None) -> list[Call]:
        out = []
        for call in self.calls:
            if not is_git(call.argv):
                continue
            sub = git_subcommand(call.argv)
            if subcommand is None or (sub and sub[0] == subcommand):
                out.append(call)
        return out


class ProjectSandbox(RealGitSandbox):
    """Главная копия пульта (настоящий git), учебный внешний проект с клоном
    `.artel/projects/<имя>/repo` и bare-`origin` вне корня песочницы,
    подставной `gh`, словарь слотов связки ключей."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        letters = string.ascii_lowercase
        self.name = "ucheb" + "".join(self.rng.choice(letters) for _ in range(5))
        self.slot = f"{self.name}-hosting-{self.rng.randrange(100, 999)}"
        self.token = "tok" + "".join(self.rng.choice(string.hexdigits.lower())
                                     for _ in range(28))
        self.slots = {self.slot: self.token}

        aux = tempfile.TemporaryDirectory(prefix="artel-hosting-")
        self.addCleanup(aux.cleanup)
        self.aux = Path(aux.name).resolve()
        self.home = self.aux / "home"
        self.home.mkdir()
        self.bin = self.aux / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH.format(python=sys.executable), encoding="utf-8")
        gh.chmod(0o755)
        (self.bin / "base.txt").write_text(config.MAIN_BRANCH, encoding="utf-8")
        self.gh_auth = "gho" + "".join(self.rng.choice(string.hexdigits.lower())
                                       for _ in range(28))
        (self.bin / "auth-token.txt").write_text(self.gh_auth, encoding="utf-8")
        self.protection_marker = self.rng.randrange(1, 6)
        (self.bin / "protection.json").write_text(json.dumps({
            "required_pull_request_reviews": {
                "required_approving_review_count": self.protection_marker},
            "enforce_admins": {"enabled": True}}), encoding="utf-8")

        # Конкурирующие помощники учётных данных: пароли, отличные от
        # токена слота.
        self.owner = "acme" + "".join(self.rng.choice(letters) for _ in range(3))
        self.repo_name = "proj" + "".join(self.rng.choice(letters) for _ in range(3))
        self.bare = self.aux / self.owner / f"{self.repo_name}.git"
        self.bare.parent.mkdir()
        self.url = f"file://{self.bare}"
        self.foreign_global = f"chuzhoy-global-{self.rng.randrange(10**6)}"
        self.foreign_url = f"chuzhoy-url-{self.rng.randrange(10**6)}"
        identity = "[user]\n\tname = artel tests\n\temail = artel@example.invalid\n"
        global_helper = ('[credential]\n\thelper = "!f() { echo username=g; '
                         f'echo password={self.foreign_global}; }}; f"\n')
        url_helper = (f'[credential "{self.url}"]\n\thelper = "!f() {{ echo '
                      f'username=u; echo password={self.foreign_url}; }}; f"\n')
        self.gitconfigs = {}
        for variant, text in (("оба", global_helper + url_helper),
                              ("глобальный", global_helper),
                              ("с областью URL", url_helper)):
            path = self.aux / f"gitconfig-{len(self.gitconfigs)}"
            path.write_text(identity + text, encoding="utf-8")
            self.gitconfigs[variant] = path

        env = mock.patch.dict(os.environ, {
            "HOME": str(self.home),
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "GIT_CONFIG_GLOBAL": str(self.gitconfigs["оба"]),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        })
        env.start()
        self.addCleanup(env.stop)
        for name in (config.ARTEL_ROLE_ENV, "GH_TOKEN", "GITHUB_TOKEN",
                     "GIT_ASKPASS", "SSH_ASKPASS", "GIT_CONFIG_COUNT",
                     "GIT_TRACE"):
            os.environ.pop(name, None)

        token_patch = mock.patch.object(keychain, "token",
                                        side_effect=self.read_slot)
        self.keychain = token_patch.start()
        self.addCleanup(token_patch.stop)
        home_patch = mock.patch.object(Path, "home", lambda *a, **k: self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

        self.use_role_map()
        self.build_project()
        self.conn = store.db()

    # ------------------------------------------------------------ фикстура

    def read_slot(self, slot):
        if slot in self.slots:
            return self.slots[slot]
        return f"model-token-of-{slot}"

    def slot_reads(self) -> list:
        return [c.args[0] if c.args else c.kwargs.get("slot")
                for c in self.keychain.call_args_list]

    def cgit(self, *args: str) -> str:
        return self.git("-C", str(self.clone), *args)

    def commit_file(self, rel: str, text: str, message: str) -> str:
        path = self.clone / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.cgit("add", rel)
        self.cgit("commit", "-q", "-m", message)
        return self.cgit("rev-parse", "HEAD").strip()

    def build_project(self) -> None:
        init_bare_origin(self.bare, self.git)
        self.project_dir = config.PROJECTS / self.name
        self.clone = self.project_dir / "repo"
        self.clone.mkdir(parents=True)
        self.cgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.cgit("config", "user.email", "artel@example.invalid")
        self.cgit("config", "user.name", "artel tests")
        self.kept = f"keep/{self.rng.randrange(10**6)}.txt"
        self.commit_file(self.kept, "kept\n", "init")
        self.commit_file("sub/conftest.py", "# conftest\n", "conftest")
        self.commit_file(".github/workflows/ci.yml",
                         "name: ci\non: [push, pull_request]\njobs: {}\n", "ci")
        self.cgit("remote", "add", "origin", self.url)
        self.cgit("push", "-q", "origin", config.MAIN_BRANCH)
        self.cgit("fetch", "-q", "origin")
        self.no_paths = [self.kept, "**/conftest.py"]
        self.write_targets()

    def entry_text(self, *, no_paths=None, project_skills=(),
                   token_slot=True) -> str:
        no_paths = self.no_paths if no_paths is None else no_paths
        lines = [f"  {self.name}:", "    forge: github", f"    url: {self.url}",
                 f"    base: {config.MAIN_BRANCH}"]
        lines.append(f"    token_slot: {self.slot}")
        # `yamlmini` не разбирает кавычки в потоковом списке.
        lines.append("    no_paths: [" + ", ".join(no_paths) + "]")
        lines.append("    project_skills: [" + ", ".join(project_skills) + "]")
        lines.append("    merge_gate: operator")
        return "\n".join(lines) + "\n"

    def write_targets(self, external: bool = True, **entry) -> None:
        text = "targets:\n" + artel_target_entry()
        if external:
            text += self.entry_text(**entry)
        config.TARGETS.write_text(text, encoding="utf-8")

    @contextlib.contextmanager
    def without_token_slot(self):
        """`targets.load` отдаёт запись проекта без поля `token_slot`."""
        real_load = targets.load

        def load():
            entries = real_load()
            out = {}
            for name, entry in entries.items():
                entry = dict(entry)
                if name == self.name:
                    entry.pop("token_slot", None)
                out[name] = entry
            return out

        with mock.patch.object(targets, "load", side_effect=load):
            yield

    @contextlib.contextmanager
    def role_process(self, variant: str):
        """Признак процесса роли: маркер `ARTEL_ROLE` либо `HOME` дома роли
        без маркера (`runner.in_role_environment`)."""
        if variant == "маркер ARTEL_ROLE":
            with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
                self.assertTrue(runner.in_role_environment())
                yield
        else:
            config.ROLE_HOME.mkdir(parents=True, exist_ok=True)
            with mock.patch.dict(os.environ, {"HOME": str(config.ROLE_HOME)}):
                os.environ.pop(config.ARTEL_ROLE_ENV, None)
                self.assertTrue(runner.in_role_environment())
                yield

    @contextlib.contextmanager
    def recording(self):
        rec = Recorder()
        with mock.patch.object(subprocess, "run", side_effect=rec.run), \
                mock.patch.object(subprocess, "Popen", side_effect=rec.popen):
            yield rec

    def gh_calls(self) -> list[dict]:
        log = self.bin / "gh-calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in
                log.read_text(encoding="utf-8").splitlines() if line]

    def reset_gh_calls(self) -> None:
        (self.bin / "gh-calls.jsonl").unlink(missing_ok=True)

    def passwords(self, env: dict, variant: str = "оба") -> list[str]:
        """Пароли, которые `git credential fill` по URL проекта отдаёт в
        окружении `env` при конкурирующих помощниках `variant`."""
        env = dict(env)
        env.update(GIT_CONFIG_GLOBAL=str(self.gitconfigs[variant]),
                   GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        res = network_guarded_real_run(
            ["git", "credential", "fill"], input=f"url={self.url}\n\n",
            capture_output=True, text=True, env=env, cwd=str(self.aux),
            timeout=60)
        return [line[len("password="):] for line in res.stdout.splitlines()
                if line.startswith("password=")]

    def assert_slot_credential(self, env: dict, what: str) -> None:
        for variant in self.gitconfigs:
            with self.subTest(помощники=variant, вызов=what):
                self.assertEqual(
                    self.passwords(env, variant), [self.token],
                    self.msg(f"{what}: `git credential fill` по URL проекта "
                             f"при помощниках «{variant}» отдаёт не только "
                             f"токен слота {self.slot}"))

    def ctx(self, path: Path) -> "repo_context.RepoContext":
        return repo_context.RepoContext(path=Path(path), remote="origin",
                                        base=config.MAIN_BRANCH,
                                        target=self.name)

    def pult_git(self, path: Path, *args: str):
        """git-вызов пульта с `-C <path>` (`gitcmd.in_repo` через
        `repo_context.git`)."""
        return repo_context.git(self.ctx(path), *args)

    def origin_has(self, ref: str) -> str:
        res = network_guarded_real_run(
            ["git", "-C", str(self.bare), "rev-parse", "--verify", "--quiet",
             ref], capture_output=True, text=True)
        return res.stdout.strip() if res.returncode == 0 else ""

    def new_task(self, target: str, branch: str, **fields) -> str:
        task_id = "".join(self.rng.choice(string.ascii_uppercase + string.digits)
                          for _ in range(26))
        store.insert_task(self.conn, task_id, f"Задача {task_id[:6]}",
                          "in_dev", branch, target, 25.0)
        if fields:
            store.update_task(self.conn, task_id, **fields)
        return task_id

    def task_branch_with_protected_touch(self) -> str:
        branch = f"task/{self.rng.randrange(10**6)}-uchebnaya"
        self.cgit("checkout", "-q", "-b", branch)
        self.commit_file(self.kept, f"правка {self.rng.random()}\n", "правка")
        self.cgit("checkout", "-q", config.MAIN_BRANCH)
        return branch

    def journal_text(self, task_id: str) -> str:
        steps = " ".join(f"{s['action']} {s['detail']}"
                         for s in store.task_steps(self.conn, task_id))
        alerts = " ".join(a["message"] for a in store.open_alerts(self.conn))
        return steps + " " + alerts

    def doctor_checks(self) -> list:
        with self.recording() as rec:
            checks = doctor.all_checks(store.db())
        self.last_rec = rec
        return checks

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


def by_name(checks) -> dict:
    out = {}
    for c in checks:
        out.setdefault(c.name, []).append(c)
    return out


def flipped(good, bad, good_status: str, bad_status: str) -> list[str]:
    """Имена проверок, у которых в `bad` исходов `bad_status` больше, а в
    `good` исходов `good_status` больше, чем в другом состоянии."""
    g, b = by_name(good), by_name(bad)
    names = []
    for name in set(g) & set(b):
        gc = Counter(c.status for c in g[name])
        bc = Counter(c.status for c in b[name])
        if bc[bad_status] > gc[bad_status] and gc[good_status] > bc[good_status]:
            names.append(name)
    return sorted(names)


def lines_with(checks, text: str) -> list:
    return [c for c in checks if text in f"{c.name} {c.detail}"]


def render(checks) -> str:
    return "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)


# ===================================================================== токен


class HostingTokenTest(ProjectSandbox):
    """Механизм токена хостинга: `gh` и git-вызовы пульта."""

    def test_ac1_artel_calls_keep_main_env_and_args(self):
        """Вызовы git и `gh` артели — окружение и argv как на main.

        `gitcmd.git("-C", …)` в клоне артели, в рабочей копии артели и в путях
        под корнем пульта вне `.artel/projects` — случайные подкоманды, в том
        числе говорящие с remote: argv ровно `git -C <путь> …`, окружение —
        окружение процесса плюс маркер `ARTEL_PULT_GIT=1`, слот связки ключей
        не читается. `gh` артели (`ci.gh` без `repo=` и `undraft_mr` задачи
        артели) — argv без добавок и окружение процесса.

        Ловит мутацию: признак проекта по пути `-C` не исключает
        `.artel/projects/artel/` или корень пульта — вызов артели получает
        `GIT_CONFIG_*`/`GH_TOKEN` с токеном `artel-token`, окружение
        расходится с ожидаемым и слот читается.
        """
        worktree = config.PROJECTS / config.DEFAULT_TARGET / "worktrees" / "t1"
        worktree.mkdir(parents=True, exist_ok=True)
        (self.root / "docs").mkdir(exist_ok=True)
        paths = [config.PROJECTS / config.DEFAULT_TARGET / "repo", worktree,
                 config.ROOT, config.ROOT / "docs"]
        commands = [("fetch", "-q", "origin"), ("push", "-q", "origin", "HEAD:x"),
                    ("ls-remote", "origin"), ("pull", "-q", "--ff-only"),
                    ("status", "--porcelain"), ("rev-parse", "HEAD")]
        for path in paths:
            for args in self.rng.sample(commands, 3):
                with self.subTest(путь=str(path), команда=args[0]):
                    with self.recording() as rec:
                        repo_context.git(repo_context.RepoContext(
                            path=path, remote="origin", base=config.MAIN_BRANCH,
                            target=config.DEFAULT_TARGET), *args)
                    calls = rec.git_calls()
                    self.assertEqual(len(calls), 1, self.msg(str(rec.calls)))
                    expected = dict(os.environ)
                    expected[PULT_MARKER[0]] = PULT_MARKER[1]
                    self.assertEqual(calls[0].argv,
                                     ["git", "-C", str(path), *args],
                                     self.msg("argv git артели изменён"))
                    self.assertEqual(calls[0].env, expected,
                                     self.msg("окружение git артели изменено"))
        self.assertEqual(self.slot_reads(), [],
                         self.msg("git артели читал связку ключей"))

        branch = f"task/{self.rng.randrange(10**6)}-artel"
        with self.recording() as rec:
            ci.gh("pr", "view", branch)
        task = self.new_task(config.DEFAULT_TARGET, branch, draft_mr_created=1)
        with self.recording() as rec2:
            github_adapter.undraft_mr(self.conn, task,
                                      store.get_task(self.conn, task))
        for argv_tail, rec_ in ((["pr", "view", branch], rec),
                                (["pr", "ready", branch], rec2)):
            gh = [c for c in rec_.calls if is_gh(c.argv)]
            with self.subTest(gh=argv_tail):
                self.assertEqual([c.argv for c in gh], [["gh", *argv_tail]],
                                 self.msg("argv gh артели изменён"))
                self.assertEqual(gh[0].env, dict(os.environ),
                                 self.msg("окружение gh артели изменено"))
        self.assertEqual(self.slot_reads(), [],
                         self.msg("gh артели читал связку ключей"))

    def test_ac2_adapter_gh_gets_project_token(self):
        """Draft MR внешнего проекта: каждый `gh` с `repo=` несёт `GH_TOKEN` слота.

        `ensure_draft_mr` задачи проекта (ветка с коммитом, задевающим путь
        `no_paths`) зовёт `gh pr create` и `gh pr comment`, затем
        `undraft_mr` — `gh pr ready`. Подставной `gh` записывает свой
        `GH_TOKEN`: во всех трёх вызовах он равен значению слота `token_slot`.

        Ловит мутацию: токен подставляется только в `pr create` (или только в
        `ci.gh` без учёта вызова комментария) — у `pr comment`/`pr ready`
        `GH_TOKEN` пуст.
        """
        branch = self.task_branch_with_protected_touch()
        task = self.new_task(self.name, branch)
        with self.recording():
            github_adapter.ensure_draft_mr(self.conn, task,
                                           store.get_task(self.conn, task))
            github_adapter.undraft_mr(self.conn, task,
                                      store.get_task(self.conn, task))
        seen = {}
        for call in self.gh_calls():
            if call["argv"][:1] == ["pr"] and len(call["argv"]) > 1:
                seen.setdefault(call["argv"][1], []).append(call["gh_token"])
        for sub in ("create", "comment", "ready"):
            with self.subTest(gh=f"pr {sub}"):
                self.assertTrue(seen.get(sub), self.msg(
                    f"gh pr {sub} не вызван; журнал: {self.journal_text(task)}"))
                self.assertEqual(set(seen[sub]), {self.token}, self.msg(
                    f"GH_TOKEN у gh pr {sub} — не токен слота {self.slot}"))

    def test_ac3_git_push_uses_slot_helper_only(self):
        """git-push пульта в `origin` проекта — помощник пульта, конфиг клона цел.

        Push ветки клона в bare-`origin` через `gitcmd.in_repo` проходит
        (ветка в `origin` на голове клона), байты `.git/config` клона те же.
        В окружении этого вызова `git credential fill` по URL проекта отдаёт
        ровно один пароль — токен слота — при каждом из наборов
        конкурирующих помощников (глобальный, с областью URL, оба).

        Ловит мутацию: помощник пульта добавлен без предшествующего пустого
        `credential.helper` (чужие помощники не сброшены) — `credential
        fill` отдаёт пароль глобального помощника либо помощника с областью
        URL; либо помощник прописан в `.git/config` клона — байты конфига
        меняются.
        """
        branch = f"task/{self.rng.randrange(10**6)}-push"
        self.cgit("branch", branch)
        head = self.cgit("rev-parse", branch).strip()
        config_before = (self.clone / ".git" / "config").read_bytes()
        with self.recording() as rec:
            res = self.pult_git(self.clone, "push", "-q", "origin",
                                f"refs/heads/{branch}:refs/heads/{branch}")
        self.assertEqual(res.returncode, 0, self.msg(f"push: {res.stderr}"))
        self.assertEqual(self.origin_has(f"refs/heads/{branch}"), head,
                         self.msg("ветка не дошла до origin"))
        self.assertEqual((self.clone / ".git" / "config").read_bytes(),
                         config_before, self.msg(".git/config клона изменён"))
        pushes = rec.git_calls("push")
        self.assertEqual(len(pushes), 1, self.msg(str(rec.calls)))
        self.assert_slot_credential(pushes[0].env, "push в origin")

    def test_ac4_empty_slot_refuses_with_slot_name(self):
        """Пустой слот: git-push и `gh` проекта отказывают, отказ называет слот.

        Слот `token_slot` пуст. Push в `origin` через `gitcmd.in_repo`:
        ненулевой код, имя слота в тексте отказа, ветки в `origin` нет.
        `undraft_mr` задачи проекта: подставной `gh` не вызван, имя слота —
        в журнале задачи (запись или инцидент).

        Ловит мутацию: пустой слот молча пропускается и вызов идёт с прежней
        авторизацией — push проходит / `gh pr ready` вызван, имени слота в
        отказе нет.
        """
        self.slots[self.slot] = None
        branch = f"task/{self.rng.randrange(10**6)}-empty"
        self.cgit("branch", branch)
        with self.subTest(операция="git push"):
            with self.recording():
                try:
                    res = self.pult_git(self.clone, "push", "-q", "origin",
                                        f"{branch}:{branch}")
                    code, text = res.returncode, f"{res.stdout} {res.stderr}"
                except Exception as exc:  # отказ исключением тоже отказ
                    code, text = 1, str(exc)
            self.assertNotEqual(code, 0, self.msg("push с пустым слотом прошёл"))
            self.assertIn(self.slot, text, self.msg(f"отказ без имени слота: {text}"))
            self.assertEqual(self.origin_has(f"refs/heads/{branch}"), "",
                             self.msg("ветка дошла до origin при пустом слоте"))
        with self.subTest(операция="gh pr ready"):
            task = self.new_task(self.name, branch, draft_mr_created=1)
            self.reset_gh_calls()
            out = io.StringIO()
            with self.recording(), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(out):
                try:
                    github_adapter.undraft_mr(self.conn, task,
                                              store.get_task(self.conn, task))
                    raised = ""
                except Exception as exc:
                    raised = str(exc)
            self.assertEqual(
                [c for c in self.gh_calls() if c["argv"][:2] == ["pr", "ready"]],
                [], self.msg("gh pr ready вызван при пустом слоте"))
            text = f"{self.journal_text(task)} {raised} {out.getvalue()}"
            self.assertIn(self.slot, text,
                          self.msg(f"отказ gh без имени слота: {text}"))

    def test_ac5_token_never_leaks(self):
        """Значения токена нет в журналах, выводе, окружении роли и argv.

        Сыграны операции AC-2 (Draft MR и снятие Draft), AC-3 (push) и
        отказанный push (`pre-receive` в `origin` отклоняет): вывод
        перехвачен. Значения токена нет ни в одном файле корня песочницы
        (БД журнала, логи), ни в журнале задач и алертах, ни в выводе и тексте
        отказа, ни в окружении роли задачи проекта (`runner.role_env`), ни в
        argv любого вызова git/`gh`, ни в argv помощника учётных данных
        (`GIT_TRACE` `credential fill` в окружении каждого хостингового
        вызова).

        Ловит мутацию: токен вписан в значение `credential.helper`
        (`-c credential.helper=!echo password=<токен>`) или в argv `gh`, либо
        текст отказа push/журнал печатает окружение вызова — значение
        находится в argv, трассе помощника или журнале.
        """
        out = io.StringIO()
        branch = self.task_branch_with_protected_touch()
        task = self.new_task(self.name, branch)
        refused_branch = f"task/{self.rng.randrange(10**6)}-refused"
        self.cgit("branch", refused_branch)
        refused_task = self.new_task(self.name, refused_branch)
        hook = self.bare / "hooks" / "pre-receive"
        with self.recording() as rec, contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            github_adapter.ensure_draft_mr(self.conn, task,
                                           store.get_task(self.conn, task))
            github_adapter.undraft_mr(self.conn, task,
                                      store.get_task(self.conn, task))
            self.pult_git(self.clone, "push", "-q", "origin",
                          f"{branch}:refs/heads/copy-{branch}")
            hook.write_text("#!/bin/sh\necho 'origin: push отклонён' >&2\n"
                            "exit 1\n", encoding="utf-8")
            hook.chmod(0o755)
            ok, detail = github_adapter.ensure_head_in_origin(
                self.conn, refused_task, refused_branch)
            print(detail)
        self.assertFalse(ok, self.msg("отказ origin не наблюдён"))
        self.assertEqual({c["gh_token"] for c in self.gh_calls()
                          if c["argv"][:1] == ["pr"]}, {self.token},
                         self.msg("операции AC-2 не сыграны с токеном"))
        secret = self.token
        self.assertNotIn(secret, out.getvalue(), self.msg("токен в выводе"))
        self.assertNotIn(secret, self.journal_text(task) + self.journal_text(
            refused_task), self.msg("токен в журнале задачи"))
        for path in self.root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                self.assertNotIn(secret.encode(), path.read_bytes(),
                                 self.msg(f"токен в файле {path}"))
        for call in rec.calls:
            self.assertNotIn(secret, " ".join(call.argv),
                             self.msg(f"токен в argv {call.argv[:3]}"))
        for call in self.gh_calls():
            self.assertNotIn(secret, " ".join(call["argv"]),
                             self.msg("токен в argv gh"))
        hosting = [c for c in rec.git_calls()
                   if git_subcommand(c.argv)[:1] and
                   git_subcommand(c.argv)[0] in REMOTE_SUBCOMMANDS]
        self.assertTrue(hosting, self.msg("хостинговых git-вызовов нет"))
        for call in hosting:
            trace = self.aux / f"trace-{self.rng.randrange(10**9)}.log"
            env = dict(call.env, GIT_TRACE=str(trace))
            self.passwords(env)
            text = trace.read_text(encoding="utf-8") if trace.exists() else ""
            self.assertNotIn(secret, text,
                             self.msg("токен в argv помощника учётных данных"))
        self.use_role_map()
        with mock.patch.object(stack, "check_stack", _stub_check_stack):
            env = runner.role_env("developer", task, project=self.name)
        self.assertNotIn(secret, " ".join(f"{k}={v}" for k, v in env.items()),
                         self.msg("токен в окружении роли"))

    def test_ac10_role_process_refuses_hosting(self):
        """Процесс роли: хостинговая операция проекта — именованный отказ.

        Оба признака роли (маркер `ARTEL_ROLE`; `HOME` дома роли без маркера)
        и обе записи (с `token_slot` и без поля): push в `origin` клона
        отказывает непустым текстом, ветки в `origin` нет; `undraft_mr`
        задачи проекта не зовёт `gh`; слот проекта не читается.

        Ловит мутацию: проверка роли смотрит только на `ARTEL_ROLE` (не на
        дом роли) либо стоит только на ветке с `token_slot` — запись без поля
        идёт прежней авторизацией в процессе роли: push проходит или слот
        читается.
        """
        for variant in ("маркер ARTEL_ROLE", "HOME дома роли"):
            for has_slot in (True, False):
                branch = f"task/{self.rng.randrange(10**6)}-role"
                self.cgit("branch", branch)
                task = self.new_task(self.name, branch, draft_mr_created=1)
                self.keychain.reset_mock()
                self.reset_gh_calls()
                slot_ctx = (contextlib.nullcontext() if has_slot
                            else self.without_token_slot())
                with self.subTest(роль=variant, token_slot=has_slot), \
                        slot_ctx, self.role_process(variant):
                    with self.recording():
                        try:
                            res = self.pult_git(self.clone, "push", "-q",
                                                "origin", f"{branch}:{branch}")
                            code, text = res.returncode, res.stdout + res.stderr
                        except Exception as exc:
                            code, text = 1, str(exc)
                        try:
                            github_adapter.undraft_mr(
                                self.conn, task, store.get_task(self.conn, task))
                        except Exception:
                            pass
                    self.assertNotEqual(code, 0, self.msg("push в процессе роли прошёл"))
                    self.assertTrue(text.strip(), self.msg("отказ без текста"))
                    self.assertEqual(self.origin_has(f"refs/heads/{branch}"), "",
                                     self.msg("ветка дошла до origin из роли"))
                    self.assertEqual(
                        [c for c in self.gh_calls() if c["argv"][:1] == ["pr"]],
                        [], self.msg("gh проекта вызван в процессе роли"))
                    self.assertNotIn(self.slot, self.slot_reads(),
                                     self.msg("слот проекта прочитан в роли"))

    def test_ac12_local_commands_skip_slot_remote_ones_use_it(self):
        """Локальные команды — без слота, remote-команды клона — с токеном.

        Слот пуст: случайные локальные команды (`status`, `log`, `rev-parse`,
        `branch`, `config`, `worktree list`) в клоне и в рабочей копии
        проекта проходят и не читают слот. Слот полон: `fetch`, `push`,
        `push --delete`, `pull`, `ls-remote` в клоне — в окружении каждого
        `credential fill` отдаёт токен слота. Вызов с `-C` самого каталога
        проекта — слот не читается, токена в окружении нет.

        Ловит мутацию: признак remote-подкоманды заменён на «любая команда
        в клоне» (локальная читает слот и при пустом отказывает) либо
        `pull`/`ls-remote`/`push --delete` выпали из перечня — их окружение
        без помощника; либо `-C .artel/projects/<имя>` считается клоном.
        """
        worktree = self.project_dir / "worktrees" / f"w{self.rng.randrange(1000)}"
        self.cgit("worktree", "add", "-q", "-b",
                  f"task/{self.rng.randrange(10**6)}-wt", str(worktree))
        local = [("status", "--porcelain"), ("log", "-1", "--format=%H"),
                 ("rev-parse", "HEAD"), ("branch", "--list"),
                 ("config", "--get", "remote.origin.url"), ("worktree", "list")]
        self.slots[self.slot] = None
        for path in (self.clone, worktree):
            for args in self.rng.sample(local, 4):
                with self.subTest(путь=str(path), локальная=args[0]):
                    self.keychain.reset_mock()
                    with self.recording():
                        res = self.pult_git(path, *args)
                    self.assertEqual(res.returncode, 0,
                                     self.msg(f"{args}: {res.stderr}"))
                    self.assertNotIn(self.slot, self.slot_reads(),
                                     self.msg(f"{args} читал слот"))
        self.slots[self.slot] = self.token
        doomed = f"task/{self.rng.randrange(10**6)}-del"
        self.cgit("push", "-q", "origin", f"{config.MAIN_BRANCH}:{doomed}")
        remote = [("fetch", "-q", "origin"),
                  ("push", "-q", "origin", f"HEAD:refs/heads/r{self.rng.randrange(10**6)}"),
                  ("push", "-q", "--delete", "origin", doomed),
                  ("pull", "-q", "--ff-only", "origin", config.MAIN_BRANCH),
                  ("ls-remote", "origin")]
        for args in remote:
            with self.subTest(remote=" ".join(args[:2])):
                with self.recording() as rec:
                    self.pult_git(self.clone, *args)
                calls = rec.git_calls(args[0])
                self.assertEqual(len(calls), 1, self.msg(str(rec.calls)))
                self.assert_slot_credential(calls[0].env, " ".join(args[:3]))
        with self.subTest(путь="каталог проекта"):
            self.keychain.reset_mock()
            with self.recording() as rec:
                self.pult_git(self.project_dir, "fetch", "-q", "origin")
            self.assertNotIn(self.slot, self.slot_reads(),
                             self.msg("-C каталога проекта читал слот"))
            for call in rec.git_calls():
                self.assertNotIn(self.token, " ".join(call.env.values()),
                                 self.msg("токен в окружении -C каталога проекта"))

    def test_ac13_push_by_project_url_from_outside_area(self):
        """Push по URL проекта из репозитория вне области проекта — с токеном.

        Источник `-C` — корень пульта (под `config.ROOT`, вне
        `config.PROJECTS`) либо посторонний репозиторий вне корня; URL
        аргумента push — `url` записи проекта. Push проходит, в его
        окружении `credential fill` отдаёт токен слота.

        Ловит мутацию: второй признак (URL push) не реализован или
        проверяется только для `-C` вне `config.ROOT` — у push из корня
        пульта помощника нет и `credential fill` отдаёт чужой пароль.
        """
        outside = self.aux / "outside"
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(outside))
        self.git("-C", str(outside), "commit", "-q", "--allow-empty", "-m", "x")
        for source in (config.ROOT, outside):
            ref = f"refs/heads/ext-{self.rng.randrange(10**6)}"
            with self.subTest(источник=str(source)):
                with self.recording() as rec:
                    res = self.pult_git(source, "push", "-q", self.url,
                                        f"HEAD:{ref}")
                self.assertEqual(res.returncode, 0, self.msg(res.stderr))
                self.assertTrue(self.origin_has(ref), self.msg("push не дошёл"))
                pushes = rec.git_calls("push")
                self.assertEqual(len(pushes), 1, self.msg(str(rec.calls)))
                self.assert_slot_credential(pushes[0].env, f"push из {source}")

    def test_ac14_check_base_branch_gh_gets_project_token(self):
        """`check_base_branch` внешнего проекта зовёт `gh` с `GH_TOKEN` слота.

        Запись проекта из `targets.yaml` песочницы; подставной `gh` отвечает
        на `repo view` и записывает свой `GH_TOKEN` — он равен токену слота.

        Ловит мутацию: токен подставляется в `ci.gh`, а прямой
        `subprocess.run` `check_base_branch` оставлен без него — `GH_TOKEN`
        вызова пуст.
        """
        entry = targets.target(self.name)
        with self.recording():
            check = doctor.check_base_branch(self.name, entry)
        views = [c for c in self.gh_calls() if c["argv"][:2] == ["repo", "view"]]
        self.assertTrue(views, self.msg(f"gh repo view не вызван: {check}"))
        self.assertEqual({c["gh_token"] for c in views}, {self.token},
                         self.msg("GH_TOKEN gh repo view — не токен слота"))

    def test_ac15_entry_without_slot_keeps_main_auth(self):
        """Запись без `token_slot` вне роли — прежняя авторизация.

        `targets.load` отдаёт запись проекта без поля: push в `origin` клона
        проходит с окружением как на main (окружение процесса плюс маркер
        пульта), слот не читается; `check_base_branch` с записью без поля
        зовёт `gh` без `GH_TOKEN`.

        Ловит мутацию: отсутствие поля трактуется как пустой слот (отказ)
        либо подставляется слот по умолчанию — push отказан, окружение
        отличается от main или `GH_TOKEN` непуст.
        """
        branch = f"task/{self.rng.randrange(10**6)}-noslot"
        self.cgit("branch", branch)
        with self.without_token_slot():
            entry = targets.target(self.name)
            self.assertNotIn("token_slot", entry)
            with self.recording() as rec:
                res = self.pult_git(self.clone, "push", "-q", "origin",
                                    f"{branch}:{branch}")
                doctor.check_base_branch(self.name, entry)
        self.assertEqual(res.returncode, 0, self.msg(res.stderr))
        self.assertTrue(self.origin_has(f"refs/heads/{branch}"))
        expected = dict(os.environ)
        expected[PULT_MARKER[0]] = PULT_MARKER[1]
        pushes = rec.git_calls("push")
        self.assertEqual(len(pushes), 1, self.msg(str(rec.calls)))
        self.assertEqual(pushes[0].env, expected,
                         self.msg("окружение push записи без слота ≠ main"))
        self.assertEqual(self.slot_reads(), [], self.msg("слот прочитан"))
        views = [c for c in self.gh_calls() if c["argv"][:2] == ["repo", "view"]]
        self.assertTrue(views, self.msg("gh repo view не вызван"))
        self.assertEqual({c["gh_token"] for c in views}, {None},
                         self.msg("GH_TOKEN у записи без слота"))


# ===================================================================== doctor


class ProjectDoctorTest(ProjectSandbox):
    """Проверки `doctor` по записи внешнего проекта (требование 5 SPEC)."""

    def setUp(self):
        super().setUp()
        self.good = self.doctor_checks()

    def test_ac6_bad_project_skills_fail(self):
        """Неверный `project_skills` записи проекта — fail проверки doctor.

        Имя вне `skills/` (`../…`) и имя несуществующего скила: у какой-то
        проверки `doctor` число fail растёт по сравнению с записью с пустым
        `project_skills`.

        Ловит мутацию: `doctor` не зовёт `brief.project_skills_refusal` по
        записи проекта (или отказ печатает как warn) — fail не появляется.
        """
        for bad in (f"../outside{self.rng.randrange(1000)}",
                    f"net-takogo-skila-{self.rng.randrange(10**6)}"):
            with self.subTest(project_skills=bad):
                self.write_targets(project_skills=[bad])
                checks = self.doctor_checks()
                good, bad_ = by_name(self.good), by_name(checks)
                grown = [n for n in bad_ if
                         Counter(c.status for c in bad_[n])["fail"] >
                         Counter(c.status for c in good.get(n, []))["fail"]]
                self.assertTrue(grown, self.msg(
                    f"нет fail по project_skills {bad}:\n{render(checks)}"))
        self.write_targets()

    def test_ac7_clone_freshness_states(self):
        """Проверка 5.1 на шести состояниях клона.

        Хорошее состояние (свежий `FETCH_HEAD`, `origin` = `url`, fetch
        проходит) против: клона нет — fail; `origin` не тот — fail; fetch
        отказан — fail (у одной и той же проверки ok сменился на fail).
        `FETCH_HEAD` старше 24 ч — warn «клон не обновлялся N ч» с N ≈
        возрасту; `FETCH_HEAD` нет — warn «клон ещё не обновлялся пультом».
        Рабочие копии (клон и рабочая копия задачи) не меняются, хотя в
        `origin` есть новый коммит; в окружении fetch самой проверки
        `credential fill` отдаёт токен слота.

        Ловит мутацию: возраст `FETCH_HEAD` берётся после fetch проверки
        (warn пропадает), отсутствие `FETCH_HEAD` даёт fail, fetch сделан
        `pull`-ом (голова клона сдвинулась), сверка `origin` с `url`
        пропущена (ok при чужом `origin`).
        """
        outsider = self.aux / "pusher"
        self.git("clone", "-q", self.url, str(outsider))
        self.git("-C", str(outsider), "commit", "-q", "--allow-empty", "-m", "new")
        self.git("-C", str(outsider), "push", "-q", "origin", config.MAIN_BRANCH)
        worktree = self.project_dir / "worktrees" / "wt"
        self.cgit("worktree", "add", "-q", "-b", "task/wt", str(worktree))

        def snapshot():
            return [(self.git("-C", str(p), "rev-parse", "HEAD"),
                     self.git("-C", str(p), "status", "--porcelain"),
                     self.git("-C", str(p), "show-ref", "--heads"))
                    for p in (self.clone, worktree)]

        before = snapshot()
        good = self.doctor_checks()
        self.assertEqual(snapshot(), before, self.msg("рабочие копии изменены"))
        fetches = [c for c in self.last_rec.git_calls("fetch")
                   if str(self.clone) in " ".join(c.argv) or self.url in c.argv]
        self.assertTrue(fetches, self.msg("проверка не делала fetch клона"))
        self.assert_slot_credential(fetches[0].env, "fetch проверки клона")

        fetch_head = self.clone / ".git" / "FETCH_HEAD"
        hours = 24 + self.rng.randrange(2, 200)
        with self.subTest(состояние="FETCH_HEAD старый"):
            self.cgit("fetch", "-q", "origin")
            old = time.time() - hours * 3600
            os.utime(fetch_head, (old, old))
            checks = self.doctor_checks()
            found = [re.search(r"клон не обновлялся (\d+) ч", c.detail)
                     for c in checks if c.status == "warn"]
            ages = [int(m.group(1)) for m in found if m]
            self.assertTrue(ages, self.msg(f"нет warn о давности:\n{render(checks)}"))
            self.assertTrue(any(abs(a - hours) <= 1 for a in ages),
                            self.msg(f"N={ages}, ожидалось ≈{hours}"))
        with self.subTest(состояние="FETCH_HEAD нет"):
            fetch_head.unlink(missing_ok=True)
            checks = self.doctor_checks()
            hits = lines_with(checks, "клон ещё не обновлялся пультом")
            self.assertTrue(hits, self.msg(render(checks)))
            self.assertEqual({c.status for c in hits}, {"warn"}, self.msg(str(hits)))
        self.cgit("fetch", "-q", "origin")

        def fail_state(label, spoil, restore, refuse=None):
            with self.subTest(состояние=label):
                spoil()
                try:
                    if refuse is None:
                        bad = self.doctor_checks()
                    else:
                        with self.recording() as rec:
                            rec.fail.append(refuse)
                            bad = doctor.all_checks(store.db())
                finally:
                    restore()
                self.assertTrue(flipped(good, bad, "ok", "fail"), self.msg(
                    f"{label}: ни одна проверка не сменила ok на fail:\n"
                    f"{render(bad)}"))

        moved = self.aux / "moved-clone"
        fail_state("клона нет", lambda: shutil.move(str(self.clone), str(moved)),
                   lambda: shutil.move(str(moved), str(self.clone)))
        other = self.aux / "other.git"
        self.git("clone", "-q", "--bare", self.url, str(other))
        fail_state("origin не тот",
                   lambda: self.cgit("remote", "set-url", "origin", f"file://{other}"),
                   lambda: self.cgit("remote", "set-url", "origin", self.url))
        fail_state("fetch отказан", lambda: None, lambda: None,
                   refuse=lambda argv: is_git(argv)
                   and git_subcommand(argv)[:1] == ["fetch"])

    def test_ac8_push_ci_protection_token_no_paths(self):
        """Проверки 5.2–5.6 на подготовленных состояниях.

        5.2 — пробный `push --dry-run` в `refs/artifacts/*` проходит (ok) /
        отказан origin (ok → fail), в его окружении `credential fill` даёт
        токен слота. 5.3 — файл workflow в дереве клона (коммит только в
        клоне, не в `origin`) с `pull_request` в трёх формах `on:` — ok,
        только `on: push` — warn «verifying будет ждать до потолка». 5.4 —
        `gh api …/branches/<base>/protection` ответил — строка без
        «недоступно», отказал — «недоступно» и не fail; `GH_TOKEN` вызова —
        токен слота. 5.5 — токен ≠ `gh auth token` — ok, равен — warn со
        ссылкой `docs/triggers.md` №24, слота нет — fail; значений токенов в
        выводе нет. 5.6 — пути `no_paths` (включая маску `**/conftest.py`)
        есть — ok, отсутствующий путь — warn с этим путём.

        Ловит мутацию: распознаётся одна форма `on:` (строка или список),
        маска `no_paths` проверяется как буквальный путь, равенство токенов
        не сверяется, отказ `gh api` даёт fail, `push --dry-run` идёт без
        помощника пульта, вывод проверки 5.5 печатает токен.
        """
        good = self.good
        # 5.2
        dry = [c for c in self.last_rec.git_calls("push")
               if "--dry-run" in c.argv]
        self.assertTrue(dry, self.msg("пробного push --dry-run нет"))
        self.assertTrue(any("refs/artifacts/" in " ".join(c.argv) for c in dry),
                        self.msg(f"push --dry-run не в refs/artifacts/*: {dry}"))
        self.assert_slot_credential(dry[0].env, "push --dry-run doctor")
        with self.subTest(проверка="5.2 отказ"):
            with self.recording() as rec:
                rec.fail.append(lambda argv: is_git(argv) and "--dry-run" in argv
                                and git_subcommand(argv)[:1] == ["push"])
                bad = doctor.all_checks(store.db())
            self.assertTrue(flipped(good, bad, "ok", "fail"),
                            self.msg(f"отказ push --dry-run без fail:\n{render(bad)}"))
        # 5.3
        workflow = ".github/workflows/ci.yml"
        with self.subTest(проверка="5.3 нет pull_request"):
            self.commit_file(workflow, "name: ci\non: push\njobs: {}\n", "без PR")
            checks = self.doctor_checks()
            warn = [c for c in lines_with(checks, "verifying будет ждать до потолка")
                    if c.status == "warn"]
            self.assertTrue(warn, self.msg(render(checks)))
            ci_names = {c.name for c in warn}
        forms = {"строка": "on: pull_request\n",
                 "список": "on: [push, pull_request]\n",
                 "отображение": "on:\n  push:\n  pull_request:\n    branches: [main]\n"}
        for form, text in forms.items():
            with self.subTest(проверка="5.3", форма=form):
                self.commit_file(workflow, f"name: ci\n{text}jobs: {{}}\n", form)
                checks = self.doctor_checks()
                mine = [c for c in checks if c.name in ci_names]
                self.assertTrue(mine, self.msg(render(checks)))
                self.assertEqual({c.status for c in mine}, {"ok"},
                                 self.msg(f"форма «{form}»: {mine}"))
        # 5.4
        protection = self.bin / "protection.json"
        data = protection.read_text(encoding="utf-8")
        with self.subTest(проверка="5.4"):
            self.reset_gh_calls()
            answered = self.doctor_checks()
            calls = [c for c in self.gh_calls() if c["argv"][:1] == ["api"] and
                     any(re.fullmatch(rf"/?repos/[^/]+/[^/]+/branches/"
                                      rf"{config.MAIN_BRANCH}/protection", a)
                         for a in c["argv"])]
            self.assertTrue(calls, self.msg(f"gh api protection не вызван: "
                                            f"{self.gh_calls()}"))
            self.assertEqual({c["gh_token"] for c in calls}, {self.token},
                             self.msg("GH_TOKEN gh api — не токен слота"))
            protection.unlink()
            refused = self.doctor_checks()
            protection.write_text(data, encoding="utf-8")
            na = lines_with(refused, "недоступно")
            self.assertTrue(na, self.msg(f"нет «недоступно»:\n{render(refused)}"))
            self.assertNotIn("fail", {c.status for c in na}, self.msg(str(na)))
            names = {c.name for c in na}
            same = [c for c in answered if c.name in names]
            self.assertTrue(same, self.msg(render(answered)))
            self.assertFalse([c for c in same if "недоступно" in c.detail],
                             self.msg(f"ответ gh не выведен: {same}"))
        # 5.5
        auth = self.bin / "auth-token.txt"
        with self.subTest(проверка="5.5"):
            auth.write_text(self.token, encoding="utf-8")
            equal = self.doctor_checks()
            auth.write_text(self.gh_auth, encoding="utf-8")
            warn = [c for c in equal if c.status == "warn"
                    and "docs/triggers.md" in c.detail and "24" in c.detail]
            self.assertTrue(warn, self.msg(render(equal)))
            names = {c.name for c in warn}
            self.assertEqual({c.status for c in good if c.name in names}, {"ok"},
                             self.msg("различные токены — не ok"))
            self.slots[self.slot] = None
            absent = self.doctor_checks()
            self.slots[self.slot] = self.token
            self.assertIn("fail", {c.status for c in absent if c.name in names},
                          self.msg(f"слот пуст — не fail:\n{render(absent)}"))
            for state in (good, equal, absent):
                text = render(state)
                self.assertNotIn(self.token, text, self.msg("токен слота в выводе"))
                self.assertNotIn(self.gh_auth, text, self.msg("токен gh в выводе"))
        # 5.6
        with self.subTest(проверка="5.6"):
            missing = f"net/{self.rng.randrange(10**6)}.txt"
            self.write_targets(no_paths=self.no_paths + [missing])
            checks = self.doctor_checks()
            self.write_targets()
            warn = [c for c in checks if c.status == "warn" and missing in c.detail]
            self.assertTrue(warn, self.msg(render(checks)))
            names = {c.name for c in warn}
            self.assertEqual({c.status for c in good if c.name in names}, {"ok"},
                             self.msg("пути no_paths с маской есть — не ok"))

    def test_ac9_artel_record_not_applicable(self):
        """По записи артели `doctor` выводит «неприменимо», а не молчит.

        `targets.yaml` — только запись артели: среди строк `doctor` есть
        строка «неприменимо», ни одна такая строка не fail.

        Ловит мутацию: проверки п.5 для артели пропускаются циклом без строки
        (`continue` по `is_artel`) — «неприменимо» в выводе нет.
        """
        self.write_targets(external=False)
        checks = self.doctor_checks()
        na = lines_with(checks, "неприменимо")
        self.assertTrue(na, self.msg(render(checks)))
        self.assertNotIn("fail", {c.status for c in na}, self.msg(str(na)))

    def test_ac10_doctor_in_role_skips_operator_checks(self):
        """Процесс роли: 5.1, 5.2, 5.5 — пропуск «только в сессии Оператора».

        Оба признака роли: не меньше трёх строк «только в сессии Оператора»,
        ни fetch клона, ни пробного `push --dry-run`, слот проекта не читается.

        Ловит мутацию: признак роли берётся только по `ARTEL_ROLE` либо
        пропуск стоит у одной 5.1 — в варианте «HOME дома роли» fetch клона
        сделан или слот прочитан, строк пропуска меньше трёх.
        """
        for variant in ("маркер ARTEL_ROLE", "HOME дома роли"):
            with self.subTest(роль=variant), self.role_process(variant):
                self.keychain.reset_mock()
                checks = self.doctor_checks()
                skips = lines_with(checks, "только в сессии Оператора")
                self.assertGreaterEqual(len(skips), 3, self.msg(render(checks)))
                fetches = [c for c in self.last_rec.git_calls("fetch")
                           if str(self.clone) in " ".join(c.argv)
                           or self.url in c.argv]
                self.assertEqual(fetches, [], self.msg("fetch клона в роли"))
                dry = [c for c in self.last_rec.git_calls("push")
                       if "--dry-run" in c.argv]
                self.assertEqual(dry, [], self.msg("push --dry-run в роли"))
                self.assertNotIn(self.slot, self.slot_reads(),
                                 self.msg("слот проекта прочитан в роли"))

    def test_ac15_doctor_warns_missing_token_slot(self):
        """Запись без `token_slot` — warn «нет токена проекта».

        Ловит мутацию: отсутствие поля даёт fail (как пустой слот) или
        проверка 5.5 молчит — warn с этим текстом нет.
        """
        with self.without_token_slot():
            checks = self.doctor_checks()
        hits = [c for c in lines_with(checks, "нет токена проекта")
                if c.status == "warn"]
        self.assertTrue(hits, self.msg(render(checks)))


# ================================================================ песочница


class SandboxKeychainTmpRootTest(TmpRootTest):
    """`keychain.token` в лёгкой песочнице `TmpRootTest`."""

    def test_ac16_sandbox_keychain_is_fake(self):
        """В `TmpRootTest` `keychain.token` — тестовый токен от имени слота.

        Случайные имена слотов: значение — непустая строка, повторный вызов
        даёт то же, разные слоты — разные значения; `security` не запускался.

        Ловит мутацию: подмены в песочнице нет либо она отдаёт одну константу
        на все слоты — значение `None`/запуск `security` или равные значения
        разных слотов.
        """
        check_fake_keychain(self)


class SandboxKeychainRealGitTest(RealGitSandbox):
    """`keychain.token` в песочнице с настоящим git (`RealGitSandbox`)."""

    def test_ac16_real_git_sandbox_keychain_is_fake(self):
        """В `RealGitSandbox` `keychain.token` — тестовый токен от имени слота.

        Ловит мутацию: подмена стоит только в `TmpRootTest.setUp`, а
        `RealGitSandbox.setUp` (не зовущий его) её не получает — `None` или
        запуск `security`.
        """
        check_fake_keychain(self)


def check_fake_keychain(test) -> None:
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    launched = []
    real_run = subprocess.run

    def run(cmd, *args, **kwargs):
        argv = [cmd] if isinstance(cmd, (str, Path)) else list(cmd)
        if argv and Path(str(argv[0])).name == "security":
            launched.append(argv)
            return subprocess.CompletedProcess(argv, 44, "", "песочница")
        return real_run(cmd, *args, **kwargs)

    slots = {f"slot-{rng.randrange(10**9)}-{''.join(rng.choice(string.ascii_lowercase) for _ in range(4))}"
             for _ in range(4)}
    with mock.patch.object(subprocess, "run", side_effect=run), \
            mock.patch.object(subprocess, "Popen",
                              side_effect=AssertionError("Popen в keychain")):
        values = {slot: keychain.token(slot) for slot in slots}
        again = {slot: keychain.token(slot) for slot in slots}
    test.assertEqual(launched, [], f"зерно: {seed}; запущен security")
    for slot, value in values.items():
        test.assertIsInstance(value, str, f"зерно: {seed}; {slot}: {value!r}")
        test.assertTrue(value, f"зерно: {seed}; {slot}: пусто")
    test.assertEqual(values, again, f"зерно: {seed}; значение слота не постоянно")
    test.assertEqual(len(set(values.values())), len(slots),
                     f"зерно: {seed}; разные слоты дали одно значение")
