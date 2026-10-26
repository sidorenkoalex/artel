"""Единая точка отправки `gitcmd`: журнал «ветка отправлена: <sha>», опции `push_options`, белый список отправок проекта с `merge_gate`, отличным от `operator`, отказ при неизвестном `merge_gate` и подставах конфигурации клона.

Группа: разовый
Красен до реализации: `gitcmd` пропускает любую отправку к git без проверки — шпион процессов видит `push` в `main`, чужую ветку, с `--tags`/`-o ci.skip`/подставами конфигурации; записи «ветка отправлена: <sha>» в журнале нет, `-o` из `policy.push_options` не добавляется, отказа с журналом и алертом `branch_push_whitelist` нет.

Группа «разовый» — не по смыслу свойства (оно обязано держаться и после
мержа), а по правилу guard: долгоживущему файлу закрыт импорт
`orchestrator.gitcmd` (`scripts/guard.py::_GIT_MODULES`), а предмет этих
критериев — сами пять точек запуска git модуля `gitcmd`.

Песочница — `initialized_tmp_root` (пути `config` во временном каталоге,
БД со схемой, `keychain.token` подменён, признак роли снят). Клон проекта —
настоящий git-репозиторий по адресу `repo_context.clone_path(<проект>)` с
`origin`, равным `url` записи локального слоя. `subprocess.run` и
`subprocess.Popen` подменены шпионом: git-вызов отправки (подкоманда после
глобальных опций — `push`, `send-pack` или псевдоним клона) записывается и
не исполняется (успех либо заданный код), прочие локальные git-вызовы
исполняются настоящим git — так проверки конфигурации клона видят её
настоящей. Отказ — ненулевой код результата либо исключение точки; причина
— их текст. Окружение очищено от `ARTEL_TASK` и `GIT_CONFIG_*`. Имена
проектов, веток и ключи порождаются модулем `random` при каждом запуске;
зерно печатается и входит в текст провала.
"""
import inspect
import os
import random
import subprocess
from pathlib import Path

import pytest

from orchestrator import alerts, config, gitcmd, idgen, repo_context, store, targets

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
LETTERS = "abcdefghijkmnopqrstuvwxyz"
PUSH_SUBCOMMANDS = ("push", "send-pack")
NETWORK = ("fetch", "ls-remote", "pull", "clone")
GLOBAL_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace",
                     "--config-env", "--exec-path")
SENT = "ветка отправлена"
WHITELIST_SOURCE = "branch_push_whitelist"
GIT_CONFIG_ENV = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")


# --- окружение сценария ---

def subcommand(argv: list) -> str | None:
    """Подкоманда git-вызова после глобальных опций; `None` — не git."""
    if not argv or Path(os.fsdecode(argv[0])).name != "git":
        return None
    words = [os.fsdecode(a) for a in argv[1:]]
    i = 0
    while i < len(words) and words[i].startswith("-"):
        i += 2 if (words[i] in GLOBAL_WITH_VALUE) else 1
    return words[i] if i < len(words) else None


class Stand:
    """Сценарий: шпион процессов, проекты, клоны, задачи."""

    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
        self.calls: list = []
        self.pushes: list = []
        self.aliases: set = set()
        self.push_code = 0

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def is_push(self, argv) -> bool:
        sub = subcommand(list(argv)) if isinstance(argv, (list, tuple)) else None
        return sub in PUSH_SUBCOMMANDS or sub in self.aliases

    def run(self, argv, *args, **kwargs):
        self.calls.append(list(argv) if isinstance(argv, (list, tuple)) else argv)
        text = bool(kwargs.get("text") or kwargs.get("encoding")
                    or kwargs.get("universal_newlines"))
        empty = "" if text else b""
        if self.is_push(argv):
            self.pushes.append([os.fsdecode(a) for a in argv])
            return subprocess.CompletedProcess(argv, self.push_code, empty, empty)
        if isinstance(argv, (list, tuple)) and subcommand(list(argv)) in NETWORK:
            return subprocess.CompletedProcess(argv, 128, empty, empty)
        return REAL_RUN(argv, *args, **kwargs)

    def popen(self, argv, *args, **kwargs):
        self.calls.append(list(argv) if isinstance(argv, (list, tuple)) else argv)
        if self.is_push(argv):
            self.pushes.append([os.fsdecode(a) for a in argv])
            raise OSError("песочница: отправка процессом Popen не исполняется")
        return REAL_POPEN(argv, *args, **kwargs)

    def name(self, prefix: str = "q") -> str:
        return prefix + "".join(self.rng.choice(LETTERS) for _ in range(7))


