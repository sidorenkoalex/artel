"""Метка размера на каждом пути, где правила размера исполняются: выход из `tests_writing`, `amend-tests` (оба режима, прежнее правило и правило планки не по умолчанию), `preflight`.

Группа: долгоживущий
Красен до реализации: подполя `size_marks` нет — запись вымышленного проекта с ним отвергается («неизвестное подполе» у `test_profile`, «неизвестное поле» у компонента), профиль не прочитан, и каждый путь отказывает на записи, не доходя до долгоживущих файлов (проверка «путь отработал» краснеет первой в каждом тесте, в том числе в случае залоченного файла — его запись тоже несёт подполе).

Провалидировано временным стабом реализации (удалён, не закоммичен):
поле профиля и компонента, правила `size_findings`/`heavy_sandbox_names`,
параметры guard и передача флага, исходников песочниц рабочей копии и
`lint_base` на `amend.py:317` у вызывающих — все методы файла зелёные;
снятие `lint_base` на `amend.py:317` в любом из режимов краснит случай
залоченного файла.

Связка «запись проекта — профиль — дифф кодовой ветки — FSM/команда»:
стенд — настоящий git (`tests.sandbox.RealGitSandbox` фикстурой
`real_git`, плюс закоммиченный `.gitignore` и синхронный `origin`);
вымышленные проекты — `tests.sandbox.make_project_repo` со своим `origin` и
записью в `targets.yaml` песочницы. Задачи — `store.insert_task`, рабочая
копия кода — `workspace.ensure`.

Пути и как сценарий до них доходит (по образцу
`tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py` и
`tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py`):
- выход из `tests_writing` — долгоживущий файл в рабочей копии кода,
  чекпоинты шага, `fsm.cmd_advance`; текст — detail записи отказа;
- `amend-tests` (прежнее правило) — задача `in_dev` с локом и перечнем
  чистого файла; новый долгоживущий файл — в рабочей копии (режим рабочей
  копии) либо коммитом кодовой ветки (`--from-branch`);
- `amend-tests` с правилом планки не по умолчанию — запись `components:`
  из компонента Vitest (правило планки не умолчание) и компонента pytest
  с шаблоном `long_lived`; компонент задачи выбран её зоной;
- `preflight` — проверка долгоживущих файлов кодовой ветки.

Чтобы каждый путь заведомо отработал, у метода фикстурного файла нет
«Ловит мутацию: …» — эта ошибка есть в тексте пути при любом правиле
размера; предмет проверки — только строки «размер —». Имена проектов,
файлов и методов — от `random`; зерно печатается и входит в текст провала.
"""
import contextlib
import hashlib
import io
import os
import random
import re
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (amend, checkpoint, config, fsm, github_adapter,
                          preflight, project_profile, store, workspace)
from orchestrator.advance_gates import tests_writing as transition_gates
from scripts import guard
from tests.sandbox import ARTEL_TEST_PROFILE, make_project_repo

pytestmark = pytest.mark.size("medium")

NO_MARK = "нет метки размера"
SIZE_PREFIX = "размер —"
CLAIM_NEEDLE = "Ловит мутацию"
FIELD_LINE = "size_marks: required"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
DOCS_REF_PREFIX = "refs/artifacts/"
GITIGNORE = "__pycache__/\n*.pyc\n*.log\n.artel/\n"
HEADER = re.compile(r"^(\S.*?): (пройдена|отказ)$")
SANDBOX_SOURCE = ("import unittest\n\n\n"
                  "class TmpRootTest(unittest.TestCase):\n    pass\n\n\n"
                  "class RealGitSandbox(TmpRootTest):\n    pass\n")
ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    components:
"""

PLACE_TESTS_WRITING = "tests_writing: долгоживущие файлы кодовой ветки"
PLACE_AMEND_WORKTREE = "amend-tests: рабочая копия"
PLACE_AMEND_BRANCH = "amend-tests --from-branch"
PLACE_RULE_WORKTREE = "amend-tests с правилом планки: рабочая копия"
PLACE_RULE_BRANCH = "amend-tests с правилом планки: --from-branch"
PLACE_PREFLIGHT = "preflight: долгоживущие файлы кодовой ветки"


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def pieces(text: str) -> list:
    """Строки отказа: записи журнала соединены «; », вывод — переводами строк."""
    return [p.strip() for p in re.split(r"; |\n", text) if p.strip()]


def size_lines(text: str) -> list:
    return [p for p in pieces(text) if SIZE_PREFIX in p]


def spec_text(task_id: str) -> str:
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура метки размера\n\n## Контекст\n\n"
            "## Требования\n\n## Критерии приёмки\n\n"
            "AC-1. Критерий фикстуры.\n\n## Не входит\n")


def one_off_source(name: str) -> str:
    """Разовый файл планки без нарушений, покрывает AC-1 фикстуры."""
    return "\n".join([
        '"""Разовая фикстура ' + name + ".", "",
        "Группа: " + guard.GROUP_ONE_OFF,
        "Красен " + "до реализации: фикстура " + name + " ждёт кода.",
        '"""', "import unittest", "", "",
        "class FixturePlankTest(unittest.TestCase):", "",
        f"    def test_ac1_{name}(self):",
        '        """Фикстурный метод."""',
        "        self.assertEqual(2 + 2, 4)", ""])


