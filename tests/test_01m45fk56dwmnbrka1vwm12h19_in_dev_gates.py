"""Гейты выхода из `in_dev` по перечню защищённых путей проекта задачи:
гейт зон, допуск и применимость приложений PLAN.

Группа: долгоживущий
Красен до реализации: гейт зон и гейт применимости приложений PLAN для задачи внешнего проекта не исполняются вовсе (развилка по проекту пульта) — отказов «вне зон», «защищённый путь» и «приложение неприменимо» у внешнего проекта нет (AC-1, AC-3, AC-4, AC-8); перечень защищённых путей у всех мест сверки — `config.PROTECTED_PATHS`, поэтому приложение к пути `no_paths` внешнего проекта отвергается как «не защищённый», а к пути, защищённому только у артели, допускается (AC-7); `python3 scripts/guard.py <PLAN.md>` разделы «## Приложение» не сверяет вовсе (AC-7). Половина артели (AC-2, AC-4) держит сегодняшнее поведение и зелёная с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): корень — клон
артели с bare `origin`; внешний проект — свой клон с bare `origin`
(`tests.sandbox.make_project_repo`). `targets.yaml` песочницы пишется
сценарием: запись внешнего проекта несёт поле `no_paths` из случайных
каталогов и файлов (имена с префиксом `zn`, вне `config.PROTECTED_PATHS`),
запись артели — случайное расхождение с `config.PROTECTED_PATHS`.

Каждый сценарий — своя задача в `in_dev` с зонами в БД, своя рабочая копия
(`workspace.ensure`), код задачи закоммичен в ветку задачи, PLAN.md `ready`
(с разделами «## Приложение» по сценарию) и SPEC.md `schema_version: 1` — в
ссылке документов автокоммитом шага (`checkpoint.commit_step_artifacts`).
Переход — `fsm.cmd_advance`; наблюдаются новые записи журнала задачи, её
состояние и вывод команды. «Переход не держит» — среди новых записей нет
отказа названного гейта: следующие гейты выхода из `in_dev` предметом не
служат.

Провалидировано временным стабом реализации (удалён, не закоммичен):
перечень проекта (`config.PROTECTED_PATHS` для артели, `no_paths` записи
иначе), гейты зон и приложений без развилки по проекту, общие зоны только
у артели, разбор приложений в самостоятельном запуске guard — все методы
зелёные.

Зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (checkpoint, config, fsm, github_adapter, idgen,
                          store, workspace)
from orchestrator.advance_gates.plan_appendix import (
    PLAN_APPENDIX_GATE_FAILURE_ACTION, PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION)
from scripts import guard
from tests.sandbox import RealGitSandbox, make_project_repo

REPO = Path(__file__).resolve().parent.parent
ARTEL = config.DEFAULT_TARGET
EXT = "vnesh"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

ZONES_ACTION = "переход отклонён: гейт зон"
PROTECTED_ACTION = "переход отклонён: защищённый путь"

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

# Профиль тестов артели — как в `targets.yaml` пульта: без него пульт
# проекту артели отказывает (fail-closed). Внешнему проекту не пишется.
ARTEL_PROFILE = """    test_profile:
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

# PLAN: фикстура гейтов выхода из in_dev

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

# SPEC: фикстура гейтов выхода из in_dev

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


def new_file_diff(rel: str, line: str) -> str:
    """Приложение, создающее файл `rel` из одной строки, — применимо к
    любому дереву, где файла `rel` нет."""
    return (f"diff --git a/{rel} b/{rel}\n"
            f"new file mode 100644\n"
            f"--- /dev/null\n"
            f"+++ b/{rel}\n"
            f"@@ -0,0 +1 @@\n"
            f"+{line}\n")


def edit_diff(rel: str, old: str, new: str) -> str:
    """Приложение, меняющее строку `old` файла `rel` из одной строки на
    `new` (заголовки без `new file`)."""
    return (f"diff --git a/{rel} b/{rel}\n"
            f"--- a/{rel}\n"
            f"+++ b/{rel}\n"
            f"@@ -1 +1 @@\n"
            f"-{old}\n"
            f"+{new}\n")


