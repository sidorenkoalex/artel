"""Единая точка отправки `gitcmd` при сбое чтения записи проекта или БД: отказ с причиной вместо пропуска (AC-4, AC-5, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-17).

Группа: разовый
Красен до реализации: отправка по адресу-URL при непрочитанной записи считается отправкой артели и уходит в git (AC-5); `in_flight_refusal` глотает `TargetsError`/`sqlite3.Error` в `None` (AC-7); проверка `max_in_flight` в `_push_plan` и чтение `in_repo` глотают `sqlite3.Error` и отправляют (AC-9, AC-10); отказ пределом несёт код 1, как любой отказ точки отправки, а `github_adapter` узнаёт предел по строке stderr (AC-12). Методы AC-4, AC-8, AC-11, AC-17, отправка артели AC-5, вариант «запись не прочитана» AC-10 (на main его отказывает следующее чтение «гейт мержа неизвестен») и вариант «код предела» AC-12 — сторожа прежнего поведения, зелены и на main.

Почему разовый, хотя свойства — свойства кода: предмет — модуль
`orchestrator.gitcmd`, импорт которого долгоживущему файлу запрещён
(`scripts/guard.py`, признак «git-модуль»), а шов сбоя БД, который
называет SPEC (требование 12), — чтение внутри закрытых `_push_plan` и
`in_repo` (постоянный `sqlite3.Error` валит отправку исключением раньше, в
`gitcmd._project_tasks`). Долгоживущий тест — забота разработчика в
`tests/` (как `tests/test_gitcmd_push_point.py`).

Стенд — песочница `initialized_tmp_root`; клон внешнего проекта —
настоящий git-репозиторий по адресу `repo_context.clone_path`, запись
проекта — в локальном слое (`targets.local_path()`), «непрочитанная
запись» — сломанный локальный слой (`targets.load()` бросает
`TargetsError`). `subprocess.run`/`Popen` подменены шпионом: отправка
(`push`) записывается и не исполняется, прочие git-вызовы идут к
настоящему git. Сбой БД — подмена публичного чтения `store` в названной
точке: первый вызов `store.project_tasks` (чтение `in_repo` до `git`),
`store.last_task_step_of` (счёт `max_in_flight`), `store.db` (чтение
проекта задачи в `in_flight_refusal`).

Имена проектов, пределы и адреса — из `random`, зерно печатается.

Провалидировано временным стабом (удалён, не закоммичен): отказ
`in_flight_refusal`/`_push_plan`/`in_repo` вне артели при сбое, отказ
URL-отправки при непрочитанной записи, именованный код отказа пределом и
его чтение в `github_adapter`.
"""
import contextlib
import io
import random
import sqlite3
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (alerts, amend, artifact_branch, ci, config,
                          github_adapter, gitcmd, idgen, keychain,
                          repo_context, store, targets)

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
GATE_UNKNOWN = "гейт мержа неизвестен"
GATE_UNKNOWN_UNREAD = "гейт мержа неизвестен — targets.yaml не читается"
AMEND_IN_FLIGHT = "первая отправка ветки"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class Spy:
    """Шпион процессов: отправка записывается и не исполняется."""

    def __init__(self, seed: int):
        self.pushes: list = []
        self.seed = seed
        self.rng = random.Random(seed)

    @staticmethod
    def is_push(argv) -> bool:
        return isinstance(argv, list) and "push" in argv and argv[0] == "git"

    def run(self, argv, *args, **kwargs):
        if self.is_push(argv):
            self.pushes.append(list(argv))
            empty = "" if kwargs.get("text") else b""
            return subprocess.CompletedProcess(argv, 0, empty, empty)
        return REAL_RUN(argv, *args, **kwargs)

    def popen(self, argv, *args, **kwargs):
        if self.is_push(argv):
            self.pushes.append(list(argv))
            raise OSError("отправка процессом Popen не исполняется")
        return REAL_POPEN(argv, *args, **kwargs)

    def word(self) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(6))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


