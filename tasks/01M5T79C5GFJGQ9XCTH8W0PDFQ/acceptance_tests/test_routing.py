"""Маршрут запуска git семи мест «Контекста» SPEC: откуда запускается git, с
какими аргументами, окружением и типом вывода, и кто его видит под
подменами существующих тестов.

Группа: разовый
Красен до реализации: AC-1 — git мест запускается прямо из их модулей (кадр-запускатель `acceptance.py`/`brief.py`/`reference_cache.py`/`tz_check.py`/`outcome_integrity.py`, не `gitcmd.py`), и в модулях есть `subprocess.run`/`Popen` с git; тест AC-7 об отсутствующем `cwd` смотрит, что упавший запуск места 1 пришёл из `gitcmd.py`; остальные тесты AC-7 и тесты AC-9 держат прежнее поведение и зелены с рождения.

Каждое место исполняется по-настоящему на репозитории-фикстуре
(`_places.Repo`) под шпионом `subprocess.Popen` (`_places.spy_popen`):
запуск git с «запускателем» — файлом первого кадра вне `subprocess.py` —
показывает, через какой модуль пульта прошёл git, без знания имён новых
функций `gitcmd`.

Провалидировано временным стабом реализации (удалён, не закоммичен):
функции `gitcmd` со сроком, байтовым выводом/входом, своим окружением на
`Popen` и потоковым чтением, места переведены на них — все методы зелёные.
"""
import ast
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _places  # noqa: E402
from _places import (GITCMD_FILE, Repo, deadline_in, git_launches,  # noqa: E402
                     raw_git, spy_popen)

from orchestrator import (acceptance, brief, config, gitcmd,  # noqa: E402
                          reference_cache, tz_check)
from orchestrator.advance_gates import outcome_integrity  # noqa: E402
from tests.sandbox import SpyRun  # noqa: E402

MODULES = ("orchestrator/acceptance.py", "orchestrator/brief.py",
           "orchestrator/reference_cache.py", "orchestrator/tz_check.py",
           "orchestrator/advance_gates/outcome_integrity.py")

EXCLUDED = tuple(config.FULL_SUITE_BASE_EXCLUDED_PATHS)


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path)


def scenario(name, repo: Repo):
    """(вызов места, ожидаемый результат-функция, свои argv места по порядку,
    номер места, вывод текстом, всего запусков git)."""
    p = str(repo.path)
    head, base = repo.head, repo.base
    if name == "1-worktree":
        (repo.path / "a.py").write_text("x = 1\nz = 3\nw = 4\n", encoding="utf-8")
        return (lambda: acceptance.suite_tree_hash(repo.path),
                repo.worktree_tree,
                [["git", "-C", p, "add", "-u", "--", "."],
                 ["git", "-C", p, "write-tree"]], 1, True, 4)
    if name == "1-ref":
        return (lambda: acceptance.suite_tree_hash(repo.path, ref=base,
                                                   worktree=False),
                lambda: raw_git(repo.path, "rev-parse", f"{base}^{{tree}}"),
                [["git", "-C", p, "read-tree", base],
                 ["git", "-C", p, "write-tree"]], 1, True, 3)
    if name == "1-base":
        return (lambda: acceptance.suite_tree_hash(repo.path, base=True,
                                                   worktree=False),
                lambda: repo.tree,
                [["git", "-C", p, "read-tree", "HEAD"],
                 ["git", "-C", p, "rm", "-q", "--cached", "-r",
                  "--ignore-unmatch", "--", *EXCLUDED],
                 ["git", "-C", p, "write-tree"]], 1, True, 4)
    if name == "2-ls-tree":
        return (lambda: brief._clone_git(repo.path, "ls-tree", "-z", head,
                                         literal=True),
                lambda: (_places.REAL_RUN(["git", "-C", p, "ls-tree", "-z", head],
                                          capture_output=True).stdout, ""),
                [["git", "-C", p, "--literal-pathspecs", "ls-tree", "-z", head]],
                2, False, 1)
    if name == "2-show":
        return (lambda: brief._clone_git(repo.path, "show", f"{head}:a.py"),
                lambda: (b"x = 1\nz = 3\n", ""),
                [["git", "-C", p, "show", f"{head}:a.py"]], 2, False, 1)
    if name == "3":
        return (lambda: reference_cache.branch_commit(repo.path, "main"),
                lambda: (head, ""),
                [["git", "-C", p, "rev-parse", "--verify", "--quiet",
                  "refs/heads/main^{commit}"]], 3, True, 1)
    if name == "4":
        return (lambda: reference_cache._list_tree(repo.path, head,
                                                   deadline_in(120)),
                lambda: ([("a.py", repo.blob_a, 12), ("sub/b.py", repo.blob_b, 6)],
                         0),
                [["git", "-C", p, "ls-tree", "-r", "-l", "-z", head]], 4, False, 1)
    if name == "5":
        return (lambda: reference_cache._cat_blobs(
                    repo.path, [repo.blob_a, repo.blob_b], deadline_in(120)),
                lambda: {repo.blob_a: b"x = 1\nz = 3\n", repo.blob_b: b"y = 2\n"},
                [["git", "-C", p, "cat-file", "--batch"]], 5, False, 1)
    if name == "6-git":
        return (lambda: (lambda r: (r.returncode, r.stdout))(
                    tz_check._git(repo.path, "show", f"{head}:a.py")),
                lambda: (0, b"x = 1\nz = 3\n"),
                [["git", "-C", p, "show", f"{head}:a.py"]], 6, False, 1)
    if name == "6-git-ok":
        return (lambda: tz_check._git_ok(repo.path, "rev-parse", "HEAD"),
                lambda: (head + "\n").encode(),
                [["git", "-C", p, "rev-parse", "HEAD"]], 6, False, 1)
    if name == "7":
        return (lambda: outcome_integrity._added_lines(repo.path, base, head),
                lambda: {"a.py": [(2, "z = 3")]},
                [["git", "-C", p, "-c", "core.quotePath=false", "diff",
                  "--no-color", "--no-ext-diff", "--no-textconv", "--no-relative",
                  "--src-prefix=a/", "--dst-prefix=b/", "-M", "-U0", base, head]],
                7, False, 1)
    raise AssertionError(name)


