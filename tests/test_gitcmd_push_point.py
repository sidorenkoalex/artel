"""Единая точка отправки `gitcmd` (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 3): белый список проекта не `operator`, журнал «ветка отправлена», опции `policy.push_options`.

Планка задачи — разовая; здесь — долгоживущий минимум свойств точки
отправки. Клон проекта — настоящий git-репозиторий по адресу
`repo_context.clone_path`; `subprocess.run`/`Popen` подменены шпионом:
отправка (`push`) записывается и не исполняется, прочие git-вызовы идут к
настоящему git.
"""
import subprocess
from pathlib import Path

import pytest

from orchestrator import alerts, config, gitcmd, idgen, repo_context, store, targets

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen


class Spy:
    def __init__(self):
        self.pushes = []

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


@pytest.fixture
def spy(initialized_tmp_root, monkeypatch):
    monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    s = Spy()
    monkeypatch.setattr(subprocess, "run", s.run)
    monkeypatch.setattr(subprocess, "Popen", s.popen)
    return s


def git_in(repo: Path, *args: str) -> str:
    return REAL_RUN(["git", *args], cwd=repo, check=True, capture_output=True,
                    text=True).stdout.strip()


def project(name: str, gate: str, policy: str = "") -> Path:
    """Запись проекта в локальном слое и его клон с веткой `feature/x`."""
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
        f"      url: https://localhost/team/{name}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")
    assert targets.target(name)["merge_gate"] == gate
    clone = repo_context.clone_path(name)
    clone.mkdir(parents=True)
    git_in(clone, "init", "-q", "-b", config.MAIN_BRANCH)
    git_in(clone, "config", "user.email", "artel@example.invalid")
    git_in(clone, "config", "user.name", "artel tests")
    git_in(clone, "commit", "-q", "--allow-empty", "-m", "init")
    git_in(clone, "remote", "add", "origin", f"https://localhost/team/{name}")
    git_in(clone, "branch", "feature/x")
    return clone


def task(name: str, branch: str = "feature/x", state: str = "in_dev") -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача", state, branch, name,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def sent(task_id: str) -> list:
    return [r["detail"] for r in store.task_steps(store.db(), task_id)
            if r["action"] == gitcmd.PUSH_SENT_ACTION]


def test_whitelist_refuses_base_push_with_alert(spy):
    """Проект `target-human`: отправка в `main` без своей задачи — отказ до процесса и алерт `incident`.

    Ловит мутацию: белый список не включается для `merge_gate`, отличного
    от `operator` (`targets.push_whitelisted` всегда False), — отправка в
    `main` дойдёт до процесса; отказ без контекста не заводит алерт с
    источником `branch_push_whitelist`.
    """
    clone = project("qhuman", "target-human")
    res = gitcmd.in_repo(clone, "push", "origin", config.MAIN_BRANCH)
    assert res.returncode != 0 and res.stderr, res
    assert spy.pushes == []
    sources = [r["source"] for r in alerts.open_alerts(store.db(), "incident")]
    assert gitcmd.PUSH_WHITELIST_SOURCE in sources


def test_whitelist_lease_checked_against_last_sent_sha(spy):
    """Проект `target-human`: перезапись `--force-with-lease=<ветка>:<sha>` проходит только с sha последней записи «ветка отправлена».

    Ловит мутацию: sha аренды не сверяется с журналом — чужой sha пройдёт;
    запись «ветка отправлена» не пишется после успешной отправки — верный
    sha будет отказан.
    """
    clone = project("qlease", "target-human")
    own = task("qlease")
    sha = git_in(clone, "rev-parse", "feature/x")
    assert gitcmd.in_repo(clone, "push", "origin", "feature/x").returncode == 0
    assert any(d.startswith(sha) for d in sent(own)), sent(own)
    wrong = gitcmd.in_repo(clone, "push", f"--force-with-lease=feature/x:{'0' * 40}",
                           "origin", "feature/x")
    assert wrong.returncode != 0
    pushes = len(spy.pushes)
    right = gitcmd.in_repo(clone, "push", f"--force-with-lease=feature/x:{sha}",
                           "origin", "feature/x")
    assert right.returncode == 0, right.stderr
    assert len(spy.pushes) == pushes + 1
    assert "push.pushOption=" in spy.pushes[-1]


def test_operator_push_gets_options_and_record(spy):
    """Проект `operator` с `push_options: [A=1]`: ветка задачи уходит с `-o A=1` и записью «ветка отправлена»; ссылка документов — без `-o`, белого списка нет.

    Ловит мутацию: опции добавляются и к `refs/artifacts/*`; запись пишется
    только под белым списком; к отправке проекта `operator` добавлен сброс
    `-c push.pushOption=`.
    """
    clone = project("qoper", "operator", "      push_options: [A=1]\n")
    own = task("qoper")
    assert gitcmd.in_repo(clone, "push", "origin", "feature/x").returncode == 0
    argv = spy.pushes[-1]
    assert argv[argv.index("-o") + 1] == "A=1"
    assert "push.pushOption=" not in argv
    assert sent(own)
    assert gitcmd.in_repo(clone, "push", "origin",
                          f"refs/artifacts/{own}").returncode == 0
    assert "-o" not in spy.pushes[-1]
    assert gitcmd.in_repo(clone, "push", "origin", config.MAIN_BRANCH).returncode == 0