def long_lived_source(name: str, *, mark: str | None = None, claim: bool = False,
                      base: str | None = None, tail: str = "") -> str:
    """Долгоживущий файл фикстуры: `mark` — размер метки модуля (`None` — без
    метки), `claim=False` — метод без «Ловит мутацию: …», `base` — класс
    `tests.sandbox`, которому наследует класс файла."""
    lines = ['"""Долгоживущая фикстура ' + name + ".", "",
             "Группа: " + guard.GROUP_LONG_LIVED,
             "Красен " + "до реализации: фикстура " + name + " ждёт кода.",
             '"""', "import random", "import unittest", ""]
    if base is not None:
        lines += [f"from tests.sandbox import {base}", ""]
    if mark is not None:
        lines += ["import pytest", "",
                  f"pytestmark = pytest.mark.size(\"{mark}\")", ""]
    lines += ["", f"class FixtureLongLivedTest({base or 'unittest.TestCase'}):",
              "", f"    def test_ac1_{name}(self):", '        """Фикстурный метод.']
    if claim:
        lines += ["", "        Ловит " + "мутацию: фикстура " + name
                  + " — сумма перестаёт совпадать."]
    lines += ['        """', "        seed = random.randrange(1 << 30)",
              '        self.assertEqual(seed + 1, 1 + seed, f"зерно: {seed}")', ""]
    return "\n".join(lines) + tail


