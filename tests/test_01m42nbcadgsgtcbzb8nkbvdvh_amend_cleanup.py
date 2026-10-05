"""`amend-tests` убирает материализованный каталог задачи из рабочей копии
кода после успешной фиксации и не трогает его на отказе.

Группа: долгоживущий

Красен до реализации: `amend-tests` после фиксации правки в ссылку документов оставляет каталог задачи в рабочей копии кода — метод AC-1 красный; AC-2 (отказ не трогает каталог) держит существующее поведение и зелёный.

Сценарий на настоящем git: пульт — `self.root`; задача артели заводится
`catalog.cmd_new`, её ссылка документов `refs/artifacts/<id>` в git пульта
несёт SPEC.md с одним критерием и зелёную планку, `tests_locked_sha` стоит
на этом коммите, фиксация заведена `store.record_fixation`. Ветка задачи
заведена от `MAIN_BRANCH` до вызова, рабочая копия кода —
`workspace.ensure`. Оператор кладёт правку планки прямо в каталог задачи
рабочей копии, затем `amend.cmd_amend_tests` (режим рабочей копии).

Рядом с правкой в рабочей копии лежат файлы, игнорируемые `.gitignore`
песочницы (`*.log`, `dropme/`), в том числе внутри каталога ДРУГОЙ задачи
под тем же `tasks`-каталогом: «прочие пути не трогаются» проверяется на
них и на побайтном содержимом отслеживаемых файлов. Вид правки, имена
игнорируемых файлов и вид отказа — из `random`, зерно печатается и входит
в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import amend, catalog, config, projects, store, workspace
from tests.sandbox import GitignoreCommittedRealGitSandbox

REF_PREFIX = "refs/artifacts/"
PLANK_NAME = "test_plank.py"

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

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_criterion(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''

EXTRA_TEXT = '''"""Дополнительный файл правки Оператора.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixtureExtraTest(unittest.TestCase):

    def test_ac1_fixture_extra(self):
        """Фикстурный метод правки."""
        self.assertEqual(2 + 2, 4)
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

TITLES = ("Правка планки", "Уборка каталога", "Фиксация правки")


class AmendSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели с залоченной планкой в ссылке документов и рабочей
    копией кода; правку планки кладёт сам тест."""

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
        self.commit_docs({
            "SPEC.md": SPEC_TEMPLATE.replace("TASK_ID", self.task_id),
            "acceptance_tests/" + PLANK_NAME: PLANK_TEXT,
        }, "планка")
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.head())
        store.record_fixation(store.db(), self.task_id)
        self.locked_before = self.locked()

        self.branch = store.get_task(store.db(), self.task_id)["branch"]
        self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.task_dir = self.wt / "tasks" / self.task_id
        self.tests_dir = self.task_dir / "acceptance_tests"

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

    def operator_edit(self) -> str:
        """Правка Оператора в каталоге задачи рабочей копии: залоченная
        планка на диске плюс реальное изменение; возвращает вид правки."""
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        kind = self.rng.choice(("комментарий", "новый файл", "докстринг"))
        plank = PLANK_TEXT
        if kind == "комментарий":
            plank += f"\n# правка Оператора {self.rng.randrange(1 << 20)}\n"
        elif kind == "докстринг":
            plank = plank.replace("Фикстурный метод.",
                                  f"Фикстурный метод, правка {self.seed}.")
        else:
            (self.tests_dir / "test_extra.py").write_text(EXTRA_TEXT,
                                                         encoding="utf-8")
        (self.tests_dir / PLANK_NAME).write_text(plank, encoding="utf-8")
        return kind

    def plant_ignored(self) -> dict[Path, bytes]:
        """Игнорируемые `.gitignore` песочницы файлы рабочей копии вне
        каталога задачи — в корне, в `dropme/` и в каталоге другой задачи."""
        other = "OTHER" + str(self.rng.randrange(10 ** 6))
        candidates = [
            self.wt / f"build-{self.rng.randrange(1000)}.log",
            self.wt / "dropme" / f"scratch-{self.rng.randrange(1000)}.txt",
            self.wt / "tasks" / other / f"notes-{self.rng.randrange(1000)}.log",
        ]
        planted = {}
        for path in self.rng.sample(candidates, self.rng.randint(2, 3)):
            path.parent.mkdir(parents=True, exist_ok=True)
            data = f"чужой файл {path.name} {self.seed}\n".encode("utf-8")
            path.write_bytes(data)
            planted[path] = data
        return planted

    def tracked_bytes(self) -> dict[str, bytes]:
        names = [n for n in self.git("-C", str(self.wt), "ls-files").splitlines()
                 if n.strip()]
        return {n: (self.wt / n).read_bytes() for n in names}

    def dir_bytes(self, root: Path) -> dict[str, bytes]:
        return {str(p.relative_to(root)): p.read_bytes()
                for p in sorted(root.rglob("*")) if p.is_file()
                and "__pycache__" not in p.parts}

    def amend(self) -> tuple[str, bool]:
        return self.run_cmd(amend.cmd_amend_tests, self.task_id,
                            f"правка планки {self.seed}")


class AmendSuccessCleanupTest(AmendSandbox):

    def test_ac1_successful_amend_removes_task_dir_and_keeps_the_rest(self):
        """Успешный `amend-tests` с реальной правкой — каталога задачи в рабочей копии нет, прочие файлы целы.

        Сценарий: Оператор кладёт правку планки (вид — случайно) в каталог
        задачи рабочей копии кода; рядом — игнорируемые файлы в корне, в
        `dropme/` и в каталоге другой задачи. `amend-tests` завершается без
        отказа, `tests_locked_sha` сдвинут на голову ссылки документов
        (правка зафиксирована). После этого каталога задачи в рабочей копии
        нет, игнорируемые файлы на месте побайтно, отслеживаемые файлы
        рабочей копии побайтно прежние.

        Ловит мутацию: уборка каталога задачи не добавлена (каталог с
        материализованной планкой остаётся в рабочей копии, как на пине);
        уборка сносит весь каталог `tasks` рабочей копии (пропадает файл
        другой задачи) или идёт `git clean`/`git checkout` по всей рабочей
        копии (пропадают игнорируемые файлы или откатываются отслеживаемые).
        """
        kind = self.operator_edit()
        planted = self.plant_ignored()
        tracked = self.tracked_bytes()

        out, refused = self.amend()

        self.assertFalse(refused, self.note(f"правка «{kind}» отклонена:\n{out}"))
        self.assertNotEqual(self.locked(), self.locked_before, self.note(
            f"предпосылка: правка «{kind}» не зафиксирована:\n{out}"))
        self.assertEqual(self.locked(), self.head(), self.note(
            "предпосылка: лок не на голове ссылки документов"))
        self.assertFalse(self.task_dir.exists(), self.note(
            f"каталог задачи остался в рабочей копии после правки «{kind}»: "
            f"{sorted(self.dir_bytes(self.task_dir)) if self.task_dir.is_dir() else self.task_dir}"))
        for path, data in planted.items():
            self.assertTrue(path.is_file(), self.note(
                f"игнорируемый файл вне каталога задачи пропал: {path}"))
            self.assertEqual(path.read_bytes(), data, self.note(
                f"игнорируемый файл изменён: {path}"))
        self.assertEqual(self.tracked_bytes(), tracked, self.note(
            "отслеживаемые файлы рабочей копии изменены"))


class AmendRefusalKeepsDirTest(AmendSandbox):

    def test_ac2_refused_amend_keeps_task_dir_byte_for_byte(self):
        """`amend-tests`, закончившийся отказом, оставляет каталог задачи в рабочей копии побайтно как был.

        Сценарий: Оператор кладёт правку планки в каталог задачи рабочей
        копии, и правка отказная (случайно): либо рядом с ней в рабочей
        копии лежит неотслеживаемый файл вне `acceptance_tests/` (отказ
        «за пределами»), либо правка сняла метод критерия (отказ
        трассируемости). `amend-tests` отказывает ненулевым кодом,
        `tests_locked_sha` прежний; содержимое каталога задачи рабочей
        копии побайтно то же, что до вызова.

        Ловит мутацию: уборка каталога задачи стоит в `finally`/до проверок
        и срабатывает и на отказе — правка Оператора пропадает с диска;
        уборка на отказе сносит только материализованное командой, но
        переписывает правку Оператора содержимым ссылки документов.
        """
        self.operator_edit()
        kind = self.rng.choice(("за пределами", "трассируемость"))
        if kind == "за пределами":
            stray = self.wt / f"stray-{self.rng.randrange(1000)}.txt"
            stray.write_text("сторонняя правка\n", encoding="utf-8")
        else:
            for path in self.tests_dir.glob("test_*.py"):
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace("def test_ac1_", "def test_other_"),
                                encoding="utf-8")
        before = self.dir_bytes(self.task_dir)

        out, refused = self.amend()

        self.assertTrue(refused, self.note(f"отказная правка «{kind}» принята:\n{out}"))
        self.assertEqual(self.locked(), self.locked_before, self.note(
            f"лок сдвинут отказной правкой «{kind}»"))
        self.assertTrue(self.task_dir.is_dir(), self.note(
            f"каталог задачи убран на отказе «{kind}»:\n{out}"))
        self.assertEqual(self.dir_bytes(self.task_dir), before, self.note(
            f"каталог задачи изменён на отказе «{kind}»:\n{out}"))


if __name__ == "__main__":
    unittest.main()
