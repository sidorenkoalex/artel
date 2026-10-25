"""Обвязка внешнего проекта в местах сверки перечня защищённых путей: гейт зон на выходе из `in_dev`, гейт диффа на мерже, подсветка Draft MR, зоны ТЗ, SPEC и `guard.protected_zones`.

Группа: долгоживущий
Красен до реализации: перечень защищённых путей внешнего проекта — один его `no_paths`, обвязка в него не входит — правка `CLAUDE.md`, `sub/AGENTS.md`, `.claude/x`, `frontend/.claude/rules/x.md` и пути `agent_wrapper` проходит гейт зон и мерж без отказа (AC-10, AC-11), подсветка Draft MR не называет `CLAUDE.md`, а источник перечня — «no_paths проекта … в targets.yaml» без обвязки (AC-12), зоны `.claude`/`sub/.claude/` не отказывают (AC-13); строка источника у артели и зона `docs/` держат прежнее поведение.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`repo_context.protected_paths` — места сверки (`fsm.cmd_advance`,
`fsm.cmd_approve`, `github_adapter.ensure_draft_mr`, `catalog.cmd_new`,
`guard.protected_zones`)». Песочница — настоящий git
(`tests.sandbox.RealGitSandbox`, фикстура `real_git`): корень — клон артели,
внешний проект — клон с bare `origin` (`tests.sandbox.make_project_repo`),
его запись — `forge: github`, `no_paths` из случайного каталога `zn…/`, по
сценарию — `agent_wrapper: [harness/]`. Рабочая копия задачи —
`workspace.ensure`; код задачи пишется в неё и коммитится
`git add --sparse -f -- <пути>` (путь обвязки на диске рабочей копии без
обвязки лежит вне определения sparse-checkout и может быть отбит игнором
копии — правку обвязки сценарий вносит в ветку явно). PLAN.md и SPEC.md — в
ссылке документов
автокоммитом шага `checkpoint.commit_step_artifacts`.

Подменены внешние проверки, которых в песочнице нет: Draft MR форджа на
выходе из `in_dev` и на мерже, цвет CI (`ci.branch_status`,
`ci.main_line_status`), полный прогон набора (`acceptance.run_full_suite`),
фордж `gh` подсветки — шпион, отвечающий успехом и запоминающий аргументы.
Имена каталогов и файлов — от зерна `random`; зерно печатается и входит в
текст каждого провала.

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
import re
import subprocess
from unittest import mock

import pytest

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, repo_context, store, workspace)
from scripts import guard
from tests.sandbox import (artel_target_entry, capture, capture_new_task_id,
                           make_project_repo)

EXT = "vnesh"
ARTEL = config.DEFAULT_TARGET
LETTERS = "abcdefghijkmnopqrstuvwxyz"
PROTECTED_ACTION = "переход отклонён: защищённый путь"
HIGHLIGHT = re.compile(r"затрагивает защищённые пути: (.+?) \((.*)\)\.\s*$", re.S)

EXT_ENTRY = """  {name}:
    forge: github
    url: http://localhost/{name}
    base: main
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
{extra}"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура обвязки

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
{zones}---

# SPEC: фикстура обвязки

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

TZ_TEXT = """# ТЗ: фикстура зон {word}

Требуется: правка по зонам.

Зоны: {zones}.
"""


class Stand:
    """Сценарий над песочницей `RealGitSandbox`: проект, задачи, вызовы."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.gh_calls: list = []
        sb.add_synced_origin()
        self.clone = make_project_repo(EXT)
        self.no_path = f"zn{self.word()}/"
        self.write_targets(wrapper=False)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def write_targets(self, wrapper: bool) -> None:
        extra = "    agent_wrapper: [harness/]\n" if wrapper else ""
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + EXT_ENTRY.format(name=EXT, no_paths=self.no_path, extra=extra),
            encoding="utf-8")

    def spy_gh(self, *args, **kwargs):
        self.gh_calls.append(list(args))
        return subprocess.CompletedProcess(list(args), 0,
                                           f"http://localhost/{EXT}/pull/1\n", "")

    def new_task(self, target: str, state: str, code: dict, zones=None) -> str:
        """Задача `target` в `state`: код `code` закоммичен в ветку задачи из
        её рабочей копии, PLAN.md и SPEC.md — в ссылке документов."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-wrap"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, target, config.DEFAULT_BUDGET_USD)
        if zones:
            store.update_task(self.conn, task_id, zones=", ".join(zones))
        wt, error = workspace.ensure(task_id, branch)
        assert error is None, self.msg(f"рабочая копия не заведена: {error}")
        for rel, text in code.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.sb.git("-C", str(wt), "add", "--sparse", "-f", "--", *code)
        self.sb.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        docs = config.PROJECTS / target / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=task_id),
                                      encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id, zones=""),
                                      encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, task_id, "developer")
        return task_id

    def code(self) -> tuple[str, str]:
        zone = f"kod{self.word()}/"
        return zone, f"{zone}{self.word()}.py"

    @staticmethod
    def run(fn, *args, **kwargs) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def journal(self, task_id: str) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id)]

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]


