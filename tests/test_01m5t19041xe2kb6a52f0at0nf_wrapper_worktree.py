"""Рабочая копия задачи внешнего проекта без обвязки: `workspace.ensure` исключает пути действующего списка обвязки с диска (sparse-checkout без конусов), приводит исключения к текущему списку, убирает неотслеживаемые и игнорируемые файлы под ними; ветка и дифф задачи не меняются; у артели копия полная.

Группа: долгоживущий
Красен до реализации: `workspace.ensure` выписывает рабочую копию внешнего проекта полностью — `CLAUDE.md`, `.claude/x`, `harness/a.py`, `sub/CLAUDE.md`, `sub/AGENTS.md`, `frontend/.claude/x` лежат на диске (AC-15..AC-20), неотслеживаемый `.claude/settings.local.json` остаётся (AC-19), команды `git sparse-checkout` ensure не зовёт — подменённый сбой её не задевает, причины нет и шаг стартует (AC-21). AC-22 держит полную копию артели и зелёный с рождения.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`workspace.ensure` — git рабочей копии (sparse-checkout, индекс, диск) —
чекпоинт шага `checkpoint.commit_success_checkpoint` — запуск шага
`runner.cmd_run`». Песочница — настоящий git (`tests.sandbox.RealGitSandbox`,
фикстура `real_git`): корень — клон артели с bare `origin`; внешний проект —
клон с bare `origin` (`tests.sandbox.make_project_repo`), в `main` которого
закоммичены файлы обвязки, `src/m.py`, `sub/.mcp.json` и `.gitignore` с
`*.log`; запись проекта несёт `agent_wrapper: [harness/]` (кроме AC-18).
Задача — строка БД в `in_dev`, ветка заводится `ensure` от `origin/main`.
Набор файлов на диске — обход каталога без `.git`. Сбой sparse-checkout
(AC-21) — подменённый `subprocess.run`, отвечающий кодом 1 на git-вызовы
с `sparse-checkout`; запуск агента — подменённый `runner.spawn_agent`.
Тексты файлов — от зерна `random`; зерно печатается и входит в текст
каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
константа маркеров, формула `**/<каталог>/`, поле `agent_wrapper` в обоих
слоях и переносе, перечень проекта, отказ `knowledge`, зоны каталога
обвязки, источник подсветки, sparse-checkout рабочей копии с игнором и
уборкой путей обвязки, строка `doctor` — все методы зелёные.
"""
import os
import random
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (catalog, checkpoint, config, idgen,  # noqa: F401
                          runner, store, workspace)
from tests.sandbox import artel_target_entry, capture, make_project_repo

EXT = "vnesh"
ARTEL = config.DEFAULT_TARGET
LETTERS = "abcdefghijkmnopqrstuvwxyz"
WRAPPER_FILES = ("CLAUDE.md", ".claude/x", "harness/a.py", "sub/CLAUDE.md",
                 "sub/AGENTS.md", "frontend/.claude/x")
KEPT_FILES = ("src/m.py", "sub/.mcp.json")

EXT_ENTRY = """  {name}:
    forge: github
    url: http://localhost/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
{extra}"""


class Stand:
    """Внешний проект с обвязкой в дереве и задачи на нём."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.clone = make_project_repo(EXT)
        self.contents = {rel: f"{rel} {self.word()}\n"
                         for rel in (*WRAPPER_FILES, *KEPT_FILES)}
        self.contents[".gitignore"] = "*.log\n"
        for rel, text in self.contents.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.cgit("add", "-A")
        self.cgit("commit", "-q", "-m", "проект с обвязкой")
        self.cgit("push", "-q", "origin", config.MAIN_BRANCH)
        self.base = self.cgit("rev-parse", "HEAD").strip()
        self.write_targets(wrapper=True)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def cgit(self, *args: str) -> str:
        return self.sb.git("-C", str(self.clone), *args)

    def wgit(self, wt: Path, *args: str) -> str:
        return self.sb.git("-C", str(wt), *args)

    def write_targets(self, wrapper: bool) -> None:
        extra = "    agent_wrapper: [harness/]\n" if wrapper else ""
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + EXT_ENTRY.format(name=EXT, extra=extra), encoding="utf-8")

    def new_task(self, target: str = EXT) -> tuple[str, str]:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-wt"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        return task_id, branch

    def ensured(self) -> tuple[str, str, Path]:
        task_id, branch = self.new_task()
        wt, error = workspace.ensure(task_id, branch)
        assert error is None, self.msg(f"рабочая копия не заведена: {error}")
        return task_id, branch, wt


def on_disk(root: Path) -> set[str]:
    """Пути файлов под `root` без каталога и файла `.git`."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts}