class InDevGatesSandbox(RealGitSandbox):
    """Клон артели и клон внешнего проекта; задачи в `in_dev`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        # Draft MR — обращение к форджу, которого у песочницы нет.
        for patcher in (mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                        mock.patch.object(github_adapter, "ensure_draft_mr",
                                          lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.ext_clone = make_project_repo(EXT)
        self.conn = store.db()
        # Перечень внешнего проекта: два-три каталога и один-два файла.
        self.ext_dirs = self.fresh_names(self.rng.randint(2, 3), "/")
        self.ext_files = self.fresh_names(self.rng.randint(1, 2), ".cfg")
        self.ext_no_paths = self.ext_dirs + self.ext_files
        self.artel_no_paths = list(config.PROTECTED_PATHS)
        self.write_targets()

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def fresh_names(self, count: int, suffix: str) -> list[str]:
        names: list[str] = []
        while len(names) < count:
            name = f"zn{self.word()}{suffix}"
            if name not in names and not config.is_protected_path(name):
                names.append(name)
        return names

    def under(self, entry: str) -> str:
        """Путь файла под записью перечня: каталог — файл в нём, маска
        `**/<имя>` — файл с этим именем в случайном каталоге, файл — он
        сам."""
        if entry.startswith("**/"):
            return f"zd{self.word()}/{entry[3:]}"
        if entry.endswith("/"):
            return f"{entry}{self.word()}.md"
        return entry

    def ext_protected_path(self) -> tuple[str, str]:
        """(запись `no_paths` внешнего проекта, путь под ней)."""
        entry = self.rng.choice(self.ext_no_paths)
        return entry, self.under(entry)

    def artel_only_path(self, exclude_prefixes: tuple = ()) -> tuple[str, str]:
        """(запись `config.PROTECTED_PATHS`, путь под ней) — путь не задет
        перечнем внешнего проекта."""
        entries = [e for e in config.PROTECTED_PATHS
                   if not e.startswith(exclude_prefixes)]
        entry = self.rng.choice(entries)
        return entry, self.under(entry)

    def explain(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # -------------------------------------------------------- targets.yaml

    def write_targets(self) -> None:
        """`targets.yaml` песочницы: запись артели с `self.artel_no_paths`,
        внешнего проекта — с `self.ext_no_paths`."""
        text = "targets:\n" + TARGET_ENTRY.format(
            name=ARTEL, url="http://localhost/artel", base=config.MAIN_BRANCH,
            no_paths=", ".join(self.artel_no_paths))
        text += ARTEL_PROFILE
        text += TARGET_ENTRY.format(
            name=EXT, url=f"file:///nonexistent/{EXT}",
            base=config.MAIN_BRANCH, no_paths=", ".join(self.ext_no_paths))
        config.TARGETS.write_text(text, encoding="utf-8")

    # ------------------------------------------------------- задача и ветка

    def new_task(self, target: str, zones: list[str] | None,
                 code: dict[str, str], appendices: list[str] = ()) -> str:
        """Задача `target` в `in_dev` с зонами `zones`, кодом `code`
        ({путь: текст}) в ветке и PLAN.md с приложениями `appendices`
        (тексты диффов) в ссылке документов."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-gate"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        if zones:
            store.update_task(self.conn, task_id, zones=", ".join(zones))
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
        checkpoint.commit_step_artifacts(self.conn, task_id, "developer")
        return task_id

    def code_file(self) -> tuple[str, str]:
        """(зона-каталог, файл кода в ней)."""
        zone = f"pk{self.word()}/"
        return zone, f"{zone}{self.word()}.py"

    # ------------------------------------------------------------- переход

    def advance(self, task_id: str) -> tuple[list[dict], str]:
        """(новые записи журнала задачи, вывод `advance` с текстом отказа)."""
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(task_id)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        new_rows = [dict(r) for r in store.task_steps(self.conn, task_id)
                    if r["id"] > before]
        return new_rows, buf.getvalue()

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    @staticmethod
    def with_action(rows: list[dict], action: str) -> list[dict]:
        return [r for r in rows if r["action"] == action]

    @staticmethod
    def text_of(rows: list[dict], out: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in rows) + "\n--- вывод:\n" + out