@pytest.fixture
def stand(initialized_tmp_root, monkeypatch):
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    for var in list(os.environ):
        if var in GIT_CONFIG_ENV or var.startswith(("GIT_CONFIG_KEY_",
                                                     "GIT_CONFIG_VALUE_")):
            monkeypatch.delenv(var)
    s = Stand(value)
    monkeypatch.setattr(subprocess, "run", s.run)
    monkeypatch.setattr(subprocess, "Popen", s.popen)
    return s


def real_git(repo: Path, *args: str) -> str:
    return REAL_RUN(["git", *args], cwd=repo, check=True, capture_output=True,
                    text=True).stdout.strip()


def url_of(name: str) -> str:
    return f"https://localhost/team/{name}"


def declare(name: str, gate: str, policy: str = "") -> None:
    """Запись проекта `name` в локальном слое (дописывается)."""
    entry = (f"  {name}:\n"
             f"    description:\n      base: {config.MAIN_BRANCH}\n"
             f"      test_profile:\n        command: [python3, -m, pytest]\n"
             f"        long_lived_dir: tests\n"
             f"        long_lived_name: test_<id>_<name>.py\n"
             f"    policy:\n      no_paths: []\n      project_skills: []\n"
             f"      merge_gate: {gate}\n"
             f"      weakening_scope: [tests/**/*.py]\n"
             f"      mutation_claim_scope: [tests/test_*.py]\n{policy}"
             f"    machine:\n      forge: github\n"
             f"      url: {url_of(name)}\n"
             f"      token_slot: {name}-token\n")
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    text = local.read_text(encoding="utf-8") if local.exists() else "targets:\n"
    local.write_text(text + entry, encoding="utf-8")


def make_clone(path: Path, url: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    real_git(path, "init", "-q", "-b", config.MAIN_BRANCH)
    real_git(path, "config", "user.email", "artel@example.invalid")
    real_git(path, "config", "user.name", "artel tests")
    real_git(path, "commit", "-q", "--allow-empty", "-m", "init")
    real_git(path, "remote", "add", "origin", url)
    return path


class Project:
    def __init__(self, stand: Stand, gate: str, policy: str = "",
                 record: bool = True):
        self.stand = stand
        self.name = stand.name()
        if record:
            declare(self.name, gate, policy)
        self.clone = make_clone(repo_context.clone_path(self.name), url_of(self.name))

    def task(self, state: str = "in_dev", branch: str | None = None) -> tuple:
        """(id, ветка, локальный sha) задачи проекта; ветка заведена в клоне
        отдельным коммитом."""
        task_id = idgen.new_task_id()
        branch = branch or f"feature/{self.stand.name('b')}"
        store.insert_task(store.db(), task_id, "Задача отправки", state, branch,
                          self.name, config.DEFAULT_BUDGET_USD)
        real_git(self.clone, "checkout", "-q", "-b", branch)
        real_git(self.clone, "commit", "-q", "--allow-empty", "-m", f"на {branch}")
        sha = real_git(self.clone, "rev-parse", branch)
        real_git(self.clone, "checkout", "-q", config.MAIN_BRANCH)
        return task_id, branch, sha


def attempt(fn, *args, **kwargs) -> tuple:
    """(отказ, причина, результат) вызова точки отправки."""
    try:
        res = fn(*args, **kwargs)
    except Exception as exc:  # отказ точки исключением — тоже отказ
        return True, str(exc), None
    err = res.stderr
    if isinstance(err, bytes):
        err = err.decode(errors="replace")
    return res.returncode != 0, (err or "").strip(), res


def steps(task_id: str) -> list:
    return [(r["action"] or "", r["detail"] or "")
            for r in store.task_steps(store.db(), task_id)]


def mentions(entry: tuple, reason: str) -> bool:
    action, detail = entry
    return bool((detail.strip() and detail.strip() in reason)
                or (reason.strip() and reason.strip() in f"{action} {detail}"))


def sent_records(task_id: str) -> list:
    return [f"{a} {d}" for a, d in steps(task_id) if SENT in f"{a} {d}"]


def has_pair(argv: list, first: str, second: str) -> bool:
    return any(argv[i] == first and argv[i + 1] == second for i in range(len(argv) - 1))


def whitelist_alerts() -> list:
    return [r["id"] for r in alerts.open_alerts(store.db(), "incident")
            if r["source"] == WHITELIST_SOURCE]


def assert_refused(stand: Stand, outcome: tuple, start: int, what: str) -> None:
    refused, reason, _res = outcome
    assert refused, stand.note(f"{what}: отправка не отказана")
    assert reason, stand.note(f"{what}: отказ без причины")
    assert stand.pushes[start:] == [], stand.note(
        f"{what}: процесс отправки запущен: {stand.pushes[start:]}")


def assert_passed(stand: Stand, outcome: tuple, start: int, what: str) -> list:
    refused, reason, _res = outcome
    assert not refused, stand.note(f"{what}: отказано: {reason}")
    assert len(stand.pushes) > start, stand.note(f"{what}: процесс отправки не запущен")
    return stand.pushes[-1]


# --- AC-6 ---

FLAG_CASES = ["--tags", "--follow-tags", "--mirror", "--all", "--force", "-f",
              "--dry-run", "--prune", "--receive-pack=x"]
OPTION_CASES = ["merge_request.create", "ci.skip", "novalue", "ci.variable=SECRET=1"]
GLOBAL_CASES = ["-c", "--config-env", "--git-dir"]
ENV_CASES = ["GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0",
             "GIT_CONFIG_PARAMETERS"]
ENV_VALUES = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.sshCommand",
              "GIT_CONFIG_VALUE_0": "x",
              "GIT_CONFIG_PARAMETERS": "'core.sshCommand'='x'"}
