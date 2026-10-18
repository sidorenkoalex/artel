"""Команда `artel.py guard <id> [<файл>]` проверяет артефакты каталога документов задачи правилом `scripts/guard.py`.

Группа: долгоживущий
Красен до реализации: команды guard в диспетчере `artel.py` нет и в белом списке роли её нет — под ролью отказ «команда недоступна процессу роли», строк нарушений нет, код 1 и на чистом артефакте.

Эталон — тот же процесс и та же песочница: `scripts.guard.main()` с argv
из абсолютных путей файлов каталога документов (режим по файлам), вывод
снимается с `sys.stdout`. Строка нарушения — строка вида «<абсолютный
путь файла>: <текст>» (у эталона — после «  - »); сравниваются множества
таких строк, пометки пропуска записок шагов и паспорта в них не входят.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): клон артели —
сам репозиторий песочницы с bare `origin`, клон учебного внешнего проекта —
`tests.sandbox.make_project_repo`. Каталог документов задачи — каталог
`<id>` под каталогом задач проекта в `config.PROJECTS`, документы
перенесены в ссылку документов `checkpoint.commit_step_artifacts` и
вновь положены на диск (материализация на старте шага); рабочая копия
кода и ветка задачи — `workspace.ensure`. Окружение роли — признаки,
которые ставит `runner.role_env` (метка роли `config.ARTEL_ROLE_ENV` и
HOME дома роли `config.ROLE_HOME`), поверх окружения теста: сам
`role_env` в песочнице отказывает без `.artel/venv`. Команда зовётся
через `artel.main()`. Имена файлов, путей и текстов — из `random`, зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
команда в белом списке роли зовёт `scripts.guard.main()` с абсолютными
путями файлов каталога документов; все методы зелёные.
"""
import io
import os
import random
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import artel, checkpoint, config, idgen, store, workspace
from scripts import guard
from tests.sandbox import RealGitSandbox, artel_target_entry, make_project_repo

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
ROLE_REFUSAL = "команда недоступна процессу роли"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: {status}
schema_version: 5
zones: {zones}
budget_usd: 30
---

# SPEC: фикстура {word}

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура {mention}.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: фикстура {word}

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

Нет.
{appendix}"""

BROKEN_APPENDIX = """
## Приложение 1: {word}