class Stand:
    """Клон артели с `origin`; вымышленные проекты и задачи заводит сценарий."""

    def __init__(self, box, seed: int):
        self.box = box
        self.seed = seed
        self.rng = random.Random(seed)
        self.used: set = set()
        self.conn = store.db()
        self.clones = {config.DEFAULT_TARGET: box.root}
        fake = Path(tempfile.mkdtemp(prefix="artel-size-")).resolve()
        box.addCleanup(shutil.rmtree, fake, True)
        self.installer = fake / "install"
        self.installer.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.installer.chmod(0o755)

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args: str) -> str:
        return self.box.git(*args)

    # --- проекты --------------------------------------------------------

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    def commit_to_project(self, clone: Path, files: dict) -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def profile_project(self, size_marks: bool, sandbox: bool = False) -> str:
        """Проект с записью `test_profile` на pytest (значения профиля
        артели), с подполем `size_marks: required` или без него;
        `sandbox` — в дереве проекта лежит `tests/sandbox.py` с
        `RealGitSandbox`."""
        target = "p" + self.word()
        clone = make_project_repo(target)
        profile = ARTEL_TEST_PROFILE
        if size_marks:
            profile += f"      {FIELD_LINE}\n"
        self.append_entry(profile)
        if sandbox:
            self.commit_to_project(clone, {"tests/sandbox.py": SANDBOX_SOURCE})
        self.clones[target] = clone
        return target

    def components_project(self, size_marks: bool) -> str:
        """Проект `components:` — компонент Vitest (правило планки не
        умолчание) и компонент pytest с шаблоном `long_lived`
        `tests/test_<id>_<name>.py`, путями `^back/` и, по сценарию,
        `size_marks: required`."""
        target = "c" + self.word()
        version = next(f"{major}.0.0" for major, flags in
                       project_profile.VITEST_VERSION_FLAGS.items()
                       if flags.require_assertions)
        web = {"command": flow(project_profile.VITEST_BASE_ARGV),
               "report": "pult-vitest",
               "report_args": flow(["--reporter=default",
                                    "--reporter={pult_reporter}",
                                    "--outputFile={path}"]),
               "failure_errors": flow(["AssertionError"]),
               "select": flow([f"--sel{self.word()}", "{tests}"]),
               "install": flow([str(self.installer)]),
               "tests": flow(["frontend/src/**/*.test.jsx"]),
               "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>",
               "weakening_scope": flow(["frontend/src/**"]),
               "mutation_claim_scope": flow(["frontend/src/**"]),
               "paths": flow(["^frontend/"]),
               "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx"}
        py = {"command": flow(["python3", "-m", "pytest"]),
              "tests": flow(["tests/test_*.py"]),
              "weakening_scope": flow(["tests/**/*.py"]),
              "mutation_claim_scope": flow(["tests/test_*.py"]),
              "paths": flow(["^back/"]),
              "long_lived": "tests/test_<id>_<name>.py"}
        if size_marks:
            py["size_marks"] = "required"
        lines = [ENTRY_HEAD.format(name=target), "      web:\n"]
        lines += [f"        {key}: {value}\n" for key, value in web.items()]
        lines += ["        tools:\n", f'          vitest: "{version}"\n',
                  "      py:\n"]
        lines += [f"        {key}: {value}\n" for key, value in py.items()]
        self.append_entry("".join(lines))
        clone = make_project_repo(target)
        self.commit_to_project(clone, {
            "package.json": '{"name": "web"}\n',
            "frontend/src/app.jsx": "export const app = 1;\n",
            "back/app.py": "VALUE = 1\n"})
        self.clones[target] = clone
        return target

    # --- задачи ---------------------------------------------------------

    def new_task(self, target: str, state: str = "tests_writing",
                 zones: str | None = None):
        tid = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        branch = f"task/{tid.lower()}-size"
        store.insert_task(self.conn, tid, "Фикстура метки размера", state,
                          branch, target, 25.0)
        if zones is not None:
            store.update_task(self.conn, tid, zones=zones)
        wt, error = workspace.ensure(tid, branch)
        t = SimpleNamespace(id=tid, branch=branch, target=target,
                            wt=Path(wt) if wt else None, error=error)
        t.docs = config.PROJECTS / target / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid), encoding="utf-8")
        return t

    def write_plank(self, t, files: dict) -> None:
        t.plank.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (t.plank / name).write_text(text, encoding="utf-8")

    def long_lived_rel(self, t) -> str:
        return "/".join(("tests", f"test_{t.id.lower()}_{self.word()}.py"))

    def write_code_file(self, t, rel: str, text: str) -> None:
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit_code(self, t, rel: str, text: str, message: str) -> None:
        self.write_code_file(t, rel, text)
        self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)

    def docs_head(self, t) -> str:
        return self.git("-C", str(self.clones[t.target]), "for-each-ref",
                        "--format=%(objectname)", DOCS_REF_PREFIX + t.id).strip()

    @staticmethod
    def captured(fn, *args, **kwargs) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        return buf.getvalue()

    # --- пути -----------------------------------------------------------

    def run_tests_writing(self, target: str, source: str) -> tuple:
        """(текст отказа «долгоживущие файлы tests/», путь файла): файл
        `source` — новый долгоживущий файл рабочей копии кода."""
        t = self.new_task(target)
        name = self.word()
        self.write_plank(t, {f"test_{name}.py": one_off_source(name)})
        rel = self.long_lived_rel(t)
        self.write_code_file(t, rel, source)
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        before = len(store.task_steps(self.conn, t.id))
        output = self.captured(fsm.cmd_advance, t.id)
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        details = [r["detail"] or "" for r in rows
                   if r["action"] == transition_gates.LONG_LIVED_ACTION]
        return (details[-1] if details else
                output + "\n" + repr([(r["action"], r["detail"]) for r in rows])), rel

    def run_preflight(self, target: str, source: str) -> tuple:
        """(строки раздела предпроверки с ошибками файла либо весь вывод,
        путь файла)."""
        t = self.new_task(target)
        name = self.word()
        self.write_plank(t, {f"test_{name}.py": one_off_source(name)})
        rel = self.long_lived_rel(t)
        self.write_code_file(t, rel, source)
        output = self.captured(preflight.cmd_preflight, t.id)
        current, owned = None, []
        for raw in output.splitlines():
            line = raw.rstrip()
            if not line:
                continue
            if not line[0].isspace():
                match = HEADER.match(line)
                current = [] if match else None
                if current is not None:
                    owned.append(current)
                continue
            if current is not None:
                current.append(line.strip())
        for lines in owned:
            if any(line.startswith(rel + ":") for line in lines):
                return "\n".join(lines), rel
        return output, rel

    def locked_task(self, target: str, locked_text: str,
                    zones: str | None = None):
        """(задача, путь залоченного файла): задача `in_dev` с локом планки
        и перечнем закоммиченного долгоживущего файла `locked_text`."""
        t = self.new_task(target, state="in_dev", zones=zones)
        rel = self.long_lived_rel(t)
        self.commit_code(t, rel, locked_text, "долгоживущий файл")
        digest = hashlib.sha256((t.wt / rel).read_bytes()).hexdigest()
        plank = self.word()
        self.write_plank(t, {
            f"test_{plank}.py": one_off_source(plank),
            guard.LONG_LIVED_MANIFEST_NAME:
                guard.render_long_lived_manifest({rel: digest})})
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        store.update_task(self.conn, t.id, tests_locked_sha=self.docs_head(t))
        store.record_fixation(self.conn, t.id)
        return t, rel

    def amend(self, t, from_branch: bool) -> str:
        return self.captured(amend.cmd_amend_tests, t.id,
                             f"правка {self.seed}", from_branch=from_branch)

    def run_amend_new_file(self, target: str, source: str, from_branch: bool,
                           zones: str | None = None) -> tuple:
        """(текст `amend-tests`, путь нового файла): лок с чистым файлом
        (метка `small`, заявка мутации), затем новый долгоживущий файл
        `source` — в рабочей копии либо коммитом кодовой ветки."""
        clean = long_lived_source(self.word(), mark="small", claim=True)
        t, _locked = self.locked_task(target, clean, zones)
        rel = self.long_lived_rel(t)
        if from_branch:
            self.commit_code(t, rel, source, "новый долгоживущий файл")
        else:
            self.write_code_file(t, rel, source)
        return self.amend(t, from_branch), rel

    def run_amend_locked_edit(self, target: str, locked_text: str,
                              from_branch: bool, zones: str | None = None) -> tuple:
        """(текст `amend-tests`, путь файла): лок файла `locked_text`,
        затем правка того же файла (дописан комментарий) — в рабочей
        копии либо коммитом кодовой ветки."""
        t, rel = self.locked_task(target, locked_text, zones)
        edited = locked_text + f"# правка {self.word()}\n"
        if from_branch:
            self.commit_code(t, rel, edited, "правка долгоживущего файла")
        else:
            self.write_code_file(t, rel, edited)
        return self.amend(t, from_branch), rel