@pytest.mark.parametrize("form", ["path", "file-url"])
@pytest.mark.parametrize("layer", ["target-human", "broken"])
def test_dest_into_project_clone_refused_as_path_or_file_url(spy, form, layer):
    """Отправка из корня пульта в клон внешнего проекта — простым путём и `file://`-адресом — отказ до процесса: под белым списком и при нечитаемом `targets.yaml`.

    Ловит мутацию: назначение `file://<клон>` не распознаётся как путь в
    клон проекта (проверка пути только для назначения без схемы) — отправка
    в `main` клона уходит в процесс без белого списка и без отказа
    «гейт мержа неизвестен».
    """
    clone = project("qfile", "target-human")
    if layer == "broken":
        targets.local_path().write_text("targets: [не запись\n", encoding="utf-8")
        with pytest.raises(targets.TargetsError):
            targets.load()
    dest = clone.as_uri() if form == "file-url" else str(clone)
    res = gitcmd.git("push", dest, config.MAIN_BRANCH)
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert spy.pushes == []


class AliasSpy(Spy):
    """Отправкой считается и вызов подкоманды `p` — псевдонима `push`."""

    @staticmethod
    def is_push(argv) -> bool:
        return (isinstance(argv, list) and argv[0] == "git"
                and ("push" in argv or "p" in argv))


@pytest.fixture
def alias_spy(initialized_tmp_root, monkeypatch):
    monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    for name in gitcmd.GIT_LOCATION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    s = AliasSpy()
    monkeypatch.setattr(subprocess, "run", s.run)
    monkeypatch.setattr(subprocess, "Popen", s.popen)
    return s


@pytest.mark.parametrize("gate", ["target-human", "operator"])
@pytest.mark.parametrize("form", ["-c", "--config-env", "--config-env="])
def test_alias_defined_in_command_refused(alias_spy, monkeypatch, form, gate):
    """Псевдоним `push`, заданный самой командой (`-c alias.p=push`, `--config-env alias.p=VAR`, `--config-env=alias.p=VAR`), в клоне проекта под белым списком — отказ до процесса, с записью алерта; у проекта `operator` вызов прежний и уходит в процесс.

    Ловит мутацию: псевдоним в argv не распознаётся (`_alias_in_argv`
    всегда None) — у проекта `target-human` вызов `p origin main` уходит в
    процесс отправки в `main`; и обратную: отказ псевдонима без условия
    белого списка — вызов проекта `operator` не доходит до процесса.
    """
    clone = project("qalias", gate)
    monkeypatch.setenv("ALIAS_VALUE", "push")
    words = {"-c": ("-c", "alias.p=push"),
             "--config-env": ("--config-env", "alias.p=ALIAS_VALUE"),
             "--config-env=": ("--config-env=alias.p=ALIAS_VALUE",)}[form]
    res = gitcmd.in_repo(clone, *words, "p", "origin", config.MAIN_BRANCH)
    if gate == "operator":
        assert gitcmd.PUSH_REFUSED_ACTION not in res.stderr, res
        assert len(alias_spy.pushes) == 1
        return
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert alias_spy.pushes == []
    sources = [r["source"] for r in alerts.open_alerts(store.db(), "incident")]
    assert gitcmd.PUSH_WHITELIST_SOURCE in sources


@pytest.mark.parametrize("dest", ["path", "file-url"])
def test_alias_in_command_into_whitelisted_clone_from_pult_root_refused(
        alias_spy, dest):
    """Псевдоним `push` в argv из корня пульта с назначением — путём или `file://`-адресом клона проекта под белым списком — отказ до процесса; тот же вызов без назначения в клон внешнего проекта (как у `repo_context.git` с `!`-псевдонимом) отказом не становится.

    Ловит мутацию: для псевдонима в argv проект ищется только по рабочему
    каталогу (`_alias_guarded_project` не смотрит слова после подкоманды)
    — `-c alias.p=push p <клон> main` из корня пульта уходит в процесс.
    """
    clone = project("qaliasdest", "target-human")
    target = clone.as_uri() if dest == "file-url" else str(clone)
    res = gitcmd.git("-c", "alias.p=push", "p", target, config.MAIN_BRANCH)
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert alias_spy.pushes == []
    res = gitcmd.git("-c", "alias.p=push", "p", "origin", config.MAIN_BRANCH)
    assert gitcmd.PUSH_REFUSED_ACTION not in res.stderr, res


