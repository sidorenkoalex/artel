"""Общая песочница приёмочных тестов задачи 01M1P9QCHPHSCEA6TK13PV85SP
(«Механика зон, часть 3: сверка диффа с зонами при переходе in_dev ->
review»).

Не сканируется guard'ом на AC-маркеры/тест-методы (только test_*.py,
SPEC T081) — файлы test_ac*.py этого каталога делят с ним фикстуры,
тем же приёмом, что `_sandbox.py` соседних задач (например
tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/_sandbox.py,
`GateSandbox`, чей каркас `in_dev -> review` через `fsm.cmd_advance`
эта песочница повторяет дословно).

Часть 1 нарезки (01M1NKVPD2A79PQ6K0JVV1B2Q1) на момент написания этой
планки одобрена ревью, но ещё не смержена в main (SPEC, «Контекст») —
колонка `zones` таблицы `tasks` и `orchestrator/config.COMMON_ZONES` в
текущем дереве не существуют. Песочница не ждёт мержа: колонка
добавляется тем же идемпотентным `store.add_column`, которым часть 1
сама её заведёт в `store.migrate` (вызов `add_column(conn, "tasks",
"zones", "TEXT")` — безопасно и до, и после мержа), а `COMMON_ZONES`
подставляется `mock.patch.object(..., create=True)` с ТЕМИ ЖЕ четырьмя
путями, что несёт готовая реализация части 1 (ветка
`task/01m1nkvpd2a79pq6k0jvv1b2q1-mekhanika-zon-mashinochitaemye`,
коммит d3590a01: `orchestrator/config.py::COMMON_ZONES`) — после мержа
части 1 патч продолжает работать (`create=True` не мешает патчить уже
существующий атрибут), тест не зависит от точного момента мержа.
"""
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import brief, catalog, config, fsm, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import (TmpRootTest, capture, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git)

# Состав части 1 нарезки (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-4) — точные
# четыре пути уже зафиксированы её собственной приёмочной планкой
# (test_ac4_common_zones_named_list.py) и её юнит-тестом
# (tests/test_guard_zones.py::CommonZonesDeclarationTest); эта задача
# только читает список, не определяет его.
COMMON_ZONES = ("orchestrator/config.py", "docs/codebase-map.md", "tests/",
               "roles.yaml")

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сверка диффа с зонами

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

# AC-3 (ANSWER-1.md Оператора этой задачи, вариант (b) уточнённый):
# раздел PLAN.md «## Расширение зон» со строкой «Пути: <путь1>, <путь2>»
# — тот же приём через запятую, что поле `zones:` части 1.
PLAN_WITH_ZONES_EXTENSION = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сверка диффа с зонами

## Подход

## Шаги

## Покрытие требований

## Влияние на систему

## Расширение зон

Пути: {paths}

{justification}
"""

# AC-3 (ANSWER-1.md, п.2): мандат Оператора — строка в любом ANSWER-n.md
# задачи, начинающаяся с маркера «Расширение зон разрешено:», далее
# список путей через запятую.
ANSWER_WITH_ZONES_MANDATE = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

## Ответы

Расширение зон разрешено: {paths}
"""


def _diff_git_header(path: str) -> str:
    """Один синтетический hunk unified diff для `path` — заголовок
    `diff --git a/<path> b/<path>` присутствует в обоих правдоподобных
    способах получить список тронутых файлов (полный текст diff,
    `review.git_diff_part`, ИЛИ построчный список имён, `gitcmd.
    diff_names` — см. `ZonesGateSandbox.advance_with_diff_files`)."""
    return (f"diff --git a/{path} b/{path}\n"
           f"index 0000000..1111111 100644\n"
           f"--- a/{path}\n"
           f"+++ b/{path}\n"
           f"@@ -0,0 +1 @@\n+x\n")