class ExternalPerimeterTest(InDevGatesSandbox):

    def test_ac1_external_task_perimeter_is_its_no_paths(self):
        """Задача внешнего проекта признаёт защищёнными ровно пути под своим `no_paths`.

        Сценарий: для каждой записи `no_paths` внешнего проекта (каталоги и
        файлы со случайными именами) — своя задача, чей код трогает путь под
        этой записью; зоны задачи покрывают и его, и файл кода. `advance` из
        `in_dev` даёт отказ «защищённый путь», называющий этот путь. Ещё две
        задачи трогают путь под случайной записью `config.PROTECTED_PATHS`
        (её нет в `no_paths` проекта), покрытый зонами: отказа «защищённый
        путь» нет.

        Ловит мутацию: перечень проекта для внешней задачи берётся из
        `config.PROTECTED_PATHS` — путь под `no_paths` не признан защищённым,
        а путь под записью пульта признан; поле `no_paths` читается не той
        записи (артели) — пути проекта не защищены.
        """
        for entry in self.ext_no_paths:
            with self.subTest(entry=entry):
                rel = self.under(entry)
                zone, code = self.code_file()
                task = self.new_task(EXT, [zone, rel], {code: "A = 1\n", rel: "x\n"})
                rows, out = self.advance(task)
                refusals = self.with_action(rows, PROTECTED_ACTION)
                self.assertTrue(refusals and rel in refusals[0]["detail"],
                                self.explain(f"{entry}: {self.text_of(rows, out)}"))
        for _ in range(2):
            entry, rel = self.artel_only_path()
            with self.subTest(entry=entry):
                zone, code = self.code_file()
                task = self.new_task(EXT, [zone, rel], {code: "A = 1\n", rel: "x\n"})
                rows, out = self.advance(task)
                self.assertEqual(self.with_action(rows, PROTECTED_ACTION), [],
                                 self.explain(f"{entry}: {self.text_of(rows, out)}"))


class ArtelPerimeterTest(InDevGatesSandbox):

    def test_ac2_artel_perimeter_is_protected_paths_read_at_call(self):
        """Перечень артели — `config.PROTECTED_PATHS` в момент вызова; поле `no_paths` записи `artel` на него не влияет.

        Сценарий: запись `artel` в `targets.yaml` расходится с
        `config.PROTECTED_PATHS` — без случайной записи пульта и с лишней
        записью `zn…/`. Задача артели трогает путь под пропущенной в
        `no_paths` записью пульта — отказ «защищённый путь». Задача артели
        трогает путь под лишней записью `no_paths` (покрыт зонами) — отказа
        «защищённый путь» нет. Затем `config.PROTECTED_PATHS` подменён
        перечнем с новой записью `zp…/`: задача, трогающая путь под ней
        (покрыт зонами), получает отказ «защищённый путь»; та же форма
        задачи без подмены отказа не получает.

        Ловит мутацию: перечень артели взят из поля `no_paths` её записи —
        путь под пропущенной записью пульта проходит, а под лишней записью
        отказывает; перечень снят снимком при загрузке модуля (значение по
        умолчанию параметра, константа модуля) — подмена
        `config.PROTECTED_PATHS` не меняет исход.
        """
        missing, missing_rel = self.artel_only_path(exclude_prefixes=("**/",))
        extra = self.fresh_names(1, "/")[0]
        self.artel_no_paths = [e for e in config.PROTECTED_PATHS if e != missing]
        self.artel_no_paths.append(extra)
        self.write_targets()

        cases = [("запись пульта, пропущенная в no_paths", missing_rel, True, None),
                 ("лишняя запись no_paths", self.under(extra), False, None)]
        added = f"zp{self.word()}/"
        added_rel = self.under(added)
        cases += [("запись, добавленная подменой PROTECTED_PATHS", added_rel, True,
                   tuple(config.PROTECTED_PATHS) + (added,)),
                  ("та же запись без подмены", added_rel, False, None)]
        for label, rel, protected, patched in cases:
            with self.subTest(case=label):
                zone, code = self.code_file()
                task = self.new_task(ARTEL, [zone, rel],
                                     {code: "A = 1\n", rel: "x\n"})
                patch = (mock.patch.object(config, "PROTECTED_PATHS", patched)
                         if patched is not None else contextlib.nullcontext())
                with patch:
                    rows, out = self.advance(task)
                refusals = self.with_action(rows, PROTECTED_ACTION)
                note = self.explain(f"{label} ({rel}): {self.text_of(rows, out)}")
                if protected:
                    self.assertTrue(refusals and rel in refusals[0]["detail"], note)
                else:
                    self.assertEqual(refusals, [], note)