@pytest.fixture
def stand(real_git):
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield Stand(real_git)


# ------------------------------------------------------------ AC-10

def in_dev_refusal(stand: Stand, rel: str) -> tuple[list[str], str]:
    """(записи отказа «защищённый путь» после `advance`, контекст) задачи
    внешнего проекта, чей код трогает `rel` (покрыт зонами)."""
    zone, code = stand.code()
    task = stand.new_task(EXT, "in_dev", {code: "A = 1\n", rel: "x\n"},
                          zones=[zone, rel])
    with mock.patch.object(github_adapter, "ensure_draft_mr",
                           lambda conn, task_id, t: None):
        out = stand.run(fsm.cmd_advance, task)
    rows = [r for r in stand.journal(task) if r.startswith(PROTECTED_ACTION)]
    return rows, stand.msg(f"{rel}: " + "\n".join(stand.journal(task))
                           + "\n--- вывод:\n" + out)


def test_ac10_wrapper_paths_refused_on_in_dev_exit(stand):
    """Правка пути обвязки в ветке внешнего проекта — отказ «защищённый путь» на `in_dev -> verifying`, как у пути `no_paths`.

    Сценарий: запись проекта без `agent_wrapper`. Задачи, чей код трогает
    путь под `no_paths` (контроль), `CLAUDE.md`, `sub/AGENTS.md`, `.claude/x`
    и `frontend/.claude/rules/x.md` (каждый покрыт зонами задачи): у каждой
    после `advance` есть запись «переход отклонён: защищённый путь»,
    называющая этот путь. Затем в запись добавлено `agent_wrapper:
    [harness/]` — задача, трогающая `harness/x.py`, получает тот же отказ.

    Ловит мутацию: перечень внешнего проекта — один `no_paths` — пути
    обвязки проходят гейт; `**/.claude/` сверяется по последнему компоненту
    — `.claude/x` и `frontend/.claude/rules/x.md` проходят; `agent_wrapper`
    не входит в перечень — `harness/x.py` проходит.
    """
    for rel in (f"{stand.no_path}{stand.word()}.md", "CLAUDE.md", "sub/AGENTS.md",
                ".claude/x", "frontend/.claude/rules/x.md"):
        rows, note = in_dev_refusal(stand, rel)
        assert rows and rel in rows[0], note
    stand.write_targets(wrapper=True)
    rows, note = in_dev_refusal(stand, "harness/x.py")
    assert rows and "harness/x.py" in rows[0], note


# ------------------------------------------------------------ AC-11