@pytest.fixture
def stand(real_git):
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield Stand(real_git)


# ------------------------------------------------------------ AC-15

def test_ac15_ensure_checks_out_without_wrapper(stand):
    """Сразу после `ensure` на диске рабочей копии нет файлов обвязки, прочие на месте, дифф от базы и статус пусты.

    Сценарий: дерево `main` проекта несёт корневые и вложенные `CLAUDE.md`/
    `AGENTS.md`, `.claude/` в корне и в `frontend/`, `harness/a.py` (элемент
    `agent_wrapper`), `sub/.mcp.json` и `src/m.py`. После `ensure` новой
    задачи: файлов обвязки на диске нет, `src/m.py` и `sub/.mcp.json` есть с
    содержимым базы; `git diff <база>` и `git status --porcelain` пусты.

    Ловит мутацию: `.mcp.json` исключается на любой глубине — пропал
    `sub/.mcp.json`; маркеры `**/…` исключаются только в корне — на месте
    `sub/CLAUDE.md` и `frontend/.claude/x`; элементы `agent_wrapper` не
    исключаются — на месте `harness/a.py`; файлы убраны с диска удалением, а
    не исключением — статус показывает удалённые файлы.
    """
    _task, _branch, wt = stand.ensured()
    files = on_disk(wt)
    assert [rel for rel in WRAPPER_FILES if rel in files] == [], stand.msg(files)
    for rel in KEPT_FILES:
        assert (wt / rel).read_text(encoding="utf-8") == stand.contents[rel], \
            stand.msg(rel)
    assert stand.wgit(wt, "diff", stand.base) == "", stand.msg("дифф")
    assert stand.wgit(wt, "status", "--porcelain") == "", stand.msg("статус")


# ------------------------------------------------------------ AC-16

def test_ac16_step_checkpoint_keeps_wrapper_in_branch(stand):
    """Чекпоинт шага в рабочей копии без обвязки коммитит правку роли и оставляет файлы обвязки в дереве ветки.

    Сценарий: рабочая копия AC-15 (файлов обвязки на диске нет); роль
    правит `src/m.py`; `checkpoint.commit_success_checkpoint` за роль
    `developer`. В дереве головы ветки задачи `src/m.py` — новый текст, а
    каждый файл обвязки — на месте с содержимым базы.

    Ловит мутацию: обвязка снята с диска без пометки sparse-checkout
    (удаление файлов) — `git add -A` чекпоинта коммитит их удаление из
    ветки; исключения записаны так, что чекпоинт не коммитит правку.
    """
    task, branch, wt = stand.ensured()
    assert [rel for rel in WRAPPER_FILES if (wt / rel).exists()] == [], \
        stand.msg("обвязка на диске после ensure")
    new_text = f"A = {stand.seed}\n"
    (wt / "src/m.py").write_text(new_text, encoding="utf-8")
    capture(checkpoint.commit_success_checkpoint, stand.conn, task, "developer")
    assert stand.cgit("show", f"{branch}:src/m.py") == new_text, stand.msg("правка")
    for rel in WRAPPER_FILES:
        assert stand.cgit("show", f"{branch}:{rel}") == stand.contents[rel], \
            stand.msg(rel)


# ------------------------------------------------------------ AC-17