SCENARIOS = ["1-worktree", "1-ref", "1-base", "2-ls-tree", "2-show", "3", "4",
             "5", "6-git", "6-git-ok", "7"]
PLACE1 = ["1-worktree", "1-ref", "1-base"]
RUN_VISIBLE = ["2-ls-tree", "2-show", "3", "5", "6-git", "6-git-ok", "7"]


# --- AC-1 -----------------------------------------------------------------

def _git_list(node) -> bool:
    return (isinstance(node, (ast.List, ast.Tuple)) and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value == "git")


def raw_git_calls(source: str) -> list:
    """Строки вызовов `subprocess.run`/`subprocess.Popen` (и обёрток
    `_launch`/`_run_capture`) с argv, начинающимся литералом "git" — прямо
    или через имя, которому такой список присвоен в той же функции."""
    tree = ast.parse(source)
    hits = []
    scopes = [n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))]
    for scope in scopes:
        git_names = {t.id for n in ast.walk(scope) if isinstance(n, ast.Assign)
                     and _git_list(n.value)
                     for t in n.targets if isinstance(t, ast.Name)}
        for n in ast.walk(scope):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            raw = ((isinstance(f, ast.Attribute) and f.attr in ("run", "Popen")
                    and isinstance(f.value, ast.Name) and f.value.id == "subprocess")
                   or (isinstance(f, ast.Name)
                       and f.id in ("_launch", "_run_capture", "Popen")))
            if not raw:
                continue
            argv = n.args[0] if n.args else next(
                (k.value for k in n.keywords if k.arg == "args"), None)
            if argv is None:
                continue
            if _git_list(argv) or (isinstance(argv, ast.Name)
                                   and argv.id in git_names):
                hits.append(n.lineno)
    return sorted(set(hits))


@pytest.mark.parametrize("module", MODULES)
def test_ac1_modules_have_no_raw_git_subprocess(module):
    """Текст модуля из перечня AC-1 не несёт вызова `subprocess.run`/`Popen` с git.

    Разбор `ast`: вызов `subprocess.run(...)`/`subprocess.Popen(...)` или
    обёрток `_launch`/`_run_capture`, первый аргумент которого — список с
    литералом "git" в начале либо имя, которому такой список присвоен.

    Ловит мутацию: место 7 оставлено на `subprocess.run(argv, …)` с
    `argv = ["git", "-C", …]` — строка вызова попадает в находки.
    """
    source = (config.ROOT / module).read_text(encoding="utf-8")
    assert raw_git_calls(source) == [], (
        f"{module}: прямой запуск git через subprocess в строках "
        f"{raw_git_calls(source)}")


