"""Гейт мержа по перечню защищённых путей проекта задачи: защищённые пути
в диффе, применение приложений PLAN и карта кодовой базы.

Группа: долгоживущий
Красен до реализации: на гейте мержа сверка защищённых путей диффа и применение приложений PLAN включены только для артели — дифф внешнего проекта под его `no_paths` мержится без эскалации, приложения PLAN внешнего проекта не применяются и записи «нет профиля тестов» нет (AC-5, AC-9); шаг карты включён признаком артели, а не наличием генератора — у артели без `scripts/codebase_map.py` он заводит инцидент «регенерация карты FAILED», у внешнего проекта с генератором карта не строится (AC-11). Случаи «дифф только по пути пульта у внешнего проекта не эскалирует» (AC-5) и классы полного прогона артели (AC-9) держат сегодняшнее поведение и зелёные с рождения.

Сценарий — сквозной `fsm.cmd_approve` задачи на `merge_gate` в настоящем git
песочницы (`tests.sandbox.RealGitSandbox`): корень — клон артели с bare
`origin`; внешний проект — свой клон с bare `origin`
(`tests.sandbox.make_project_repo`), запись в `targets.yaml` песочницы с
полем `no_paths` из случайных каталогов `zn…/` и без профиля тестов. Ветка
задачи заведена рабочей копией (`workspace.ensure`) от `origin` клона
проекта, код закоммичен в неё; PLAN.md (с разделами «## Приложение» по
сценарию) и SPEC.md — в ссылке документов автокоммитом шага
(`checkpoint.commit_step_artifacts`).

Подменены только внешние проверки, которых в песочнице нет: цвет CI ветки
и `main` (`ci.branch_status`, `ci.main_line_status`), Draft MR форджа
(`github_adapter.ensure_draft_mr`/`undraft_mr`) и полный прогон набора
(`acceptance.run_full_suite` — единственная точка подмены прогона; подмена
отвечает «зелено» и запоминает вызов).

Провалидировано временным стабом реализации (удалён, не закоммичен):
сверка диффа и применение приложений по перечню проекта без развилки,
запись «нет профиля тестов» вместо прогона у внешнего проекта, шаг карты
по наличию генератора в дереве мержа — все методы зелёные.

Зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, store, workspace)
from tests.sandbox import RealGitSandbox, capture, make_project_repo

ARTEL = config.DEFAULT_TARGET
EXT = "vnesh"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

# Классы приложений артели, требующие полного прогона (SPEC, требование 6):
# путь-образец под каждым классом строится от случайного имени.
FULL_SUITE_CLASSES = ("tests/", ".github/", "**/conftest.py", "pyproject.toml",
                      "pytest.ini", "setup.cfg", "tox.ini")

MAP_REL = "docs/codebase-map.md"
MAP_PLACEHOLDER = "---\nbuilt_at_sha: 0\n---\n\n# Карта-заглушка\n"
MAP_INCIDENT_ACTION = "регенерация карты FAILED"
MAP_ALERT_SOURCE = "fsm.map_regen"

# Генератор карты песочницы: пишет карту со своей меткой — её появление в
# `main` и есть «карта регенерирована и закоммичена».
GENERATOR = """from pathlib import Path
Path("docs").mkdir(exist_ok=True)
Path("docs/codebase-map.md").write_text(
    "---\\nbuilt_at_sha: 1\\n---\\n\\n# Карта MARK\\n", encoding="utf-8")
"""

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: фикстура гейта мержа

## Подход

Фикстура.
{appendices}"""

