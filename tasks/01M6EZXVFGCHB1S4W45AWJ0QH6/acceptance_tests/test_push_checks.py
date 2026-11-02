"""Сверки единой точки отправки `gitcmd` перед отправкой проекта `target-human` и опция `-c core.hooksPath` в argv отправки пульта.

Группа: разовый
Красен до реализации: `gitcmd` не сверяет `remote.origin.url` с адресом записи, `url.*.insteadOf`/`pushInsteadOf`, `core.sshCommand`, иной `core.hooksPath`, переменные `GIT_SSH_COMMAND`/`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` — шпион видит такую отправку; argv отправки клона `target-human` не несёт `-c core.hooksPath=<config.ROOT>/scripts/git-hooks/target-human`.

Группа «разовый» — не по смыслу свойства (оно обязано держаться и после
мержа), а по правилу guard: долгоживущему файлу закрыт импорт
`orchestrator.gitcmd` (`scripts/guard.py::_GIT_MODULES`), а предмет
критериев — сама единая точка отправки модуля.

Стенд — `_stand.Stand` поверх `real_git`: клон проекта заводит
`workspace.ensure_clone` (`remote.origin.url` = `url` записи), в БД — живая
задача проекта с веткой по шаблону, ветка есть в клоне. Затем
`subprocess.run`/`Popen` подменены шпионом: отправка (`push`, псевдоним
`p`) журналируется и не исполняется, прочие git-вызовы идут к настоящему
git — сверки конфигурации видят её настоящей. Каждый сценарий сначала
проверяет, что без находки отправка доходит до шпиона, — отказ после
находки вызван ею. Имена порождаются `random`; зерно печатается и входит в
текст провала.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stand import OPERATOR, TARGET_HUMAN, Stand, git  # noqa: E402

from orchestrator import gitcmd  # noqa: E402


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(real_git, monkeypatch, tmp_path)


def ready_push(stand, monkeypatch, gate: str = TARGET_HUMAN) -> tuple:
    """(клон, ветка) проекта с живой задачей; шпион включён, и отправка
    ветки без находок уже дошла до шпиона."""
    name, clone, _bare = stand.project(gate)
    branch = stand.template_branch()
    stand.commit_branch(clone, branch)
    stand.task(name, branch)
    stand.spy(monkeypatch)
    res = gitcmd.in_repo(clone, "push", "origin", branch)
    assert res.returncode == 0 and len(stand.pushes) == 1, stand.note(
        f"без находок отправка не дошла до git: {res.stderr}")
    return clone, branch


def assert_refused(stand, res, needle: str, what: str) -> None:
    """Отказ до вызова git: ненулевой код, шпион не видел новой отправки,
    причина называет находку (без учёта регистра — ключ git
    регистронезависим)."""
    assert res.returncode != 0, stand.note(f"{what}: отправка не отказана")
    assert len(stand.pushes) == 1, stand.note(f"{what}: шпион видел push "
                                              f"{stand.pushes[1:]}")
    assert needle.lower() in (res.stderr or "").lower(), stand.note(
        f"{what}: причина не называет {needle}: {res.stderr}")


# --------------------------------------------------------------------- AC-7

@pytest.mark.parametrize("finding, needle", [
    ("url", "remote.origin.url"),
    ("insteadOf", "insteadOf"),
    ("pushInsteadOf", "pushInsteadOf"),
    ("sshCommand", "core.sshCommand"),
    ("hooksPath", "core.hooksPath"),
    ("pushurl", "remote.origin.pushurl"),
    ("push", "remote.origin.push"),
    ("mirror", "remote.origin.mirror"),
    ("pushOption", "push.pushOption"),
])
def test_ac7_config_findings_refuse_before_git(stand, monkeypatch, tmp_path,
                                               finding, needle):
    """Находка в конфигурации клона `target-human` — отказ отправки до вызова git, причина её называет.

    Сценарий: отправка ветки задачи дошла до шпиона; в конфигурацию клона
    добавлена одна находка `finding`; та же отправка — ненулевой код,
    шпион новой отправки не видел, в причине — имя находки.

    Ловит мутацию: сверка `remote.origin.url` с `url` записи пропущена —
    отправка в подменённый `origin` доходит до шпиона; конфигурация
    читается только для `remote.origin.*`, и `url.*.insteadOf`/
    `pushInsteadOf`, `core.sshCommand`, иной `core.hooksPath` проходят;
    прежние отказы `pushurl`/`push`/`mirror`/`push.pushOption` сняты.
    """
    clone, branch = ready_push(stand, monkeypatch)
    other = str(tmp_path / "chuzhoy.git")
    url = git(clone, "remote", "get-url", "origin").stdout.strip()
    setup = {
        "url": ("remote", "set-url", "origin", other),
        "insteadOf": ("config", f"url.{other}.insteadOf", url),
        "pushInsteadOf": ("config", f"url.{other}.pushInsteadOf", url),
        "sshCommand": ("config", "core.sshCommand", "ssh -o BatchMode=yes"),
        "hooksPath": ("config", "core.hooksPath", str(tmp_path / "chuzhie-huki")),
        "pushurl": ("config", "remote.origin.pushurl", other),
        "push": ("config", "remote.origin.push", "refs/heads/*:refs/heads/*"),
        "mirror": ("config", "remote.origin.mirror", "true"),
        "pushOption": ("config", "push.pushOption", "ci.skip"),
    }[finding]
    git(clone, *setup)
    res = gitcmd.in_repo(clone, "push", "origin", branch)
    assert_refused(stand, res, needle, finding)


def test_ac7_unset_hooks_path_reaches_git(stand, monkeypatch):
    """Снятый `core.hooksPath` клона `target-human` без иных находок — отправка доходит до git.

    Сценарий: после первой отправки у клона снят `core.hooksPath`; повтор
    отправки ветки задачи — код 0, шпион видит вторую отправку.

    Ловит мутацию: сверка `core.hooksPath` отказывает и незаданному значению
    (сравнение «не равен каталогу» без условия «задан»).
    """
    clone, branch = ready_push(stand, monkeypatch)
    git(clone, "config", "--unset-all", "core.hooksPath", check=False)
    res = gitcmd.in_repo(clone, "push", "origin", branch)
    assert res.returncode == 0, stand.note(f"отказ без находок: {res.stderr}")
    assert len(stand.pushes) == 2, stand.note(f"шпион: {stand.pushes}")


# --------------------------------------------------------------------- AC-8

@pytest.mark.parametrize("variable", [
    "GIT_DIR", "GIT_WORK_TREE", "GIT_SSH_COMMAND", "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_KEY_0",
])
def test_ac8_env_findings_refuse_before_git(stand, monkeypatch, tmp_path, variable):
    """Переменная окружения вызова из перечня — отказ отправки клона `target-human` до вызова git, причина называет переменную.

    Сценарий: отправка ветки задачи дошла до шпиона; в окружении процесса
    выставлена `variable`; та же отправка — ненулевой код, шпион новой
    отправки не видел, в причине — имя переменной.

    Ловит мутацию: перечень переменных сверки не дополнен `GIT_SSH_COMMAND`,
    `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM` либо из него выпали прежние
    `GIT_DIR`/`GIT_WORK_TREE`/`GIT_COMMON_DIR`/`GIT_CONFIG_*`.
    """
    clone, branch = ready_push(stand, monkeypatch)
    empty = tmp_path / "pustoy.gitconfig"
    empty.write_text("", encoding="utf-8")
    value = {
        "GIT_DIR": str(clone / ".git"),
        "GIT_WORK_TREE": str(clone),
        "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
        "GIT_CONFIG_GLOBAL": str(empty),
        "GIT_CONFIG_SYSTEM": str(empty),
        "GIT_COMMON_DIR": str(clone / ".git"),
        "GIT_CONFIG_COUNT": "0",
        "GIT_CONFIG_PARAMETERS": "'color.ui'='never'",
        "GIT_CONFIG_KEY_0": "color.ui",
    }[variable]
    monkeypatch.setenv(variable, value)
    res = gitcmd.in_repo(clone, "push", "origin", branch)
    assert_refused(stand, res, variable, variable)


# --------------------------------------------------------------------- AC-9

def test_ac9_bang_alias_with_hooks_path_refused(stand, monkeypatch):
    """`!`-псевдоним в аргументах команды с `-c core.hooksPath=` в теле, вызванный в клоне `target-human`, — отказ до вызова git.

    Сценарий: `gitcmd.in_repo(<клон>, "-c", "alias.p=!git -c
    core.hooksPath=/dev/null push origin <ветка>", "p")` — ненулевой код,
    шпион не видит ни `push`, ни `p`.

    Ловит мутацию: отказ псевдонима в argv сужен до формы без `!` либо
    тело с `-c core.hooksPath=` принято за безопасное — отправка мимо хука
    уходит в процесс.
    """
    clone, branch = ready_push(stand, monkeypatch)
    res = gitcmd.in_repo(
        clone, "-c", f"alias.p=!git -c core.hooksPath=/dev/null push origin {branch}",
        "p")
    assert res.returncode != 0, stand.note("псевдоним не отказан")
    assert len(stand.pushes) == 1, stand.note(f"шпион: {stand.pushes[1:]}")


# -------------------------------------------------------------------- AC-10

def hooks_pairs(argv: list) -> list:
    return [argv[i + 1] for i in range(len(argv) - 1)
            if argv[i] == "-c" and argv[i + 1].lower().startswith("core.hookspath=")]


def test_ac10_human_push_carries_hooks_path_pair(stand, monkeypatch):
    """Отправка пульта из клона `target-human`, прошедшая сверки, несёт `-c core.hooksPath=<config.ROOT>/scripts/git-hooks/target-human`.

    Сценарий: вызывающий зовёт `gitcmd.in_repo(<клон>, "push", "origin",
    <ветка>)` без такой опции; в argv, который увидел шпион, есть пара
    `-c core.hooksPath=<каталог хуков target-human>`.

    Ловит мутацию: `_push_plan` не вставляет опцию (или вставляет прежний
    `<config.ROOT>/scripts/git-hooks`, или относительный путь).
    """
    _clone, _branch = ready_push(stand, monkeypatch)
    argv = stand.pushes[0]
    pairs = hooks_pairs(argv)
    expected = {f"core.hooksPath={stand.human_hooks_dir()}",
                f"core.hooksPath={stand.human_hooks_dir().resolve()}"}
    assert any(p in expected for p in pairs), stand.note(f"argv отправки: {argv}")


def test_ac10_operator_push_has_no_hooks_path_pair(stand, monkeypatch):
    """Отправка пульта из клона проекта `github` + `operator` пары `-c core.hooksPath=` не несёт.

    Сценарий: та же отправка ветки задачи из клона проекта `operator`; в
    argv шпиона нет `core.hooksPath=`.

    Ловит мутацию: опция вставляется всем внешним проектам, а не только
    `target-human` (признак не через `merged_by_project_people`).
    """
    _clone, _branch = ready_push(stand, monkeypatch, OPERATOR)
    argv = stand.pushes[0]
    assert not any("core.hookspath=" in a.lower() for a in argv), \
        stand.note(f"argv отправки: {argv}")