REFUSED_CASES = (
    ["foreign-branch", "done-branch", "killed-branch", "main", "delete-own",
     "colon-own", "delete-unknown-artifacts", "colon-artifacts", "tag",
     "no-refspec", "plus", "send-pack", "other-url", "bare-lease",
     "lease-without-sha", "lease-wrong-sha", "lease-without-record"]
    + [f"flag{f}" for f in FLAG_CASES] + [f"option:{o}" for o in OPTION_CASES]
    + [f"global{g}" for g in GLOBAL_CASES] + [f"env:{e}" for e in ENV_CASES])
HUMAN_POLICY = "      push_options_forbidden: [SECRET]\n"


def refused_scenario(stand: Stand, proj: Project, case: str, monkeypatch) -> tuple:
    """(аргументы in_repo, задача, к журналу которой относится отказ, или None)."""
    own, branch, sha = proj.task()
    clone = proj.clone
    if case == "foreign-branch":
        return ("push", "origin", f"feature/PROJ-{stand.rng.randrange(10 ** 6)}"), None
    if case in ("done-branch", "killed-branch"):
        dead, dead_branch, _ = proj.task(case.split("-")[0])
        return ("push", "origin", dead_branch), dead
    if case == "main":
        return ("push", "origin", config.MAIN_BRANCH), None
    if case == "delete-own":
        return ("push", "origin", "--delete", branch), own
    if case == "colon-own":
        return ("push", "origin", f":{branch}"), own
    if case == "delete-unknown-artifacts":
        return ("push", "origin", "--delete", f"refs/artifacts/{idgen.new_task_id()}"), None
    if case == "colon-artifacts":
        return ("push", "origin", f":refs/artifacts/{own}"), own
    if case == "tag":
        return ("push", "origin", f"refs/tags/v{stand.rng.randrange(100)}"), None
    if case == "no-refspec":
        return ("push", "origin"), None
    if case == "plus":
        return ("push", "origin", f"+{branch}"), own
    if case == "send-pack":
        return ("send-pack", "origin", branch), own
    if case == "other-url":
        return ("push", f"https://localhost/other/{stand.name()}", branch), own
    if case == "bare-lease":
        return ("push", "--force-with-lease", "origin", branch), own
    if case == "lease-without-sha":
        return ("push", f"--force-with-lease=refs/heads/{branch}", "origin", branch), own
    if case == "lease-wrong-sha":
        start = len(stand.pushes)
        assert_passed(stand, attempt(gitcmd.in_repo, clone, "push", "origin", branch),
                      start, "предпосылка: первая отправка своей ветки")
        other = "".join(stand.rng.choice("0123456789abcdef") for _ in range(40))
        return ("push", f"--force-with-lease=refs/heads/{branch}:{other}",
                "origin", branch), own
    if case == "lease-without-record":
        return ("push", f"--force-with-lease=refs/heads/{branch}:{sha}",
                "origin", branch), own
    if case.startswith("flag"):
        return ("push", case[len("flag"):], "origin", branch), own
    if case.startswith("option:"):
        return ("push", "-o", case.split(":", 1)[1], "origin", branch), own
    if case == "global-c":
        return ("-c", "core.sshCommand=x", "push", "origin", branch), own
    if case == "global--config-env":
        monkeypatch.setenv("VAR", "x")
        return ("--config-env=core.sshCommand=VAR", "push", "origin", branch), own
    if case == "global--git-dir":
        return (f"--git-dir={clone / '.git'}", "push", "origin", branch), own
    if case.startswith("env:"):
        var = case.split(":", 1)[1]
        monkeypatch.setenv(var, ENV_VALUES[var])
        return ("push", "origin", branch), own
    raise AssertionError(case)


