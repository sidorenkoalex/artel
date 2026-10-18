"""Правило импортов долгоживущих файлов по профилю проекта — на пяти местах трёх рубежей.

Группа: долгоживущий
Красен до реализации: подполя `test_profile.long_lived_imports` нет — проверка записи внешнего проекта с ним отказывает «неизвестное подполе», профиль не прочитан, и ни одно из пяти мест не доходит до проверки долгоживущих файлов (AC-2…AC-5); у проекта без подполя текст признака «импорт вне перечня» не называет `test_profile.long_lived_imports` (AC-6); тесты артели (AC-1) держат сегодняшнее правило и тексты и зелены с рождения.

Стенд — настоящий git (`tests/sandbox.py::GitignoreCommittedRealGitSandbox`):
клон артели — корень песочницы с синхронным bare `origin`; учебный внешний
проект — `tests.sandbox.make_project_repo` со своим `origin` и профилем
тестов в `targets.yaml` песочницы (значения профиля артели плюс, по
сценарию, подполе `long_lived_imports`). Задачи заведены в БД пульта
напрямую (`store.insert_task`), рабочая копия кода — `workspace.ensure`.

Пять мест (SPEC, требование 5) и как сценарий до них доходит:
- гейт планки выхода из `tests_writing` — файл с группой «долгоживущий»
  лежит в планке; черновик переносится штатными чекпоинтами шага,
  затем `fsm.cmd_advance`; текст места — detail записи
  `TEST_GROUPS_ACTION`;
- гейт кодовой ветки выхода из `tests_writing` — планка без нарушений,
  долгоживущий файл задачи в `tests/` рабочей копии кода; текст места —
  detail записи `LONG_LIVED_ACTION`;
- `preflight` — проверка групп планки и проверка долгоживущих файлов
  кодовой ветки: тот же файл в планке и в рабочей копии одной задачи;
  текст места — строки раздела вывода, где стоит ошибка этого файла;
- `amend-tests` — задача в `in_dev` с локом планки и перечнем
  долгоживущего файла; Оператор переписывает этот файл в рабочей копии;
  текст места — текст отказа команды.

Чтобы каждое место заведомо отработало (а не отказало раньше или молча
прошло), у фикстурного долгоживущего файла метод без «Ловит мутацию: …» —
эта ошибка есть в тексте места при любом правиле импортов; предмет
проверки — только наличие или отсутствие признака «импорт вне перечня».
Имена проекта, файлов, зависимостей и посторонних модулей — от `random`;
зерно печатается и входит в текст провала.
"""
import contextlib
import hashlib
import io
import keyword
import os
import random
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (amend, checkpoint, config, fsm, github_adapter,
                          preflight, store, workspace)
from orchestrator.advance_gates import tests_writing as transition_gates
from scripts import guard
from tests.sandbox import (ARTEL_TEST_PROFILE, GitignoreCommittedRealGitSandbox,
                           make_project_repo)

SIGN = "импорт вне перечня"
# Пояснение признака у артели — литерал критерия AC-1, не значение из кода.
ARTEL_EXPLANATION = ("только стандартная библиотека, orchestrator, scripts, "
                     "tests — помощники из tests/sandbox.py")
FIELD = "long_lived_imports"
QUALIFIED_FIELD = "test_profile.long_lived_imports"
CLAIM_NEEDLE = "Ловит мутацию"
DEPENDENCIES = ("fastapi", "httpx", "sqlalchemy", "pydantic", "jwt", "dotenv")
ULID_LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
DOCS_REF_PREFIX = "refs/artifacts/"
HEADER = re.compile(r"^(\S.*?): (пройдена|отказ)$")