@pytest.fixture
def pult(initialized_tmp_root, monkeypatch):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    spy = Spy(seed)
    monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    monkeypatch.setattr(keychain, "token", lambda *a, **k: "tok")
    monkeypatch.setattr(subprocess, "run", spy.run)
    monkeypatch.setattr(subprocess, "Popen", spy.popen)
    return spy


# ------------------------------------------------------------ помощники


def git_in(repo: Path, *args: str) -> str:
    return REAL_RUN(["git", *args], cwd=repo, check=True, capture_output=True,
                    text=True).stdout.strip()


def init_repo(path: Path, origin_url: str) -> Path:
    """git-репозиторий с коммитом, веткой `feature/x` и `origin`."""
    path.mkdir(parents=True)
    git_in(path, "init", "-q", "-b", config.MAIN_BRANCH)
    git_in(path, "config", "user.email", "artel@example.invalid")
    git_in(path, "config", "user.name", "artel tests")
    git_in(path, "commit", "-q", "--allow-empty", "-m", "init")
    git_in(path, "remote", "add", "origin", origin_url)
    git_in(path, "branch", "feature/x")
    return path


def project(pult, gate: str, policy: str = "") -> tuple:
    """Запись проекта `forge: github` с гейтом `gate` в локальном слое и его
    клон. (имя, клон, адрес записи)."""
    name = f"q{pult.word()}"
    url = f"https://localhost/team/{name}"
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(
        f"targets:\n  {name}:\n"
        f"    description:\n      base: {config.MAIN_BRANCH}\n"
        f"      test_profile:\n        command: [python3, -m, pytest]\n"
        f"        long_lived_dir: tests\n"
        f"        long_lived_name: test_<id>_<name>.py\n"
        f"    policy:\n      no_paths: []\n      project_skills: []\n"
        f"      merge_gate: {gate}\n"
        f"      weakening_scope: [tests/**/*.py]\n"
        f"      mutation_claim_scope: [tests/test_*.py]\n{policy}"
        f"    machine:\n      forge: github\n"
        f"      url: {url}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")
    clone = init_repo(repo_context.clone_path(name), url)
    return name, clone, url


def task(name: str, branch: str = "feature/x", state: str = "in_dev") -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача", state, branch, name,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def sent(task_id: str) -> list:
    return [r["detail"] for r in store.task_steps(store.db(), task_id)
            if r["action"] == gitcmd.PUSH_SENT_ACTION]


def break_entries(pult) -> None:
    """Локальный слой записей сломан: `targets.load()` бросает."""
    targets.local_path().write_text(f"targets: [не запись {pult.word()}\n",
                                    encoding="utf-8")
    try:
        targets.load()
    except targets.TargetsError:
        return
    pytest.fail(pult.note("стенд: сломанный слой записей загрузился"))


def artel_repo(pult) -> Path:
    """Репозиторий вне области проектов — отправка из него идёт как
    отправка артели."""
    return init_repo(Path(config.ROOT) / f"artel-{pult.word()}",
                     "https://localhost/team/artel")