class ExternalZonesGateTest(InDevGatesSandbox):

    def test_ac3_external_zones_gate_refuses_out_of_zone_and_no_paths(self):
        """Гейт зон исполняется для задачи внешнего проекта с заявленными зонами.

        Сценарий: три задачи внешнего проекта с зонами в БД. (1) Код трогает
        файл вне `zones` — отказ «переход отклонён: гейт зон», называющий
        файл, задача в `in_dev`. (2) Код трогает путь под записью `no_paths`
        (покрыт зонами) — отказ «переход отклонён: защищённый путь»,
        называющий путь, задача в `in_dev`. (3) Код трогает путь под записью
        `config.PROTECTED_PATHS`, которой нет в `no_paths`, покрытый зонами,
        — ни отказа гейта зон, ни отказа «защищённый путь».

        Ловит мутацию: развилка «внешний проект — гейт не проверяется»
        оставлена — случаи (1) и (2) проходят без отказа; гейт исполняется,
        но с перечнем пульта — случай (2) проходит, а (3) отказывает.
        """
        zone, code = self.code_file()
        stray = f"zs{self.word()}/{self.word()}.py"
        task = self.new_task(EXT, [zone], {code: "A = 1\n", stray: "B = 2\n"})
        rows, out = self.advance(task)
        refusals = self.with_action(rows, ZONES_ACTION)
        self.assertTrue(refusals and stray in refusals[0]["detail"],
                        self.explain(f"вне зон: {self.text_of(rows, out)}"))
        self.assertEqual(self.state(task), "in_dev", self.explain("вне зон"))

        entry, rel = self.ext_protected_path()
        zone, code = self.code_file()
        task = self.new_task(EXT, [zone, rel], {code: "A = 1\n", rel: "x\n"})
        rows, out = self.advance(task)
        refusals = self.with_action(rows, PROTECTED_ACTION)
        self.assertTrue(refusals and rel in refusals[0]["detail"],
                        self.explain(f"no_paths {entry}: {self.text_of(rows, out)}"))
        self.assertEqual(self.state(task), "in_dev", self.explain("no_paths"))

        entry, rel = self.artel_only_path()
        zone, code = self.code_file()
        task = self.new_task(EXT, [zone, rel], {code: "A = 1\n", rel: "x\n"})
        rows, out = self.advance(task)
        held = (self.with_action(rows, ZONES_ACTION)
                + self.with_action(rows, PROTECTED_ACTION))
        self.assertEqual(held, [], self.explain(
            f"путь пульта {entry} держит переход: {self.text_of(rows, out)}"))


