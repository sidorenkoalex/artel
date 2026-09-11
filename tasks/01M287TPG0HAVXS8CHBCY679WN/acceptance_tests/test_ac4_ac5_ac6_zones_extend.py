"""Приёмочные тесты AC-4/AC-5/AC-6 задачи 01M287TPG0HAVXS8CHBCY679WN:
новая команда `zones-extend <id> <путь>[, <путь>]` (SPEC, требование 2).

Красен до реализации: `zones-extend` не зарегистрирована в диспетчере
`orchestrator/artel.py::main` (таблица `table` не несёт ключ
`"zones-extend"`) — `artel.main()` с этой командой падает `sys.exit`
«Неизвестная команда» на КАЖДОМ из тестов ниже, ещё до какой-либо
логики зон.

Через CLI (`artel.main()` с подменённым `sys.argv`), не через прямой
вызов внутренней функции — SPEC называет только командную форму
`zones-extend <id> <путь>[, <путь>]`, конкретное имя реализующей
функции документ не фиксирует (та же логика, что уже применяет
`tests/test_analyst_role.py::CliParsingTest`/`tests/test_invariants.py`
для команд, у которых важен именно интерфейс CLI). Настоящий git
(`RealGitSandbox`) — команда коммитит `ANSWER-n.md` плотницки в
артефактную ветку пульта, тем же приёмом, что `answer` (см. `tests/
test_answer.py`), а AC-5 сверх того обязана провести настоящий `git
diff` через гейт зон (`fsm_advance._zones_gate_refuses`), заглушкой это
не изобразить.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artel, artifact_branch, catalog, fsm_advance,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402

PLAN_WITH_EXTENSION_SECTION = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: сценарий zones-extend

## Подход

## Шаги

## Покрытие требований

## Влияние на систему

## Расширение зон

Пути: {paths}

Обоснование: правка затрагивает путь вне заявленных zones.
"""


class _ZonesExtendSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "zones-extend: мандат Оператора")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def artifact_branch_files(self) -> list:
        return gitcmd.ls_tree_files(self.branch, f"tasks/{self.TASK}") or []

    def artifact_text(self, rel: str) -> str | None:
        text, _reason = gitcmd.show(self.branch, rel)
        return text

    def journal_texts(self) -> list:
        return [f"{s['action']} {s['detail']}"
               for s in store.task_steps(self.conn, self.TASK)]

    def run_zones_extend(self, paths_arg: str) -> str:
        argv = ["artel.py", "zones-extend", self.TASK, paths_arg]
        with mock.patch.object(sys, "argv", argv):
            return capture(artel.main)


class Ac4ZonesExtendCommitsMandateAnswerTest(_ZonesExtendSandbox):
    """AC-4."""

    def test_ac4_commits_answer_with_marker_line_and_mandate_text(self):
        """`zones-extend <id> <путь1>, <путь2>` коммитит в артефактную
        ветку задачи `ANSWER-n.md` со строкой маркера «Расширение зон
        разрешено: <пути>» и текстом «мандат Оператора: <пути>».

        Ловит мутацию: команда пишет только текст «мандат Оператора:
        ...», без самой строки маркера (`fsm_advance._ZONES_MANDATE_
        MARKER`) — `_answer_zones_mandate` никогда не увидит этот
        мандат при разборе ANSWER-файлов.
        """
        self.run_zones_extend("docs/a.md, docs/b.md")

        rel = f"tasks/{self.TASK}/ANSWER-1.md"
        self.assertIn(rel, self.artifact_branch_files())
        text = self.artifact_text(rel)
        self.assertIsNotNone(text, f"{rel} не прочитан с артефактной ветки")

        marker_line = next(
            (line for line in text.splitlines()
             if line.strip().startswith(fsm_advance._ZONES_MANDATE_MARKER)),
            None)
        self.assertIsNotNone(
            marker_line, f"нет строки маркера «{fsm_advance._ZONES_MANDATE_MARKER}» "
            f"в {rel}:\n{text}")
        marker_paths = fsm_advance._split_zone_paths(
            marker_line.split(":", 1)[1])
        self.assertEqual(marker_paths, ["docs/a.md", "docs/b.md"])

        self.assertIn("мандат Оператора:", text)
        mandate_line = next(
            (line for line in text.splitlines()
             if "мандат Оператора:" in line), None)
        self.assertIsNotNone(mandate_line, f"нет текста мандата в {rel}:\n{text}")
        mandate_paths = fsm_advance._split_zone_paths(
            mandate_line.split("мандат Оператора:", 1)[1])
        self.assertEqual(mandate_paths, ["docs/a.md", "docs/b.md"])


