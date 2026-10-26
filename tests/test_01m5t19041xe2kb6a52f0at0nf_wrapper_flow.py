"""Сквозной ход задачи внешнего проекта на рабочей копии без обвязки: планка (`plank-run`), `suite-run`, гейт зон на `in_dev -> verifying` и сборка диффа ревью.

Группа: долгоживущий
Красен до реализации: `workspace.ensure` выписывает рабочую копию внешнего проекта полностью — на диске после заведения лежат `CLAUDE.md`, `.claude/x`, `harness/a.py`, и предусловие «рабочая копия без обвязки» каждого сценария не выполняется.

Связка, которую держит файл: «`workspace.ensure` (копия без обвязки) —
команды пульта `plank-run` и `suite-run` (`artel.main`) — переход
`fsm.cmd_advance` — пакет ревьювера `review.review_package`» на настоящем
git (`tests.sandbox.RealGitSandbox`, фикстура `real_git`). Внешний проект —
клон с bare `origin` (`tests.sandbox.make_project_repo`); в `main` —
файлы обвязки песочницы AC-15, `src/m.py`, `sub/.mcp.json` и тест
`tests/test_m.py`, импортирующий `src/m.py`; запись — `agent_wrapper:
[harness/]` и профиль тестов `python3 -m pytest`. Тесты проекта и планка
гоняются настоящим pytest. Фоновый процесс `suite-run` (интерпретатор
`-c` с телом `suite_run.background`) исполняется в процессе теста тем же
публичным `suite_run.background` с аргументами процесса; отчёт забирается
`suite-run <id> --wait 0`. Draft MR форджа на выходе из `in_dev` подменён
(форджа в песочнице нет). Тексты — от зерна `random`; зерно печатается и
входит в текст провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
константа маркеров, формула `**/<каталог>/`, поле `agent_wrapper` в обоих
слоях и переносе, перечень проекта, отказ `knowledge`, зоны каталога
обвязки, источник подсветки, sparse-checkout рабочей копии с игнором и
уборкой путей обвязки, строка `doctor` — все методы зелёные.
"""
import contextlib
import io
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (artel, catalog, checkpoint, config, fsm,  # noqa: F401
                          github_adapter, idgen, review, store, suite_run,
                          workspace)
from tests.sandbox import artel_target_entry, capture, make_project_repo

EXT = "vnesh"
LETTERS = "abcdefghijkmnopqrstuvwxyz"
WRAPPER_FILES = ("CLAUDE.md", ".claude/x", "harness/a.py", "sub/CLAUDE.md",
                 "sub/AGENTS.md", "frontend/.claude/x")
ZONES_ACTION = "переход отклонён: гейт зон"
PROTECTED_ACTION = "переход отклонён: защищённый путь"

EXT_ENTRY = """  {name}:
    forge: github
    url: http://localhost/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    agent_wrapper: [harness/]
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура хода задачи

## Подход
Фикстура сценария.

## Шаги
1. Правка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура хода задачи

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

PLANK_TEXT = '''"""Планка фикстуры.

Группа: разовый
Зелёный с рождения: фикстура хода задачи.
"""


def test_ac1_{word}():
    """Фикстура: модуль проекта читается с диска рабочей копии.

    Зелёный с рождения: фикстура.
    """
    from pathlib import Path
    assert Path("src/m.py").read_text(encoding="utf-8") == {text!r}
'''


class Stand:
    """Внешний проект с обвязкой в дереве, профилем тестов и задачами."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.clone = make_project_repo(EXT)
        config.TARGETS.write_text("targets:\n" + artel_target_entry()
                                  + EXT_ENTRY.format(name=EXT), encoding="utf-8")
        self.m_text = f"VALUE = {self.seed}\n"
        files = {rel: f"{rel} {self.word()}\n" for rel in WRAPPER_FILES}
        files.update({
            "sub/.mcp.json": "{}\n", "src/__init__.py": "", "src/m.py": self.m_text,
            "tests/test_m.py": ("from src import m\n\n\n"
                                "def test_value():\n"
                                f"    assert m.VALUE == {self.seed}\n")})
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.cgit("add", "-A")
        self.cgit("commit", "-q", "-m", "проект с обвязкой")
        self.cgit("push", "-q", "origin", config.MAIN_BRANCH)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def cgit(self, *args: str) -> str:
        return self.sb.git("-C", str(self.clone), *args)

    def new_task(self, state: str, zones=None) -> tuple[str, str, Path]:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-flow"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, EXT, config.DEFAULT_BUDGET_USD)
        if zones:
            store.update_task(self.conn, task_id, zones=", ".join(zones))
        wt, error = workspace.ensure(task_id, branch)
        assert error is None, self.msg(f"рабочая копия не заведена: {error}")
        on_disk = [rel for rel in WRAPPER_FILES if (wt / rel).exists()]
        assert on_disk == [], self.msg(f"обвязка на диске рабочей копии: {on_disk}")
        return task_id, branch, wt

    def docs(self, task_id: str, files: dict, role: str) -> None:
        folder = config.PROJECTS / EXT / "tasks" / task_id
        for rel, text in files.items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_text(text, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, task_id, role)

    def cli(self, *argv: str) -> tuple[object, str]:
        """(код выхода — `None` при возврате, вывод) `artel.py <argv>`."""
        out = io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + (f"\n{code}" if isinstance(code, str) else "")

    def journal(self, task_id: str) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id)]