class CommonZonesTest(InDevGatesSandbox):

    def common_zone_path(self) -> str:
        """Путь под случайной записью `config.COMMON_ZONES`, не защищённый
        у артели."""
        while True:
            entry = self.rng.choice(config.COMMON_ZONES)
            rel = (f"{entry}test_{self.word()}.py" if entry.endswith("/")
                   else entry)
            if not config.is_protected_path(rel):
                return rel

    def test_ac4_common_zones_cover_artel_only(self):
        """Общие зоны вне конфликта покрывают файлы задачи артели и не покрывают файлы задачи внешнего проекта.

        Сценарий: дважды случайный путь под записью `config.COMMON_ZONES`
        (не защищённый у артели) вне заявленных зон. Задача внешнего
        проекта с таким файлом — отказ «переход отклонён: гейт зон»,
        называющий файл; задача артели с тем же файлом — отказа гейта зон
        нет.

        Ловит мутацию: внешнему проекту оставлены общие зоны пульта
        (`config.COMMON_ZONES` для любого проекта) — его файл
        `orchestrator/config.py`/`tests/…` проходит вне заявленных зон;
        общие зоны отняты и у артели — её файл под общей зоной отказывает.
        """
        for _ in range(2):
            rel = self.common_zone_path()
            with self.subTest(path=rel):
                zone, code = self.code_file()
                task = self.new_task(EXT, [zone], {code: "A = 1\n", rel: "x = 1\n"})
                rows, out = self.advance(task)
                refusals = self.with_action(rows, ZONES_ACTION)
                self.assertTrue(refusals and rel in refusals[0]["detail"],
                                self.explain(f"внешний проект, {rel}: "
                                             f"{self.text_of(rows, out)}"))
                zone, code = self.code_file()
                task = self.new_task(ARTEL, [zone], {code: "A = 1\n", rel: "x = 1\n"})
                rows, out = self.advance(task)
                self.assertEqual(self.with_action(rows, ZONES_ACTION), [],
                                 self.explain(f"артель, {rel}: "
                                              f"{self.text_of(rows, out)}"))


class AppendixAdmissionTest(InDevGatesSandbox):

    def test_ac7_external_appendix_admitted_by_project_perimeter(self):
        """Приложение PLAN задачи внешнего проекта допускается по её перечню, а не по перечню пульта.

        Сценарий: задача внешнего проекта, PLAN несёт применимое приложение
        (новый файл) к пути под записью `no_paths` — ни в журнале, ни в
        выводе `advance` нет ошибки «путь … не защищённый» для этого пути, и
        отказа «приложение PLAN неприменимо» нет. Вторая задача: приложение
        к пути под записью `config.PROTECTED_PATHS`, которой нет в
        `no_paths`, — именованная ошибка `guard.appendix_unprotected_path_error`
        для этого пути в журнале или выводе, задача остаётся в `in_dev`.

        Ловит мутацию: допуск путей приложений (`guard.plan_appendices` в
        вызовах пульта) сверяет по `config.PROTECTED_PATHS` — приложение к
        `no_paths` проекта отвергнуто как «не защищённый», а к пути пульта
        допущено; вызов пульта не передаёт перечень проекта задачи.
        """
        entry, rel = self.ext_protected_path()
        zone, code = self.code_file()
        task = self.new_task(EXT, [zone], {code: "A = 1\n"},
                             [new_file_diff(rel, f"строка {self.seed}")])
        rows, out = self.advance(task)
        text = self.text_of(rows, out)
        error = guard.appendix_unprotected_path_error(rel)
        self.assertNotIn(error, text, self.explain(f"no_paths {entry}: {text}"))
        self.assertEqual(
            self.with_action(rows, PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION), [],
            self.explain(f"no_paths {entry}: {text}"))

        entry, rel = self.artel_only_path()
        zone, code = self.code_file()
        task = self.new_task(EXT, [zone], {code: "A = 1\n"},
                             [new_file_diff(rel, f"строка {self.seed}")])
        rows, out = self.advance(task)
        text = self.text_of(rows, out)
        self.assertIn(guard.appendix_unprotected_path_error(rel), text,
                      self.explain(f"путь пульта {entry}: {text}"))
        self.assertEqual(self.state(task), "in_dev", self.explain(text))

    def test_ac7_guard_cli_without_project_checks_by_protected_paths(self):
        """`python3 scripts/guard.py <PLAN.md>` без перечня проекта сверяет пути приложений по `config.PROTECTED_PATHS`.

        Сценарий: PLAN.md во временном каталоге с одним приложением (новый
        файл). Приложение к пути под случайной записью
        `config.PROTECTED_PATHS` — вывод guard не несёт ошибки
        `guard.appendix_unprotected_path_error` для этого пути. Приложение к
        пути `zn…/…` (вне перечня пульта) — вывод несёт эту ошибку для него,
        код выхода ненулевой. Запуск — отдельным процессом интерпретатора из
        корня репозитория.

        Ловит мутацию: самостоятельный запуск guard по PLAN.md не разбирает
        разделы «## Приложение» — путь вне защищённых проходит молча;
        перечень по умолчанию пуст или взят из `no_paths` записи `artel` —
        приложение к пути пульта, которого там нет, отвергается.
        """
        tmp = Path(tempfile.mkdtemp(dir=self.root / ".artel"))
        for protected in (True, False):
            if protected:
                entry, rel = self.artel_only_path(exclude_prefixes=("**/",))
            else:
                entry, rel = "вне перечня", f"zn{self.word()}/{self.word()}.md"
            with self.subTest(entry=entry):
                plan = tmp / f"PLAN-{int(protected)}.md"
                plan.write_text(PLAN_TEXT.format(
                    task=idgen.new_task_id(), appendices=APPENDIX_SECTION.format(
                        number=1, heading=self.word(),
                        diff=new_file_diff(rel, f"строка {self.seed}"))),
                    encoding="utf-8")
                res = subprocess.run([sys.executable, "scripts/guard.py", str(plan)],
                                     cwd=REPO, capture_output=True, text=True)
                text = res.stdout + res.stderr
                error = guard.appendix_unprotected_path_error(rel)
                if protected:
                    self.assertNotIn(error, text, self.explain(f"{entry}: {text}"))
                else:
                    self.assertIn(error, text, self.explain(f"{entry}: {text}"))
                    self.assertNotEqual(res.returncode, 0, self.explain(text))


