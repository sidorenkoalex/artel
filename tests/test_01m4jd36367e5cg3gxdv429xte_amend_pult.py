"""`amend-tests` проводит правку планки, импортирующей помощник пульта `_pult.py`.

Группа: долгоживущий

Красен до реализации: amend-tests не выкладывает помощник `_pult.py` рядом с планкой и не исключает его из сверки — прогон правки падает на «No module named '_pult'» (AC-1, AC-2, AC-9), простой путь без сухого сбора пропускает неимпортируемую планку с маркером красноты (AC-1, мутация), выложенный гейтом помощник читается правкой и уходит в ссылку документов (AC-4, AC-5); AC-2 (мутация), AC-3 и AC-8 держат существующее поведение и зелёные.

Сценарий на настоящем git: пульт — `self.root`; задача артели заводится
`catalog.cmd_new`, её ссылка документов `refs/artifacts/<id>` в git пульта
несёт SPEC.md с одним критерием и планку из двух файлов: один делает
`from _pult import TASK_ID` и сверяет значение с id задачи, второй —
обычный. Путь с долгоживущими файлами: в кодовой ветке задачи закоммичен
долгоживущий файл `tests/test_<id>_fixture.py`, а планка лока несёт его
перечень сумм. `tests_locked_sha` стоит на коммите планки, фиксация
заведена `store.record_fixation`. Оператор кладёт правку в каталог задачи
рабочей копии кода и зовёт `amend.cmd_amend_tests`.

Мутация «помощник не выложен» (AC-1, AC-2) разыгрывается подменой имени,
под которым узел выкладки `orchestrator/acceptance.py` кладёт помощник
(`acceptance.PLANK_HELPER_NAME`): помощник ложится под чужим именем, и
`from _pult import …` планки его не находит — ровно то, что видит планка
без выкладки. Вид правки, правимый файл и путь команды — из `random`, зерно
печатается и входит в текст провала.
"""
import contextlib
import hashlib
import io
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, amend, catalog, config, fsm, projects,
                          store, workspace)
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox

REF_PREFIX = "refs/artifacts/"
HELPER = "_pult.py"
NO_MODULE = "No module named '_pult'"
PULT_PLANK = "test_plank.py"
OTHER_PLANK = "test_other.py"

SPEC_TEMPLATE = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: <название задачи>

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстурный критерий песочницы.

## Не входит
"""

GREEN_MARKER = "Зелёный с рождения: фикстура песочницы."

# Файл планки, импортирующий помощник пульта: значение `TASK_ID` помощника
# сверяется с id задачи, так что помощник чужой выкладки тоже красит прогон.
PULT_PLANK_TEMPLATE = '''"""Фикстура планки, импортирующей помощник пульта.

Группа: разовый
MARKER_LINE
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import TASK_ID  # noqa: E402


class FixturePultPlankTest(unittest.TestCase):

    def test_ac1_fixture_reads_helper(self):
        """Фикстурный метод: помощник выложен для этой задачи."""
        self.assertEqual(TASK_ID, "EXPECTED_ID", "FAIL_NOTE")
'''

OTHER_PLANK_TEXT = '''"""Второй файл планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixtureOtherTest(unittest.TestCase):

    def test_ac1_fixture_other(self):
        """Фикстурный метод второго файла."""
        self.assertEqual(2 + 2, 4)
'''

LONG_LIVED_TEXT = '''"""Фикстура долгоживущего файла песочницы.