PLACE_PLANK = "tests_writing: гейт планки"
PLACE_CODE = "tests_writing: гейт кодовой ветки"
PLACE_PREFLIGHT_GROUPS = "preflight: проверка групп планки"
PLACE_PREFLIGHT_LONG = "preflight: долгоживущие файлы кодовой ветки"
PLACE_AMEND = "amend-tests"
TESTS_WRITING_PLACES = (PLACE_PLANK, PLACE_CODE)
PREFLIGHT_PLACES = (PLACE_PREFLIGHT_GROUPS, PLACE_PREFLIGHT_LONG)
ALL_PLACES = TESTS_WRITING_PLACES + PREFLIGHT_PLACES + (PLACE_AMEND,)


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(ULID_LETTERS) for _ in range(24))


def word(rng: random.Random, size: int = 7) -> str:
    """Идентификатор из строчных букв: не ключевое слово, не модуль
    стандартной библиотеки, не имя пакета пульта."""
    while True:
        value = "".join(rng.choice(LETTERS) for _ in range(size))
        if (not keyword.iskeyword(value) and value not in sys.stdlib_module_names
                and value not in ("orchestrator", "scripts", "tests")):
            return value


def spec_text(task_id: str) -> str:
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура правила импортов\n\n## Контекст\n\n"
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


def long_lived_source(name: str, imports: list, claim: bool) -> str:
    """Долгоживущий файл фикстуры с импортами `imports`; `claim=False` —
    метод без «Ловит мутацию: …» (ошибка, которую место печатает всегда)."""
    lines = ['"""Долгоживущая фикстура ' + name + ".", "",
             "Группа: " + guard.GROUP_LONG_LIVED,
             "Красен " + "до реализации: фикстура " + name + " ждёт кода.",
             '"""', "import random", "import unittest", *imports, "", "",
             "class FixtureLongLivedTest(unittest.TestCase):", "",
             f"    def test_ac1_{name}(self):",
             '        """Фикстурный метод.']
    if claim:
        lines += ["", "        Ловит " + "мутацию: фикстура " + name
                  + " — сумма перестаёт совпадать."]
    lines += ['        """', "        seed = random.randrange(1 << 30)",
              '        self.assertEqual(seed + 1, 1 + seed, f"зерно: {seed}")', ""]
    return "\n".join(lines)


def sections(output: str) -> list:
    """[(проверка, исход, [строки под заголовком])] вывода предпроверки."""
    found, current = [], None
    for raw in output.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line[0].isspace():
            if current is not None:
                current[2].append(line.strip())
            continue
        match = HEADER.match(line)
        current = [match.group(1), match.group(2), []] if match else None
        if current is not None:
            found.append(current)
    return found


class ImportRuleSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебные внешние проекты заводит сценарий."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        push = mock.patch.object(github_adapter, "ensure_head_in_origin",
                                 lambda *args, **kwargs: (True, ""))
        push.start()
        self.addCleanup(push.stop)
        self.add_synced_origin()
        self.clones = {config.DEFAULT_TARGET: self.root}
        self.conn = store.db()

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # --- проекты и входы ----------------------------------------------

    def external_project(self, imports) -> str:
        """Учебный внешний проект с профилем тестов; `imports` — значение
        `long_lived_imports` (список) либо `None` — подполя нет."""
        target = "proj" + word(self.rng, 6)
        self.clones[target] = make_project_repo(target)
        profile = ARTEL_TEST_PROFILE
        if imports is not None:
            profile += f"      {FIELD}: [{', '.join(imports)}]\n"
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + profile,
                                  encoding="utf-8")
        return target

    def dependency(self) -> str:
        return self.rng.choice(DEPENDENCIES)

    def foreign_module(self, *taken: str) -> str:
        """Верхнее имя импорта вне прежнего набора и вне `taken`."""
        while True:
            name = word(self.rng)
            if name not in taken:
                return name

    # --- задачи -------------------------------------------------------

    def new_task(self, target: str, state: str = "tests_writing"):
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-imports"
        store.insert_task(self.conn, tid, "Фикстура правила импортов", state,
                          branch, target, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, branch=branch, target=target, wt=Path(wt))
        t.docs = config.PROJECTS / target / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid), encoding="utf-8")
        return t

    def write_plank(self, t, files: dict) -> None:
        for name, text in files.items():
            (t.plank / name).write_text(text, encoding="utf-8")

    def long_lived_rel(self, t) -> str:
        return "/".join(("tests", f"test_{t.id.lower()}_{word(self.rng, 6)}.py"))

    def write_code_file(self, t, rel: str, text: str) -> None:
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def step_and_advance(self, t) -> tuple:
        """Черновик — в ссылку документов и кодовую ветку чекпоинтами шага,
        затем `advance`: (новые записи журнала, вывод advance)."""
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        before = len(store.task_steps(self.conn, t.id))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def refusal_detail(self, rows: list, action: str, output: str,
                       place: str) -> str:
        details = [r["detail"] or "" for r in rows if r["action"] == action]
        self.assertTrue(details, self.note(
            f"{place}: advance не записал «{action}» — место не отработало:\n"
            f"{[(r['action'], r['detail']) for r in rows]}\n{output}"))
        return details[-1]

    # --- места --------------------------------------------------------

    def run_plank_gate(self, target: str, source: str) -> str:
        t = self.new_task(target)
        self.write_plank(t, {f"test_{word(self.rng, 6)}.py": source})
        rows, output = self.step_and_advance(t)
        return self.refusal_detail(rows, transition_gates.TEST_GROUPS_ACTION,
                                   output, PLACE_PLANK)

    def run_code_gate(self, target: str, source: str) -> str:
        t = self.new_task(target)
        name = word(self.rng, 6)
        self.write_plank(t, {f"test_{name}.py": one_off_source(name)})
        self.write_code_file(t, self.long_lived_rel(t), source)
        rows, output = self.step_and_advance(t)
        return self.refusal_detail(rows, transition_gates.LONG_LIVED_ACTION,
                                   output, PLACE_CODE)

    def run_preflight(self, target: str, source: str) -> dict:
        """{место: строки раздела вывода с ошибками файла} обеих проверок
        предпроверки одной задачи."""
        t = self.new_task(target)
        name, plank_name = word(self.rng, 6), f"test_{word(self.rng, 6)}.py"
        self.write_plank(t, {f"test_{name}.py": one_off_source(name),
                             plank_name: source})
        rel = self.long_lived_rel(t)
        self.write_code_file(t, rel, source)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                preflight.cmd_preflight(t.id)
            except SystemExit as exc:
                err.write(f"\nSystemExit: {exc.code}")
        output = out.getvalue() + err.getvalue()
        found = {}
        for place, label in ((PLACE_PREFLIGHT_GROUPS, f"{PLANK_DIR}/{plank_name}"),
                             (PLACE_PREFLIGHT_LONG, rel)):
            owners = [lines for _check, _outcome, lines in sections(output)
                      if any(line.startswith(label + ":") for line in lines)]
            self.assertTrue(owners, self.note(
                f"{place}: в выводе нет раздела с ошибками {label} — место не "
                f"отработало:\n{output}"))
            found[place] = "\n".join(owners[0])
        return found

    def docs_head(self, t) -> str:
        return self.git("-C", str(self.clones[t.target]), "for-each-ref",
                        "--format=%(objectname)", DOCS_REF_PREFIX + t.id).strip()

    def run_amend(self, target: str, source: str) -> str:
        """Лок планки с перечнем чистого долгоживущего файла, затем правка
        Оператора — `source` в рабочей копии и `amend-tests`."""
        t = self.new_task(target, state="in_dev")
        rel = self.long_lived_rel(t)
        name = word(self.rng, 6)
        self.write_code_file(t, rel, long_lived_source(name, [], claim=True))
        self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "долгоживущий файл")
        digest = hashlib.sha256((t.wt / rel).read_bytes()).hexdigest()
        plank = word(self.rng, 6)
        self.write_plank(t, {
            f"test_{plank}.py": one_off_source(plank),
            guard.LONG_LIVED_MANIFEST_NAME:
                guard.render_long_lived_manifest({rel: digest})})
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        head = self.docs_head(t)
        self.assertTrue(head, self.note(f"{PLACE_AMEND}: ссылки документов нет"))
        store.update_task(self.conn, t.id, tests_locked_sha=head)
        store.record_fixation(self.conn, t.id)
        self.write_code_file(t, rel, source)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                amend.cmd_amend_tests(t.id, f"правка долгоживущего файла {self.seed}")
            except SystemExit as exc:
                buf.write(f"\n{exc.code}")
        text = buf.getvalue()
        self.assertIn(CLAIM_NEEDLE, text, self.note(
            f"{PLACE_AMEND}: отказ не дошёл до проверки долгоживущих файлов:\n{text}"))
        return text

    def place_texts(self, target: str, imports: list, places=ALL_PLACES) -> dict:
        """{место: текст места} для долгоживущего файла с `imports` и
        методом без заявки мутации."""
        source = long_lived_source(word(self.rng, 6), imports, claim=False)
        texts = {}
        order = list(places)
        self.rng.shuffle(order)
        preflight_texts = None
        for place in order:
            if place == PLACE_PLANK:
                texts[place] = self.run_plank_gate(target, source)
            elif place == PLACE_CODE:
                texts[place] = self.run_code_gate(target, source)
            elif place in PREFLIGHT_PLACES:
                if preflight_texts is None:
                    preflight_texts = self.run_preflight(target, source)
                texts[place] = preflight_texts[place]
            else:
                texts[place] = self.run_amend(target, source)
        for place, text in texts.items():
            self.assertIn(CLAIM_NEEDLE, text, self.note(
                f"{place}: в тексте места нет ошибки метода без заявки — "
                f"место не отработало:\n{text}"))
        return texts

    # --- утверждения --------------------------------------------------

    def assert_sign(self, texts: dict, label: str) -> None:
        for place, text in texts.items():
            with self.subTest(сценарий=label, место=place):
                self.assertIn(SIGN, text, self.note(
                    f"{label}, {place}: нет признака «{SIGN}»:\n{text}"))

    def assert_no_sign(self, texts: dict, label: str) -> None:
        for place, text in texts.items():
            with self.subTest(сценарий=label, место=place):
                self.assertNotIn(SIGN, text, self.note(
                    f"{label}, {place}: признак «{SIGN}» у разрешённых "
                    f"импортов:\n{text}"))