@pytest.fixture
def stand(real_git):
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield Stand(real_git)


def in_process_background(real_popen):
    """Фоновый процесс `suite-run` — в процессе теста тем же
    `suite_run.background`; прочие процессы — настоящие."""
    def popen(argv, *args, **kwargs):
        words = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
        if (len(words) > 3 and words[0] == sys.executable and words[1] == "-c"
                and "suite_run.background" in words[2]):
            suite_run.background(*words[3:])
            return mock.Mock(pid=2 ** 22 + 7)
        return real_popen(argv, *args, **kwargs)
    return popen


def test_ac25_plank_run_green_on_worktree_without_wrapper(stand):
    """`plank-run` задачи в `tests_writing` проходит зелёным на рабочей копии без обвязки.

    Сценарий: задача внешнего проекта в `tests_writing`, её копия без файлов
    обвязки; SPEC.md — в ссылке документов, черновик планки — файл
    `acceptance_tests/test_ac1_<слово>.py` в каталоге документов, читающий
    `src/m.py` с диска рабочей копии. `plank-run <id>` возвращается без
    ненулевого кода, вывод несёт «код выхода pytest: 0».

    Ловит мутацию: исключения обвязки ломают выкладку планки в рабочую копию
    (каталог выкладки планки попадает под шаблон исключения или выкладка
    отказывает на sparse-копии) — pytest не находит планку, код выхода не 0.
    """
    task, _branch, _wt = stand.new_task("tests_writing")
    stand.docs(task, {"SPEC.md": SPEC_TEXT.format(task=task)}, "test_author")
    folder = config.PROJECTS / EXT / "tasks" / task / "acceptance_tests"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"test_ac1_{stand.word()}.py").write_text(
        PLANK_TEXT.format(word=stand.word(), text=stand.m_text), encoding="utf-8")
    code, out = stand.cli("plank-run", task)
    assert code in (None, 0), stand.msg(out)
    assert "код выхода pytest: 0" in out, stand.msg(out)


def test_ac25_suite_run_zones_gate_and_review_diff(stand):
    """`suite-run`, гейт зон на `in_dev -> verifying` и сборка диффа ревью проходят на рабочей копии без обвязки; дифф не называет файлы обвязки удалёнными.

    Сценарий: задача внешнего проекта в `in_dev` с зонами `src/`, её копия
    без обвязки; правка `src/m.py` и `tests/test_m.py` закоммичена в ветку;
    PLAN.md (`ready`) и SPEC.md — в ссылке документов. (1) `suite-run <id>`
    запускает прогон, `suite-run <id> --wait 0` отдаёт отчёт «зелёный
    прогон» без ненулевого кода. (2) `advance` — ни отказа «гейт зон», ни
    отказа «защищённый путь». (3) Пакет ревьювера `review.review_package`
    несёт дифф `src/m.py`, в нём нет заголовка `diff --git` ни одного файла
    обвязки и нет «deleted file mode».

    Ловит мутацию: дерево прогона `suite-run` строится из рабочей копии,
    где исключённые пути читаются удалёнными, — прогон падает или не
    стартует; обвязка снята с диска удалением файлов, и удаление попало в
    ветку — гейт зон отказывает путям обвязки вне зон, дифф ревью называет
    их удалёнными.
    """
    task, branch, wt = stand.new_task("in_dev", zones=["src/", "tests/"])
    new_value = stand.seed + 1
    (wt / "src/m.py").write_text(f"VALUE = {new_value}\n", encoding="utf-8")
    (wt / "tests/test_m.py").write_text(
        "from src import m\n\n\ndef test_value():\n"
        f"    assert m.VALUE == {new_value}\n", encoding="utf-8")
    stand.sb.git("-C", str(wt), "add", "-A")
    stand.sb.git("-C", str(wt), "commit", "-q", "-m", f"{task}: правка")
    stand.docs(task, {"PLAN.md": PLAN_TEXT.format(task=task),
                      "SPEC.md": SPEC_TEXT.format(task=task)}, "developer")

    with mock.patch.object(subprocess, "Popen", in_process_background(subprocess.Popen)):
        code, out = stand.cli("suite-run", task)
    assert code in (None, 0), stand.msg(f"запуск suite-run: {out}")
    code, out = stand.cli("suite-run", task, "--wait", "0")
    assert code in (None, 0) and "зелёный прогон" in out, stand.msg(f"отчёт: {out}")

    with mock.patch.object(github_adapter, "ensure_draft_mr",
                           lambda conn, task_id, t: None):
        code, out = stand.cli("advance", task)
    held = [e for e in stand.journal(task)
            if e.startswith((ZONES_ACTION, PROTECTED_ACTION))]
    assert held == [], stand.msg("\n".join(stand.journal(task)) + "\n" + out)

    text = review.review_package(stand.conn, task, "Фикстура", branch)["text"]
    assert "diff --git a/src/m.py b/src/m.py" in text, stand.msg(text[-3000:])
    assert "deleted file mode" not in text, stand.msg(text[-3000:])
    for rel in WRAPPER_FILES:
        assert f"diff --git a/{rel} b/{rel}" not in text, stand.msg(rel)