@pytest.fixture
def stand(real_git):
    """Стенд сценария над `real_git`: `.gitignore`, синхронный `origin`,
    подмены отправки головы и окружения роли."""
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    (real_git.root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    real_git.git("add", ".gitignore")
    real_git.git("commit", "-q", "-m", "gitignore")
    with mock.patch.dict(os.environ), mock.patch.object(
            github_adapter, "ensure_head_in_origin",
            lambda *args, **kwargs: (True, "")):
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        real_git.add_synced_origin()
        yield Stand(real_git, seed)


def run_place(stand, place: str, size_marks: bool, source: str) -> tuple:
    """(текст пути, путь файла) для нового долгоживущего файла `source` у
    вымышленного проекта с подполем `size_marks` или без него."""
    if place == PLACE_TESTS_WRITING:
        return stand.run_tests_writing(stand.profile_project(size_marks), source)
    if place == PLACE_PREFLIGHT:
        return stand.run_preflight(stand.profile_project(size_marks), source)
    if place in (PLACE_AMEND_WORKTREE, PLACE_AMEND_BRANCH):
        return stand.run_amend_new_file(stand.profile_project(size_marks), source,
                                        place == PLACE_AMEND_BRANCH)
    return stand.run_amend_new_file(stand.components_project(size_marks), source,
                                    place == PLACE_RULE_BRANCH,
                                    zones="back/app.py")


@pytest.mark.parametrize("place", [PLACE_TESTS_WRITING, PLACE_AMEND_WORKTREE,
                                   PLACE_AMEND_BRANCH, PLACE_RULE_WORKTREE,
                                   PLACE_RULE_BRANCH, PLACE_PREFLIGHT])
def test_ac6_missing_mark_refused_only_with_field(stand, place):
    """Новый долгоживущий файл без метки у проекта с `size_marks: required` — отказ пути с именем файла и «нет метки размера»; у проекта без подполя тот же файл — без строк «размер —».

    Сценарий: путь из перечня AC-6 (выход из `tests_writing`;
    `amend-tests` прежнего правила в режиме рабочей копии и
    `--from-branch`; `amend-tests` с правилом планки не по умолчанию —
    запись `components:` — в обоих режимах; `preflight`). Сначала проект с
    подполем: в тексте пути есть ошибка метода без заявки (путь
    отработал) и строка «размер —» с путём файла и «нет метки размера».
    Затем новый проект без подполя с тем же файлом: ошибка метода без
    заявки есть, строк «размер —» нет.

    Ловит мутацию: вызывающий пути не передаёт `size_marks=True` из
    профиля (флаг не читается на этом пути, `amend.py:317` оставлен без
    флага) — отказа нет; флаг передаётся безусловно — у проекта без
    подполя «нет метки размера»; подполе компонента не переносится в
    профиль компонента — путь `components:` без отказа.
    """
    source = long_lived_source(stand.word(), claim=False)
    text, rel = run_place(stand, place, True, source)
    assert CLAIM_NEEDLE in text, stand.note(
        f"{place}: путь не дошёл до проверки долгоживущих файлов:\n{text}")
    assert any(rel in p and NO_MARK in p for p in size_lines(text)), stand.note(
        f"{place}: нет отказа «{NO_MARK}» с {rel}:\n{text}")
    text, rel = run_place(stand, place, False, source)
    assert CLAIM_NEEDLE in text, stand.note(
        f"{place}, без подполя: путь не дошёл до проверки:\n{text}")
    assert size_lines(text) == [], stand.note(
        f"{place}, без подполя: строки размера:\n{text}")


@pytest.mark.parametrize("from_branch", [False, True])
def test_ac6_rule_path_locked_without_mark_not_refused(stand, from_branch):
    """Путь `amend-tests` с правилом планки не по умолчанию: залоченный текст без метки и правка того же файла без метки — без строк «размер —».

    Сценарий: запись `components:` с `size_marks: required` у компонента
    pytest; задача `in_dev` с локом долгоживущего файла без метки (метод
    без заявки); правка файла (дописан комментарий) в рабочей копии либо
    коммитом кодовой ветки, `amend-tests` соответствующего режима. В
    тексте есть ошибка метода без заявки (путь отработал), строк «размер
    —» нет.

    Ловит мутацию: на пути `amend.py:317` `lint_base` не передаётся в
    одном из режимов (рабочая копия — голова кодовой ветки до правки,
    `--from-branch` — залоченные тексты по суммам перечня) — залоченный до
    правила файл получает «нет метки размера».
    """
    target = stand.components_project(True)
    locked = long_lived_source(stand.word(), claim=False)
    text, rel = stand.run_amend_locked_edit(target, locked, from_branch,
                                            zones="back/app.py")
    assert CLAIM_NEEDLE in text, stand.note(
        f"путь не дошёл до проверки долгоживущих файлов:\n{text}")
    assert rel in text, stand.note(f"отказ не называет {rel}:\n{text}")
    assert size_lines(text) == [], stand.note(f"строки размера:\n{text}")


def test_ac6_small_file_with_project_sandbox_refused(stand):
    """Выход из `tests_writing`: малый файл, класс которого наследует `RealGitSandbox` из `tests/sandbox.py` дерева проекта, — отказ с именем базы; у проекта без файлов песочниц тот же файл — без строк «размер —».

    Сценарий: проект с `size_marks: required`, в дереве которого
    закоммичен `tests/sandbox.py` с `RealGitSandbox`; новый долгоживущий
    файл с `size("small")` и классом `(RealGitSandbox)`. Отказ несёт
    строку «размер —» с путём файла и `RealGitSandbox`. Второй проект с
    тем же подполем без `tests/sandbox.py` (перечень песочниц пуст): тот
    же файл — путь отработал (ошибка метода без заявки), строк «размер
    —» нет.

    Ловит мутацию: вызывающий не читает исходники песочниц из дерева
    проверки (передаёт пустой перечень или читает дерево пульта) — у
    первого проекта отказа нет; перечень жёсткий и не зависит от дерева —
    у второго проекта отказ.
    """
    source = long_lived_source(stand.word(), mark="small", claim=False,
                               base="RealGitSandbox")
    text, rel = stand.run_tests_writing(
        stand.profile_project(True, sandbox=True), source)
    assert CLAIM_NEEDLE in text, stand.note(
        f"путь не дошёл до проверки долгоживущих файлов:\n{text}")
    assert any(rel in p and "RealGitSandbox" in p for p in size_lines(text)), (
        stand.note(f"нет отказа с RealGitSandbox у {rel}:\n{text}"))
    text, rel = stand.run_tests_writing(stand.profile_project(True), source)
    assert CLAIM_NEEDLE in text, stand.note(
        f"без песочниц: путь не дошёл до проверки:\n{text}")
    assert size_lines(text) == [], stand.note(
        f"без песочниц: строки размера:\n{text}")