def test_ac11_wrapper_paths_escalate_on_merge_gate(stand):
    """Путь обвязки в диффе задачи внешнего проекта на гейте мержа даёт ту же эскалацию, что путь `no_paths`.

    Сценарий: задачи на `merge_gate`, чей код трогает путь под `no_paths`
    (контроль), `CLAUDE.md`, а после добавления `agent_wrapper: [harness/]`
    в запись — `harness/x.py`. После `approve` каждая задача в `escalated`,
    журнал несёт «защищённый путь <путь> — правит только Оператор коммитом
    в main».

    Ловит мутацию: гейт диффа на мерже сверяет `no_paths` записи напрямую,
    а не `protected_paths` — `CLAUDE.md` мержится; `agent_wrapper` не входит
    в перечень — `harness/x.py` мержится.
    """
    green = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "", "зелёный (тест)")
    patches = (
        mock.patch.object(acceptance, "run_full_suite",
                          lambda root, *a, **k: (True, "1 passed (тест)")),
        mock.patch.object(ci, "branch_status",
                          lambda branch, repo=None: (True, "зелёный (тест)")),
        mock.patch.object(ci, "main_line_status", lambda sha, repo=None: green),
        mock.patch.object(github_adapter, "ensure_draft_mr",
                          lambda conn, task_id, t: None),
        mock.patch.object(github_adapter, "undraft_mr",
                          lambda conn, task_id, t: None))
    with contextlib.ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        capture(catalog.cmd_init)
        cases = [(f"{stand.no_path}{stand.word()}.cfg", False),
                 ("CLAUDE.md", False), ("harness/x.py", True)]
        for rel, wrapper in cases:
            stand.write_targets(wrapper=wrapper)
            _zone, code = stand.code()
            task = stand.new_task(EXT, "merge_gate",
                                  {code: f"A = {stand.seed}\n", rel: "x\n"})
            out = stand.run(fsm.cmd_approve, task)
            note = stand.msg(f"{rel}: " + "\n".join(stand.journal(task))
                             + "\n--- вывод:\n" + out)
            assert stand.state(task) == "escalated", note
            expected = f"защищённый путь {rel} — правит только Оператор коммитом в main"
            assert [e for e in stand.journal(task) if expected in e], note


# ------------------------------------------------------------ AC-12

def highlight(stand: Stand, target: str, files: list[str]) -> tuple[list, list, str]:
    """(пути подсветки, источники перечня, контекст) черновика MR задачи
    `target` с кодом `files`."""
    task = stand.new_task(target, "in_dev", {rel: f"{rel} {stand.seed}\n"
                                             for rel in files})
    stand.gh_calls.clear()
    with mock.patch.object(github_adapter.ci, "gh", stand.spy_gh):
        github_adapter.ensure_draft_mr(stand.conn, task,
                                       store.get_task(stand.conn, task))
    comments = [args[args.index("--body") + 1] for args in stand.gh_calls
                if args[:2] == ["pr", "comment"] and "--body" in args]
    paths, sources = [], []
    for body in comments:
        match = HIGHLIGHT.search(body)
        assert match, stand.msg(f"комментарий без перечня: {body}")
        paths.extend(match.group(1).split(", "))
        sources.append(match.group(2))
    return paths, sources, stand.msg(f"{target}: {stand.gh_calls}; журнал: "
                                     f"{stand.journal(task)}")


def test_ac12_draft_mr_names_wrapper_and_its_source(stand):
    """Подсветка Draft MR внешнего проекта называет `CLAUDE.md` защищённым, а источник перечня — `no_paths` и обвязку без « (»; у артели источник прежний.

    Сценарий: дифф задачи внешнего проекта — файл кода и `CLAUDE.md`. После
    `ensure_draft_mr` комментарий `gh pr comment` перечисляет `CLAUDE.md`;
    текст источника в скобках называет `no_paths` и обвязку (слово
    «обвязка», имя поля `agent_wrapper` или константы
    `AGENT_WRAPPER_MARKERS`) и не содержит « (». Задача артели с правкой
    `skills/<файл>` — источник ровно `config.PROTECTED_PATHS`.

    Ловит мутацию: подсветка берёт `no_paths` записи вместо
    `protected_paths` — `CLAUDE.md` не назван; источник оставлен «no_paths
    проекта … в targets.yaml» — обвязка не названа; источник со скобкой
    внутри — « (» в тексте; у артели источник сменён.
    """
    _zone, code = stand.code()
    paths, sources, note = highlight(stand, EXT, [code, "CLAUDE.md"])
    assert "CLAUDE.md" in paths, note
    assert sources, note
    for source in sources:
        assert " (" not in source, note
        assert "no_paths" in source, note
        assert any(word in source for word in
                   ("обвязк", "agent_wrapper", "AGENT_WRAPPER_MARKERS")), note
    _zone, code = stand.code()
    rel = f"skills/{stand.word()}.md"
    paths, sources, note = highlight(stand, ARTEL, [code, rel])
    assert rel in paths, note
    assert sources and all(s == "config.PROTECTED_PATHS" for s in sources), note