@pytest.mark.parametrize("case", REFUSED_CASES)
def test_ac6_whitelist_refuses_before_git(stand, monkeypatch, case):
    """Отправка вне белого списка проекта `target-human` — отказ до запуска git с причиной и записью в журнал задачи.

    Сценарий: проект `merge_gate: target-human` (`push_options_forbidden:
    [SECRET]`), живая задача со своей веткой в клоне. Каждая отправка
    `gitcmd.in_repo(<клон>, …)` из перечня AC-6 — чужая ветка
    `feature/PROJ-<n>`, ветка задачи в `done`/`killed`, `main`, удаление
    своей ветки `--delete` и `:<ветка>`, `--delete refs/artifacts/<id>`
    задачи не из БД, `:refs/artifacts/<id>` своей задачи, тег, без
    refspec, `+<ветка>`, `send-pack`, URL не из записи, голый
    `--force-with-lease`, без sha, с sha не последней записи «ветка
    отправлена» и без записи, флаги вне списка, `-o merge_request.create`/
    `ci.skip`/`novalue`/`ci.variable=SECRET=1`, глобальные `-c`,
    `--config-env`, `--git-dir` перед `push`, переменные `GIT_CONFIG_*` в
    окружении — отказана: ненулевой код или исключение с текстом причины,
    шпион процессов не видел ни одного вызова отправки. Отказ, относящийся
    к задаче проекта (её ветка или ссылка документов), оставляет в её
    журнале запись с причиной.

    Ловит мутацию: «своя ветка» ищется среди задач в любом состоянии,
    включая `done`/`killed`, — отправка в ветку `done` пройдёт; подкоманда
    ищется первым словом argv, а не после глобальных опций — `-c … push`
    пройдёт; `-o` в argv не проверяется нормой `push_options` — `ci.skip`
    пройдёт; `GIT_CONFIG_*` окружения не проверяются; sha аренды не
    сверяется с журналом; `:<ref>` разбирается как обычный refspec; отказ
    не журналируется — записи с причиной нет.
    """
    proj = Project(stand, "target-human", HUMAN_POLICY)
    args, related = refused_scenario(stand, proj, case, monkeypatch)
    before = len(steps(related)) if related else 0
    start = len(stand.pushes)
    outcome = attempt(gitcmd.in_repo, proj.clone, *args)
    what = f"{case}: {args}"
    assert_refused(stand, outcome, start, what)
    if related:
        added = steps(related)[before:]
        assert any(mentions(e, outcome[1]) for e in added), stand.note(
            f"{what}: в журнале задачи нет записи с причиной «{outcome[1]}»: {added}")


SEND_POINTS = ["in_repo", "git", "carpentry", "read", "read_env", "read_stream"]


def call_point(point: str, clone: Path, args: tuple, **kwargs):
    """Вызов точки запуска git `point` с git-аргументами `args` в клоне."""
    if point == "in_repo":
        return attempt(gitcmd.in_repo, clone, *args, **kwargs)
    if point == "git":
        return attempt(gitcmd.git, "-C", str(clone), *args, **kwargs)
    if point == "carpentry":
        return attempt(gitcmd.carpentry, clone, list(args), dict(os.environ), **kwargs)
    if point == "read":
        return attempt(gitcmd.read, clone, *args, **kwargs)
    if point == "read_env":
        return attempt(gitcmd.read_env, clone, dict(os.environ), *args, timeout=60, **kwargs)
    return attempt(gitcmd.read_stream, clone, *args, limit=1 << 20, timeout=60, **kwargs)