```diff
--- a/{word}.cfg
+++ b/{word}.cfg
@@ -0,0 +1 @@
+{word}
```
"""


class GuardCommandSandbox(RealGitSandbox):
    """Задачи артели и учебного внешнего проекта с каталогом документов,
    ссылкой документов, веткой и рабочей копией кода."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"sled{self.word()}"
        self.add_synced_origin()
        config.TARGETS.write_text("targets:\n" + artel_target_entry(),
                                  encoding="utf-8")
        self.ext_clone = make_project_repo(self.ext)
        self.docs_files: dict = {}

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def clone(self, target: str) -> Path:
        return self.root if target == ARTEL else self.ext_clone

    def new_task(self, target: str, state: str = "in_dev") -> str:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, target, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        return task_id

    def docs_dir(self, task_id: str) -> Path:
        return (config.PROJECTS / store.task_target(self.conn, task_id)
                / "tasks" / task_id)

    def put_docs(self, task_id: str, files: dict) -> None:
        """Файлы в ссылку документов задачи и — как после материализации
        на старте шага — на диск каталога документов."""
        known = self.docs_files.setdefault(task_id, {})
        known.update(files)
        self.write_docs(task_id, known)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, task_id, "analyst")
        store.record_fixation(self.conn, task_id)
        self.write_docs(task_id, known)

    def write_docs(self, task_id: str, files: dict) -> None:
        for name, text in files.items():
            path = self.docs_dir(task_id) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    # ------------------------------------------------------- артефакты

    def clean_spec(self, task_id: str) -> str:
        return SPEC_TEXT.format(task=task_id, status="ready",
                                zones=f"z{self.word()}/", word=self.word(),
                                mention="без путей")

    def structural_spec(self, task_id: str) -> str:
        return SPEC_TEXT.format(task=task_id, status=f"st{self.word()}",
                                zones=f"z{self.word()}/", word=self.word(),
                                mention="без путей")

    def path_spec(self, task_id: str) -> str:
        """SPEC, упоминающий существующий файл репозитория вне зон."""
        rel = f"k{self.word()}/m{self.word()}.py"
        (config.ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (config.ROOT / rel).write_text("A = 1\n", encoding="utf-8")
        return SPEC_TEXT.format(task=task_id, status="ready",
                                zones=f"z{self.word()}/", word=self.word(),
                                mention=f"правит `{rel}`")

    def broken_plan(self, task_id: str) -> str:
        return PLAN_TEXT.format(task=task_id, word=self.word(),
                                appendix=BROKEN_APPENDIX.format(word=self.word()))

    def clean_plan(self, task_id: str) -> str:
        return PLAN_TEXT.format(task=task_id, word=self.word(), appendix="")

    # ------------------------------------------------------- прогоны

    def role_markers(self, role: str, task_id: str) -> dict:
        """Признаки процесса роли, которые ставит `runner.role_env`: метка
        роли и HOME дома роли."""
        return {config.ARTEL_ROLE_ENV: role, "HOME": str(config.ROLE_HOME)}

    def guard_command(self, task_id: str, *extra: str,
                      role: str = "analyst") -> tuple:
        """(код выхода, весь вывод) `artel.py guard <id> [файл]` в окружении
        роли."""
        argv = ["artel.py", "guard", task_id, *extra]
        out, err = io.StringIO(), io.StringIO()
        code = None
        markers = self.role_markers(role, task_id)
        with mock.patch.dict(os.environ, markers), \
                mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, "\n".join((out.getvalue(), err.getvalue(), message))

    def reference(self, paths: list) -> tuple:
        """(код выхода, строки нарушений) эталона `scripts/guard.py <пути>`."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["guard.py", *map(str, paths)]), \
                redirect_stdout(out):
            code = guard.main()
        lines = {line[len("  - "):] for line in out.getvalue().splitlines()
                 if line.startswith("  - ")}
        return code, lines

    def violation_lines(self, output: str, task_id: str) -> set:
        """Строки вывода команды вида «<абсолютный путь файла каталога
        документов>: <текст>», без пометок пропуска записок и паспорта."""
        pattern = re.compile(r"^\s*(?:-\s+)?(" + re.escape(
            str(self.docs_dir(task_id))) + r"/[^\s:]+: .*)$")
        found = set()
        for line in output.splitlines():
            match = pattern.match(line)
            if match and guard.PASSPORT_SKIP_NOTE not in line \
                    and guard.STEP_NOTE_SKIP_NOTE not in line:
                found.add(match.group(1))
        return found

    def explain(self, output: str, ref=None) -> str:
        return self.note(f"вывод guard:\n{output[-3000:]}\n--- эталон: {ref}")


class Ac1GuardOneFileTest(GuardCommandSandbox):

    def test_ac1_guard_file_matches_reference_for_each_violation_kind(self):
        """`guard <id> SPEC.md` (и `PLAN.md`) под ролью: код 0 на чистом артефакте, на нарушении — ненулевой код и строки эталона с абсолютной путь-меткой.

        Сценарий для задачи учебного внешнего проекта и задачи артели, в
        окружении роли: чистый SPEC.md — код 0, строк нарушений нет;
        SPEC.md с недопустимым status (структура, `check`), SPEC.md с
        упоминанием существующего файла репозитория вне зон
        (`spec_path_errors`) и PLAN.md с приложением без заголовка `diff
        --git` (`plan_appendix_errors`) — ненулевой код, и множество строк
        «<путь>: <текст>» вывода команды равно множеству строк нарушений
        эталона `scripts/guard.py <абсолютный путь файла каталога
        документов>`; эталон на каждом виде действительно видит нарушение
        своим правилом.

        Ловит мутацию: команда не внесена в белый список роли — отказ
        «команда недоступна процессу роли»; проверка собрана своей копией
        правил или без `spec_path_errors`/`plan_appendix_errors` (как в
        `--all`) — строки нарушения путей или приложения пропадают, код 0;
        путь-метка — путь от корня репозитория или имя файла вместо
        абсолютного пути каталога документов — строки не совпадают с
        эталоном; код выхода не зависит от нарушений — 0 при нарушении.
        """
        for target in (self.ext, ARTEL):
            task_id = self.new_task(target)
            spec = self.docs_dir(task_id) / "SPEC.md"
            plan = self.docs_dir(task_id) / "PLAN.md"
            with self.subTest(target=target, kind="чистый", seed=self.seed):
                self.put_docs(task_id, {"SPEC.md": self.clean_spec(task_id)})
                ref_code, ref_lines = self.reference([spec])
                self.assertEqual((ref_code, ref_lines), (0, set()),
                                 self.note("чистый SPEC не чист для эталона"))
                status, output = self.guard_command(task_id, "SPEC.md")
                self.assertNotIn(ROLE_REFUSAL, output, self.explain(output))
                self.assertEqual(status, 0, self.explain(output))
                self.assertEqual(self.violation_lines(output, task_id), set(),
                                 self.explain(output))
            for kind, name, text, rule in (
                    ("check", "SPEC.md", self.structural_spec(task_id),
                     guard.check),
                    ("spec_path_errors", "SPEC.md", self.path_spec(task_id),
                     guard.spec_path_errors),
                    ("plan_appendix_errors", "PLAN.md",
                     self.broken_plan(task_id), guard.plan_appendix_errors)):
                with self.subTest(target=target, kind=kind, seed=self.seed):
                    self.put_docs(task_id, {name: text})
                    path = spec if name == "SPEC.md" else plan
                    self.assertTrue(rule(path),
                                    self.note(f"правило {kind} не видит нарушения"))
                    ref_code, ref_lines = self.reference([path])
                    self.assertNotEqual(ref_code, 0, self.note(str(ref_lines)))
                    self.assertTrue(all(line.startswith(f"{path}: ")
                                        for line in ref_lines),
                                    self.note(f"метка эталона: {ref_lines}"))
                    status, output = self.guard_command(task_id, name)
                    self.assertNotIn(ROLE_REFUSAL, output, self.explain(output))
                    self.assertNotEqual(status, 0, self.explain(output, ref_lines))
                    self.assertEqual(self.violation_lines(output, task_id),
                                     ref_lines, self.explain(output, ref_lines))
                self.put_docs(task_id, {"SPEC.md": self.clean_spec(task_id),
                                        "PLAN.md": self.clean_plan(task_id)})


class Ac2GuardAllArtifactsTest(GuardCommandSandbox):

    def test_ac2_guard_without_file_checks_all_first_level_md(self):
        """`guard <id>` без файла проверяет все `*.md` первого уровня каталога документов; записки и паспорт нарушениями не становятся.

        Сценарий для задачи артели и задачи учебного проекта: в каталоге
        документов — SPEC.md, PLAN.md, записка шага `NOTE-<роль>.md` и
        паспорт `PASSPORT.md` (оба без frontmatter); нарушение — в одном
        случайно выбранном артефакте (SPEC.md или PLAN.md), другой чист.
        Код выхода ненулевой; множество строк нарушений вывода команды
        равно множеству строк эталона `scripts/guard.py` по абсолютным
        путям тех же четырёх файлов; ни одна строка нарушения не называет
        записку или паспорт.

        Ловит мутацию: без файла проверяется только SPEC.md (или первый
        файл) — нарушение PLAN.md пропадает, код 0; записки и паспорт не
        пропускаются — строки «нет frontmatter» по ним; файлы каталога
        собраны рекурсивно с подкаталогами — лишние строки о файле
        `acceptance_tests/` без frontmatter.
        """
        for target in (ARTEL, self.ext):
            with self.subTest(target=target, seed=self.seed):
                task_id = self.new_task(target)
                broken = self.rng.choice(("SPEC.md", "PLAN.md"))
                note = guard.step_note_name(self.rng.choice(guard.STEP_NOTE_ROLES))
                files = {
                    "SPEC.md": (self.structural_spec(task_id)
                                if broken == "SPEC.md"
                                else self.clean_spec(task_id)),
                    "PLAN.md": (self.broken_plan(task_id)
                                if broken == "PLAN.md"
                                else self.clean_plan(task_id)),
                    note: f"записка {self.word()} без заголовочного блока\n",
                    "PASSPORT.md": f"паспорт {self.word()}\n",
                    f"acceptance_tests/n{self.word()}.md":
                        f"заметка {self.word()}\n"}
                self.put_docs(task_id, files)
                docs = self.docs_dir(task_id)
                paths = [docs / name for name in sorted(files) if "/" not in name]
                ref_code, ref_lines = self.reference(paths)
                self.assertNotEqual(ref_code, 0, self.note(str(ref_lines)))
                status, output = self.guard_command(task_id)
                self.assertNotIn(ROLE_REFUSAL, output, self.explain(output))
                self.assertNotEqual(status, 0, self.explain(output, ref_lines))
                lines = self.violation_lines(output, task_id)
                self.assertEqual(lines, ref_lines, self.explain(output, ref_lines))
                self.assertFalse(any(line.startswith(str(docs / name))
                                     for line in lines
                                     for name in (note, "PASSPORT.md")),
                                 self.explain(output, ref_lines))


class Ac3GuardReadOnlyTest(GuardCommandSandbox):

    def snapshot(self, task_id: str) -> tuple:
        target = store.task_target(self.conn, task_id)
        clone = str(self.clone(target))
        row = dict(store.get_task(self.conn, task_id))
        steps = [dict(r) for r in store.task_steps(self.conn, task_id)]
        ref = self.git("-C", clone, "for-each-ref", "--format=%(objectname)",
                       f"refs/artifacts/{task_id}").strip()
        branch = self.git("-C", clone, "rev-parse",
                          f"refs/heads/{row['branch']}").strip()
        docs = self.docs_dir(task_id)
        files = {p.relative_to(docs).as_posix(): p.read_bytes()
                 for p in sorted(docs.rglob("*")) if p.is_file()}
        return row, steps, ref, branch, files

    def test_ac3_guard_changes_nothing_and_takes_no_lease(self):
        """`guard` с файлом и без под ролью не меняет строку задачи, журнал, ссылку документов, ветку и каталог документов, lease не берёт.

        Сценарий для задачи артели и задачи учебного проекта: каталог
        документов с SPEC.md (с нарушением и без, по зерну) и PLAN.md;
        под случайной ролью `guard <id> SPEC.md` и `guard <id>`. Строка
        задачи в БД (все поля), записи журнала шагов задачи, голова
        `refs/artifacts/<id>`, голова ветки задачи и байты каждого файла
        каталога документов до и после совпадают; строки lease задачи нет;
        отказа роли в выводе нет.

        Ловит мутацию: команда берёт lease (`lease.acquire`) и не снимает
        его — строка lease после вызова; пишет запись журнала о проверке
        или перефиксирует ссылку (`record_fixation`/автокоммит документов)
        — журнал, строка задачи или голова ссылки отличаются; правит файл
        (нормализует frontmatter) — байты файла каталога отличаются;
        команда вне белого списка роли — отказ «команда недоступна
        процессу роли».
        """
        for target in (ARTEL, self.ext):
            with self.subTest(target=target, seed=self.seed):
                task_id = self.new_task(target)
                spec = (self.structural_spec(task_id) if self.rng.random() < 0.5
                        else self.clean_spec(task_id))
                self.put_docs(task_id, {"SPEC.md": spec,
                                        "PLAN.md": self.clean_plan(task_id)})
                role = self.rng.choice(("analyst", "developer", "spec_auditor",
                                        "reviewer"))
                for extra in (("SPEC.md",), ()):
                    before = self.snapshot(task_id)
                    _status, output = self.guard_command(task_id, *extra,
                                                         role=role)
                    self.assertNotIn(ROLE_REFUSAL, output, self.explain(output))
                    after = self.snapshot(task_id)
                    for label, a, b in zip(("строка задачи", "журнал шагов",
                                            "ссылка документов", "ветка задачи",
                                            "каталог документов"),
                                           before, after):
                        self.assertEqual(a, b, self.explain(
                            f"{label} изменена вызовом guard {extra}\n{output}"))
                    self.assertIsNone(store.lease_row(self.conn, task_id),
                                      self.explain(f"lease взят\n{output}"))