# ------------------------------------------------------------ AC-13

WRAPPER_ZONES = ("sub/.claude/", "sub/.claude", ".claude/", ".claude")


def refusal_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if guard.PROTECTED_ZONE_REFUSAL in line]


def test_ac13_tz_zones_under_wrapper_dir_refused(stand):
    """«Зоны:» ТЗ на `new` внешнего проекта: каталог обвязки с `/` и без, корневой и вложенный, — отказ «защищённый путь только приложением»; `docs/` — нет.

    Сценарий: для каждой зоны критерия — свой ТЗ со строкой «Зоны: <зона>,
    src/.» и `catalog.cmd_new` для внешнего проекта; вывод несёт отказ,
    в строке которого названа зона. ТЗ с зоной `docs/` отказа не даёт.

    Ловит мутацию: зоны сверяются формулой путей файлов — `.claude` и
    `sub/.claude` без `/` проходят; перечень зон на `new` — один `no_paths`.
    """
    capture(catalog.cmd_init)
    for zone in (*WRAPPER_ZONES, "docs/"):
        tz = config.ROOT / ".artel" / f"tz-{stand.word()}.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text(TZ_TEXT.format(word=stand.word(), zones=f"{zone}, src/"),
                      encoding="utf-8")
        out = stand.run(catalog.cmd_new, f"Фикстура {stand.word()}", str(tz),
                        target=EXT)
        lines = refusal_lines(out)
        if zone == "docs/":
            assert lines == [], stand.msg(f"{zone}: {out}")
        else:
            assert [line for line in lines if zone in line], stand.msg(f"{zone}: {out}")


def test_ac13_spec_gate_zones_under_wrapper_dir_refused(stand):
    """`zones:` SPEC на `approve` гейта SPEC внешнего проекта: каталог обвязки отказывает, `docs/` — нет.

    Сценарий: для каждой зоны критерия — задача внешнего проекта
    (`catalog.cmd_new`), SPEC.md с `zones: <зона>, src/` в ссылке документов,
    задача на `spec_gate`, `approve`. В выводе или журнале — отказ
    «защищённый путь только приложением», называющий зону; задача осталась
    на `spec_gate`. Зона `docs/` такого отказа не даёт.

    Ловит мутацию: гейт SPEC сверяет зоны формулой путей файлов — `.claude`
    проходит; сверка по `no_paths` записи — ни одна зона обвязки не
    отказывает.
    """
    capture(catalog.cmd_init)
    for zone in (*WRAPPER_ZONES, "docs/"):
        _out, task = capture_new_task_id(
            lambda: catalog.cmd_new(f"Фикстура {stand.word()}", target=EXT))
        docs = config.PROJECTS / EXT / "tasks" / task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(
            task=task, zones=f"zones: {zone}, src/\n"), encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, stand.conn, task, "analyst")
        store.update_task(stand.conn, task, state="spec_gate")
        out = stand.run(fsm.cmd_approve, task)
        text = out + "\n" + "\n".join(stand.journal(task))
        lines = refusal_lines(text)
        if zone == "docs/":
            assert lines == [], stand.msg(f"{zone}: {text}")
        else:
            assert [line for line in lines if zone in line], stand.msg(f"{zone}: {text}")
            assert stand.state(task) == "spec_gate", stand.msg(f"{zone}: {text}")


def test_ac13_guard_protected_zones_with_project_perimeter(stand):
    """`guard.protected_zones` с перечнем внешнего проекта возвращает зоны каталога обвязки и не возвращает `docs/`.

    Сценарий: зоны критерия и `docs/` в случайном порядке; перечень —
    `repo_context.protected_paths` контекста проекта.

    Ловит мутацию: `protected_zones` сверяет зоны формулой путей файлов —
    `.claude` и `sub/.claude` (без вложения) не возвращены.
    """
    zones = [*WRAPPER_ZONES, "docs/"]
    stand.rng.shuffle(zones)
    perimeter = repo_context.protected_paths(repo_context.resolve(EXT))
    assert guard.protected_zones(zones, perimeter) == sorted(WRAPPER_ZONES), \
        stand.msg(f"{zones}, перечень {perimeter}")