class ZonesGateSandbox(TmpRootTest):
    """Задача в `in_dev` с готовым PLAN.md и объявленными `zones` —
    переход `in_dev -> review` через `fsm.cmd_advance` (тот же каркас
    настройки, что `tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/
    _sandbox.py::GateSandbox`)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")

        self.wt_path = self.root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        with mock.patch.object(gitcmd, "git", fake_git):
            self.capture(catalog.cmd_init)
            _, self.TASK = capture_new_task_id(catalog.cmd_new, "Сверка зон")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]

        # Часть 1 (01M1NKVPD2A79PQ6K0JVV1B2Q1) — колонка `zones`;
        # идемпотентно, работает и до, и после её мержа в main (см.
        # докстринг модуля).
        store.add_column(store.db(), "tasks", "zones", "TEXT")

        common_zones_patcher = mock.patch.object(
            config, "COMMON_ZONES", COMMON_ZONES, create=True)
        common_zones_patcher.start()
        self.addCleanup(common_zones_patcher.stop)

        # AC-3: мандат Оператора живёт в ANSWER-n.md, обнаруживаемых
        # перебором `gitcmd.ls_tree_files` (тот же узел, что уже несёт
        # `orchestrator/fsm.py::_answer_file_count`) — `fake_git` в
        # `advance_with_diff_files` не отвечает на подкоманду `ls-tree`
        # содержательно (генерик-ветка отдаёт пустую строку), поэтому
        # без прямого патча ЛЮБАЯ реализация, читающая список ANSWER-*.md
        # тем же путём, что и существующий гейт возврата из эскалации,
        # видела бы ноль файлов и не нашла бы мандат никогда — тест AC-3
        # был бы недостижимо красным даже при верной реализации. Патч —
        # тот же приём, что `tests/test_answer_gate.py` (`disk_backed_show`/
        # `disk_backed_ls_tree_files` поверх `gitcmd.show`/`ls_tree_files`
        # напрямую, в обход `gitcmd.git`).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

    def task_row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def set_zones(self, zones: str) -> None:
        store.update_task(store.db(), self.TASK, zones=zones)

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def write_plan_with_zones_extension(
            self, paths: str, justification: str = "Обоснование расширения зон.") -> None:
        """PLAN.md с разделом `## Расширение зон` (ANSWER-1.md, п.1):
        строка `Пути: <paths>` (через запятую, как `zones:` части 1) и
        свободный текст обоснования ниже."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_WITH_ZONES_EXTENSION.format(
                task=self.TASK, paths=paths, justification=justification),
            encoding="utf-8")

    def write_answer_mandate(self, n: int, paths: str) -> None:
        """ANSWER-{n}.md с маркером `Расширение зон разрешено: <paths>`
        (ANSWER-1.md, п.2) — единственная строка, которую код обязан
        разобрать по префиксу; свободный текст ANSWER не анализируется."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / f"ANSWER-{n}.md").write_text(
            ANSWER_WITH_ZONES_MANDATE.format(task=self.TASK, n=n, paths=paths),
            encoding="utf-8")

    def zones_extension(self):
        """Значение колонки `tasks.zones_extension` (ANSWER-1.md, п.3) —
        `sqlite3.Row` кидает `IndexError` на отсутствующей колонке, что
        ДО реализации этой задачи корректно (колонку заводит миграция
        задачи, тем же приёмом, что и `zones` части 1)."""
        return self.task_row()["zones_extension"]

    def _set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def advance_with_diff_files(self, files: list, write_plan: bool = True) -> str:
        """Прогон `advance` из `in_dev` с диффом ветки, трогающим ровно
        `files`; ветка не отстала от main (`commits_behind` = 0) —
        подтяжка не звонится. `git_stub` отвечает и на построчный
        список файлов (`git diff --name-only main branch --`,
        `gitcmd.diff_names` — уже используется этим же переходом для
        лока `acceptance_tests/`), и на полный текстовый diff
        (`git diff main...branch`, `review.git_diff_part` — уже
        используется гейтом ёмкости на этом же переходе) синтетическим
        содержимым с теми же файлами: какой из двух способов получения
        списка файлов выберет реализация зон, заранее не известно, а
        оба уже используются существующим кодом того же перехода.

        `write_plan=False` (AC-3) — PLAN.md уже написан вызывающим кодом
        (`write_plan_with_zones_extension`) до этого вызова; писать поверх
        него стандартный PLAN_READY стёрло бы раздел «## Расширение
        зон»."""
        if write_plan:
            self.write_plan_ready()
        self._set_state("in_dev")
        full_diff = "".join(_diff_git_header(f) for f in files)

        def git_stub(*args):
            if args and args[0] == "diff":
                joined = " ".join(args)
                if config.MAIN_BRANCH in joined and self.branch in joined:
                    if "--name-only" in args:
                        return subprocess.CompletedProcess(
                            list(args), 0, "\n".join(files), "")
                    return subprocess.CompletedProcess(
                        list(args), 0, full_diff, "")
            return fake_git(*args)

        with mock.patch.object(gitcmd, "git", git_stub), \
                mock.patch.object(gitcmd, "commits_behind", return_value=0):
            return capture(fsm.cmd_advance, self.TASK)