APPENDIX_SECTION = """
## Приложение {number}: {heading}

```diff
{diff}```
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура гейта мержа

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


def new_file_diff(rel: str, line: str) -> str:
    return (f"diff --git a/{rel} b/{rel}\n"
            f"new file mode 100644\n"
            f"--- /dev/null\n"
            f"+++ b/{rel}\n"
            f"@@ -0,0 +1 @@\n"
            f"+{line}\n")


class MergeGateSandbox(RealGitSandbox):
    """Клон артели и клон внешнего проекта, задачи на `merge_gate`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.full_suite_calls: list[Path] = []
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch.object(acceptance, "run_full_suite",
                                  self.fake_full_suite),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.artel_origin = self.add_synced_origin()
        self.ext_clone = make_project_repo(EXT)
        self.ext_origin = config.PROJECTS / EXT / "origin.git"
        self.ext_dirs = []
        while len(self.ext_dirs) < self.rng.randint(2, 3):
            name = f"zn{self.word()}/"
            if name not in self.ext_dirs:
                self.ext_dirs.append(name)
        self.write_targets()
        capture(catalog.cmd_init)

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def explain(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def fake_full_suite(self, root):
        self.full_suite_calls.append(Path(root))
        return (True, "1 passed (тест)")

    def write_targets(self) -> None:
        text = "targets:\n" + TARGET_ENTRY.format(
            name=ARTEL, url="http://localhost/artel", base=config.MAIN_BRANCH,
            no_paths=", ".join(config.PROTECTED_PATHS))
        text += TARGET_ENTRY.format(
            name=EXT, url=f"file:///nonexistent/{EXT}", base=config.MAIN_BRANCH,
            no_paths=", ".join(self.ext_dirs))
        config.TARGETS.write_text(text, encoding="utf-8")

    def ext_protected_path(self) -> str:
        return f"{self.rng.choice(self.ext_dirs)}{self.word()}.cfg"

    def artel_only_path(self) -> str:
        """Путь под случайной записью `config.PROTECTED_PATHS` (не маской)."""
        entry = self.rng.choice([e for e in config.PROTECTED_PATHS
                                 if not e.startswith("**/")])
        return f"{entry}{self.word()}.md" if entry.endswith("/") else entry

    # ----------------------------------------------------------- проект

    def commit_to_project_main(self, target: str, files: dict[str, str]) -> None:
        """Файлы `files` — коммитом в `main` клона проекта и его `origin`."""
        clone = self.root if target == ARTEL else self.ext_clone
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def origin(self, target: str) -> Path:
        return self.artel_origin if target == ARTEL else self.ext_origin

    def origin_tree(self, target: str) -> list[str]:
        return self.git("--git-dir", str(self.origin(target)), "ls-tree", "-r",
                        "--name-only", f"refs/heads/{config.MAIN_BRANCH}").splitlines()

    def origin_file(self, target: str, rel: str) -> str:
        return self.git("--git-dir", str(self.origin(target)), "show",
                        f"refs/heads/{config.MAIN_BRANCH}:{rel}")

    def origin_subjects(self, target: str) -> list[str]:
        return self.git("--git-dir", str(self.origin(target)), "log",
                        "--format=%s", f"refs/heads/{config.MAIN_BRANCH}").splitlines()

    # ------------------------------------------------------------ задача

    def new_task(self, target: str, code: dict[str, str],
                 appendices: list[str] = ()) -> str:
        """Задача `target` на `merge_gate`: код `code` в ветке, PLAN.md с
        приложениями `appendices` в ссылке документов."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-merge"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "merge_gate", branch, target,
                          config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.explain(f"рабочая копия не заведена: {error}"))
        for rel, text in code.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        sections = "".join(
            APPENDIX_SECTION.format(number=n, heading=self.word(), diff=diff)
            for n, diff in enumerate(appendices, 1))
        docs = config.PROJECTS / target / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(
            PLAN_TEXT.format(task=task_id, appendices=sections), encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id),
                                      encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, task_id, "developer")
        return task_id

    def code(self) -> dict[str, str]:
        return {f"kod{self.word()}/{self.word()}.py": f"A = {self.seed}\n"}

    def approve(self, task_id: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(task_id)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    def journal(self, task_id: str) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id)]

    def context(self, task_id: str, out: str) -> str:
        return self.explain("\n".join(self.journal(task_id))
                            + "\n--- вывод approve:\n" + out)

    def map_alerts_after(self, before: int) -> list:
        """Алерты шага карты, заведённые после алерта с id `before`."""
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM alerts WHERE source=? AND id>?",
            (MAP_ALERT_SOURCE, before))]

    def last_alert_id(self) -> int:
        row = self.conn.execute("SELECT MAX(id) FROM alerts").fetchone()
        return row[0] or 0


class ProtectedDiffTest(MergeGateSandbox):

    def test_ac5_external_diff_checked_by_project_no_paths(self):
        """Дифф задачи внешнего проекта сверяется на гейте мержа по её `no_paths`.

        Сценарий: задача внешнего проекта, чей код трогает путь под
        случайной записью `no_paths` (и файл кода), — после `approve` задача
        в `escalated`, журнал несёт текст «защищённый путь <путь> — правит
        только Оператор коммитом в main», `origin/main` проекта не несёт
        этого пути. Вторая задача трогает только путь под записью
        `config.PROTECTED_PATHS` (её нет в `no_paths`) — задача не
        эскалирована и доходит до `done`, путь — в `origin/main` проекта.

        Ловит мутацию: признак артели оставлен на сверке защищённых путей
        диффа — путь `no_paths` внешнего проекта мержится молча; сверка
        включена, но по `config.PROTECTED_PATHS` — путь пульта эскалирует
        задачу внешнего проекта, а путь её `no_paths` нет.
        """
        rel = self.ext_protected_path()
        code = self.code()
        code[rel] = "защищённое\n"
        task = self.new_task(EXT, code)
        out = self.approve(task)
        context = self.context(task, out)
        self.assertEqual(self.state(task), "escalated", context)
        expected = f"защищённый путь {rel} — правит только Оператор коммитом в main"
        self.assertTrue([e for e in self.journal(task) if expected in e], context)
        self.assertNotIn(rel, self.origin_tree(EXT), context)

        rel = self.artel_only_path()
        task = self.new_task(EXT, {rel: "путь пульта\n"})
        out = self.approve(task)
        context = self.context(task, out)
        self.assertNotEqual(self.state(task), "escalated", context)
        self.assertEqual(self.state(task), "done", context)
        self.assertIn(rel, self.origin_tree(EXT), context)


class ExternalAppendixTest(MergeGateSandbox):

    def test_ac9_external_appendix_without_profile_applied_without_full_suite(self):
        """Приложение PLAN задачи внешнего проекта без профиля тестов применяется в мерж без полного прогона, с записью в журнале.

        Сценарий: проект без профиля тестов; PLAN задачи несёт одно-два
        применимых приложения (новые файлы) к путям под `no_paths`. После
        `approve`: задача в `done`; строка каждого приложения — в
        соответствующем файле `origin/main` проекта; подмена полного прогона
        не вызвана ни разу; журнал задачи несёт запись, называющую
        невыполненный полный прогон и отсутствие профиля тестов.

        Ловит мутацию: признак артели оставлен на применении приложений —
        приложения внешнего проекта не попадают в его `main`; без профиля
        гейт гоняет полный набор командой пульта; пропуск прогона молчаливый
        — записи о профиле в журнале нет.
        """
        appendices, lines = [], {}
        for _ in range(self.rng.randint(1, 2)):
            rel = self.ext_protected_path()
            lines[rel] = f"строка приложения {self.word()}"
            appendices.append(new_file_diff(rel, lines[rel]))
        task = self.new_task(EXT, self.code(), appendices)
        out = self.approve(task)
        context = self.context(task, out)
        self.assertEqual(self.state(task), "done", context)
        for rel, line in lines.items():
            self.assertIn(rel, self.origin_tree(EXT), context)
            self.assertIn(line, self.origin_file(EXT, rel), context)
        self.assertEqual(self.full_suite_calls, [], context)
        noted = [e for e in self.journal(task)
                 if "профил" in e.lower() and "прогон" in e.lower()]
        self.assertTrue(noted, context)


class ArtelFullSuiteClassesTest(MergeGateSandbox):

    def class_path(self, entry: str) -> str:
        if entry.startswith("**/"):
            return f"zd{self.word()}/{entry[3:]}"
        if entry.endswith("/"):
            return f"{entry}zn{self.word()}.py"
        return entry

    def test_ac9_artel_full_suite_only_for_test_collection_classes(self):
        """У артели полный прогон после приложений требуют только классы сбора тестов.

        Сценарий: три задачи артели на `merge_gate`. Две — с приложением
        (новый файл) к пути под случайным классом из `tests/`, `.github/`,
        `**/conftest.py`, `pyproject.toml`, `pytest.ini`, `setup.cfg`,
        `tox.ini`: после `approve` подмена полного прогона вызвана, задача в
        `done`. Третья — с приложением к пути под записью
        `config.PROTECTED_PATHS` вне этих классов: подмена не вызвана,
        задача в `done`, строка приложения — в `origin/main`.

        Ловит мутацию: «каждое приложение требует полного прогона» (правило
        внешнего проекта) применено и к артели — прогон вызван для
        приложения к `skills/`/`templates/`; классы артели потеряны (правило
        «без профиля — без прогона») — приложение к `tests/` не прогоняется.
        """
        protected_classes = [c for c in FULL_SUITE_CLASSES
                             if config.is_protected_path(self.class_path(c))]
        self.assertTrue(protected_classes, self.explain(
            "ни один класс полного прогона не защищён у артели"))
        for entry in self.rng.sample(protected_classes,
                                     min(2, len(protected_classes))):
            with self.subTest(full_suite_class=entry):
                rel = self.class_path(entry)
                self.full_suite_calls.clear()
                task = self.new_task(ARTEL, self.code(),
                                     [new_file_diff(rel, f"# {self.word()}")])
                out = self.approve(task)
                context = self.context(task, out)
                self.assertEqual(self.state(task), "done", context)
                self.assertTrue(self.full_suite_calls, context)
        others = [e for e in config.PROTECTED_PATHS
                  if not e.startswith("**/")
                  and not any(config.is_protected_path(self.class_path(e), (c,))
                              for c in FULL_SUITE_CLASSES)]
        entry = self.rng.choice(others)
        rel = f"{entry}zn{self.word()}.md" if entry.endswith("/") else entry
        line = f"строка {self.word()}"
        self.full_suite_calls.clear()
        task = self.new_task(ARTEL, self.code(), [new_file_diff(rel, line)])
        out = self.approve(task)
        context = self.context(task, out)
        self.assertEqual(self.state(task), "done", context)
        self.assertEqual(self.full_suite_calls, [], context)
        self.assertIn(line, self.origin_file(ARTEL, rel), context)


class NoGeneratorMapTest(MergeGateSandbox):

    def test_ac11_no_generator_no_map_no_incident(self):
        """Без генератора карты в дереве мержа гейт мержа карту не строит, инцидента не заводит и доходит до `done`.

        Сценарий: в `main` ни артели, ни внешнего проекта нет
        `scripts/codebase_map.py`. Задача каждого проекта (порядок случаен)
        после `approve` — в `done`; в истории `origin/main` проекта нет
        коммита «карта кодовой базы…»; в журнале задачи нет записи
        «регенерация карты FAILED», среди алертов нет алерта шага карты; в
        журнале есть запись, называющая карту и отсутствие генератора.

        Ловит мутацию: шаг карты оставлен под признаком артели — у артели без
        генератора он заводит инцидент и алерт; отсутствие генератора
        пропускается молча — записи журнала нет.
        """
        projects = [ARTEL, EXT]
        self.rng.shuffle(projects)
        for target in projects:
            with self.subTest(project=target):
                task = self.new_task(target, self.code())
                alerts_before = self.last_alert_id()
                out = self.approve(task)
                context = self.context(task, out)
                self.assertEqual(self.state(task), "done", context)
                self.assertFalse([s for s in self.origin_subjects(target)
                                  if s.startswith("карта кодовой базы")], context)
                self.assertFalse([e for e in self.journal(task)
                                  if e.startswith(MAP_INCIDENT_ACTION)], context)
                self.assertEqual(self.map_alerts_after(alerts_before), [], context)
                noted = [e for e in self.journal(task)
                         if "карт" in e.lower() and "генератор" in e.lower()]
                self.assertTrue(noted, context)


class GeneratorMapTest(MergeGateSandbox):

    def test_ac11_generator_in_merge_tree_regenerates_map_for_any_project(self):
        """С генератором карты в дереве мержа карта регенерируется и коммитится у любого проекта.

        Сценарий: в `main` артели и внешнего проекта — генератор
        `scripts/codebase_map.py` песочницы (пишет карту со случайной меткой)
        и карта-заглушка. Задача каждого проекта (порядок случаен) после
        `approve` — в `done`; `docs/codebase-map.md` в `origin/main` проекта
        несёт метку генератора; инцидента карты в журнале нет.

        Ловит мутацию: признак шага карты — «проект артель» вместо «генератор
        в дереве мержа» — у внешнего проекта с генератором карта остаётся
        заглушкой; признак проверяет генератор в главной копии пульта, а не в
        дереве мержа проекта.
        """
        marks = {}
        for target in (ARTEL, EXT):
            marks[target] = f"метка {self.word(8)}"
            self.commit_to_project_main(target, {
                "scripts/codebase_map.py": GENERATOR.replace("MARK", marks[target]),
                MAP_REL: MAP_PLACEHOLDER})
        projects = [ARTEL, EXT]
        self.rng.shuffle(projects)
        for target in projects:
            with self.subTest(project=target):
                task = self.new_task(target, self.code())
                out = self.approve(task)
                context = self.context(task, out)
                self.assertEqual(self.state(task), "done", context)
                self.assertIn(marks[target], self.origin_file(target, MAP_REL),
                              context)
                self.assertFalse([e for e in self.journal(task)
                                  if e.startswith(MAP_INCIDENT_ACTION)], context)


if __name__ == "__main__":
    unittest.main()