@pytest.mark.parametrize("name", SCENARIOS)
def test_ac1_place_launches_git_through_gitcmd(repo, name):
    """Место, исполненное на репозитории-фикстуре, запускает свой git из `gitcmd.py`.

    Под шпионом `subprocess.Popen` у каждого запуска git — кадр-запускатель
    (первый кадр вне `subprocess.py`). Свои команды места (argv из SPEC)
    обязаны прийти из `orchestrator/gitcmd.py`, как и все прочие запуски git
    вызова; других запусков git, кроме прежнего их числа, нет. Обёртки
    `acceptance._launch`/`_run_capture` дали бы запускатель `acceptance.py`.

    Ловит мутацию: `reference_cache._cat_blobs` оставлен на прямом
    `subprocess.run([...cat-file...])` — запускатель его запуска
    `reference_cache.py`, а не `gitcmd.py`.
    """
    call, _expected, own, place, _text, total = scenario(name, repo)
    with spy_popen() as log:
        call()
    launches = git_launches(log)
    mine = [r for r in launches if r.argv in own]
    assert [r.argv for r in mine] == own
    assert {(tuple(r.argv[3:5]), r.launcher) for r in launches
            if r.launcher != GITCMD_FILE} == set(), (
        f"место {place}: запуск git мимо gitcmd.py")
    assert len(launches) == total, [r.argv for r in launches]


# --- AC-7 -----------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_ac7_place_keeps_args_repo_env_types_and_process_count(repo, name):
    """Место запускает git с прежними argv, `-C <клон>`, окружением и типом вывода.

    Сверяется по шпиону `subprocess.Popen`: argv своих команд места (с
    `-C <клон>`), окружение — ровно `gitcmd.pult_env()` (у места 1 —
    `pult_env` поверх окружения с `GIT_INDEX_FILE` временного индекса, не
    индекса клона, одного на все команды вызова и убранного после),
    `cwd` места 1 — `config.ROOT`, текстовый вывод у мест 1 и 3 и байтовый у
    остальных, байтовый вход `cat-file` места 5, число процессов git и
    результат места.

    Ловит мутацию: перенос места 6 на функцию `gitcmd` с `text=True` —
    у запуска `wants_text` истинно, и `tz_check._git` отдаёт `str` вместо
    `bytes`.
    """
    call, expected, own, place, text, total = scenario(name, repo)
    with spy_popen() as log:
        result = call()
    launches = git_launches(log)
    mine = [r for r in launches if r.argv in own]
    assert [r.argv for r in mine] == own
    assert len(launches) == total
    assert result == expected()
    for rec in mine:
        assert rec.wants_text is text, rec.argv
        env = rec.kwargs.get("env")
        if place == 1:
            index = env.get("GIT_INDEX_FILE")
            assert index and Path(index) != repo.path / ".git" / "index"
            assert not Path(index).exists()
            assert env == gitcmd.pult_env({**os.environ, "GIT_INDEX_FILE": index})
            assert Path(rec.kwargs.get("cwd")) == Path(config.ROOT)
        else:
            assert env == gitcmd.pult_env()
    if place == 1:
        assert len({r.kwargs["env"]["GIT_INDEX_FILE"] for r in mine}) == 1
    if place == 5:
        assert mine[0].inputs == [(repo.blob_a + "\n" + repo.blob_b + "\n").encode()]


def test_ac7_place1_missing_cwd_raises_from_gitcmd_launch(repo, tmp_path):
    """При отсутствующем каталоге `config.ROOT` запуск места 1 падает исключением наружу.

    Прочие git-вызовы `suite_tree_hash` (`rev-parse`) идут через
    подменённый `gitcmd.git`, исполняющий git в существующем каталоге;
    `config.ROOT` указывает на несуществующий каталог — `cwd` своих команд
    места 1. `OSError` выходит из `suite_tree_hash` (не `None`), а упавший
    запуск — `read-tree` места 1, запущенный из `gitcmd.py`.

    Ловит мутацию: функция `gitcmd` места 1 запускает git с `cwd=repo`
    вместо `config.ROOT` — исключения нет, `suite_tree_hash` возвращает sha.
    """
    def git_elsewhere(*args):
        return _places.REAL_RUN(["git", *args], cwd=str(tmp_path),
                                capture_output=True, text=True,
                                env=gitcmd.pult_env())

    missing = tmp_path / "нет-такого-каталога"
    with mock.patch.object(gitcmd, "git", git_elsewhere), \
            mock.patch.object(config, "ROOT", missing), spy_popen() as log:
        with pytest.raises(OSError):
            acceptance.suite_tree_hash(repo.path, worktree=False)
    failed = git_launches(log)[-1]
    assert failed.argv == ["git", "-C", str(repo.path), "read-tree", "HEAD"]
    assert failed.launcher == GITCMD_FILE


