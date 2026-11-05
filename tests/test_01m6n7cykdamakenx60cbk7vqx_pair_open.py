"""Пара `github` + `target-human` поддержана: `unsupported_reason` — `None`, действия `new`, `run`, `auto`, `approve`, `epic draft promote` не отказывают причиной поддержки и не зовут ни настоящий `gh`, ни сетевой git по адресу записи, строка `project-support-<проект>` — `ok`; пара `gitlab` + `operator` отказывает во всех этих действиях точным текстом с новым перечнем пар.

Группа: долгоживущий
Красен до реализации: `SUPPORTED_PAIRS` — `{("github", "operator"), ("gitlab", "target-human")}`: проект `github` + `target-human` получает причину «гейт мержа target-human не поддержан для хостинга github (…)», его действия отказывают, строка `project-support` — `fail`; причина `gitlab` + `operator` перечисляет две пары вместо трёх.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`targets.unsupported_reason` — команда CLI `artel.py` (`new`, `run`, `auto`,
`approve`, `epic draft promote`) — БД — внешние процессы». Песочница —
`initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`: пути
`config` во временном каталоге, `subprocess.run` подменён шпионом
`git_spy`, который записывает КАЖДУЮ команду процесса — это и шпион git, и
шпион запуска настоящего `gh`). Агент `runner.spawn_agent` и переход
`fsm.cmd_advance` подменены и при вызове поднимают `Halt`: команда на них
обрывается, тест видит факт вызова. `ci.gh` — подделка, отвечающая
отказом (настоящий `gh` не нужен ни одному случаю). Клон проекта заведён
заранее (`tests.sandbox.make_project_repo`): его `origin` — локальный голый
репозиторий, а `url` записи — `https://localhost/team/<имя>`, поэтому
шпион git сверяет, что ни одна сетевая команда (`clone`, `fetch`, `push`,
`ls-remote`) не идёт ни по адресу `http(s)://`, ни по имени remote с таким
адресом. Строки `doctor` — `doctor.all_checks` при отказе запуска внешних
процессов, кроме локальных.

Имена проектов порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import configparser
import contextlib
import io
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (artel, ci, config, doctor, epics, fsm, idgen,
                          repo_context, runner, store, targets)
from tests.sandbox import artel_target_entry, make_project_repo

LETTERS = "abcdefhkmnpqrsvwxyz"
NETWORK_GIT = ("clone", "fetch", "push", "ls-remote")
SUPPORT_WORDS = "не поддержан"
GLOP_REASON = ("гейт мержа operator не поддержан для хостинга gitlab "
               "(поддержаны: github + operator, github + target-human, "
               "gitlab + target-human)")
ACTIONS = ["new", "run", "auto", "approve", "epic draft promote"]


class Halt(Exception):
    """Подменённая зависимость вызвана: команда обрывается здесь."""


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def halted():
    """Агент и переход FSM подменены: вызов поднимает `Halt`."""
    with mock.patch.object(runner, "spawn_agent", side_effect=Halt("spawn_agent")) as spawn, \
            mock.patch.object(fsm, "cmd_advance", side_effect=Halt("cmd_advance")) as advance:
        yield {"spawn": spawn, "advance": advance}


@pytest.fixture
def fake_gh(monkeypatch):
    """Подделка `ci.gh`: каждый вызов записан, ответ — отказ."""
    calls: list = []

    def gh(*args, **kwargs):
        calls.append([str(a) for a in args])
        return subprocess.CompletedProcess(list(args), 1, "", "gh вне сценария теста")

    monkeypatch.setattr(ci, "gh", gh)
    return calls


def project_name(rng: random.Random) -> str:
    return "q" + "".join(rng.choice(LETTERS) for _ in range(8))


def declare(name: str, forge_name: str, gate: str) -> None:
    """Дописывает плоскую запись проекта в `targets.yaml` песочницы."""
    text = (config.TARGETS.read_text(encoding="utf-8")
            if config.TARGETS.exists() else "targets:\n" + artel_target_entry())
    entry = (f"  {name}:\n    forge: {forge_name}\n"
             f"    url: https://localhost/team/{name}\n"
             f"    base: {config.MAIN_BRANCH}\n"
             f"    token_slot: {name}-token\n    no_paths: []\n"
             f"    project_skills: []\n    merge_gate: {gate}\n")
    config.TARGETS.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")


def cli(*args: str) -> tuple:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода).
    Оборванная на подменённой зависимости команда — код `"Halt"`."""
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
        except Halt as exc:
            buf.write(f"\nHalt: {exc}")
            code = "Halt"
    return buf.getvalue(), code