def test_ac6_refusal_without_own_task_goes_to_context_task_or_alert(stand, monkeypatch):
    """Отказ отправки в `main` пишется в журнал задачи из `ARTEL_TASK` или параметра `task_id`, без контекста — алерт `incident`.

    Сценарий: проект `target-human`, задача контекста. Отправка `main`
    при `ARTEL_TASK=<id>` в окружении оставляет в журнале этой задачи
    запись с причиной. Затем без `ARTEL_TASK` — через каждую точку
    отправки `gitcmd`, у которой есть параметр `task_id` (хотя бы одна
    обязана его иметь), с `task_id=<id>` — та же запись. Без `ARTEL_TASK`
    и без `task_id` — новый открытый алерт вида `incident` с источником
    `branch_push_whitelist`. Процесс отправки ни разу не запущен.

    Ловит мутацию: контекст берётся только из `ARTEL_TASK`, параметр
    `task_id` не принят или игнорируется — записи нет; отказ без своей
    задачи и без контекста не пишет алерт либо пишет его с другим
    источником или видом.
    """
    proj = Project(stand, "target-human", HUMAN_POLICY)
    ctx, _branch, _sha = proj.task()
    args = ("push", "origin", config.MAIN_BRANCH)

    monkeypatch.setenv(config.ARTEL_TASK_ENV, ctx)
    before, start = len(steps(ctx)), len(stand.pushes)
    outcome = call_point("in_repo", proj.clone, args)
    assert_refused(stand, outcome, start, "ARTEL_TASK")
    assert any(mentions(e, outcome[1]) for e in steps(ctx)[before:]), stand.note(
        f"ARTEL_TASK: нет записи с причиной «{outcome[1]}»: {steps(ctx)[before:]}")
    monkeypatch.delenv(config.ARTEL_TASK_ENV)

    accepting = [p for p in SEND_POINTS
                 if "task_id" in inspect.signature(getattr(gitcmd, p)).parameters]
    assert accepting, stand.note("ни у одной точки отправки нет параметра task_id")
    for point in accepting:
        before, start = len(steps(ctx)), len(stand.pushes)
        outcome = call_point(point, proj.clone, args, task_id=ctx)
        assert_refused(stand, outcome, start, f"{point}(task_id=…)")
        assert any(mentions(e, outcome[1]) for e in steps(ctx)[before:]), stand.note(
            f"{point}(task_id=…): нет записи с причиной «{outcome[1]}»")

    before_alerts, start = whitelist_alerts(), len(stand.pushes)
    outcome = call_point("in_repo", proj.clone, args)
    assert_refused(stand, outcome, start, "без контекста")
    assert set(whitelist_alerts()) - set(before_alerts), stand.note(
        f"без контекста: нет нового алерта {WHITELIST_SOURCE}")


PASSED_CASES = ["origin", "record-url", "-u", "-q", "-o A=1", "lease-last-record",
                "artifacts", "delete-artifacts"]


@pytest.mark.parametrize("case", PASSED_CASES)
def test_ac6_whitelisted_push_passes_with_reset_options(stand, case):
    """Разрешённая отправка проекта `target-human` доходит до git и несёт `-c push.followTags=false` и `-c push.pushOption=`.

    Сценарий: живая задача проекта `target-human`. Отправка своей ветки в
    `origin`, по URL записи, с `-u`, `-q`, `-o A=1`; перезапись
    `--force-with-lease=refs/heads/<ветка>:<sha>` с sha последней записи
    «ветка отправлена» (после первой отправки); отправка
    `refs/artifacts/<id>` и `--delete refs/artifacts/<id>` своей задачи —
    не отказаны, шпион видел вызов отправки, в его argv есть пары `-c
    push.followTags=false` и `-c push.pushOption=`.

    Ловит мутацию: белый список отказывает `-u`/`-q`/`-o` или URL записи;
    аренда сверяется не с последней записью журнала, а с удалённой
    головой; удаление ссылки документов отказывается вместе с прочими
    `--delete`; сброс `push.followTags`/`push.pushOption` не добавлен в
    вызов.
    """
    proj = Project(stand, "target-human", HUMAN_POLICY)
    own, branch, sha = proj.task()
    args = {
        "origin": ("push", "origin", branch),
        "record-url": ("push", url_of(proj.name), branch),
        "-u": ("push", "-u", "origin", branch),
        "-q": ("push", "-q", "origin", branch),
        "-o A=1": ("push", "-o", "A=1", "origin", branch),
        "lease-last-record": ("push", f"--force-with-lease=refs/heads/{branch}:{sha}",
                              "origin", branch),
        "artifacts": ("push", "origin", f"refs/artifacts/{own}"),
        "delete-artifacts": ("push", "origin", "--delete", f"refs/artifacts/{own}"),
    }[case]
    if case == "lease-last-record":
        start = len(stand.pushes)
        assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, "push", "origin", branch),
                      start, "предпосылка: первая отправка")
    start = len(stand.pushes)
    argv = assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, *args), start,
                         f"{case}: {args}")
    assert has_pair(argv, "-c", "push.followTags=false"), stand.note(f"{case}: {argv}")
    assert has_pair(argv, "-c", "push.pushOption="), stand.note(f"{case}: {argv}")