def fail_first(monkeypatch, name: str, exc: Exception) -> list:
    """Первый вызов `store.<name>` бросает `exc`, следующие — настоящие.
    Список вызовов."""
    real = getattr(store, name)
    calls: list = []

    def wrapper(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise exc
        return real(*args, **kwargs)

    monkeypatch.setattr(store, name, wrapper)
    return calls


def fail_always(monkeypatch, module, name: str, exc: Exception) -> list:
    calls: list = []

    def wrapper(*args, **kwargs):
        calls.append(args)
        raise exc

    monkeypatch.setattr(module, name, wrapper)
    return calls


def ghosts(name: str, count: int, rng) -> None:
    """`count` незакрытых задач проекта с записью «ветка отправлена»."""
    for _ in range(count):
        other = task(name, branch=f"task/{''.join(rng.choice(ALPHABET) for _ in range(8))}")
        store.journal(store.db(), other, "orchestrator", gitcmd.PUSH_SENT_ACTION,
                      f"{'a' * 40} {store.get_task(store.db(), other)['branch']}")


def described(res) -> str:
    return f"код {res.returncode}; stderr: {res.stderr!r}"


# ------------------------------------------------------------------- AC-4


@pytest.mark.parametrize("gate", ["target-human", "operator"])
def test_ac4_unread_entry_by_call_site_refused(pult, gate):
    """Отправка из клона внешнего проекта при непрочитанной записи — отказ «гейт мержа неизвестен», `git push` не вызван.

    Сценарий: запись проекта (гейт по параметру) и его клон с веткой своей
    задачи; слой записей сломан. `gitcmd.in_repo(<клон>, "push", "origin",
    <ветка>)`: ненулевой код, в stderr «гейт мержа неизвестен», шпион не
    видит отправки. Сторож регрессии: на main уже так.

    Ловит мутацию: при `entries is None` точка отправки считает проект
    узнанным без записи и пропускает гейт (`entry is None` трактуется как
    «проект `operator`») — шпион видит `git push`.
    """
    name, clone, _url = project(pult, gate)
    task(name)
    break_entries(pult)
    res = gitcmd.in_repo(clone, "push", "origin", "feature/x")
    where = pult.note(described(res))
    assert res.returncode != 0 and GATE_UNKNOWN in (res.stderr or ""), where
    assert pult.pushes == [], where


# ------------------------------------------------------------------- AC-5


@pytest.mark.parametrize("dest", ["адрес записи", "посторонний адрес"])
def test_ac5_url_push_with_unread_entry_refused(pult, dest):
    """Отправка из корня пульта по адресу-URL, не адресу `origin` артели, при непрочитанной записи — отказ «гейт мержа неизвестен — targets.yaml не читается».

    Сценарий: запись внешнего проекта и его клон; слой записей сломан.
    `gitcmd.git("push", <URL>, "feature/x")` из корня пульта, URL — адрес
    из записи проекта либо посторонний адрес хостинга: ненулевой код, в
    stderr «гейт мержа неизвестен — targets.yaml не читается», шпион не
    видит отправки.

    Ловит мутацию: при непрочитанной записи URL по-прежнему не
    сопоставляется ни с чем и отправка считается отправкой артели
    (`gitcmd.py:812-816`) — шпион видит `git push`, код 0.
    """
    _name, _clone, url = project(pult, pult.rng.choice(["target-human",
                                                       "operator"]))
    break_entries(pult)
    if dest == "посторонний адрес":
        url = f"https://localhost/{pult.word()}/{pult.word()}.git"
    res = gitcmd.git("push", url, "feature/x")
    where = pult.note(f"{url}: {described(res)}")
    assert res.returncode != 0, where
    assert GATE_UNKNOWN_UNREAD in (res.stderr or ""), where
    assert pult.pushes == [], where


def test_ac5_artel_origin_push_with_unread_entry_unchanged(pult):
    """Отправка артели в `origin` при непрочитанной записи идёт, как прежде.

    Сценарий: слой записей сломан; `gitcmd.git("push", "origin",
    <ветка>)` из корня пульта: код 0, шпион видит ровно одну отправку.

    Ловит мутацию: отказ «гейт мержа неизвестен» распространён на любую
    отправку при непрочитанной записи, включая отправку артели в `origin`
    — код ненулевой, шпион отправки не видит.
    """
    project(pult, "target-human")
    break_entries(pult)
    res = gitcmd.git("push", "origin", f"task/{pult.word()}")
    where = pult.note(described(res))
    assert res.returncode == 0, where
    assert len(pult.pushes) == 1, where


# ------------------------------------------------------------------- AC-7


@pytest.mark.parametrize("gate", ["operator", "target-human"])
@pytest.mark.parametrize("fault", ["TargetsError", "sqlite3: проект задачи",
                                   "sqlite3: журнал"])
def test_ac7_in_flight_refusal_external_fault_refuses(pult, monkeypatch, gate,
                                                      fault):
    """`in_flight_refusal` задачи внешнего проекта при сбое чтения записи или БД — причина отказа, не `None`.

    Сценарий: запись проекта (гейт по параметру) с `max_in_flight`, задача
    проекта без записи «ветка отправлена». Сбой в точке чтения:
    «TargetsError» — `targets.load`/`targets.target` бросают;
    «sqlite3: проект задачи» — `store.db` бросает `sqlite3.Error` (проект
    задачи не прочитан); «sqlite3: журнал» — `store.last_task_step_of`
    бросает `sqlite3.Error` (счёт отправленных). Ответ
    `gitcmd.in_flight_refusal(<задача>)` — непустая строка причины.

    Ловит мутацию: `except (targets.TargetsError, sqlite3.Error): return
    None` (`gitcmd.py:774-775`) оставлен — ответ `None`, и `amend-tests`
    коммитит правку при неизвестном пределе.
    """
    limit = pult.rng.randint(1, 3)
    name, _clone, _url = project(pult, gate, f"      max_in_flight: {limit}\n")
    own = task(name)
    message = f"сбой {pult.word()}"
    if fault == "TargetsError":
        fail_always(monkeypatch, targets, "load", targets.TargetsError(message))
        fail_always(monkeypatch, targets, "target", targets.TargetsError(message))
    elif fault == "sqlite3: проект задачи":
        fail_always(monkeypatch, store, "db", sqlite3.OperationalError(message))
    else:
        fail_always(monkeypatch, store, "last_task_step_of",
                    sqlite3.OperationalError(message))
    why = gitcmd.in_flight_refusal(own)
    where = pult.note(f"{gate}, {fault}: ответ {why!r}")
    assert isinstance(why, str) and why.strip(), where


# ------------------------------------------------------------------- AC-8


def test_ac8_in_flight_refusal_artel_targets_error_none(pult, monkeypatch):
    """`in_flight_refusal` задачи артели при `TargetsError` в чтении записи — `None`, как прежде.

    Сценарий: задача артели в БД; `targets.load`/`targets.target` бросают
    `TargetsError`. Ответ `gitcmd.in_flight_refusal(<задача>)` — `None`.

    Ловит мутацию: отказ при `TargetsError` распространён на артель — ответ
    причина, и `amend-tests` артели при сломанном `targets.yaml` отказывает
    пределом.
    """
    own = task(config.DEFAULT_TARGET, branch=f"task/{pult.word()}")
    message = f"сбой {pult.word()}"
    fail_always(monkeypatch, targets, "load", targets.TargetsError(message))
    fail_always(monkeypatch, targets, "target", targets.TargetsError(message))
    assert gitcmd.in_flight_refusal(own) is None, pult.note("ответ не None")


def test_ac8_artel_amend_tests_not_refused_by_in_flight(pult):
    """`amend-tests` задачи артели при сломанном `targets.yaml` не отказывает пределом `max_in_flight`.

    Сценарий: задача артели в `in_dev`; слой записей сломан. `amend.
    cmd_amend_tests(<задача>, <основание>)` (команда может выйти по иной
    причине): ни в выводе, ни в журнале задачи нет отказа «первая отправка
    ветки» (`amend.py:857-859`).

    Ловит мутацию: `in_flight_refusal` отдаёт причину для артели при
    `TargetsError` — `amend-tests` выходит «отказ — первая отправка ветки:
    …» первым действием.
    """
    own = task(config.DEFAULT_TARGET, branch=f"task/{pult.word()}")
    break_entries(pult)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            amend.cmd_amend_tests(own, f"основание {pult.word()}")
        except SystemExit as exc:
            buf.write(f"\n{exc.code}")
    out = buf.getvalue()
    journal = "\n".join(f"{r['action']} | {r['detail'] or ''}"
                        for r in store.task_steps(store.db(), own))
    where = pult.note(f"--- вывод:\n{out}\n--- журнал:\n{journal}")
    assert AMEND_IN_FLIGHT not in out, where
    assert AMEND_IN_FLIGHT not in journal, where


# ------------------------------------------------------------------- AC-9


@pytest.mark.parametrize("gate", ["operator", "target-human"])
def test_ac9_push_plan_in_flight_db_error_refused(pult, monkeypatch, gate):
    """`sqlite3.Error` в проверке `max_in_flight` отправки проекта вне артели — отказ с причиной, `git push` не вызван.

    Сценарий: запись проекта (гейт по параметру) с `max_in_flight`, задача
    проекта без записи «ветка отправлена»; `store.last_task_step_of`
    бросает `sqlite3.Error`. `gitcmd.in_repo(<клон>, "push", "origin",
    <ветка>)`: ненулевой код, непустой stderr, шпион не видит отправки.

    Ловит мутацию: `except sqlite3.Error: waiting = None`
    (`gitcmd.py:960-961`) оставлен — предел пропущен, шпион видит `git
    push`.
    """
    limit = pult.rng.randint(1, 3)
    name, clone, _url = project(pult, gate, f"      max_in_flight: {limit}\n")
    task(name)
    calls = fail_always(monkeypatch, store, "last_task_step_of",
                        sqlite3.OperationalError(f"сбой {pult.word()}"))
    res = gitcmd.in_repo(clone, "push", "origin", "feature/x")
    where = pult.note(f"{gate}: {described(res)}; чтений журнала {len(calls)}")
    assert calls, pult.note(f"стенд: счёт max_in_flight не читал журнал; {where}")
    assert res.returncode != 0 and (res.stderr or "").strip(), where
    assert pult.pushes == [], where


# ------------------------------------------------------------------ AC-10


@pytest.mark.parametrize("case", ["target-human", "operator",
                                  "запись не прочитана"])
def test_ac10_in_repo_db_error_external_refused(pult, monkeypatch, case):
    """`sqlite3.Error` в чтении `in_repo` при отправке проекта вне артели — отказ с причиной, `git push` не вызван.

    Сценарий: запись проекта под белым списком (`target-human`), с
    `merge_gate: operator` либо непрочитанная (слой сломан); задача
    проекта. Первый вызов `store.project_tasks` — чтение `in_repo` до
    `git` — бросает `sqlite3.Error`, следующие — настоящие.
    `gitcmd.in_repo(<клон>, "push", "origin", <ветка>)`: ненулевой код,
    непустой stderr, шпион не видит отправки.

    Ловит мутацию: `except sqlite3.Error: refusal = None`
    (`gitcmd.py:1244-1245`) оставлен — у `operator` и под белым списком
    отправка уходит в git (шпион видит `git push`).
    """
    gate = case if case != "запись не прочитана" else pult.rng.choice(
        ["target-human", "operator"])
    name, clone, _url = project(pult, gate)
    task(name)
    if case == "запись не прочитана":
        break_entries(pult)
    calls = fail_first(monkeypatch, "project_tasks",
                       sqlite3.OperationalError(f"сбой {pult.word()}"))
    res = gitcmd.in_repo(clone, "push", "origin", "feature/x")
    where = pult.note(f"{case}: {described(res)}")
    assert calls, pult.note(f"стенд: in_repo не читал БД; {where}")
    assert res.returncode != 0 and (res.stderr or "").strip(), where
    assert pult.pushes == [], where


# ------------------------------------------------------------------ AC-11


def test_ac11_in_repo_db_error_artel_push_unchanged(pult, monkeypatch):
    """`sqlite3.Error` в чтении `in_repo` при отправке артели — отказа нет, отправка идёт.

    Сценарий: репозиторий вне области проектов (отправка артели);
    первый вызов `store.project_tasks` бросает `sqlite3.Error`.
    `gitcmd.in_repo(<репозиторий>, "push", "origin", <ветка>)`: код 0,
    шпион видит ровно одну отправку.

    Ловит мутацию: отказ при `sqlite3.Error` в `in_repo` распространён на
    артель — код ненулевой, отправки нет.
    """
    repo = artel_repo(pult)
    calls = fail_first(monkeypatch, "project_tasks",
                       sqlite3.OperationalError(f"сбой {pult.word()}"))
    res = gitcmd.in_repo(repo, "push", "origin", "feature/x")
    where = pult.note(described(res))
    assert calls, pult.note(f"стенд: in_repo не читал БД; {where}")
    assert res.returncode == 0, where
    assert len(pult.pushes) == 1, where


# ------------------------------------------------------------------ AC-12


def in_flight_refused(pult) -> tuple:
    """Проект `operator` с достигнутым `max_in_flight` и задача без записи
    «ветка отправлена»: (клон, результат `in_repo`, результат `git`)."""
    limit = pult.rng.randint(1, 3)
    name, clone, _url = project(pult, "operator",
                                f"      max_in_flight: {limit}\n")
    task(name)
    ghosts(name, limit, pult.rng)
    by_repo = gitcmd.in_repo(clone, "push", "origin", "feature/x")
    by_git = gitcmd.git("-C", str(clone), "push", "origin", "feature/x")
    return clone, by_repo, by_git


def int_constants() -> dict:
    return {n: v for n, v in vars(gitcmd).items()
            if n.isupper() and type(v) is int}


def test_ac12_in_flight_refusal_has_own_named_code(pult):
    """Отказ пределом `max_in_flight` из `gitcmd.git` и `gitcmd.in_repo` несёт код именованной константы `gitcmd`, отличный от кода прочих отказов.

    Сценарий: проект `operator` с `max_in_flight` = N, N задач проекта с
    записью «ветка отправлена», задача без неё. Отправка её ветки через
    `in_repo` и через `git("-C", <клон>, …)`: оба — отказ со строкой
    `IN_FLIGHT_LIMIT_REASON` в stderr и одним и тем же ненулевым кодом,
    равным значению целой константы модуля `gitcmd` (имя ПРОПИСНЫМИ);
    шпион не видит отправки. Затем слой записей сломан — отказ «гейт мержа
    неизвестен» той же отправки: код ненулевой и отличен от кода предела.

    Ловит мутацию: отказ пределом идёт общим `_refused` с кодом 1 — коды
    предела и «гейт мержа неизвестен» совпадают; либо код задан литералом
    без константы модуля.
    """
    _clone, by_repo, by_git = in_flight_refused(pult)
    where = pult.note(f"in_repo: {described(by_repo)}; git: {described(by_git)}")
    for res in (by_repo, by_git):
        assert gitcmd.IN_FLIGHT_LIMIT_REASON in (res.stderr or ""), where
    code = by_repo.returncode
    assert code != 0 and by_git.returncode == code, where
    named = [n for n, v in int_constants().items() if v == code]
    assert named, where + f"; целые константы gitcmd: {int_constants()}"
    assert pult.pushes == [], where
    break_entries(pult)
    other = gitcmd.in_repo(_clone, "push", "origin", "feature/x")
    where += f"; гейт неизвестен: {described(other)}"
    assert GATE_UNKNOWN in (other.stderr or ""), where
    assert other.returncode not in (0, code), where


@pytest.mark.parametrize("kind", ["код предела", "иной код со строкой предела"])
def test_ac12_github_draft_mr_reads_limit_by_code(pult, monkeypatch, kind):
    """Черновой MR GitHub: результат отправки с кодом отказа пределом — без алерта и без `gh`; иной ненулевой код со строкой предела в stderr — сбой отправки.

    Сценарий: код отказа пределом берётся из настоящего отказа точки
    отправки (как в соседнем методе). Затем `github_adapter.ensure_draft_mr`
    задачи проекта `github` + `operator` при подменённом `gitcmd.in_repo`,
    отвечающем результатом с кодом по параметру и stderr
    `IN_FLIGHT_LIMIT_REASON`. «код предела»: `alerts.raise_alert` и `ci.gh`
    не званы. «иной код со строкой предела»: алерт (инцидент
    `github_adapter`) поднят, `ci.gh` не зван.

    Ловит мутацию: `github_adapter.py:173` по-прежнему ищет
    `IN_FLIGHT_LIMIT_REASON` в stderr — иной сбой с этой строкой молча
    принят за очередь (алерта нет).
    """
    _clone, by_repo, _by_git = in_flight_refused(pult)
    limit_code = by_repo.returncode
    code = limit_code if kind == "код предела" else pult.rng.choice(
        [c for c in (1, 2, 3, 128, 255) if c != limit_code])
    name = f"q{pult.word()}"
    result = subprocess.CompletedProcess(
        [], code, "", f"{gitcmd.PUSH_REFUSED_ACTION} (проект {name}): "
                      f"{gitcmd.IN_FLIGHT_LIMIT_REASON}: 2 из 2")
    row = {"target": name, "branch": f"task/{pult.word()}", "title": "T",
           "draft_mr_created": 0, "is_canary": 0}
    gh = mock.Mock()
    alert = mock.Mock()
    monkeypatch.setattr(targets, "target",
                        lambda target: {"forge": "github", "base": "main",
                                        "merge_gate": "operator"})
    monkeypatch.setattr(gitcmd, "fetch_ref_sha", lambda *a, **k: ("", "нет"))
    monkeypatch.setattr(repo_context, "resolve", lambda target: None)
    monkeypatch.setattr(artifact_branch, "send_pending", lambda *a, **k: None)
    monkeypatch.setattr(gitcmd, "in_repo", lambda *a, **k: result)
    monkeypatch.setattr(ci, "gh", gh)
    monkeypatch.setattr(alerts, "raise_alert", alert)
    monkeypatch.setattr(store, "journal", mock.Mock())
    monkeypatch.setattr(store, "task_target", lambda conn, task_id: name)
    github_adapter.ensure_draft_mr(mock.Mock(), "T1", row)
    where = pult.note(f"{kind}: код {code}, код предела {limit_code}")
    gh.assert_not_called()
    if kind == "код предела":
        assert alert.call_count == 0, where
    else:
        assert alert.call_count >= 1, where


# ------------------------------------------------------------------ AC-17


@pytest.mark.parametrize("project_kind", ["github+operator", "артель"])
def test_ac17_readable_entry_push_unchanged(pult, project_kind):
    """Артель и `github` + `operator` при читаемых записи и БД: отправка ветки идёт, как на main.

    Сценарий: «github+operator» — запись проекта читается, задача проекта
    без предела; `gitcmd.in_repo(<клон>, "push", "origin", <ветка>)`: код
    0, шпион видит ровно одну отправку, в журнале задачи — запись «ветка
    отправлена:». «артель» — отправка из репозитория вне области проектов:
    код 0, ровно одна отправка.

    Ловит мутацию: новый отказ точки отправки срабатывает и без сбоя
    (например, проверка БД отказывает при пустом ответе) — код ненулевой,
    отправки нет.
    """
    if project_kind == "артель":
        repo, own = artel_repo(pult), None
    else:
        name, repo, _url = project(pult, "operator")
        own = task(name)
    res = gitcmd.in_repo(repo, "push", "origin", "feature/x")
    where = pult.note(f"{project_kind}: {described(res)}")
    assert res.returncode == 0, where
    assert len(pult.pushes) == 1, where
    if own is not None:
        assert sent(own), where