class ArtelRuleUnchangedTest(ImportRuleSandbox):

    def test_ac1_artel_foreign_import_refused_with_old_text(self):
        """Артель: импорт зависимости — «импорт вне перечня» с прежним пояснением, без `long_lived_imports`, на пяти местах.

        Сценарий: задача артели; долгоживущий файл несёт `import <имя>`
        (имя — из распространённых зависимостей, от зерна) и, отдельным
        сценарием, `from <имя> import <имя>` модуля от зерна. На каждом из
        пяти мест текст места несёт признак «импорт вне перечня» и литерал
        «только стандартная библиотека, orchestrator, scripts, tests —
        помощники из tests/sandbox.py» и не несёт `long_lived_imports`.

        Ловит мутацию: признак «артель/внешний проект» перевёрнут или не
        передан на одно из мест — у артели в тексте отказа появляется
        подсказка подполя `test_profile.long_lived_imports`; пояснение
        признака переписано для всех проектов — литерала нет; набор
        разрешённых имён расширен у артели — признака нет.
        """
        dependency = self.dependency()
        module = word(self.rng)
        cases = [(f"import {dependency}", [f"import {dependency}"]),
                 (f"from {module} import …", [f"from {module} import {word(self.rng)}"])]
        for label, imports in cases:
            texts = self.place_texts(config.DEFAULT_TARGET, imports)
            self.assert_sign(texts, label)
            for place, text in texts.items():
                with self.subTest(сценарий=label, место=place):
                    self.assertIn(ARTEL_EXPLANATION, text, self.note(
                        f"{label}, {place}: пояснение признака у артели "
                        f"изменилось:\n{text}"))
                    self.assertNotIn(FIELD, text, self.note(
                        f"{label}, {place}: отказ артели называет {FIELD}:\n{text}"))

    def test_ac1_artel_allowed_imports_pass(self):
        """Артель: импорты стандартной библиотеки, orchestrator, scripts, tests — без признака на пяти местах.

        Сценарий: задача артели; долгоживущий файл импортирует модули
        стандартной библиотеки (от зерна), `orchestrator`, `scripts` и
        `tests` разными формами (`import`, `from … import`). Ни на одном из
        пяти мест текст места не несёт признака «импорт вне перечня».

        Ловит мутацию: прежний набор у артели подменён перечнем профиля
        (пустым у артели) вместо объединения с ним — `orchestrator`,
        `scripts` или `tests` получают признак; стандартная библиотека
        выпала из набора.
        """
        stdlib = self.rng.sample(["json", "os.path", "collections", "textwrap",
                                  "itertools", "dataclasses"], 2)
        imports = [f"import {stdlib[0]}", f"from {stdlib[1]} import *",
                   "from orchestrator import config",
                   "import scripts.guard",
                   "from tests import sandbox"]
        self.rng.shuffle(imports)
        texts = self.place_texts(config.DEFAULT_TARGET, imports)
        self.assert_no_sign(texts, "разрешённые импорты артели")


