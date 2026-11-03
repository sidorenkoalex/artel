"""Второй рубеж белого списка отправок на стенде с настоящим git (SPEC
01M6EZXVFGCHB1S4W45AWJ0QH6): клон `target-human`, заведённый пультом,
опция `-c core.hooksPath` в отправке пульта, сверки окружения и
конфигурации перед отправкой, строка `doctor` `clone-push-hook` и её
починка, клон и подмодули с токеном слота.

Планка задачи — разовая; здесь — долгоживущий минимум тех же свойств
(REVIEW итерации 1, R1-F1). Стенд — `real_git`: `config.ROOT` — настоящий
git-репозиторий, в него закоммичен каталог `scripts/git-hooks` проверяемого
дерева (эталон хука — `HEAD` главной копии). Записи проектов — в локальном
слое, `url` записи — путь bare-репозитория во временном каталоге. `HOME` —
временный каталог, переменные `GIT_*` процесса сняты. Шпион подменяет
`subprocess.run`/`Popen`: отправка журналируется и не исполняется (если не
сказано иное), прочие вызовы идут к настоящему git.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from orchestrator import (config, doctor, gitcmd, idgen, keychain, repo_context,
                          store, targets, workspace)

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
CODE_ROOT = Path(__file__).resolve().parent.parent
TARGET_HUMAN = "target-human"
OPERATOR = "operator"
CHECK = "clone-push-hook"
GLOBALS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace",
                      "--config-env", "--exec-path", "--super-prefix")


def subcommand(argv) -> str | None:
    if not isinstance(argv, (list, tuple)) or not argv:
        return None
    if Path(os.fsdecode(argv[0])).name != "git":
        return None
    words = [os.fsdecode(a) for a in argv[1:]]
    i = 0
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in GLOBALS_WITH_VALUE else 1
    return words[i] if i < len(words) else None


def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in (gitcmd.PULT_MARKER_ENV,
                                                     config.ARTEL_TASK_ENV)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(repo: Path, *args: str, env: dict | None = None, check: bool = True):
    res = REAL_RUN(["git", "-C", str(repo), *args], capture_output=True,
                   text=True, env=env if env is not None else clean_env(),
                   timeout=60)
    if check:
        assert res.returncode == 0, f"git {' '.join(args)} в {repo}: {res.stderr}"
    return res


def out(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


class Stand:
    def __init__(self, monkeypatch, tmp_path: Path):
        self.monkeypatch = monkeypatch
        self.tmp = tmp_path
        self.projects: dict = {}
        self.calls: list = []
        self.pushes: list = []
        self.counter = 0
        home = tmp_path / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            "[user]\n\tname = artel tests\n\temail = artel@example.invalid\n"
            "[protocol \"file\"]\n\tallow = always\n"
            "[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))
        for name in list(os.environ):
            if name.startswith("GIT_") or name in (gitcmd.PULT_MARKER_ENV,
                                                   config.ARTEL_TASK_ENV):
                monkeypatch.delenv(name, raising=False)
        root = Path(config.ROOT)
        shutil.copytree(CODE_ROOT / "scripts" / "git-hooks",
                        root / "scripts" / "git-hooks",
                        ignore=shutil.ignore_patterns("__pycache__"),
                        dirs_exist_ok=True)
        git(root, "add", "-A", "scripts")
        git(root, "commit", "-q", "--no-verify", "-m", "хуки пульта")

    def name(self) -> str:
        self.counter += 1
        return f"qproj{self.counter}"

    @staticmethod
    def human_hooks_dir() -> Path:
        return Path(config.ROOT) / "scripts" / "git-hooks" / TARGET_HUMAN

    def bare(self, label: str, files: dict | None = None,
             submodule: Path | None = None) -> Path:
        bare = self.tmp / f"{label}.git"
        git(self.tmp, "init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(bare))
        seed = self.tmp / f"seed-{label}"
        git(self.tmp, "init", "-q", "-b", config.MAIN_BRANCH, str(seed))
        for rel, text in (files or {"README": f"{label}\n"}).items():
            (seed / rel).write_text(text, encoding="utf-8")
        git(seed, "add", "-A")
        if submodule is not None:
            git(seed, "-c", "protocol.file.allow=always", "submodule", "add",
                "-q", str(submodule), "sub")
        git(seed, "commit", "-q", "--no-verify", "-m", f"init {label}")
        git(seed, "push", "-q", "--no-verify", str(bare),
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return bare

    def declare(self, name: str, gate: str, url: str) -> None:
        self.projects[name] = (gate, url)
        text = "targets:\n"
        for pname, (pgate, purl) in self.projects.items():
            text += (
                f"  {pname}:\n"
                f"    description:\n      base: {config.MAIN_BRANCH}\n"
                f"      test_profile:\n        command: [python3, -m, pytest]\n"
                f"        long_lived_dir: tests\n"
                f"        long_lived_name: test_<id>_<name>.py\n"
                f"    policy:\n      no_paths: []\n      project_skills: []\n"
                f"      merge_gate: {pgate}\n"
                f"      weakening_scope: [tests/**/*.py]\n"
                f"      mutation_claim_scope: [tests/test_*.py]\n"
                f"    machine:\n      forge: github\n"
                f"      url: {purl}\n"
                f"      token_slot: {pname}-token\n")
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")

    def project(self, gate: str = TARGET_HUMAN) -> tuple:
        name = self.name()
        self.declare(name, gate, str(self.bare(name)))
        clone, error = workspace.ensure_clone(name)
        assert error is None, error
        return name, clone

    def ready_push(self, gate: str = TARGET_HUMAN) -> tuple:
        """(клон, ветка) с живой задачей; отправка без находок уже дошла
        до шпиона."""
        name, clone = self.project(gate)
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-a-b"
        git(clone, "branch", "-f", branch, config.MAIN_BRANCH)
        store.insert_task(store.db(), task_id, "Задача", "in_dev", branch, name,
                          config.DEFAULT_BUDGET_USD)
        self.spy()
        res = gitcmd.in_repo(clone, "push", "origin", branch)
        assert res.returncode == 0 and len(self.pushes) == 1, res.stderr
        return clone, branch

    def spy(self, *, execute_push: bool = False) -> None:
        def record(argv, kwargs):
            env = kwargs.get("env")
            self.calls.append({"argv": [os.fsdecode(a) for a in argv]
                               if isinstance(argv, (list, tuple)) else argv,
                               "env": dict(env if env is not None else os.environ)})
            return subcommand(argv)

        def run(argv, *args, **kwargs):
            if record(argv, kwargs) == "push" and not execute_push:
                self.pushes.append(self.calls[-1]["argv"])
                text = bool(kwargs.get("text") or kwargs.get("encoding"))
                empty = "" if text else b""
                return subprocess.CompletedProcess(argv, 0, empty, empty)
            return REAL_RUN(argv, *args, **kwargs)

        def popen(argv, *args, **kwargs):
            if record(argv, kwargs) == "push" and not execute_push:
                self.pushes.append(self.calls[-1]["argv"])
                raise OSError("стенд: отправка процессом Popen не исполняется")
            return REAL_POPEN(argv, *args, **kwargs)

        self.monkeypatch.setattr(subprocess, "run", run)
        self.monkeypatch.setattr(subprocess, "Popen", popen)

    def unspy(self) -> None:
        """Шпион снят: прямые вызовы теста (`REAL_RUN` зовёт `Popen` модуля)
        снова идут к настоящему git без перехвата отправки."""
        self.monkeypatch.setattr(subprocess, "run", REAL_RUN)
        self.monkeypatch.setattr(subprocess, "Popen", REAL_POPEN)


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(monkeypatch, tmp_path)


def push_line():
    found = [c for c in doctor.check_clone_hooks() if c.name == CHECK]
    assert len(found) == 1, found
    return found[0]


def assert_refused(stand, res, needle: str) -> None:
    assert res.returncode != 0, f"{needle}: отправка не отказана"
    assert len(stand.pushes) == 1, f"{needle}: шпион видел {stand.pushes[1:]}"
    assert needle.lower() in (res.stderr or "").lower(), res.stderr


# --- клон, заведённый пультом (требования 1, 2) ----------------------------

def test_ensure_clone_human_gets_own_hooks_and_policy_others_old_path(stand):
    """Клон `target-human` — `core.hooksPath` на каталог `target-human` и
    эталон файла политики в общем каталоге git; клон `operator` — прежний
    общий каталог хуков и без файла политики.

    Ловит мутацию: `ensure_clone` ставит всем клонам прежний
    `workspace.hooks_path()` либо не пишет файл политики (`pre-push`
    `target-human` откажет любой отправке); каталог `target-human` ставится и
    клону `operator`.
    """
    name, clone = stand.project(TARGET_HUMAN)
    value = out(clone, "config", "--get", "core.hooksPath")
    assert Path(value) == stand.human_hooks_dir(), value
    policy = clone / ".git" / workspace.PUSH_POLICY_NAME
    assert policy.read_text(encoding="utf-8") == (
        f"project={name}\nbase={config.MAIN_BRANCH}\n"
        f"branch_template={targets.DEFAULT_BRANCH_TEMPLATE}\n"
        f"artifacts_prefix=refs/artifacts/\n")
    _other, other = stand.project(OPERATOR)
    assert Path(out(other, "config", "--get", "core.hooksPath")) == \
        workspace.hooks_path()
    assert not (other / ".git" / workspace.PUSH_POLICY_NAME).exists()


def test_human_pre_commit_refuses_main_commit_without_marker(stand):
    """`pre-commit` каталога `target-human` отказывает ручному коммиту на
    `main` клона без `ARTEL_PULT_GIT=1`; с маркером коммит проходит.

    Ловит мутацию: в каталоге `target-human` нет `pre-commit` (или он не
    исполняемый) — перевод клона на отдельный каталог снимает защиту `main`.
    """
    _name, clone = stand.project(TARGET_HUMAN)
    refused = git(clone, "commit", "-q", "--allow-empty", "-m", "x", check=False)
    assert refused.returncode != 0, "коммит на main без маркера прошёл"
    env = clean_env()
    env[gitcmd.PULT_MARKER_ENV] = "1"
    git(clone, "commit", "-q", "--allow-empty", "-m", "x", env=env)


# --- опция -c core.hooksPath в отправке пульта (требование 6) ---------------

def hooks_pairs(argv: list) -> list:
    return [argv[i + 1] for i in range(len(argv) - 1)
            if argv[i] == "-c" and argv[i + 1].lower().startswith("core.hookspath=")]


def test_human_push_carries_hooks_path_operator_does_not(stand):
    """Отправка пульта из клона `target-human` несёт `-c
    core.hooksPath=<каталог target-human>`; отправка `operator` — нет.

    Ловит мутацию: `_push_plan` не вставляет опцию (или вставляет прежний
    общий каталог) либо вставляет её всем внешним проектам.
    """
    stand.ready_push(TARGET_HUMAN)
    pairs = hooks_pairs(stand.pushes[0])
    assert any(gitcmd.same_dir(p.split("=", 1)[1], stand.human_hooks_dir())
               for p in pairs), stand.pushes[0]
    stand.unspy()
    stand.pushes.clear()
    stand.ready_push(OPERATOR)
    assert hooks_pairs(stand.pushes[0]) == [], stand.pushes[0]


# --- сверки перед отправкой (требование 12) --------------------------------

@pytest.mark.parametrize("variable", ["GIT_SSH_COMMAND", "GIT_CONFIG_GLOBAL",
                                      "GIT_CONFIG_SYSTEM"])
def test_transport_env_refuses_before_git(stand, tmp_path, variable):
    """`GIT_SSH_COMMAND`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM` в
    окружении — отказ отправки `target-human` до вызова git, причина
    называет переменную.

    Ловит мутацию: перечень переменных сверки окружения не дополнен этими
    тремя — отправка с подменённым транспортом или конфигурацией доходит до
    git.
    """
    clone, branch = stand.ready_push()
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    value = "ssh -o BatchMode=yes" if variable == "GIT_SSH_COMMAND" else str(empty)
    stand.monkeypatch.setenv(variable, value)
    assert_refused(stand, gitcmd.in_repo(clone, "push", "origin", branch), variable)


@pytest.mark.parametrize("finding", ["url", "insteadOf", "sshCommand"])
def test_config_redirect_refuses_before_git(stand, tmp_path, finding):
    """`remote.origin.url`, не равный адресу записи, `url.<x>.insteadOf` и
    `core.sshCommand` в конфигурации клона — отказ отправки до вызова git,
    причина называет ключ.

    Ловит мутацию: сверка `remote.origin.url` с `url` записи пропущена либо
    `insteadOf`/`core.sshCommand` не входят в перечень ключей
    перенаправления.
    """
    clone, branch = stand.ready_push()
    other = str(tmp_path / "other.git")
    url = out(clone, "remote", "get-url", "origin")
    setup, needle = {
        "url": (("remote", "set-url", "origin", other), "remote.origin.url"),
        "insteadOf": (("config", f"url.{other}.insteadOf", url), "insteadOf"),
        "sshCommand": (("config", "core.sshCommand", "ssh"), "core.sshCommand"),
    }[finding]
    git(clone, *setup)
    assert_refused(stand, gitcmd.in_repo(clone, "push", "origin", branch), needle)


def test_git_ssh_env_refuses_before_git(stand):
    """`GIT_SSH` (без `_COMMAND`) в окружении — отказ отправки `target-human`
    до вызова git, причина называет переменную.

    Ловит мутацию: `GIT_SSH` не входит в перечень переменных транспорта —
    отправка с подменённой программой ssh доходит до git.
    """
    clone, branch = stand.ready_push()
    stand.monkeypatch.setenv("GIT_SSH", "/usr/bin/ssh")
    assert_refused(stand, gitcmd.in_repo(clone, "push", "origin", branch),
                   "GIT_SSH")


@pytest.mark.parametrize("scope", ["local", "global"])
def test_second_origin_url_refuses_before_git(stand, tmp_path, scope):
    """Второе значение `remote.origin.url` — в локальной конфигурации клона
    либо в `~/.gitconfig` — отказ отправки до вызова git: `git push origin`
    шлёт на каждое значение, и ветка ушла бы и на чужой адрес.

    Ловит мутацию: адрес читается `--get` (последнее значение) либо
    `--get-all` только локального слоя — при последнем значении, равном
    адресу записи, второй адрес проходит сверку.
    """
    clone, branch = stand.ready_push()
    url = out(clone, "config", "--get", "remote.origin.url")
    other = str(tmp_path / "other.git")
    if scope == "local":
        # Чужой адрес первым, адрес записи последним: `--get` видит адрес записи.
        git(clone, "config", "--unset-all", "remote.origin.url")
        git(clone, "config", "--add", "remote.origin.url", other)
        git(clone, "config", "--add", "remote.origin.url", url)
    else:
        gitconfig = Path(os.environ["HOME"]) / ".gitconfig"
        gitconfig.write_text(gitconfig.read_text(encoding="utf-8")
                             + f"[remote \"origin\"]\n\turl = {other}\n",
                             encoding="utf-8")
    assert out(clone, "config", "--get", "remote.origin.url") == url
    assert_refused(stand, gitcmd.in_repo(clone, "push", "origin", branch),
                   "remote.origin.url")


@pytest.mark.parametrize("key", ["--get-regexp", "core.hooksPath",
                                 "remote.origin.pushurl"])
def test_config_read_failure_refuses_before_git(stand, key):
    """Сбой `git config` (код не 0 и не 1) на любой сверке конфигурации —
    отказ отправки до вызова git с причиной «не прочитана», а не «ключа
    нет».

    Ловит мутацию: чтение конфигурации сверок отдаёт пустую строку при
    сбое git — `insteadOf`/`sshCommand`/`core.hooksPath`/`pushurl` молча не
    сверены, отправка доходит до git.
    """
    clone, branch = stand.ready_push()
    spied = subprocess.run

    def failing(argv, *args, **kwargs):
        words = [os.fsdecode(a) for a in argv] if isinstance(argv, list) else []
        if subcommand(argv) == "config" and key in words:
            return subprocess.CompletedProcess(argv, 128, "", "fatal: сбой")
        return spied(argv, *args, **kwargs)

    stand.monkeypatch.setattr(subprocess, "run", failing)
    assert_refused(stand, gitcmd.in_repo(clone, "push", "origin", branch),
                   "не прочитана")


# --- файл политики перед отправкой пульта (требование 4) ---------------------

@pytest.mark.parametrize("damage", ["changed", "deleted"])
def test_push_rewrites_policy_from_entry(stand, damage):
    """Перед отправкой пульт перезаписывает файл политики эталоном по
    записи проекта: изменённый или удалённый файл после отправки снова
    равен эталону, отправка доходит до git.

    Ловит мутацию: файл политики перед отправкой не перезаписывается —
    подмена политики ролью (иной шаблон ветки, иной `base`) переживает
    отправку пульта.
    """
    clone, branch = stand.ready_push()
    policy = clone / ".git" / workspace.PUSH_POLICY_NAME
    reference = policy.read_bytes()
    if damage == "changed":
        policy.write_text("project=x\nbase=dev\nbranch_template={ref}\n"
                          "artifacts_prefix=refs/\n", encoding="utf-8")
    else:
        policy.unlink()
    res = gitcmd.in_repo(clone, "push", "origin", branch)
    assert res.returncode == 0 and len(stand.pushes) == 2, res.stderr
    assert policy.read_bytes() == reference


@pytest.mark.parametrize("damage", ["unreadable", "directory"])
def test_unusable_policy_refuses_before_git(stand, damage):
    """Файл политики, который пульт не может записать или прочитать (нет
    прав, на его месте каталог), — отказ отправки до вызова git, причина
    называет путь файла.

    Ловит мутацию: сбой записи/чтения файла политики в `gitcmd` не
    сверяется — отказ остаётся только хуку, причина пульта его не называет.
    """
    clone, branch = stand.ready_push()
    policy = clone / ".git" / workspace.PUSH_POLICY_NAME
    if damage == "unreadable":
        policy.chmod(0)
    else:
        policy.unlink()
        policy.mkdir()
    try:
        assert_refused(stand, gitcmd.in_repo(clone, "push", "origin", branch),
                       str(policy))
    finally:
        if damage == "unreadable":
            policy.chmod(0o644)


# --- строка doctor clone-push-hook (требования 8, 9) ------------------------

def strip_exec(path: Path) -> None:
    path.chmod(path.stat().st_mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


@pytest.mark.parametrize("damage", ["pre-push-text", "pre-commit-exec",
                                    "policy-text", "policy-deleted",
                                    "hooks-foreign", "hooks-old", "hooks-unset"])
def test_push_hook_line_fails_on_damage_and_fix_restores(stand, tmp_path, damage):
    """Каждое расхождение клона `target-human` — строка `clone-push-hook`
    `fail`; после `doctor --fix` — `ok`, хуки и файл политики равны эталону,
    `core.hooksPath` — каталог `target-human`.

    Ловит мутацию: хук сверяется по наличию, а не по сумме с `HEAD`, или без
    бита исполнения; файл политики — по наличию; прежний общий каталог либо
    снятый `core.hooksPath` не расхождение; починка не переписывает файлы,
    не ставит бит или ставит прежний `hooks_path()`.
    """
    name, clone = stand.project(TARGET_HUMAN)
    assert push_line().status == "ok", push_line().detail
    hooks = stand.human_hooks_dir()
    policy = clone / ".git" / workspace.PUSH_POLICY_NAME
    reference = {h: (hooks / h).read_bytes() for h in ("pre-push", "pre-commit")}
    want_policy = policy.read_bytes()
    if damage == "pre-push-text":
        with (hooks / "pre-push").open("a", encoding="utf-8") as fh:
            fh.write("exit 0\n")
    elif damage == "pre-commit-exec":
        strip_exec(hooks / "pre-commit")
    elif damage == "policy-text":
        policy.write_text(policy.read_text(encoding="utf-8").replace(
            "base=main", "base=other"), encoding="utf-8")
    elif damage == "policy-deleted":
        policy.unlink()
    elif damage == "hooks-unset":
        git(clone, "config", "--unset-all", "core.hooksPath")
    else:
        path = tmp_path / "foreign" if damage == "hooks-foreign" else hooks.parent
        git(clone, "config", "core.hooksPath", str(path))
    broken = push_line()
    assert broken.status == "fail", f"{damage}: {broken.status} {broken.detail}"
    assert name in broken.detail, broken.detail
    doctor._fix_project_clones()
    for hook, text in reference.items():
        assert (hooks / hook).read_bytes() == text, hook
        assert os.access(hooks / hook, os.X_OK), hook
    assert policy.read_bytes() == want_policy
    assert Path(out(clone, "config", "--get", "core.hooksPath")) == hooks
    repaired = push_line()
    assert repaired.status == "ok", f"{damage}: {repaired.detail}"


def test_worktree_hooks_path_fails_with_value(stand, tmp_path):
    """`core.hooksPath` в `config.worktree` рабочей копии задачи клона
    `target-human` — `fail`, detail называет значение.

    Ловит мутацию: строка читает `core.hooksPath` только из конфигурации
    клона, не из рабочих копий `git worktree list`.
    """
    name, clone = stand.project(TARGET_HUMAN)
    wt = Path(config.PROJECTS) / name / "worktrees" / "T1"
    git(clone, "worktree", "add", "-q", "-b", "task/t1-a", str(wt))
    assert push_line().status == "ok"
    foreign = str(tmp_path / "role-hooks")
    git(clone, "config", "extensions.worktreeConfig", "true")
    git(wt, "config", "--worktree", "core.hooksPath", foreign)
    broken = push_line()
    assert broken.status == "fail" and foreign in broken.detail, broken.detail


def test_push_hook_line_skip_without_reference_and_absent_without_clones(stand):
    """Без клонов `target-human` строки нет, а клон `operator` с неверным
    `core.hooksPath` — по-прежнему `warn` строки `clone-hooks`; хука нет в
    `HEAD` главной копии — `skip` (ANSWER-1 п. 5).

    Ловит мутацию: строка выдаётся и без клонов `target-human`; клоны
    `target-human` не исключены из `clone-hooks` либо клоны прочих
    проектов попали в `clone-push-hook`; отсутствие эталона в `HEAD` даёт
    `fail` или `ok` вместо `skip`.
    """
    other_name, other = stand.project(OPERATOR)
    git(other, "config", "core.hooksPath", "/elsewhere")
    checks = doctor.check_clone_hooks()
    assert [c for c in checks if c.name == CHECK] == []
    human_name, _clone = stand.project(TARGET_HUMAN)
    checks = doctor.check_clone_hooks()
    hooks_line = [c for c in checks if c.name == "clone-hooks"]
    assert [c.status for c in hooks_line] == ["warn"], hooks_line
    assert other_name in hooks_line[0].detail, hooks_line[0].detail
    assert human_name not in hooks_line[0].detail, hooks_line[0].detail
    assert push_line().status == "ok", push_line().detail
    git(Path(config.ROOT), "rm", "-q", "--cached",
        f"scripts/git-hooks/{TARGET_HUMAN}/pre-push")
    git(Path(config.ROOT), "commit", "-q", "--no-verify", "-m", "без хука")
    assert push_line().status == "skip"


# --- клон и подмодули с токеном слота (требование 10) -----------------------

def carries_token(call: dict, token: str) -> bool:
    env = call["env"]
    helper = any(gitcmd.HOSTING_TOKEN_ENV in v for k, v in env.items()
                 if k.startswith("GIT_CONFIG_VALUE_"))
    return env.get(gitcmd.HOSTING_TOKEN_ENV) == token and helper


def test_clone_and_submodules_carry_slot_token(stand):
    """Подготовка клона проекта со `token_slot` и подмодулем: вызов `clone` и
    `submodule update` несут токен слота и помощник пульта, подмодуль
    извлечён.

    Ловит мутацию: `clone` не хостинговая подкоманда (клон без токена);
    подмодули не клонируются либо клонируются мимо `gitcmd`, без токена.
    """
    name = stand.name()
    sub = stand.bare(f"{name}-sub", files={"sub.txt": "sub\n"})
    stand.declare(name, OPERATOR, str(stand.bare(name, submodule=sub)))
    stand.spy(execute_push=True)
    clone, error = workspace.ensure_clone(name)
    assert error is None, error
    token = keychain.token(f"{name}-token")
    clones = [c for c in stand.calls if subcommand(c["argv"]) == "clone"]
    assert clones and all(carries_token(c, token) for c in clones), clones
    subs = [c for c in stand.calls if subcommand(c["argv"]) == "submodule"]
    assert subs and all(carries_token(c, token) for c in subs), subs
    assert (clone / "sub" / "sub.txt").read_text(encoding="utf-8") == "sub\n"


def test_clone_without_slot_goes_without_token(stand):
    """Запись без `token_slot`: клон идёт без токена, как прежде.

    Ловит мутацию: токен ставится клону любого внешнего проекта либо
    отсутствие слота даёт отказ клона.
    """
    name = stand.name()
    stand.declare(name, OPERATOR, str(stand.bare(name)))
    real_load = targets.load

    def load():
        entries = {k: dict(v) for k, v in real_load().items()}
        entries[name].pop("token_slot", None)
        return entries

    stand.monkeypatch.setattr(targets, "load", load)
    stand.spy(execute_push=True)
    clone, error = workspace.ensure_clone(name)
    assert error is None and clone == repo_context.clone_path(name), error
    clones = [c for c in stand.calls if subcommand(c["argv"]) == "clone"]
    assert clones
    assert not any(gitcmd.HOSTING_TOKEN_ENV in c["env"] for c in clones)