Группа: долгоживущий
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_ac1_long_fixture(self):
        """Фикстурный метод долгоживущего файла.

        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, 2, f"зерно: {seed}")
'''

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

TITLES = ("Правка планки", "Помощник пульта", "Фиксация правки")
PATHS = ("простой", "долгоживущие файлы")


class AmendPultSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели с рабочей копией кода; планку лока заводит сам тест
    (`lock_plank`), правку планки кладёт он же."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(SPEC_TEMPLATE, encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.task_id = catalog.cmd_new(self.rng.choice(TITLES),
                                           target=config.DEFAULT_TARGET)
        self.branch = store.get_task(store.db(), self.task_id)["branch"]
        self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.task_dir = self.wt / "tasks" / self.task_id
        self.tests_dir = self.task_dir / "acceptance_tests"
        self.long_rel = f"tests/test_{self.task_id.lower()}_fixture.py"
        self.locked_files: dict[str, str] = {}

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def run_cmd(self, fn, *args, **kwargs) -> tuple[str, bool]:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        refused = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    refused = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), refused

    def ref(self) -> str:
        return REF_PREFIX + self.task_id

    def head(self) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        self.ref()).strip()

    def locked(self) -> str:
        return store.get_task(store.db(), self.task_id)["tests_locked_sha"]

    def task_rel(self, *parts: str) -> str:
        """Путь от корня репозитория внутри каталога задачи."""
        return "/".join(("tasks", self.task_id, *parts))

    def pult_plank(self, marker: str = GREEN_MARKER, expected: str = "",
                   fail_note: str = "") -> str:
        return (PULT_PLANK_TEMPLATE.replace("MARKER_LINE", marker)
                .replace("EXPECTED_ID", expected or self.task_id)
                .replace("FAIL_NOTE", fail_note or "помощник чужой задачи"))

    def commit_docs(self, files: dict, message: str) -> None:
        """Коммит `files` (путь внутри каталога задачи -> текст) в ссылку
        документов: отдельная рабочая копия на её голове и `update-ref`."""
        old = self.head()
        self.assertTrue(old, self.note(f"ссылки {self.ref()} нет"))
        scratch = Path(tempfile.mkdtemp(prefix="artel-docs-copy-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        copy = scratch / "copy"
        self.git("worktree", "add", "-q", "--detach", str(copy), old)
        try:
            for rel, text in files.items():
                path = copy / "tasks" / self.task_id / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            self.git("-C", str(copy), "add", "-A")
            self.git("-C", str(copy), "commit", "-q", "-m",
                     f"{self.task_id}: {message}")
            new = self.git("-C", str(copy), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(copy))
        self.git("update-ref", self.ref(), new, old)

    def commit_code(self, rel: str, text: str, message: str) -> None:
        """Коммит файла `rel` в кодовую ветку задачи из её рабочей копии."""
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("-C", str(self.wt), "add", "--", rel)
        self.git("-C", str(self.wt), "commit", "-q", "-m", message)

    def manifest_text(self) -> str:
        digest = hashlib.sha256((self.wt / self.long_rel).read_bytes()).hexdigest()
        return guard.render_long_lived_manifest({self.long_rel: digest})

    def lock_plank(self, long_lived: bool, pult_text: str | None = None) -> None:
        """Планка из двух файлов (один импортирует `_pult`) в ссылке
        документов и лок на её коммите; `long_lived` — ещё долгоживущий
        файл в кодовой ветке и перечень его суммы в планке лока."""
        self.locked_files = {
            "acceptance_tests/" + PULT_PLANK: pult_text or self.pult_plank(),
            "acceptance_tests/" + OTHER_PLANK: OTHER_PLANK_TEXT,
        }
        if long_lived:
            self.commit_code(self.long_rel, LONG_LIVED_TEXT,
                             f"{self.task_id}: долгоживущий файл")
            self.locked_files["acceptance_tests/"
                              + guard.LONG_LIVED_MANIFEST_NAME] = self.manifest_text()
        self.commit_docs({"SPEC.md": SPEC_TEMPLATE.replace("TASK_ID", self.task_id),
                          **self.locked_files}, "планка")
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.head())
        store.record_fixation(store.db(), self.task_id)
        self.locked_before = self.locked()
        self.head_before = self.head()

    def lay_out_locked(self) -> None:
        """Планка лока целиком на диске каталога задачи рабочей копии."""
        for rel, text in self.locked_files.items():
            path = self.task_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def lay_out_by_gate(self) -> None:
        """Планка лока на диске узлом выкладки гейтов — вместе с помощником."""
        acceptance.materialize_from_branch(self.task_id, self.ref(), self.wt)
        self.assertTrue((self.tests_dir / HELPER).is_file(), self.note(
            "предпосылка: узел выкладки не положил помощник"))

    def operator_edit_one(self, by_gate: bool = False) -> str:
        """Планка лока на диске (`by_gate` — выложена узлом гейтов, с
        помощником) и правка ровно одного её файла (какого и какая — из
        `random`); возвращает имя правленого файла."""
        if by_gate:
            self.lay_out_by_gate()
        else:
            self.lay_out_locked()
        name = self.rng.choice((PULT_PLANK, OTHER_PLANK))
        path = self.tests_dir / name
        text = path.read_text(encoding="utf-8")
        if self.rng.random() < 0.5:
            text += f"\n# правка Оператора {self.rng.randrange(1 << 20)}\n"
        else:
            text = text.replace("Фикстурный метод",
                                f"Фикстурный метод, правка {self.seed},", 1)
        path.write_text(text, encoding="utf-8")
        self.edited = (name, text)
        return name

    def amend(self, **kwargs) -> tuple[str, bool]:
        return self.run_cmd(amend.cmd_amend_tests, self.task_id,
                            f"правка планки {self.seed}", **kwargs)

    def amend_details(self) -> list[str]:
        return [s["detail"] or "" for s in store.task_steps(store.db(), self.task_id)
                if amend.AMEND_ACTION in s["action"]]

    def ref_task_paths(self) -> list[str]:
        """Пути дерева головы ссылки документов внутри каталога задачи."""
        prefix = self.task_rel() + "/"
        return [p for p in self.git("ls-tree", "-r", "--name-only",
                                    self.head()).splitlines()
                if p.startswith(prefix)]

    def without_helper(self):
        """Мутация «помощник не выложен»: узел выкладки кладёт его под
        чужим именем."""
        return mock.patch.object(acceptance, "PLANK_HELPER_NAME",
                                 f"_pult_off_{self.rng.randrange(1000)}.py")

    # --- общие проверки -------------------------------------------------

    def assert_amended_green(self, out: str, refused: bool, path: str) -> None:
        """Правка прошла: лок на новой голове ссылки, правленый файл в ней
        побайтно, прогон планки в журнале правки — без падений и ошибок."""
        self.assertFalse(refused, self.note(f"правка ({path}) отклонена:\n{out}"))
        self.assertNotIn(NO_MODULE, out, self.note(f"импорт помощника ({path})"))
        self.assertNotEqual(self.locked(), self.locked_before, self.note(
            f"правка ({path}) не зафиксирована:\n{out}"))
        self.assertEqual(self.locked(), self.head(), self.note(
            "лок не на голове ссылки документов"))
        name, text = self.edited
        shown = self.git("show", f"{self.head()}:{self.task_rel('acceptance_tests', name)}")
        self.assertEqual(shown, text, self.note(f"правка {name} не в ссылке документов"))
        details = self.amend_details()
        self.assertEqual(len(details), 1, self.note(f"событий правки: {details}"))
        summary = details[0].split("приёмочные тесты:", 1)[-1]
        self.assertRegex(summary, r"\d+ passed", self.note(
            f"прогон правки ({path}) не зелёный: {summary}"))
        self.assertNotRegex(summary, r"error|failed", self.note(
            f"прогон правки ({path}) с падениями: {summary}"))

    def assert_refused_untouched(self, out: str, refused: bool, what: str) -> None:
        self.assertTrue(refused, self.note(f"{what} принята:\n{out}"))
        self.assertEqual(self.locked(), self.locked_before, self.note(
            f"лок сдвинут ({what})"))
        self.assertEqual(self.head(), self.head_before, self.note(
            f"ссылка документов изменена ({what}):\n{out}"))
        self.assertEqual(self.amend_details(), [], self.note(
            f"событие правки планки записано ({what})"))


class SimplePathTest(AmendPultSandbox):

    def test_ac1_simple_path_amends_plank_importing_pult(self):
        """Простой путь: правка одного файла планки, импортирующей `_pult`, проходит.

        Сценарий: задача без долгоживущих файлов; планка лока — файл с
        `from _pult import TASK_ID` (маркер «Зелёный с рождения») и второй
        обычный файл. Оператор выкладывает планку в рабочую копию и правит
        один файл (какой — случайно). `amend-tests` завершается без отказа,
        в выводе нет «No module named '_pult'», лок — на новой голове ссылки
        документов, правленый файл в ней побайтно, итог прогона в журнале
        правки — «N passed» без ошибок и падений.

        Ловит мутацию: простой путь по-прежнему гоняет планку без выложенного
        помощника — прогон даёт ошибку импорта, и итог прогона в журнале
        правки несёт «error» вместо «passed» (или правка отклонена).
        """
        self.lock_plank(long_lived=False)
        self.operator_edit_one()

        out, refused = self.amend()

        self.assert_amended_green(out, refused, "простой путь")

    def test_ac1_simple_path_without_helper_refuses_on_import(self):
        """Простой путь без выкладки помощника: та же правка отказывает с ошибкой импорта `_pult`.

        Сценарий: тот же, что в соседнем методе, но узел выкладки кладёт
        помощник под чужим именем (мутация «помощник не выложен»).
        `amend-tests` отказывает ненулевым кодом, текст несёт «No module
        named '_pult'», лок и голова ссылки документов прежние, события
        правки планки нет.

        Ловит мутацию: простой путь не делает сухого сбора, а красный
        прогон планки с маркером «Зелёный с рождения» пропускает — правка
        с неимпортируемой планкой фиксируется в ссылке документов.
        """
        self.lock_plank(long_lived=False)
        self.operator_edit_one()

        with self.without_helper():
            out, refused = self.amend()

        self.assert_refused_untouched(out, refused, "правка без помощника")
        self.assertIn(NO_MODULE, out, self.note("отказ не называет ошибку импорта"))


class LongLivedPathTest(AmendPultSandbox):

    def test_ac2_long_lived_path_amends_plank_importing_pult(self):
        """Путь с долгоживущими файлами: правка одного файла планки, импортирующей `_pult`, проходит.

        Сценарий: в кодовой ветке задачи — долгоживущий файл, планка лока
        несёт перечень его суммы; правка — тот же один файл планки, что в
        AC-1 (долгоживущий файл не правится). `amend-tests` завершается без
        отказа, в выводе нет «No module named '_pult'», лок — на новой
        голове ссылки документов, правленый файл в ней побайтно, итог
        прогона в журнале правки — «N passed» без ошибок и падений.

        Ловит мутацию: сухой сбор `_collect_and_run` идёт по каталогу
        планки без помощника — сбор отказывает «No module named '_pult'», и
        правка не фиксируется.
        """
        self.lock_plank(long_lived=True)
        self.operator_edit_one()

        out, refused = self.amend()

        self.assert_amended_green(out, refused, "долгоживущие файлы")

    def test_ac2_long_lived_path_without_helper_refuses_on_import(self):
        """Путь с долгоживущими файлами без выкладки помощника: отказ с ошибкой импорта `_pult`.

        Сценарий: тот же, что в соседнем методе, но узел выкладки кладёт
        помощник под чужим именем. `amend-tests` отказывает ненулевым
        кодом, текст несёт «No module named '_pult'», лок и голова ссылки
        документов прежние, события правки планки нет.

        Ловит мутацию: отказ сухого сбора снят или ослаблен до
        предупреждения — неимпортируемая планка фиксируется в ссылке
        документов.
        """
        self.lock_plank(long_lived=True)
        self.operator_edit_one()

        with self.without_helper():
            out, refused = self.amend()

        self.assert_refused_untouched(out, refused, "правка без помощника")
        self.assertIn(NO_MODULE, out, self.note("отказ не называет ошибку импорта"))


class FromBranchTest(AmendPultSandbox):

    def test_ac3_from_branch_collects_and_runs_plank_importing_pult(self):
        """`--from-branch`: сбор и прогон планки, импортирующей `_pult`, проходят без ошибки импорта.

        Сценарий: задача с долгоживущим файлом и origin; после лока голова
        ссылки документов несёт правку файла планки с `from _pult import`,
        а голова кодовой ветки — закоммиченную правку долгоживущего файла
        (расхождение с перечнем лока — путь, на котором `--from-branch`
        собирает и гоняет планку в рабочей копии). `amend-tests
        --from-branch` завершается без отказа, в выводе нет «No module
        named '_pult'», лок сдвинут на голову ссылки документов, событие
        правки планки записано ровно одно.

        Ловит мутацию: выкладка `--from-branch` переведена на запись одних
        файлов ссылки без помощника (как `_materialize_tests_if_missing`) —
        сбор отказывает «No module named '_pult'», лок не сдвигается.
        """
        self.add_synced_origin()
        self.lock_plank(long_lived=True)
        edited = self.pult_plank() + f"\n# правка в ветке {self.seed}\n"
        self.commit_docs({"acceptance_tests/" + PULT_PLANK: edited},
                         "правка планки в ветке")
        # Автокоммит шага пульта перефиксирует ссылку документов.
        store.record_fixation(store.db(), self.task_id)
        self.commit_code(self.long_rel,
                         LONG_LIVED_TEXT + f"\n# правка кода {self.seed}\n",
                         f"{self.task_id}: правка долгоживущего файла")

        out, refused = self.amend(from_branch=True)

        self.assertFalse(refused, self.note(f"--from-branch отклонён:\n{out}"))
        self.assertNotIn(NO_MODULE, out, self.note("ошибка импорта помощника"))
        self.assertNotEqual(self.locked(), self.locked_before, self.note(
            f"лок не сдвинут:\n{out}"))
        self.assertEqual(self.locked(), self.head(), self.note(
            "лок не на голове ссылки документов"))
        self.assertEqual(len(self.amend_details()), 1, self.note(
            "событие правки планки не одно"))


class HelperNeverInDocsRefTest(AmendPultSandbox):

    def test_ac4_amended_docs_ref_has_no_helper(self):
        """После успешной правки дерево ссылки документов задачи не несёт `_pult.py`.

        Сценарий: планка лока выложена в рабочую копию узлом гейтов
        `acceptance.materialize_from_branch` (с помощником `_pult.py`), и
        Оператор правит один её файл; правка в простом пути или в пути с
        долгоживущими файлами (случайно) проходит. В дереве головы ссылки документов внутри каталога задачи
        нет ни одного файла с именем `_pult.py` — ни в `acceptance_tests/`,
        ни глубже, ни рядом; выход из `tests_writing` (`fsm.cmd_advance`
        задачи, поставленной в `tests_writing`) не пишет в журнал отказа
        «посторонние файлы планки» с именем помощника.

        Ловит мутацию: помощник выкладывается, но не исключается из снимка
        правки (`ls-files --others` его видит) — `_commit_plank` уносит
        `_pult.py` в ссылку документов, и гейт `tests_writing` отказывает
        на зарезервированном имени.
        """
        path = self.rng.choice(PATHS)
        self.lock_plank(long_lived=path != "простой")
        self.operator_edit_one(by_gate=True)

        out, refused = self.amend()

        self.assertFalse(refused, self.note(f"правка ({path}) отклонена:\n{out}"))
        self.assertNotEqual(self.locked(), self.locked_before, self.note(
            f"правка ({path}) не зафиксирована:\n{out}"))
        helpers = [p for p in self.ref_task_paths() if p.rsplit("/", 1)[-1] == HELPER]
        self.assertEqual(helpers, [], self.note(
            f"помощник в ссылке документов после правки ({path})"))

        store.update_task(store.db(), self.task_id, state="tests_writing")
        steps_before = len(store.task_steps(store.db(), self.task_id))
        gate_out, _ = self.run_cmd(fsm.cmd_advance, self.task_id)
        new_steps = store.task_steps(store.db(), self.task_id)[steps_before:]
        reserved = [f"{s['action']}: {s['detail']}" for s in new_steps
                    if HELPER in (s["detail"] or "") and "отклонён" in s["action"]]
        self.assertEqual(reserved, [], self.note(
            f"гейт tests_writing отказал на имени помощника:\n{gate_out}"))


class HelperOnlyIsNoChangeTest(AmendPultSandbox):

    def test_ac5_laid_out_plank_with_helper_is_no_change(self):
        """Выложенная гейтом планка, совпадающая со ссылкой, плюс `_pult.py` — отказ «нет изменений».

        Сценарий: планка лока (простой путь или с долгоживущими файлами —
        случайно) выложена в рабочую копию узлом гейтов
        `acceptance.materialize_from_branch` — с помощником `_pult.py`,
        других правок нет. `amend-tests` отказывает ненулевым кодом с «нет
        изменений», лок и голова ссылки документов прежние, события правки
        планки нет.

        Ловит мутацию: сверка «есть ли правка» сравнивает снимок каталога
        вместе с помощником — `_pult.py` читается новым файлом, и команда
        фиксирует его в ссылке документов вместо отказа.
        """
        path = self.rng.choice(PATHS)
        self.lock_plank(long_lived=path != "простой")
        self.lay_out_by_gate()

        out, refused = self.amend()

        self.assert_refused_untouched(out, refused, f"выкладка без правки ({path})")
        self.assertIn("нет изменений", out, self.note(f"отказ не «нет изменений»:\n{out}"))


class RealDefectsStillRefusedTest(AmendPultSandbox):

    def test_ac8_syntax_error_in_plank_refuses(self):
        """Правка с синтаксической ошибкой в файле `test_*.py` — отказ, ссылка не тронута.

        Сценарий: путь — простой или с долгоживущими файлами (случайно);
        Оператор выкладывает планку и ломает синтаксис одного файла
        `test_*.py` (какого и как — случайно). `amend-tests` отказывает
        ненулевым кодом, лок и голова ссылки документов прежние, события
        правки планки нет.

        Ловит мутацию: ошибка сбора планки отнесена к «нет помощника» и
        пропущена (например, любой красный сухой сбор при выложенном
        помощнике считается проходом) — синтаксически битая планка
        фиксируется в ссылке документов.
        """
        path = self.rng.choice(PATHS)
        self.lock_plank(long_lived=path != "простой")
        self.lay_out_locked()
        name = self.rng.choice((PULT_PLANK, OTHER_PLANK))
        target = self.tests_dir / name
        text = target.read_text(encoding="utf-8")
        broken = self.rng.choice((
            text.replace("unittest.TestCase):", "unittest.TestCase)", 1),
            text + "\ndef broken(:\n    pass\n",
            text.replace("import unittest", "import unittest +", 1)))
        self.assertNotEqual(broken, text, self.note("предпосылка: правка не внесена"))
        target.write_text(broken, encoding="utf-8")

        out, refused = self.amend()

        self.assert_refused_untouched(out, refused,
                                      f"синтаксическая ошибка в {name} ({path})")

    def test_ac9_red_plank_with_helper_refuses(self):
        """Правка, в которой тест красный при успешном импорте `_pult`, — отказ, ссылка не тронута.

        Сценарий: путь — простой или с долгоживущими файлами (случайно);
        Оператор правит файл планки с `from _pult import TASK_ID`: тест
        сверяет `TASK_ID` с чужим значением и падает со своей пометкой, у
        файла нет маркера красноты. `amend-tests` отказывает ненулевым
        кодом, текст отказа несёт пометку упавшего утверждения и не несёт
        «No module named '_pult'» (импорт помощника прошёл), лок и голова
        ссылки документов прежние, события правки планки нет.

        Ловит мутацию: с выложенным помощником красный прогон планки
        пропускается без проверки маркеров красноты — правка с красным
        тестом фиксируется в ссылке документов.
        """
        path = self.rng.choice(PATHS)
        self.lock_plank(long_lived=path != "простой")
        self.lay_out_locked()
        fail_note = f"красный тест планки {self.seed}"
        red = self.pult_plank(marker="Без маркера красноты.",
                              expected=f"чужая задача {self.seed}",
                              fail_note=fail_note)
        (self.tests_dir / PULT_PLANK).write_text(red, encoding="utf-8")

        out, refused = self.amend()

        self.assert_refused_untouched(out, refused, f"красный тест ({path})")
        self.assertNotIn(NO_MODULE, out, self.note(
            f"импорт помощника не прошёл ({path}):\n{out}"))
        self.assertIn(fail_note, out, self.note(
            f"отказ не от упавшего утверждения ({path}):\n{out}"))


if __name__ == "__main__":
    unittest.main()