class Ac5ZonesExtendMatchingPlanSectionTest(_ZonesExtendSandbox):
    """AC-5."""

    def setUp(self):
        super().setUp()
        store.update_task(self.conn, self.TASK, zones="orchestrator/store.py")
        sha = artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/PLAN.md": PLAN_WITH_EXTENSION_SECTION.format(
                task=self.TASK, paths="docs/extra.md")},
            f"{self.TASK}: PLAN с разделом «Расширение зон»")
        self.assertTrue(sha, "PLAN.md не закоммичен в артефактную ветку")

    def test_ac5_matching_plan_section_updates_zones_extension_immediately(self):
        """PLAN.md головы артефактной ветки уже несёт раздел «##
        Расширение зон» со строкой `Пути:`, перечисляющей РОВНО те же
        пути, что переданы команде — `zones-extend` сразу обновляет
        `tasks.zones_extension` этими путями, без ожидания следующего
        гейта.

        Ловит мутацию: сверка путей PLAN с аргументом команды подменена
        на «раздел просто есть» (без сравнения множеств) — обновление
        срабатывало бы и на несовпадающих путях (проверяется отдельно,
        AC-6), либо не срабатывало бы вовсе на совпадающих.
        """
        self.run_zones_extend("docs/extra.md")

        self.assertEqual(self.row()["zones_extension"], "docs/extra.md")

    def test_ac5_gate_passes_extended_path_diff_without_a_separate_answer_call(self):
        """После немедленного обновления `tasks.zones_extension`
        последующий гейт зон (`in_dev -> review`) пропускает дифф,
        трогающий путь `docs/extra.md`, — без отдельного вызова
        `answer`: сама команда `zones-extend` уже легализовала путь.

        Ловит мутацию: `zones-extend` пишет мандат ТОЛЬКО в ANSWER-файл
        (AC-4), но не обновляет `tasks.zones_extension` в обход
        требования AC-5 — гейт видит `docs/extra.md` вне `declared`
        (`zones` + `zones_extension` + `COMMON_ZONES`) и продолжает
        отказывать, пока Оператор не проведёт файл через отдельный
        механизм расширения (регресс к трёхшаговому флоу, который эта
        задача устраняет).
        """
        self.run_zones_extend("docs/extra.md")

        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        (wt_path / "docs").mkdir(parents=True, exist_ok=True)
        (wt_path / "docs" / "extra.md").write_text("контент\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(wt_path), "add", "docs/extra.md"],
                       check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(wt_path), "commit", "-q", "-m",
             f"{self.TASK}: docs/extra.md"],
            check=True, capture_output=True)

        t = self.row()
        plan_text = self.artifact_text(f"tasks/{self.TASK}/PLAN.md")
        refuses = fsm_advance._zones_gate_refuses(
            self.conn, self.TASK, t, self.code_branch, plan_text)

        self.assertFalse(
            refuses, "гейт зон обязан пропустить дифф docs/extra.md без "
            "отдельного вызова answer, раз zones-extend уже обновил "
            "tasks.zones_extension")


class Ac6ZonesExtendPlanMismatchLeavesDbUntouchedTest(_ZonesExtendSandbox):
    """AC-6."""

    def test_ac6_no_plan_section_at_all_leaves_zones_extension_untouched(self):
        """Раздела «## Расширение зон» в PLAN.md нет вовсе (PLAN.md либо
        вовсе не закоммичен, либо не несёт раздела) — `tasks.
        zones_extension` не меняется, в журнал пишется запись «раздел
        PLAN отсутствует — разработчик добавит на следующем шаге».

        Ловит мутацию: команда обновляет `tasks.zones_extension` по
        аргументам вызова БЕЗУСЛОВНО, не сверяясь с PLAN.md вовсе —
        AC-6 отличило бы это от AC-5 только по журналу, а поле БД
        менялось бы в обоих случаях одинаково.
        """
        before = self.row()["zones_extension"]

        self.run_zones_extend("docs/extra.md")

        self.assertEqual(self.row()["zones_extension"], before)
        texts = self.journal_texts()
        self.assertTrue(
            any("раздел PLAN отсутствует" in t for t in texts),
            f"нет записи о недостающем разделе PLAN в журнале: {texts}")

    def test_ac6_plan_section_with_different_paths_leaves_zones_extension_untouched(self):
        """PLAN.md несёт раздел «## Расширение зон», но его пути НЕ
        совпадают с переданными команде — тот же отказ обновления, что и
        при отсутствующем разделе (журнал «раздел PLAN отсутствует —
        разработчик добавит на следующем шаге»).

        Ловит мутацию: сверка путей — по пересечению множеств
        (`set & set`) вместо точного равенства — частично совпадающий,
        но не идентичный список путей PLAN ошибочно принимался бы как
        подтверждение AC-5.
        """
        sha = artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/PLAN.md": PLAN_WITH_EXTENSION_SECTION.format(
                task=self.TASK, paths="docs/other.md")},
            f"{self.TASK}: PLAN с несовпадающим разделом")
        self.assertTrue(sha, "PLAN.md не закоммичен в артефактную ветку")
        before = self.row()["zones_extension"]

        self.run_zones_extend("docs/extra.md")

        self.assertEqual(self.row()["zones_extension"], before)
        texts = self.journal_texts()
        self.assertTrue(
            any("раздел PLAN отсутствует" in t for t in texts),
            f"нет записи о недостающем разделе PLAN в журнале: {texts}")


if __name__ == "__main__":
    unittest.main()
