"""Дублёр ROOT планки: временный пульт с git, клоном проекта и рабочими копиями.

Обязательная форма подстановки дублёра (раздел «Критерии приёмки» SPEC):
тест в своём процессе подменяет `config.ROOT`/`config.PROJECTS` (и прочие
пути пульта под тем же корнем) на дублёр и зовёт `runner.role_env`; дочерний
git получает дублёр только через `ARTEL_GIT_GUARD_ROOT` и
`GIT_CEILING_DIRECTORIES` этого окружения. Меняющие команды git планки
исполняются только против дублёра — временного каталога pytest, вне
настоящего репозитория пульта, его клона и рабочей копии кода задачи.

`TmpRootTest` здесь не годится: он подменяет `subprocess.run` всего
процесса (`SpyRun`), а планке нужен настоящий git — и для посева дублёра
(ссылка документов плотницкими командами), и для проверяемых вызовов.

Подготовка дублёра идёт git-ом окружения посева (`seed_env`): без каталога
обёртки `orchestrator/role_bin/` в PATH, без глобального и системного
конфига — посев не зависит ни от механизма задачи, ни от машины.
"""
import os
import shutil
import signal
import subprocess
from pathlib import Path

from orchestrator import config, keychain, providers, runner, stack, store
from tests.sandbox import fake_keychain_token

OWN = "01MPLANKOWNTASK00000000000"
OTHER = "01MPLANKOTHERTASK000000000"
PROJECT = config.DEFAULT_TARGET
ROLE = "test_author"

# Каталог обёртки — рядом с модулем `orchestrator/runner.py` (требование 10),
# корень, вычисленный от расположения файла обёртки, — `role_bin/../..`.
WRAPPER_DIR = Path(runner.__file__).resolve().parent / "role_bin"
WRAPPER_ROOT = WRAPPER_DIR.parent.parent

TIMEOUT = 30
TRACKED_MARK = "pult-marker-file.md"
MODIFIED = "правка песочницы пульта\n"
GIT_NOT_REPO = "not a git repository"
PULT_PHRASE = "репозиторий пульта"
FOREIGN_PHRASE = "рабочая копия другой задачи"
TASK_RM = "task-rm"


def _without_dir(path_value: str, directory: Path) -> str:
    keep = []
    for item in path_value.split(os.pathsep):
        try:
            same = Path(item).resolve() == directory
        except OSError:
            same = False
        if item and not same:
            keep.append(item)
    return os.pathsep.join(keep)


