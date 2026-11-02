"""Общий стенд планки: главная копия пульта с каталогом хуков из проверяемого дерева, проекты с локальным bare-`origin`, клоны через `workspace.ensure_clone`, шпион процессов.

Стенд строится поверх фикстуры `real_git` (`tests/sandbox.py::RealGitSandbox`):
`config.ROOT` — настоящий git-репозиторий во временном каталоге. Каталог
`scripts/git-hooks` проверяемого дерева копируется в `config.ROOT` и
коммитится — так «эталон хука» (содержимое в коммите `HEAD` главной копии)
и «каталог хуков пульта проекта» (`<config.ROOT>/scripts/git-hooks[/…]`)
берутся из проверяемого кода, как требует преамбула критериев SPEC.

Записи проектов — в локальном слое `targets.local_path()`; `url` записи —
путь bare-репозитория во временном каталоге, поэтому `remote.origin.url`
клона, заведённого пультом, совпадает с адресом записи. `HOME` процесса —
временный каталог: глобальная конфигурация git Оператора на стенд не
влияет (в ней лишь идентичность и `protocol.file.allow=always` для
подмодуля из локального пути). Переменные окружения, которые сверки
отправки отказывают (`GIT_DIR`, `GIT_CONFIG_*`, `GIT_SSH_COMMAND`, …), и
`ARTEL_TASK` сняты.
"""
import os
import random
import shutil
import subprocess
from pathlib import Path

from orchestrator import config, gitcmd, idgen, repo_context, store, targets, workspace

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
CODE_ROOT = Path(gitcmd.__file__).resolve().parents[1]
LETTERS = "abcdefghijkmnopqrstuvwxyz"
TARGET_HUMAN = "target-human"
OPERATOR = "operator"
POLICY_NAME = "artel-push-policy"
# Хвост пути файла политики, общий у относительной (`.git/…`) и абсолютной
# (`<клон>/.git/…`) формы — по нему видно, что причина называет путь.
POLICY_TAIL = f".git/{POLICY_NAME}"
ARTIFACTS_PREFIX = "refs/artifacts/"
GLOBAL_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace",
                     "--config-env", "--exec-path", "--super-prefix")
HOSTING = ("fetch", "push", "pull", "ls-remote", "clone")
# Переменные, которые снимаются с окружения процесса стенда: сверки отправки
# пульта отказывают их присутствию (SPEC, требование 12).
DROPPED_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_SSH_COMMAND",
               "GIT_SSH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
               "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_NOSYSTEM",
               "XDG_CONFIG_HOME", "GIT_ASKPASS", "SSH_ASKPASS",
               gitcmd.PULT_MARKER_ENV, config.ARTEL_TASK_ENV)


def subcommand(argv) -> str | None:
    """Подкоманда git-вызова после глобальных опций; None — не git."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return None
    if Path(os.fsdecode(argv[0])).name != "git":
        return None
    words = [os.fsdecode(a) for a in argv[1:]]
    i = 0
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in GLOBAL_WITH_VALUE else 1
    return words[i] if i < len(words) else None


def clean_env(**extra: str) -> dict:
    """Окружение прямого git-вызова теста: без `GIT_*` и маркера пульта,
    без запроса пароля в терминал; поверх — `extra`."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in DROPPED_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(extra)
    return env


def git(repo: Path, *args: str, env: dict | None = None,
        check: bool = True) -> subprocess.CompletedProcess:
    """Настоящий git в `repo` мимо подмен `subprocess` (прямой вызов теста,
    не пульта)."""
    res = REAL_RUN(["git", "-C", str(repo), *args], capture_output=True,
                   text=True, env=env if env is not None else clean_env(),
                   timeout=60)
    if check and res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} в {repo}: {res.stderr}")
    return res