# --- AC-7 ---

@pytest.mark.parametrize("point", SEND_POINTS[1:])
def test_ac7_main_push_refused_at_every_point(stand, point):
    """Отправка в `main` проекта `target-human` отказана в каждой из пяти точек запуска git до процесса.

    Сценарий: проект `target-human` с клоном. `push origin main` через
    `gitcmd.git`, `carpentry`, `read`, `read_env`, `read_stream` —
    ненулевой код или исключение, шпионы `subprocess.run`/`Popen` не видели
    вызова отправки.

    Ловит мутацию: проверка стоит только в `git` — `carpentry`/`read`
    (`subprocess.run`) или `read_env`/`read_stream` (`subprocess.Popen`)
    запустят `push`.
    """
    proj = Project(stand, "target-human", HUMAN_POLICY)
    start = len(stand.pushes)
    refused, _reason, _res = call_point(point, proj.clone, ("push", "origin", config.MAIN_BRANCH))
    assert refused, stand.note(f"{point}: не отказано")
    assert stand.pushes[start:] == [], stand.note(f"{point}: {stand.pushes[start:]}")


def corrupt_targets() -> None:
    config.TARGETS.write_text("targets:\n  artel: [не закрыт\n", encoding="utf-8")
    with pytest.raises(targets.TargetsError):
        targets.load()


@pytest.mark.parametrize("route", ["from-clone", "url-path"])
@pytest.mark.parametrize("state", ["unreadable", "no-record"])
def test_ac7_unknown_merge_gate_refuses_project_clone_push(stand, route, state):
    """Нечитаемый `targets.yaml` или нет записи проекта — отправка из клона и по пути к клону отказана до процесса.

    Сценарий: клон внешнего проекта под `repo_context.projects_root()`.
    `unreadable` — запись проекта `merge_gate: operator`, затем
    `targets.yaml` испорчен; `no-record` — `targets.yaml` читается, записи
    проекта нет. Отправка своей ветки из клона (`in_repo`) и отправка,
    запущенная из корня пульта (`gitcmd.git`) по пути клона, — отказ,
    шпион не видел вызова отправки.

    Ловит мутацию: при пустом `_declared_targets` проект считается
    «вне белого списка» (`merge_gate` по умолчанию `operator`) — отправка
    пройдёт; назначение по пути не сверяется с областью проектов —
    отправка из корня пульта пройдёт.
    """
    proj = Project(stand, "operator", record=(state == "unreadable"))
    _own, branch, _sha = (proj.task() if state == "unreadable"
                          else (None, f"feature/{stand.name('b')}", None))
    if state == "no-record":
        real_git(proj.clone, "branch", branch)
    else:
        corrupt_targets()
    start = len(stand.pushes)
    if route == "from-clone":
        refused, _r, _res = attempt(gitcmd.in_repo, proj.clone, "push", "origin", branch)
    else:
        refused, _r, _res = attempt(gitcmd.git, "push", str(proj.clone), branch)
    assert refused, stand.note(f"{state}/{route}: не отказано")
    assert stand.pushes[start:] == [], stand.note(f"{state}/{route}: {stand.pushes[start:]}")