def seed_env(home: Path) -> dict:
    """Окружение посева: процесс теста без механизма задачи и без конфигов машины."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and not k.startswith("ARTEL_")}
    env["PATH"] = _without_dir(env.get("PATH", ""), WRAPPER_DIR)
    env["HOME"] = str(home)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    for name in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        env[name] = "plank seed"
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        env[name] = "plank@example.invalid"
    return env


def without_wrapper(env: dict) -> dict:
    """Окружение роли без механизма требований 2–3 так, как его снимает диспетчер:
    из PATH убран каталог обёртки `orchestrator/role_bin/`, остальное прежнее."""
    env = dict(env)
    env["PATH"] = _without_dir(env["PATH"], WRAPPER_DIR)
    return env


def without_ceiling(env: dict) -> dict:
    """Окружение роли без границы требования 1 (механизм требований 2–3 на месте)."""
    env = dict(env)
    env.pop("GIT_CEILING_DIRECTORIES", None)
    return env


PROCESS_HEADROOM = 64


def _kill_group(pgid: int) -> None:
    """SIGKILL группе процессов вызова, пока в ней кто-то есть (рекурсия
    fsmonitor порождает новых членов группы, пока их убивают)."""
    for _ in range(100):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            return


def _process_cap():
    """`preexec_fn`, ограничивающий дерево вызова git числом процессов.

    Без механизма задачи `core.fsmonitor='git clean -fX'` рекурсивен
    (вложенный git снова зовёт fsmonitor): цепочка за 30 с таймаута
    исчерпывает таблицу процессов машины. Лимит `RLIMIT_NPROC` дочернего
    дерева — текущее число процессов пользователя плюс `PROCESS_HEADROOM`:
    глубина рекурсии ограничена, прочие процессы машины не затронуты."""
    try:
        import resource
        listed = subprocess.run(["pgrep", "-U", str(os.getuid())],
                                capture_output=True, text=True, timeout=TIMEOUT)
        count = len(listed.stdout.split())
        _soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    except (ImportError, OSError, ValueError, subprocess.SubprocessError):
        return None
    if count == 0:
        return None
    cap = count + PROCESS_HEADROOM
    if hard != resource.RLIM_INFINITY:
        cap = min(cap, hard)

    def limit():
        resource.setrlimit(resource.RLIMIT_NPROC, (cap, hard))
    return limit


def output(res) -> str:
    return (res.stdout or "") + (res.stderr or "")


def refusal_problems(res, kind: str) -> list:
    """Расхождения исхода с отказом механизма требования 2; пусто — отказ как надо.

    `kind` — "pult" (путь внутри ROOT вне чужих рабочих копий) или "foreign"
    (путь внутри рабочей копии другой задачи)."""
    out = output(res)
    problems = []
    if res.returncode == 0:
        problems.append("код возврата 0")
    if GIT_NOT_REPO in out:
        problems.append(f"в выводе сообщение git «{GIT_NOT_REPO}»")
    if kind == "pult":
        for phrase in (PULT_PHRASE, TASK_RM):
            if phrase not in out:
                problems.append(f"в выводе нет «{phrase}»")
    else:
        if FOREIGN_PHRASE not in out:
            problems.append(f"в выводе нет «{FOREIGN_PHRASE}»")
        elif PULT_PHRASE in out and out.index(PULT_PHRASE) < out.index(FOREIGN_PHRASE):
            problems.append(f"«{PULT_PHRASE}» стоит раньше главной строки "
                            f"«{FOREIGN_PHRASE}»")
    return problems


class Doubler:
    """Дублёр ROOT: git-репозиторий пульта, клон проекта, две рабочие копии задач.

    - `root` — репозиторий пульта (`.gitignore`: `.artel/`, `ignored.txt`);
      отслеживаемый `docs/<TRACKED_MARK>` изменён (`MODIFIED`), игнорируемые
      `ignored.txt` и `.artel/models.yaml`;
    - `clone` — `<root>/.artel/projects/artel/repo` (`.gitignore`: `*.tmp`,
      отслеживаемый `sub/kept.txt`);
    - `own`/`other` — рабочие копии задач `OWN`/`OTHER` клона, в каждой
      игнорируемый `junk.tmp`;
    - `docs` — каталог документов задачи `OWN`, `outside` — каталог вне ROOT;
    - ссылка документов `refs/artifacts/OWN` клона несёт `tasks/OWN/SPEC.md`.
    """

    def __init__(self, base: Path, monkeypatch):
        base = Path(base).resolve()
        self.base = base
        self.seed_home = base / "seed-home"
        self.seed_home.mkdir()
        self.env0 = seed_env(self.seed_home)
        self.root = base / "pult"
        self.outside = base / "outside"
        self.outside.mkdir()
        root = self.root
        root.mkdir()
        self.git_seed("init", "-q", cwd=root)
        self.git_seed("checkout", "-q", "-b", config.MAIN_BRANCH, cwd=root)
        (root / ".gitignore").write_text(".artel/\nignored.txt\n", encoding="utf-8")
        (root / "docs").mkdir()
        self.tracked = root / "docs" / TRACKED_MARK
        self.tracked.write_text("исходный текст\n", encoding="utf-8")
        self.git_seed("add", "-A", cwd=root)
        self.git_seed("commit", "-q", "-m", "пульт-дублёр", cwd=root)
        self.tracked.write_text(MODIFIED, encoding="utf-8")
        self.ignored = [root / "ignored.txt", root / ".artel" / "models.yaml"]
        (root / ".artel").mkdir()
        for path in self.ignored:
            path.write_text("игнорируемый файл пульта\n", encoding="utf-8")

        self.projects = root / ".artel" / "projects"
        self.area = self.projects / PROJECT
        self.clone = self.area / "repo"
        self.clone.mkdir(parents=True)
        self.git_seed("init", "-q", cwd=self.clone)
        self.git_seed("checkout", "-q", "-b", config.MAIN_BRANCH, cwd=self.clone)
        (self.clone / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        (self.clone / "sub").mkdir()
        (self.clone / "sub" / "kept.txt").write_text("клон\n", encoding="utf-8")
        self.git_seed("add", "-A", cwd=self.clone)
        self.git_seed("commit", "-q", "-m", "клон-дублёр", cwd=self.clone)
        self.worktrees = self.area / "worktrees"
        self.own = self.worktrees / OWN
        self.other = self.worktrees / OTHER
        for task, path in ((OWN, self.own), (OTHER, self.other)):
            self.git_seed("worktree", "add", "-q", "-b", f"task/{task.lower()}",
                          str(path), cwd=self.clone)
            (path / "junk.tmp").write_text("игнорируемый файл копии\n",
                                           encoding="utf-8")
        self.docs = self.area / "tasks" / OWN
        self.docs.mkdir(parents=True)
        (self.docs / "SPEC.md").write_text("спека\n", encoding="utf-8")
        for name in ("knowledge", "logs", "epics"):
            (self.area / name).mkdir(exist_ok=True)
        (root / ".artel" / "logs").mkdir()
        self.seed_artifact_ref()

        for attr, value in (
                ("ROOT", root), ("PROJECTS", self.projects),
                ("TASKS", root / "tasks"), ("DB", root / ".artel" / "state.db"),
                ("LOGS", root / ".artel" / "logs"),
                ("TARGETS", root / ".artel" / "plank-targets.yaml"),
                ("ROLE_HOME", root / ".artel" / "home"),
                ("ROLE_CONFIG_DIR", root / ".artel" / "home" / ".claude"),
                ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                ("WORKTREES", root / ".artel" / "worktrees"),
                ("MODELS_LOCAL", root / ".artel" / "models.yaml")):
            monkeypatch.setattr(config, attr, value)
        (root / ".artel" / "home" / ".claude").mkdir(parents=True)
        monkeypatch.setattr(stack, "check_stack", lambda: [])
        monkeypatch.setattr(keychain, "token", fake_keychain_token)
        operator_home = base / "operator-home"
        operator_home.mkdir()
        monkeypatch.setenv("HOME", str(operator_home))
        for name in (config.ARTEL_ROLE_ENV, config.ARTEL_TASK_ENV,
                     "ARTEL_GIT_GUARD_ROOT", "GIT_CEILING_DIRECTORIES",
                     "GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_PARAMETERS",
                     "GIT_CONFIG_COUNT", "GIT_PAGER"):
            monkeypatch.delenv(name, raising=False)
        conn = store.db()
        store.create_schema(conn)
        for task, path in ((OWN, self.own), (OTHER, self.other)):
            store.insert_task(conn, task, "Задача дублёра", "tests_writing",
                              f"task/{task.lower()}", PROJECT, 25.0)
        conn.close()

    def git_seed(self, *args, cwd, input=None) -> str:
        """git посева дублёра; сбой — исключение (`check=True`)."""
        git = shutil.which("git", path=self.env0["PATH"])
        res = subprocess.run([git, *args], cwd=cwd, env=self.env0, input=input,
                             capture_output=True, text=True, check=True,
                             timeout=TIMEOUT)
        return res.stdout.strip()

    def seed_artifact_ref(self) -> None:
        """`refs/artifacts/OWN` клона с `tasks/OWN/SPEC.md` — плотницкими командами."""
        blob = self.git_seed("hash-object", "-w", "--stdin", cwd=self.clone,
                             input="спека\n")
        leaf = self.git_seed("mktree", cwd=self.clone,
                             input=f"100644 blob {blob}\tSPEC.md\n")
        mid = self.git_seed("mktree", cwd=self.clone,
                            input=f"040000 tree {leaf}\t{OWN}\n")
        top = self.git_seed("mktree", cwd=self.clone,
                            input=f"040000 tree {mid}\ttasks\n")
        commit = self.git_seed("commit-tree", top, "-m", "документы", cwd=self.clone)
        self.git_seed("update-ref", f"refs/artifacts/{OWN}", commit, cwd=self.clone)

    def write_config(self, where: str, key: str, value: str) -> None:
        """Запись конфигурации рабочей копии: "common" — `config` общего `.git`
        клона, "worktree" — `config.worktree` собственной рабочей копии."""
        if where == "common":
            self.git_seed("config", key, value, cwd=self.clone)
            return
        self.git_seed("config", "core.repositoryFormatVersion", "1", cwd=self.clone)
        self.git_seed("config", "extensions.worktreeConfig", "true", cwd=self.clone)
        self.git_seed("config", "--worktree", key, value, cwd=self.own)

    def role_env(self, provider: str = "claude", task: str = OWN) -> dict:
        """Окружение роли шага `task`, собранное `runner.role_env` при подменённом
        корне; локаль C — сообщения git по-английски."""
        env = runner.role_env(ROLE, task, provider=providers.get(provider),
                              project=PROJECT)
        env = dict(env)
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        return env

    def run(self, args, env: dict, cwd, extra_env=None, timeout=TIMEOUT):
        """`git <args>` так, как его зовёт шаг роли: первый `git` по PATH окружения.

        Таймаут — страховка от зависания (AC-7): превышение — `TimeoutExpired`,
        вся группа процессов вызова (вложенные git pager/fsmonitor) убита."""
        env = dict(env, **(extra_env or {}))
        git = shutil.which("git", path=env["PATH"])
        proc = subprocess.Popen([git, *args], cwd=str(cwd), env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                start_new_session=True,
                                preexec_fn=_process_cap())
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            proc.communicate()
            raise
        finally:
            _kill_group(proc.pid)
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)

    def missing_ignored(self) -> list:
        """Игнорируемые файлы дублёра, которых нет на месте (пусто — все целы)."""
        paths = self.ignored + [self.own / "junk.tmp", self.other / "junk.tmp"]
        return [str(p) for p in paths if not p.exists()]