class ExternalListedImportsTest(ImportRuleSandbox):

    def listed_texts(self, places) -> dict:
        dependency = self.dependency()
        target = self.external_project(["src", dependency])
        imports = [f"from src.app import {word(self.rng)}", f"import {dependency}"]
        self.rng.shuffle(imports)
        return self.place_texts(target, imports, places)

    def test_ac2_listed_imports_pass_tests_writing_gates(self):
        """Внешний проект с перечнем `[src, <зависимость>]`: в гейтах `tests_writing` нет признака.

        Сценарий: учебный внешний проект, `long_lived_imports` —
        `src` и зависимость (от зерна); долгоживущий файл несёт `from
        src.app import <имя>` и `import <зависимость>`. В detail отказа
        гейта планки и гейта кодовой ветки (отказ — из-за метода без
        заявки мутации) нет признака «импорт вне перечня».

        Ловит мутацию: перечень профиля не передан в узел проверки
        долгоживущих файлов из гейта планки или гейта кодовой ветки — там
        `from src.app` получает признак.
        """
        self.assert_no_sign(self.listed_texts(TESTS_WRITING_PLACES),
                            "перечень проекта")

    def test_ac3_listed_imports_pass_preflight(self):
        """Внешний проект с перечнем `[src, <зависимость>]`: в обеих проверках `preflight` нет признака.

        Сценарий: тот же проект и файл, что в AC-2; файл лежит и в планке,
        и в рабочей копии кода одной задачи. В строках раздела проверки
        групп планки и раздела проверки долгоживущих файлов кодовой ветки
        нет признака «импорт вне перечня».

        Ловит мутацию: `preflight` зовёт узел проверки без перечня проекта
        в одной из двух проверок (`_groups` или `_long_lived`) — там
        признак есть, предпроверка расходится с переходом.
        """
        self.assert_no_sign(self.listed_texts(PREFLIGHT_PLACES),
                            "перечень проекта")

    def test_ac4_listed_imports_pass_amend(self):
        """Внешний проект с перечнем `[src, <зависимость>]`: в отказе `amend-tests` нет признака.

        Сценарий: тот же проект и файл, что в AC-2; Оператор переписывает
        долгоживущий файл перечня лока этим текстом и зовёт
        `amend-tests`. Текст отказа (из-за метода без заявки мутации) не
        несёт признака «импорт вне перечня».

        Ловит мутацию: `amend-tests` зовёт узел проверки долгоживущих
        файлов без перечня проекта — правка получает признак на `from
        src.app`.
        """
        self.assert_no_sign(self.listed_texts((PLACE_AMEND,)),
                            "перечень проекта")