def test_ac7_artel_clone_push_not_refused_by_unreadable_targets(stand):
    """Отправка из клона артели при испорченном `targets.yaml` этим правилом не отказана.

    Сценарий: клон артели песочницы (`repo_context.clone_path(artel)`) с
    веткой живой задачи артели; `targets.yaml` испорчен. Отправка этой
    ветки из клона артели доходит до git (шпион видел вызов отправки).

    Ловит мутацию: исключения клона артели нет — правило «неизвестный
    `merge_gate`» отказывает любую отправку под областью проектов, включая
    `.artel/projects/artel/repo`.
    """
    clone = repo_context.clone_path(config.DEFAULT_TARGET)
    real_git(clone, "config", "user.email", "artel@example.invalid")
    real_git(clone, "config", "user.name", "artel tests")
    real_git(clone, "commit", "-q", "--allow-empty", "-m", "init")
    task_id = idgen.new_task_id()
    branch = f"task/{task_id.lower()}-x"
    store.insert_task(store.db(), task_id, "Задача артели", "in_dev", branch,
                      config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
    real_git(clone, "branch", branch)
    corrupt_targets()
    start = len(stand.pushes)
    assert_passed(stand, attempt(gitcmd.in_repo, clone, "push", "origin", branch),
                  start, "клон артели")


SUBSTITUTIONS = {
    "pushurl": ("remote.origin.pushurl", "https://localhost/evil/x"),
    "push-refspec": ("remote.origin.push", "refs/heads/*:refs/heads/evil/*"),
    "mirror": ("remote.origin.mirror", "true"),
    "push-option": ("push.pushOption", "ci.skip"),
    "alias": ("alias.p", "push"),
}


@pytest.mark.parametrize("gate", ["target-human", "operator"])
@pytest.mark.parametrize("case", list(SUBSTITUTIONS))
def test_ac7_clone_config_substitution(stand, case, gate):
    """Подстава конфигурации клона отказывает отправку проекта `target-human` и не трогает проект `operator`.

    Сценарий: в конфигурации клона задан `remote.origin.pushurl`,
    `remote.origin.push`, `remote.origin.mirror=true`, непустой
    `push.pushOption` или псевдоним `alias.p=push`; отправка своей ветки с
    разрешённым argv (`push origin <ветка>`, для псевдонима — `p origin
    <ветка>`). У `target-human` — отказ с причиной, ни один вызов шпионов
    не несёт подкоманду отправки. У `operator` — не отказано, вызов
    отправки дошёл до git и не несёт `-c push.pushOption=`.

    Ловит мутацию: конфигурация клона не читается до запуска — отправка
    `target-human` с `pushurl`/`mirror` уйдёт; псевдоним не распознан как
    отправка — `p origin <ветка>` минует белый список; проверка
    конфигурации или сброс `push.pushOption` применяются и к `operator` —
    его отправка откажет или понесёт `-c push.pushOption=`.
    """
    proj = Project(stand, gate, HUMAN_POLICY if gate == "target-human" else "")
    _own, branch, _sha = proj.task()
    key, value = SUBSTITUTIONS[case]
    real_git(proj.clone, "config", key, value)
    if case == "alias":
        stand.aliases.add("p")
    sub = "p" if case == "alias" else "push"
    start = len(stand.pushes)
    outcome = attempt(gitcmd.in_repo, proj.clone, sub, "origin", branch)
    if gate == "target-human":
        assert_refused(stand, outcome, start, f"{case}/{gate}")
    else:
        argv = assert_passed(stand, outcome, start, f"{case}/{gate}")
        assert not has_pair(argv, "-c", "push.pushOption="), stand.note(f"{case}: {argv}")


# --- AC-8 ---

@pytest.mark.parametrize("case", ["base", "delete", "colon-delete"])
def test_ac8_operator_project_with_template_keeps_pushes(stand, case):
    """Проект `operator` с `branch_template: feature/{ref}`: отправка в `base` и удаление своей ветки не отказаны.

    Сценарий: проект `merge_gate: operator`, `branch_template:
    feature/{ref}`, `ref_required: tracker`, живая задача с веткой
    `feature/PROJ-<n>`. `push origin main`, `push origin --delete
    <ветка>`, `push origin :<ветка>` доходят до git.

    Ловит мутацию: белый список включается по нестандартному
    `branch_template` (а не только по `merge_gate`) — `main` и удаление
    своей ветки откажут.
    """
    policy = '      branch_template: "feature/{ref}"\n      ref_required: tracker\n'
    proj = Project(stand, "operator", policy)
    _own, branch, _sha = proj.task(branch=f"feature/PROJ-{stand.rng.randrange(10 ** 6)}")
    args = {"base": ("push", "origin", config.MAIN_BRANCH),
            "delete": ("push", "origin", "--delete", branch),
            "colon-delete": ("push", "origin", f":{branch}")}[case]
    start = len(stand.pushes)
    assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, *args), start, f"{case}: {args}")


# --- AC-9 ---