@pytest.mark.parametrize("layer", ["target-human", "broken"])
@pytest.mark.parametrize("form", ["-c", "--config-env"])
@pytest.mark.parametrize("body", ["push", "shell-C", "shell-cd"])
def test_alias_body_into_whitelisted_clone_from_pult_root_refused(
        alias_spy, monkeypatch, body, form, layer):
    """Псевдоним из argv, у которого назначение — клон проекта под белым списком — лежит в теле (`alias.p=push <клон> main`, `!git -C <клон> push origin main`, `!cd <клон>&&git push origin main`), а не в словах после подкоманды: из корня пульта — отказ до процесса, под белым списком и при нечитаемом `targets.yaml`; тело задаётся `-c` и `--config-env`.

    Ловит мутацию: слова тела псевдонима не учитываются
    (`_alias_body_words` возвращает пустые списки) — вызов `p` без слов из
    корня пульта уходит в процесс отправки в `main` клона.
    """
    clone = project("qaliasbody", "target-human")
    if layer == "broken":
        targets.local_path().write_text("targets: [не запись\n", encoding="utf-8")
    value = {"push": f"push {clone} {config.MAIN_BRANCH}",
             "shell-C": f"!git -C {clone} push origin {config.MAIN_BRANCH}",
             "shell-cd": f"!cd {clone}&&git push origin {config.MAIN_BRANCH}",
             }[body]
    if form == "-c":
        words = ("-c", f"alias.p={value}")
    else:
        monkeypatch.setenv("ALIAS_BODY", value)
        words = ("--config-env", "alias.p=ALIAS_BODY")
    res = gitcmd.git(*words, "p")
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert alias_spy.pushes == []


def test_global_option_before_unknown_subcommand_refused(alias_spy):
    """Проект `target-human`: глобальная опция, кроме `-C`, перед подкомандой не из встроенных (`-c include.path=…` подкладывает псевдоним) — отказ до процесса.

    Ловит мутацию: для подкоманды вне встроенных глобальные опции не
    проверяются — псевдоним из подключённого файла конфигурации уходит в
    процесс отправки.
    """
    clone = project("qinclude", "target-human")
    extra = clone.parent / "alias.cfg"
    extra.write_text("[alias]\n\tp = push\n", encoding="utf-8")
    res = gitcmd.in_repo(clone, "-c", f"include.path={extra}", "p", "origin",
                         config.MAIN_BRANCH)
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert alias_spy.pushes == []


@pytest.mark.parametrize("route", ["option", "option=", "env"])
@pytest.mark.parametrize("layer", ["target-human", "broken"])
def test_git_dir_into_project_clone_from_pult_root_refused(alias_spy, monkeypatch,
                                                           route, layer):
    """Отправка из корня пульта с `--git-dir <клон>/.git`, `--git-dir=<клон>/.git` или `GIT_DIR` — проект определяется по клону: отказ до процесса под белым списком и при нечитаемом `targets.yaml`.

    Ловит мутацию: проект вызова определяется только по `-C`/рабочему
    каталогу (`_location_projects` не читает `--git-dir`/`GIT_DIR`) —
    отправка в `main` клона считается отправкой артели и уходит в процесс.
    """
    clone = project("qgitdir", "target-human")
    if layer == "broken":
        targets.local_path().write_text("targets: [не запись\n", encoding="utf-8")
    git_dir = str(clone / ".git")
    if route == "env":
        monkeypatch.setenv("GIT_DIR", git_dir)
        args = ()
    else:
        args = (("--git-dir", git_dir) if route == "option"
                else (f"--git-dir={git_dir}",))
    res = gitcmd.git(*args, "push", "origin", config.MAIN_BRANCH)
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert alias_spy.pushes == []


def test_tag_source_into_own_branch_refused_and_branch_made_explicit(spy):
    """Проект `target-human`: refspec `<тег>:<своя ветка>` — отказ до процесса с записью в журнале задачи; разрешённая отправка своей ветки уходит с явным `refs/heads/<ветка>:refs/heads/<ветка>`.

    Ловит мутацию: источник refspec не проверяется (тег проходит и git
    создаёт refs/tags/<ветка>); назначение не подставляется явным
    `refs/heads/<имя>` — тег с именем ветки перехватил бы короткий источник.
    """
    clone = project("qtag", "target-human")
    own = task("qtag")
    git_in(clone, "tag", "v9")
    res = gitcmd.in_repo(clone, "push", "origin", "v9:feature/x")
    assert res.returncode != 0 and gitcmd.PUSH_REFUSED_ACTION in res.stderr, res
    assert spy.pushes == []
    refused = [r["detail"] for r in store.task_steps(store.db(), own)
               if r["action"] == gitcmd.PUSH_REFUSED_ACTION]
    assert any("v9" in d for d in refused), refused
    git_in(clone, "tag", "feature/x")
    assert gitcmd.in_repo(clone, "push", "origin", "feature/x").returncode == 0
    assert spy.pushes[-1][-1] == "refs/heads/feature/x:refs/heads/feature/x"
    sha = git_in(clone, "rev-parse", "refs/heads/feature/x")
    assert any(d.startswith(sha) for d in sent(own)), sent(own)