class ExternalUnlistedImportTest(ImportRuleSandbox):

    def test_ac5_unlisted_import_refused_naming_list(self):
        """Внешний проект с перечнем: импорт вне перечня — признак и перечень проекта в тексте на пяти местах.

        Сценарий: учебный внешний проект, `long_lived_imports` — `src` и
        зависимость (от зерна); долгоживущий файл несёт разрешённые
        `from src.app import …`, `import <зависимость>` и `import
        <модуль>` с верхним именем от зерна вне обоих наборов. На каждом
        из пяти мест текст места несёт признак «импорт вне перечня»,
        `long_lived_imports`, `src` и имя зависимости.

        Ловит мутацию: перечень проекта разрешает любой импорт (правило
        снято у внешнего проекта) — признака нет; текст отказа прежний
        текст артели без перечня проекта — нет `long_lived_imports` или
        его значения.
        """
        dependency = self.dependency()
        listed = ["src", dependency]
        self.rng.shuffle(listed)
        target = self.external_project(listed)
        foreign = self.foreign_module(*listed)
        imports = [f"from src.app import {word(self.rng)}",
                   f"import {dependency}", f"import {foreign}"]
        self.rng.shuffle(imports)
        texts = self.place_texts(target, imports)
        self.assert_sign(texts, f"import {foreign}")
        for place, text in texts.items():
            with self.subTest(место=place):
                for needle in (FIELD, *listed):
                    self.assertIn(needle, text, self.note(
                        f"{place}: текст отказа не называет «{needle}» "
                        f"перечня проекта:\n{text}"))

    def test_ac5_list_element_prefix_does_not_allow(self):
        """Перечень `["s"]` не разрешает `import sqlalchemy` — признак на пяти местах.

        Сценарий: учебный внешний проект с `long_lived_imports: [s]`;
        долгоживущий файл несёт `import sqlalchemy`. На каждом из пяти
        мест текст места несёт признак «импорт вне перечня».

        Ловит мутацию: верхнее имя сравнивается с элементом перечня по
        началу строки (`startswith`), а не на точное совпадение, —
        `sqlalchemy` разрешён элементом `s`, признака нет.
        """
        target = self.external_project(["s"])
        texts = self.place_texts(target, ["import sqlalchemy"])
        self.assert_sign(texts, "перечень [s], import sqlalchemy")


class ExternalWithoutListTest(ImportRuleSandbox):

    def test_ac6_no_or_empty_list_refused_naming_field(self):
        """Внешний проект без подполя и с пустым перечнем: `from src.app` — признак и подсказка подполя на пяти местах.

        Сценарий: два учебных внешних проекта — без `long_lived_imports` и
        с `long_lived_imports: []` (порядок от зерна); долгоживущий файл
        несёт `from src.app import <имя>`. На каждом из пяти мест у каждого
        проекта текст места несёт признак «импорт вне перечня» и
        `test_profile.long_lived_imports`.

        Ловит мутацию: у проекта без перечня правило снято (любой импорт
        разрешён) — признака нет; подсказка подполя выводится только при
        отсутствии подполя, а пустой список даёт прежний текст артели (или
        наоборот).
        """
        kinds = [("без подполя", None), ("пустой перечень", [])]
        self.rng.shuffle(kinds)
        for label, imports in kinds:
            target = self.external_project(imports)
            texts = self.place_texts(
                target, [f"from src.app import {word(self.rng)}"])
            self.assert_sign(texts, label)
            for place, text in texts.items():
                with self.subTest(сценарий=label, место=place):
                    self.assertIn(QUALIFIED_FIELD, text, self.note(
                        f"{label}, {place}: отказ не называет подполе "
                        f"{QUALIFIED_FIELD}:\n{text}"))


if __name__ == "__main__":
    unittest.main()