@pytest.mark.parametrize("gate", ["operator", "target-human"])
def test_ac9_successful_push_journals_local_sha(stand, gate):
    """Успешная отправка ветки задачи оставляет в её журнале «ветка отправлена: <sha>» с локальным sha.

    Сценарий: проект с записью по умолчанию (`operator`) и `target-human`,
    живая задача с веткой в клоне. `push origin <ветка>` (шпион отвечает
    кодом 0) — в журнале задачи запись «ветка отправлена» с sha её
    локальной ветки.

    Ловит мутацию: запись пишется только под белым списком — у `operator`
    её нет; в запись идёт sha `HEAD` клона (ветка `main`), а не
    отправленной ветки; запись не пишется вовсе.
    """
    proj = Project(stand, gate, HUMAN_POLICY if gate == "target-human" else "")
    own, branch, sha = proj.task()
    start = len(stand.pushes)
    assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, "push", "origin", branch),
                  start, "отправка ветки")
    assert any(sha in r and SENT in r for r in sent_records(own)), stand.note(
        f"нет «{SENT}: {sha}»: {steps(own)}")


@pytest.mark.parametrize("case", ["nonzero", "dry-run", "delete-lease"])
def test_ac9_no_record_without_real_push(stand, case):
    """Неудачная отправка, `--dry-run` и удаление ветки с `--force-with-lease` записи «ветка отправлена» не оставляют.

    Сценарий: проект с записью по умолчанию, живая задача. Отправка своей
    ветки с ненулевым кодом (шпион отвечает 1); `push --dry-run origin
    <ветка>` (код 0); `push --force-with-lease --delete origin <ветка>`
    (код 0) — в журнале задачи нет записи «ветка отправлена». Контрольно
    обычная отправка той же ветки запись оставляет.

    Ловит мутацию: запись пишется до проверки кода выхода — останется
    после неудачи; `--dry-run` не исключён; удаление считается
    отправкой, потому что в argv есть имя ветки.
    """
    proj = Project(stand, "operator")
    own, branch, sha = proj.task()
    args = {"nonzero": ("push", "origin", branch),
            "dry-run": ("push", "--dry-run", "origin", branch),
            "delete-lease": ("push", "--force-with-lease", "--delete", "origin", branch)}[case]
    if case == "nonzero":
        stand.push_code = 1
    attempt(gitcmd.in_repo, proj.clone, *args)
    assert sent_records(own) == [], stand.note(f"{case}: {sent_records(own)}")
    stand.push_code = 0
    start = len(stand.pushes)
    assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, "push", "origin", branch),
                  start, "контроль")
    assert any(sha in r for r in sent_records(own)), stand.note(f"контроль: {steps(own)}")


def test_ac9_push_options_added_to_task_branch_only(stand):
    """`policy.push_options: [A=1, B=2]` даёт `-o A=1 -o B=2` отправке ветки задачи; ссылке документов и пустому списку — без `-o`.

    Сценарий: проект `operator` с `push_options: [A=1, B=2]`: отправка
    своей ветки несёт пары `-o A=1` и `-o B=2` в этом порядке; отправка
    `refs/artifacts/<id>` того же проекта — без `-o`. Проект без
    `push_options`: отправка ветки задачи — без `-o`.

    Ловит мутацию: опции добавляются к любой отправке проекта, включая
    `refs/artifacts/*`; добавляется только первая опция; порядок списка
    не сохранён; у пустого списка добавляется голый `-o`.
    """
    proj = Project(stand, "operator", "      push_options: [A=1, B=2]\n")
    own, branch, _sha = proj.task()
    start = len(stand.pushes)
    argv = assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, "push", "origin", branch),
                         start, "ветка задачи")
    assert has_pair(argv, "-o", "A=1") and has_pair(argv, "-o", "B=2"), stand.note(f"{argv}")
    assert argv.index("A=1") < argv.index("B=2"), stand.note(f"{argv}")
    start = len(stand.pushes)
    argv = assert_passed(stand, attempt(gitcmd.in_repo, proj.clone, "push", "origin",
                                        f"refs/artifacts/{own}"), start, "ссылка документов")
    assert "-o" not in argv, stand.note(f"ссылка документов: {argv}")
    plain = Project(stand, "operator")
    _id, plain_branch, _ = plain.task()
    start = len(stand.pushes)
    argv = assert_passed(stand, attempt(gitcmd.in_repo, plain.clone, "push", "origin",
                                        plain_branch), start, "пустой список")
    assert "-o" not in argv, stand.note(f"пустой список: {argv}")