def test_ac17_ensure_idempotent_and_fixes_full_worktree_only(stand):
    """Повторный `ensure` идемпотентен; полная рабочая копия задачи приводится к копии без обвязки; клон и чужая копия не задеты.

    Сценарий: (1) копия AC-15, повторный `ensure` — причина `None`, набор
    файлов на диске прежний. (2) Вторая задача: её копия заведена в клоне
    полным `git worktree add` без исключений; рядом — ещё одна копия того же
    клона (`git worktree add` вне `ensure`). `ensure` второй задачи — файлы
    обвязки пропали с её диска, `git diff <база>` пуст. В клоне и в
    посторонней копии файлы обвязки на диске и после `git read-tree -mu
    HEAD` (повторное применение правил выписки).

    Ловит мутацию: `ensure` возвращается сразу по регистрации копии — полная
    копия остаётся с обвязкой; исключения пишутся в общий конфиг клона
    (`core.sparseCheckout` без `extensions.worktreeConfig`) — клон или
    посторонняя копия теряют обвязку; повторный `ensure` пересоздаёт копию
    или меняет набор файлов.
    """
    task, branch, wt = stand.ensured()
    before = on_disk(wt)
    _path, error = workspace.ensure(task, branch)
    assert error is None, stand.msg(error)
    assert on_disk(wt) == before, stand.msg("набор файлов сменился")

    other = stand.clone.parent / f"other-{stand.word()}"
    stand.cgit("worktree", "add", "-q", "-b", f"other-{stand.word()}",
               str(other), stand.base)
    task2, branch2 = stand.new_task()
    full = workspace.path(task2, EXT)
    stand.cgit("worktree", "add", "-q", "-b", branch2, str(full), stand.base)
    assert all((full / rel).exists() for rel in WRAPPER_FILES), stand.msg("полная копия")
    _path, error = workspace.ensure(task2, branch2)
    assert error is None, stand.msg(error)
    assert [rel for rel in WRAPPER_FILES if (full / rel).exists()] == [], \
        stand.msg(on_disk(full))
    assert stand.wgit(full, "diff", stand.base) == "", stand.msg("дифф")
    for root in (stand.clone, other):
        stand.wgit(root, "read-tree", "-mu", "HEAD")
        assert [rel for rel in WRAPPER_FILES if not (root / rel).exists()] == [], \
            stand.msg(f"{root}: {on_disk(root)}")


# ------------------------------------------------------------ AC-18

def test_ac18_ensure_follows_current_wrapper_list(stand):
    """`ensure` приводит исключения копии к текущему списку обвязки: добавленный элемент `agent_wrapper` пропадает с диска.

    Сценарий: запись без `agent_wrapper`; `ensure` — `harness/a.py` на
    диске, `CLAUDE.md` нет. В запись добавлено `agent_wrapper: [harness/]`;
    следующий `ensure` той же копии — `harness/a.py` на диске нет, `src/m.py`
    на месте.

    Ловит мутацию: исключения ставятся только при заведении копии — у
    заведённой копии новый элемент списка остаётся на диске.
    """
    stand.write_targets(wrapper=False)
    task, branch, wt = stand.ensured()
    assert (wt / "harness/a.py").exists(), stand.msg(on_disk(wt))
    assert not (wt / "CLAUDE.md").exists(), stand.msg(on_disk(wt))
    stand.write_targets(wrapper=True)
    _path, error = workspace.ensure(task, branch)
    assert error is None, stand.msg(error)
    assert not (wt / "harness/a.py").exists(), stand.msg(on_disk(wt))
    assert (wt / "src/m.py").exists(), stand.msg(on_disk(wt))


# ------------------------------------------------------------ AC-19

def test_ac19_ensure_removes_untracked_and_ignored_under_wrapper(stand):
    """Неотслеживаемый и игнорируемый файлы под путями обвязки после `ensure` пропадают, неотслеживаемый файл вне обвязки остаётся.

    Сценарий: копия AC-15; роль оставила `.claude/settings.local.json`
    (неотслеживаемый), `harness/run.log` (игнорируемый по `*.log`) и
    `src/new.py` (неотслеживаемый вне обвязки). Следующий `ensure`: первых
    двух на диске нет, `src/new.py` на месте с прежним текстом.

    Ловит мутацию: уборка только неотслеживаемых (`git clean` без `-x`) —
    игнорируемый `harness/run.log` остаётся; уборка всех неотслеживаемых
    файлов копии — пропал `src/new.py`; уборки нет — остался
    `.claude/settings.local.json`.
    """
    task, branch, wt = stand.ensured()
    left = {".claude/settings.local.json": "{}\n", "harness/run.log": "лог\n",
            "src/new.py": f"B = {stand.seed}\n"}
    for rel, text in left.items():
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(text, encoding="utf-8")
    _path, error = workspace.ensure(task, branch)
    assert error is None, stand.msg(error)
    assert not (wt / ".claude/settings.local.json").exists(), stand.msg(on_disk(wt))
    assert not (wt / "harness/run.log").exists(), stand.msg(on_disk(wt))
    assert (wt / "src/new.py").read_text(encoding="utf-8") == left["src/new.py"], \
        stand.msg(on_disk(wt))


# ------------------------------------------------------------ AC-20