class AppendixApplicabilityTest(InDevGatesSandbox):

    def test_ac8_external_appendix_applicability_gate(self):
        """Гейт применимости приложений PLAN исполняется для задачи внешнего проекта в её рабочей копии.

        Сценарий: в `main` внешнего проекта — файл `zn…/…` с одной строкой
        (путь под записью `no_paths`). Задача, чьё приложение меняет в нём
        строку, которой там нет (либо правит файл, которого нет, —
        случайно), — отказ «приложение PLAN неприменимо», задача в `in_dev`.
        Задача с применимым приложением (правка настоящей строки файла либо
        новый файл — случайно) — ни отказа «неприменимо», ни отказа гейта
        приложений по сбою git.

        Ловит мутацию: развилка «внешний проект — гейт не проверяется»
        оставлена — неприменимое приложение проходит; гейт ищет базу в клоне
        артели, а не в клоне проекта задачи — применимое приложение
        отказывает (сбой git или «неприменимо»).
        """
        folder = self.rng.choice(self.ext_dirs)
        rel = f"{folder}{self.word()}.cfg"
        line = f"исходная строка {self.word()}"
        (self.ext_clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.ext_clone / rel).write_text(line + "\n", encoding="utf-8")
        self.git("-C", str(self.ext_clone), "add", "-A")
        self.git("-C", str(self.ext_clone), "commit", "-q", "-m", "файл проекта")
        self.git("-C", str(self.ext_clone), "push", "-q", "origin",
                 config.MAIN_BRANCH)

        if self.rng.random() < 0.5:
            broken = edit_diff(rel, f"нет такой строки {self.word()}", "правка")
        else:
            broken = edit_diff(f"{folder}{self.word()}.cfg", "нет файла", "правка")
        zone, code = self.code_file()
        task = self.new_task(EXT, [zone], {code: "A = 1\n"}, [broken])
        rows, out = self.advance(task)
        self.assertTrue(
            self.with_action(rows, PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION),
            self.explain(f"неприменимое: {self.text_of(rows, out)}"))
        self.assertEqual(self.state(task), "in_dev", self.explain("неприменимое"))

        if self.rng.random() < 0.5:
            good = edit_diff(rel, line, f"правка {self.word()}")
        else:
            good = new_file_diff(f"{folder}{self.word()}.cfg", "новый файл")
        zone, code = self.code_file()
        task = self.new_task(EXT, [zone], {code: "A = 1\n"}, [good])
        rows, out = self.advance(task)
        held = (self.with_action(rows, PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION)
                + self.with_action(rows, PLAN_APPENDIX_GATE_FAILURE_ACTION))
        self.assertEqual(held, [], self.explain(
            f"применимое: {self.text_of(rows, out)}"))


if __name__ == "__main__":
    unittest.main()