def insert_task(name: str, state: str) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача проекта", state,
                      f"task/{task_id.lower()}-x", name, config.DEFAULT_BUDGET_USD)
    return task_id


def action_args(action: str, name: str) -> tuple:
    """(аргументы команды `action` для проекта `name`, id задачи или None)."""
    if action == "new":
        return ["new", "Задача проекта", "--target", name], None
    if action in ("run", "auto"):
        task = insert_task(name, "in_dev")
        return [action, task, "--attach"], task
    if action == "approve":
        task = insert_task(name, "merge_gate")
        return ["approve", task], task
    conn = store.db()
    epic_id = epics.new_epic_id()
    store.insert_epic(conn, epic_id, name, "Эпик", "цель", None)
    number = store.insert_draft(conn, epic_id, "Черновик", "ТЗ черновика", None,
                                None, None)
    conn.commit()
    return ["epic", "draft", "promote", epics.draft_address(epic_id, number)], None


def journal_text(task: str | None) -> str:
    if task is None:
        return ""
    return "\n".join(f"{r['action']} {r['detail'] or ''}"
                     for r in store.task_steps(store.db(), task))


def remotes(clone: Path) -> dict:
    """Имя remote → адрес из `.git/config` клона."""
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.read(clone / ".git" / "config", encoding="utf-8")
    found = {}
    for section in parser.sections():
        if section.startswith('remote "') and section.endswith('"'):
            found[section[len('remote "'):-1]] = parser[section].get("url", "")
    return found


def git_subcommand(argv: list) -> tuple:
    """(подкоманда, аргументы после неё) git-вызова, сквозь `-C`/`-c`."""
    i = 1
    while i + 1 < len(argv) and argv[i] in ("-C", "-c"):
        i += 2
    return (argv[i], argv[i + 1:]) if i < len(argv) else ("", [])


def network_findings(calls: list, http_remotes: set) -> list:
    """Сетевые git-команды по адресу `http(s)://` или по имени remote с
    таким адресом."""
    found = []
    for call in calls:
        argv = [os.fsdecode(a) for a in call] if isinstance(call, (list, tuple)) else []
        if not argv or Path(argv[0]).name != "git":
            continue
        sub, rest = git_subcommand(argv)
        if sub not in NETWORK_GIT:
            continue
        words = [w for w in rest if not w.startswith("-")]
        if any(w.startswith(("http://", "https://")) or w in http_remotes for w in words):
            found.append(argv)
    return found


def gh_processes(calls: list) -> list:
    return [c for c in calls if isinstance(c, (list, tuple)) and c
            and Path(os.fsdecode(c[0])).name == "gh"]


# ------------------------------------------------------------------- AC-1


def test_ac1_github_people_reason_none(tmp_root, seed):
    """`targets.unsupported_reason` записи `github` + `target-human` — `None`.

    Сценарий: в `targets.yaml` песочницы — три записи `github` +
    `target-human` со случайными именами; для каждой `unsupported_reason`
    возвращает `None`, константа `SUPPORTED_PAIRS` содержит пару.

    Ловит мутацию: пара не добавлена в `SUPPORTED_PAIRS` или добавлена
    перевёрнутой (`("target-human", "github")`) — причина вместо `None`.
    """
    rng = random.Random(seed)
    names = set()
    while len(names) < 3:
        names.add(project_name(rng))
    for name in sorted(names):
        declare(name, "github", "target-human")
    for name in sorted(names):
        assert targets.unsupported_reason(name) is None, f"зерно: {seed}; {name}"
    assert ("github", "target-human") in targets.SUPPORTED_PAIRS