# --- AC-9 -----------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_ac9_place_does_not_go_through_patched_gitcmd_stubs(repo, name):
    """Под подменой `gitcmd.git`/`in_repo`/`show`/`ls_tree_files` своя команда места туда не уходит.

    Заглушки — записывающие обёртки поверх настоящих функций (как
    подмены `fake_git` и `LightTransitionSandbox`, но без смены ответа:
    прочие `rev-parse` места 1 обязаны дойти до git). Своих подкоманд
    места среди записанных вызовов нет, результат места прежний.

    Ловит мутацию: новая функция `gitcmd` места 3 собрана поверх
    `gitcmd.git(...)` — вызов `rev-parse --verify` записан подменой
    `gitcmd.git`, под `fake_git` место ответило бы фейком.
    """
    call, expected, own, _place, _text, _total = scenario(name, repo)
    seen: list = []
    real_git, real_in_repo = gitcmd.git, gitcmd.in_repo
    real_show, real_ls = gitcmd.show, gitcmd.ls_tree_files

    def rec_git(*args):
        seen.append(list(args))
        return real_git(*args)

    def rec_in_repo(r, *args):
        seen.append(["-C", str(r), *args])
        return real_in_repo(r, *args)

    def rec_show(*a, **kw):
        seen.append(["show", *map(str, a)])
        return real_show(*a, **kw)

    def rec_ls(*a, **kw):
        seen.append(["ls-tree", *map(str, a)])
        return real_ls(*a, **kw)

    with mock.patch.object(gitcmd, "git", rec_git), \
            mock.patch.object(gitcmd, "in_repo", rec_in_repo), \
            mock.patch.object(gitcmd, "show", rec_show), \
            mock.patch.object(gitcmd, "ls_tree_files", rec_ls):
        result = call()
    own_subcommands = {argv[3] if argv[3] != "--literal-pathspecs" else argv[4]
                       for argv in own}
    if own[0][3] == "-c":
        own_subcommands = {"diff"}
    # Прочие вызовы места 1 (`rev-parse --show-toplevel …`, `ls-files`)
    # своих подкоманд не несут и в находки не попадают.
    leaked = [args for args in seen if set(args) & own_subcommands]
    assert leaked == []
    assert result == expected()


@pytest.mark.parametrize("name", PLACE1 + ["4"])
def test_ac9_spyrun_does_not_intercept_places_1_and_4(repo, name):
    """Под шпионом `SpyRun` на глобальном `subprocess.run` места 1 и 4 идут мимо него.

    `SpyRun(passthrough_unknown=True)` отвечает фейковым sha `f…f` на
    `write-tree`; место 1 обязано вернуть настоящее дерево, а среди команд,
    записанных шпионом, нет своих команд мест 1 и 4.

    Ловит мутацию: место 1 перенесено на `gitcmd.carpentry` (путь
    `subprocess.run`) — `write-tree` получает `f…f`, результат места —
    фейковый sha.
    """
    call, expected, own, _place, _text, _total = scenario(name, repo)
    spy = SpyRun(passthrough_unknown=True)
    with mock.patch.object(_places.subprocess, "run", spy):
        result = call()
    assert result == expected()
    assert result != SpyRun._FAKE_SHA
    assert [c for c in spy.calls if c in own] == []


@pytest.mark.parametrize("name", RUN_VISIBLE)
def test_ac9_spyrun_sees_places_2_3_5_6_7(repo, name):
    """Места 2, 3, 5, 6, 7 остаются видны шпиону глобального `subprocess.run`.

    `SpyRun(passthrough_unknown=True)` записывает команду и отдаёт её
    настоящему `subprocess.run`: свои argv места есть среди записанных,
    результат места прежний. Место 7 — ещё и подменой
    `outcome_integrity.subprocess.run` (атрибут модуля сохранён). Место 3
    под этим шпионом и до переноса получало его отказ на
    `rev-parse --verify … refs/heads/…` — прежний результат «ветки нет».

    Ловит мутацию: место 5 перенесено на поток `Popen` (как место 4) —
    `cat-file --batch` не попадает в `spy.calls`.
    """
    call, expected, own, place, _text, _total = scenario(name, repo)
    if place == 3:
        expected = lambda: (None, "ветки main нет в клоне проекта")  # noqa: E731
    spy = SpyRun(passthrough_unknown=True)
    target = outcome_integrity.subprocess if place == 7 else _places.subprocess
    with mock.patch.object(target, "run", spy):
        result = call()
    assert result == expected()
    assert [c for c in spy.calls if c in own] == own