def test_ac20_checkpoint_with_untracked_wrapper_file_commits_step(stand):
    """Чекпоинт шага не падает на неотслеживаемом файле под обвязкой, появившемся во время шага, и коммитит правку роли.

    Сценарий: копия AC-15; во время шага появился неотслеживаемый
    `.claude/settings.local.json`, роль правит `src/m.py`;
    `checkpoint.commit_success_checkpoint` за `developer` — в голове ветки
    задачи `src/m.py` с новым текстом.

    Ловит мутацию: путь под исключениями не отбит игнором рабочей копии —
    `git add -A` чекпоинта выходит кодом 1 на файле вне определения
    sparse-checkout, коммита нет, в ветке прежний `src/m.py`.
    """
    task, branch, wt = stand.ensured()
    assert [rel for rel in WRAPPER_FILES if (wt / rel).exists()] == [], \
        stand.msg("обвязка на диске после ensure")
    (wt / ".claude").mkdir(exist_ok=True)
    (wt / ".claude/settings.local.json").write_text("{}\n", encoding="utf-8")
    new_text = f"C = {stand.seed}\n"
    (wt / "src/m.py").write_text(new_text, encoding="utf-8")
    capture(checkpoint.commit_success_checkpoint, stand.conn, task, "developer")
    assert stand.cgit("show", f"{branch}:src/m.py") == new_text, stand.msg(
        [dict(r) for r in store.task_steps(stand.conn, task)])


# ------------------------------------------------------------ AC-21

def failing_sparse(real_run):
    def run(argv, *args, **kwargs):
        words = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
        if words and Path(words[0]).name == "git" and "sparse-checkout" in words:
            return subprocess.CompletedProcess(argv, 1, "", "песочница: сбой sparse-checkout")
        return real_run(argv, *args, **kwargs)
    return run


def test_ac21_sparse_failure_is_named_refusal_and_step_not_started(stand):
    """Сбой настройки исключений — непустая причина `ensure`, рабочий каталог шага роли в этой копии не выдаётся; без сбоя выдаётся.

    Сценарий: git-вызовы с `sparse-checkout` отвечают кодом 1. `ensure`
    новой задачи возвращает непустую причину; `runner.role_cwd` той же
    задачи (рабочий каталог шага: на его `OSError` `runner.cmd_run` пишет
    «рабочий каталог роли не создан» и агента не запускает) отказывает
    `OSError`, повторный `ensure` под тем же сбоем — снова причина.
    Контроль: вторая задача без подмены — `runner.role_cwd` отдаёт путь её
    рабочей копии.

    Ловит мутацию: сбой `git sparse-checkout` не проверяется — `ensure`
    отдаёт `None`, роль стартует в копии с обвязкой; повторный `ensure`
    зарегистрированной копии отдаёт `None`, не применяя исключений; причина
    пуста.
    """
    task, branch = stand.new_task()
    with mock.patch.object(subprocess, "run", failing_sparse(subprocess.run)):
        _path, error = workspace.ensure(task, branch)
        assert isinstance(error, str) and error.strip(), stand.msg(repr(error))
        with pytest.raises(OSError):
            runner.role_cwd(stand.conn, task, EXT, role="developer")
        _path, error = workspace.ensure(task, branch)
        assert isinstance(error, str) and error.strip(), stand.msg(repr(error))
    control, _branch = stand.new_task()
    path = runner.role_cwd(stand.conn, control, EXT, role="developer")
    assert Path(path).resolve() == workspace.path(control, EXT).resolve(), \
        stand.msg(path)


# ------------------------------------------------------------ AC-22

def test_ac22_artel_worktree_is_full(stand):
    """Рабочая копия задачи артели после `ensure` полная: `CLAUDE.md` пульта на месте, sparse-checkout не включён.

    Сценарий: в `main` клона артели закоммичен `CLAUDE.md` со случайным
    текстом и отправлен в `origin`; `ensure` задачи артели — файл на диске
    её копии с тем же текстом, `core.sparseCheckout` в копии не `true`.

    Ловит мутацию: исключения обвязки применяются к любому проекту — у
    артели `CLAUDE.md` нет на диске, sparse-checkout включён.
    """
    stand.sb.add_synced_origin()
    text = f"# пульт {stand.word()}\n"
    (stand.sb.root / "CLAUDE.md").write_text(text, encoding="utf-8")
    stand.sb.git("add", "CLAUDE.md")
    stand.sb.git("commit", "-q", "-m", "CLAUDE.md пульта")
    stand.sb.git("push", "-q", "origin", config.MAIN_BRANCH)
    task, branch = stand.new_task(ARTEL)
    wt, error = workspace.ensure(task, branch)
    assert error is None, stand.msg(error)
    assert (wt / "CLAUDE.md").read_text(encoding="utf-8") == text, stand.msg(on_disk(wt))
    sparse = stand.wgit(wt, "config", "--type=bool", "--default=false", "--get",
                        "core.sparseCheckout").strip()
    assert sparse == "false", stand.msg(sparse)