def out(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def refs_of(bare: Path) -> str:
    """Все ссылки репозитория `bare` с их sha — снимок «ссылки на origin»."""
    return out(bare, "for-each-ref", "--format=%(refname) %(objectname)")


def ref_sha(bare: Path, ref: str) -> str:
    res = git(bare, "rev-parse", "--verify", "--quiet", ref, check=False)
    return res.stdout.strip() if res.returncode == 0 else ""


class Stand:
    """Главная копия пульта, проекты, их bare-`origin` и клоны."""

    def __init__(self, sandbox, monkeypatch, tmp_path: Path):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.sandbox = sandbox
        self.tmp = tmp_path
        self.projects: dict = {}
        self.calls: list = []
        self.pushes: list = []
        home = tmp_path / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            "[user]\n\tname = artel tests\n\temail = artel@example.invalid\n"
            "[protocol \"file\"]\n\tallow = always\n"
            "[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))
        for name in list(os.environ):
            if name in DROPPED_ENV or name.startswith(("GIT_CONFIG_KEY_",
                                                        "GIT_CONFIG_VALUE_")):
                monkeypatch.delenv(name, raising=False)
        root = Path(config.ROOT)
        shutil.copytree(CODE_ROOT / "scripts" / "git-hooks",
                        root / "scripts" / "git-hooks",
                        ignore=shutil.ignore_patterns("__pycache__"))
        git(root, "add", "-A", "scripts")
        git(root, "commit", "-q", "--no-verify", "-m", "хуки пульта")

    # --- сообщения ---

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def name(self, prefix: str = "q") -> str:
        return prefix + "".join(self.rng.choice(LETTERS) for _ in range(7))

    # --- пути пульта ---

    @staticmethod
    def hooks_dir() -> Path:
        """Прежний каталог хуков пульта — `<config.ROOT>/scripts/git-hooks`."""
        return Path(config.ROOT) / "scripts" / "git-hooks"

    @classmethod
    def human_hooks_dir(cls) -> Path:
        """Каталог хуков пульта проекта `target-human`."""
        return cls.hooks_dir() / TARGET_HUMAN

    @staticmethod
    def head_text(rel: str) -> bytes:
        """Содержимое `rel` в коммите `HEAD` главной копии пульта."""
        res = REAL_RUN(["git", "-C", str(config.ROOT), "show", f"HEAD:{rel}"],
                       capture_output=True, env=clean_env(), timeout=60)
        if res.returncode != 0:
            raise AssertionError(f"git show HEAD:{rel}: {res.stderr!r}")
        return res.stdout

    # --- проекты ---

    def bare_with_commit(self, label: str, files: dict | None = None,
                         submodule: Path | None = None) -> Path:
        """Bare-репозиторий с одним коммитом на `main` (файлы `files`,
        по запросу — подмодуль `sub` из `submodule`)."""
        bare = self.tmp / f"{label}.git"
        REAL_RUN(["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
                  str(bare)], check=True, capture_output=True, env=clean_env())
        seed = self.tmp / f"seed-{label}"
        REAL_RUN(["git", "init", "-q", "-b", config.MAIN_BRANCH, str(seed)],
                 check=True, capture_output=True, env=clean_env())
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

    def declare(self, name: str, gate: str, url: str, *,
                base: str = config.MAIN_BRANCH,
                branch_template: str | None = None) -> None:
        """Запись проекта `name` в локальном слое (весь слой переписывается
        по `self.projects`)."""
        self.projects[name] = {"gate": gate, "url": url, "base": base,
                               "branch_template": branch_template}
        text = "targets:\n"
        for pname, p in self.projects.items():
            policy = ""
            if p["branch_template"] is not None:
                policy = f"      branch_template: \"{p['branch_template']}\"\n"
            text += (
                f"  {pname}:\n"
                f"    description:\n      base: {p['base']}\n"
                f"      test_profile:\n        command: [python3, -m, pytest]\n"
                f"        long_lived_dir: tests\n"
                f"        long_lived_name: test_<id>_<name>.py\n"
                f"    policy:\n      no_paths: []\n      project_skills: []\n"
                f"      merge_gate: {p['gate']}\n"
                f"      weakening_scope: [tests/**/*.py]\n"
                f"      mutation_claim_scope: [tests/test_*.py]\n{policy}"
                f"    machine:\n      forge: github\n"
                f"      url: {p['url']}\n"
                f"      token_slot: {pname}-token\n")
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")
        assert targets.target(name)["merge_gate"] == gate, self.note(text)

    def project(self, gate: str = TARGET_HUMAN, *,
                base: str = config.MAIN_BRANCH,
                branch_template: str | None = None) -> tuple:
        """(имя, клон, bare-origin) проекта, клон которого заводит пульт."""
        name = self.name()
        bare = self.bare_with_commit(name)
        self.declare(name, gate, str(bare), base=base,
                     branch_template=branch_template)
        clone, error = workspace.ensure_clone(name)
        assert error is None, self.note(f"ensure_clone {name}: {error}")
        assert clone == repo_context.clone_path(name), self.note(str(clone))
        return name, clone, bare

    @staticmethod
    def policy_path(clone: Path) -> Path:
        return clone / ".git" / POLICY_NAME

    def expected_policy(self, name: str) -> bytes:
        """Эталон файла политики по записи проекта `name`."""
        p = self.projects[name]
        template = p["branch_template"] or targets.DEFAULT_BRANCH_TEMPLATE
        return (f"project={name}\nbase={p['base']}\n"
                f"branch_template={template}\n"
                f"artifacts_prefix={ARTIFACTS_PREFIX}\n").encode("utf-8")

    # --- ветки и задачи ---

    def template_branch(self, task_id: str | None = None) -> str:
        """Имя ветки по шаблону по умолчанию `task/{id}-{slug}`."""
        task_id = task_id or idgen.new_task_id()
        slug = "-".join(self.name("") for _ in range(2))
        return f"task/{task_id.lower()}-{slug}"

    def commit_branch(self, clone: Path, branch: str) -> str:
        """Ветка `branch` клона с новым коммитом поверх `main`; sha коммита."""
        git(clone, "branch", "-f", branch, config.MAIN_BRANCH)
        tree = out(clone, "rev-parse", f"{branch}^{{tree}}")
        parent = out(clone, "rev-parse", branch)
        sha = out(clone, "commit-tree", tree, "-p", parent, "-m",
                  f"коммит {branch}")
        git(clone, "update-ref", f"refs/heads/{branch}", sha)
        return sha

    def task(self, name: str, branch: str, state: str = "in_dev") -> str:
        task_id = idgen.new_task_id()
        store.insert_task(store.db(), task_id, "Задача", state, branch, name,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    # --- шпион процессов ---

    def spy(self, monkeypatch, *, execute_push: bool = False,
            fake_hosting: bool = False, aliases=("p",)) -> None:
        """Подмена `subprocess.run`/`Popen`: каждый вызов журналируется с
        окружением; отправка (`push`, `send-pack`, псевдоним из `aliases`)
        не исполняется; `fake_hosting` — хостинговые вызовы тоже не
        исполняются (успех без процесса); прочее — настоящий процесс."""
        push_like = {"push", "send-pack", *aliases}

        def record(argv, kwargs) -> str | None:
            env = kwargs.get("env")
            self.calls.append({"argv": [os.fsdecode(a) for a in argv]
                               if isinstance(argv, (list, tuple)) else argv,
                               "env": dict(env if env is not None else os.environ)})
            return subcommand(argv)

        def run(argv, *args, **kwargs):
            sub = record(argv, kwargs)
            text = bool(kwargs.get("text") or kwargs.get("encoding")
                        or kwargs.get("universal_newlines"))
            empty = "" if text else b""
            if (sub in push_like and not execute_push) or (
                    fake_hosting and sub in HOSTING):
                if sub in push_like:
                    self.pushes.append(self.calls[-1]["argv"])
                return subprocess.CompletedProcess(argv, 0, empty, empty)
            return REAL_RUN(argv, *args, **kwargs)

        def popen(argv, *args, **kwargs):
            sub = record(argv, kwargs)
            if sub in push_like and not execute_push:
                self.pushes.append(self.calls[-1]["argv"])
                raise OSError("стенд: отправка процессом Popen не исполняется")
            return REAL_POPEN(argv, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", run)
        monkeypatch.setattr(subprocess, "Popen", popen)