@pytest.mark.parametrize("action", ACTIONS)
def test_ac1_github_people_actions_not_refused_without_gh_and_network(
        initialized_tmp_root, halted, fake_gh, seed, action):
    """Действие проекта `github` + `target-human` не отказывает причиной поддержки, не запускает настоящий `gh` и сетевой git по адресу записи.

    Сценарий: запись `github` + `target-human` со случайным именем, клон
    заведён заранее (`origin` — локальный голый репозиторий; проверяется,
    что адрес `origin` не начинается с `http`). Команда по параметру
    (`run`/`auto` — задача в `in_dev`, `approve` — в `merge_gate`, `epic
    draft promote` — черновик эпика проекта). В выводе и журнале задачи нет
    «не поддержан»; `new` выходит с кодом 0 и заводит задачу проекта;
    `auto` доходит до перехода (подменённая зависимость вызвана);
    `promote` заводит задачу проекта. Шпион процессов не видел
    запуска `gh` и ни одной сетевой команды git по адресу `http(s)://` или
    по имени remote с таким адресом.

    Ловит мутацию: пара не поддержана — действие отказывает «гейт мержа
    target-human не поддержан…», `new`/`promote` задачу не заводят,
    `auto` не доходит до перехода; действие поддержанного
    проекта идёт в настоящий `gh` или в сеть по `url` записи.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    declare(name, "github", "target-human")
    clone = make_project_repo(name, origin=True)
    clone_remotes = remotes(clone)
    assert clone_remotes, f"зерно: {seed}; у клона нет remote"
    assert not any(u.startswith("http") for u in clone_remotes.values()), clone_remotes
    http_remotes = {r for r, u in clone_remotes.items() if u.startswith("http")}
    spy = initialized_tmp_root.git_spy
    before = {r["id"] for r in store.all_tasks(store.db())}
    args, task = action_args(action, name)
    start = len(spy.calls)
    out, code = cli(*args)
    calls = spy.calls[start:]
    created = [r for r in store.all_tasks(store.db())
               if r["id"] not in before and r["target"] == name and r["id"] != task]
    note = (f"зерно: {seed}; проект {name}; {action}; код {code}; "
            f"spawn {halted['spawn'].call_count}, advance {halted['advance'].call_count}\n"
            f"{out}\n--- журнал:\n{journal_text(task)}")
    assert SUPPORT_WORDS not in out, note
    assert SUPPORT_WORDS not in journal_text(task), note
    if action == "new":
        assert code == 0 and len(created) == 1, note
    if action == "epic draft promote":
        assert len(created) == 1, note
    if action == "auto":
        assert halted["advance"].call_count + halted["spawn"].call_count >= 1, note
    assert gh_processes(calls) == [], note
    assert network_findings(calls, http_remotes) == [], note


@pytest.fixture
def pult(initialized_tmp_root, monkeypatch):
    """Внешние процессы, кроме локальных (`ps`, интерпретатор, git без
    сети), не запускаются."""
    real_run, real_popen = subprocess.run, subprocess.Popen

    def local(argv) -> bool:
        if not isinstance(argv, (list, tuple)) or not argv:
            return False
        words = [os.fsdecode(a) for a in argv]
        base = Path(words[0]).name
        if base == "git":
            return not set(NETWORK_GIT) & set(words[1:])
        return base == "ps" or base.startswith("python") or words[0] == sys.executable

    def run(argv, *args, **kwargs):
        if local(argv):
            return real_run(argv, *args, **kwargs)
        empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines")) else ""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return initialized_tmp_root


def test_ac1_doctor_project_support_ok(pult, seed):
    """Строка `doctor` `project-support-<проект>` записи `github` + `target-human` — `ok`.

    Сценарий: в `targets.yaml` песочницы — артель и запись `github` +
    `target-human` со случайным именем. Среди строк `doctor.all_checks` —
    ровно одна `project-support-<проект>`, статус `ok`.

    Ловит мутацию: пара не поддержана — строка `fail` с причиной.
    """
    name = project_name(random.Random(seed))
    declare(name, "github", "target-human")
    checks = doctor.all_checks(store.db())
    found = [c for c in checks if c.name == f"project-support-{name}"]
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    note = f"зерно: {seed}; проект {name}\n{shown}"
    assert len(found) == 1 and found[0].status == "ok", note


# ------------------------------------------------------------------- AC-2


def test_ac2_gitlab_operator_reason_exact(tmp_root, seed):
    """`targets.unsupported_reason` записи `gitlab` + `operator` — точно текст с тремя поддержанными парами.

    Сценарий: три записи `gitlab` + `operator` со случайными именами;
    `unsupported_reason` каждой равен «гейт мержа operator не поддержан для
    хостинга gitlab (поддержаны: github + operator, github + target-human,
    gitlab + target-human)».

    Ловит мутацию: пара `gitlab` + `operator` попала в поддержанные
    (`None`); перечень собран не в порядке `sorted(SUPPORTED_PAIRS)` или
    без новой пары — равенство не сойдётся.
    """
    rng = random.Random(seed)
    names = set()
    while len(names) < 3:
        names.add(project_name(rng))
    for name in sorted(names):
        declare(name, "gitlab", "operator")
    for name in sorted(names):
        assert targets.unsupported_reason(name) == GLOP_REASON, f"зерно: {seed}; {name}"


@pytest.mark.parametrize("action", ACTIONS)
def test_ac2_gitlab_operator_actions_refuse_with_full_reason(
        initialized_tmp_root, halted, fake_gh, seed, action):
    """Действие проекта `gitlab` + `operator` отказывает; вывод несёт полный новый текст причины.

    Сценарий: запись `gitlab` + `operator` со случайным именем; команда по
    параметру (как в AC-1). Код выхода — не 0 и не обрыв на подменённой
    зависимости; вывод содержит текст причины целиком; агент и переход не
    вызваны.

    Ловит мутацию: пара `gitlab` + `operator` сочтена поддержанной
    (действие идёт дальше — `new` заводит задачу, `run`/`auto` доходят до
    агента/перехода); текст причины с прежним перечнем из двух пар.
    """
    name = project_name(random.Random(seed))
    declare(name, "gitlab", "operator")
    args, task = action_args(action, name)
    out, code = cli(*args)
    note = (f"зерно: {seed}; проект {name}; {action}; код {code}; "
            f"spawn {halted['spawn'].call_count}, advance {halted['advance'].call_count}\n{out}")
    assert code not in (0, "Halt"), note
    assert GLOP_REASON in out, note
    assert halted["spawn"].call_count == 0, note
    assert halted["advance"].call_count == 0, note


def test_ac2_doctor_project_support_fail_with_reason(pult, seed):
    """Строка `doctor` `project-support-<проект>` записи `gitlab` + `operator` — `fail`, причина несёт полный новый текст.

    Сценарий: артель и запись `gitlab` + `operator` со случайным именем;
    среди строк `doctor.all_checks` ровно одна `project-support-<проект>`,
    статус `fail`, в тексте — причина целиком.

    Ловит мутацию: строка `ok`/`warn` у неподдержанной пары; причина с
    прежним перечнем пар.
    """
    name = project_name(random.Random(seed))
    declare(name, "gitlab", "operator")
    checks = doctor.all_checks(store.db())
    found = [c for c in checks if c.name == f"project-support-{name}"]
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    note = f"зерно: {seed}; проект {name}\n{shown}"
    assert len(found) == 1 and found[0].status == "fail", note
    assert GLOP_REASON in found[0].detail, note
