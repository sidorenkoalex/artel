"""AC-3, AC-8 (SPEC 01M1VBEFR987MGAK0XAFMVVYZY): команда `zones-extend
<id> <путь>[, <путь>]` создаёт ANSWER-n с маркером «Расширение зон
разрешено: <пути>» и текстом «мандат Оператора: <пути>». Если PLAN.md
ветки задачи уже несёт раздел «Расширение зон» с теми же путями —
команда сразу обновляет `tasks.zones_extension` (после чего гейт зон
`in_dev -> review` пропускает файлы этих путей). Если раздела с такими
путями в PLAN.md нет — `zones_extension` не трогается, а журнал несёт
запись «раздел PLAN отсутствует — разработчик добавит на следующем
шаге». AC-8 — те же два сценария, явно поставленные SPEC как тест этого
критерия.

Красен до реализации: команды `zones-extend` сегодня нет ни в диспетчере
`orchestrator/artel.py::main()` (`table.get("zones-extend")` даёт
`None`), ни в каком-либо другом модуле — любой вызов через
`_sandbox.TaskSandbox.run_cli` падает `SystemExit`
(«Неизвестная команда zones-extend») до того, как дойдёт до сценария,
который проверяет тест.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm, fsm_advance  # noqa: E402
from tests.sandbox import capture  # noqa: E402
from _sandbox import PLAN_MD, PLAN_WITH_ZONES_EXTENSION, TaskSandbox  # noqa: E402

MANDATE_MARKER = "Расширение зон разрешено:"
OPERATOR_MANDATE_TEXT = "мандат Оператора:"


class Ac3ZonesExtendCreatesAnswerTest(TaskSandbox):

    def setUp(self):
        super().setUp()
        self.set_state("in_dev")

    def test_ac3_creates_answer_with_marker_and_operator_mandate_text(self):
        """`zones-extend <id> docs/extra_module.md` — ANSWER-1.md
        обязан появиться на артефактной ветке и нести ОБЕ строки: маркер
        «Расширение зон разрешено: docs/extra_module.md» (тот же формат,
        что уже разбирает `fsm_advance._answer_zones_mandate`) и текст
        «мандат Оператора: docs/extra_module.md» — дословно из AC-3.

        Ловит мутацию: команда пишет только маркер (без текста «мандат
        Оператора: ...») либо только текст (без строки-маркера,
        распознаваемой гейтом зон) — половина требования AC-3 тихо
        теряется, хотя сам факт создания ANSWER-файла остаётся верным."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)},
            "PLAN")

        self.run_cli("zones-extend", self.TASK, "docs/extra_module.md")

        self.assertIn(f"tasks/{self.TASK}/ANSWER-1.md",
                      self.artifact_branch_files())
        text = self.artifact_branch_text(f"tasks/{self.TASK}/ANSWER-1.md")
        self.assertIn(f"{MANDATE_MARKER} docs/extra_module.md", text)
        self.assertIn(f"{OPERATOR_MANDATE_TEXT} docs/extra_module.md", text)

    def test_ac3_multiple_comma_separated_paths_are_all_recorded_in_marker(self):
        """Синтаксис SPEC `<путь>[, <путь>]` — больше одного пути через
        запятую (тот же CSV-формат, что `zones:`/`Пути:`/маркер мандата
        везде в системе) — маркер ANSWER обязан нести ОБА пути, не только
        первый.

        Ловит мутацию: команда берёт только `paths.split(",")[0]` (или
        иначе теряет хвост списка при построении маркера) — второй путь
        мандата тихо пропадает, и гейт зон не признает его расширенным."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)},
            "PLAN")

        self.run_cli("zones-extend", self.TASK, "docs/a.md, docs/b.md")

        text = self.artifact_branch_text(f"tasks/{self.TASK}/ANSWER-1.md")
        marker_line = next(
            line for line in text.splitlines()
            if line.strip().startswith(MANDATE_MARKER))
        paths = fsm_advance._split_zone_paths(
            marker_line.strip()[len(MANDATE_MARKER):])
        self.assertEqual(paths, ["docs/a.md", "docs/b.md"])

    def test_ac3_matching_plan_section_updates_zones_extension_immediately(self):
        """PLAN.md ветки уже несёт раздел «## Расширение зон» с ТЕМ ЖЕ
        путём — `zones-extend` обязана СРАЗУ (без ожидания следующего
        `advance`) записать путь в `tasks.zones_extension`.

        Ловит мутацию: команда только создаёт ANSWER, не читая PLAN.md
        вовсе — `zones_extension` остался бы пустым даже при точном
        совпадении путей, и Оператору пришлось бы ждать отдельного
        `advance`, чтобы существующий гейт зон подхватил мандат сам
        (именно тот лишний шаг, который AC-3 обязана убрать)."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_WITH_ZONES_EXTENSION.format(
                task=self.TASK, paths="docs/extra_module.md",
                justification="Нужен отдельный модуль документации.")},
            "PLAN")

        self.run_cli("zones-extend", self.TASK, "docs/extra_module.md")

        self.assertIn("docs/extra_module.md", self.row()["zones_extension"] or "")

    def test_ac3_no_matching_plan_section_leaves_zones_extension_untouched(self):
        """PLAN.md ветки не несёт раздела «## Расширение зон» вовсе —
        `zones_extension` НЕ трогается, а журнал несёт ровно строку
        «раздел PLAN отсутствует — разработчик добавит на следующем
        шаге» (дословно из AC-3).

        Ловит мутацию: команда пишет в `zones_extension` безусловно, не
        сверяясь с PLAN.md — Оператор получил бы расширение зоны без
        единого зафиксированного обоснования в PLAN, ломая инвариант
        «расширение зоны обосновано в PLAN» (SPEC «Контекст» исходной
        задачи 01M1P9QCHPHSCEA6TK13PV85SP)."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)},
            "PLAN")

        self.run_cli("zones-extend", self.TASK, "docs/extra_module.md")

        self.assertFalse(self.row()["zones_extension"])
        self.assertTrue(
            any("раздел PLAN отсутствует — разработчик добавит на "
               "следующем шаге" in d for d in self.journal_details()),
            f"журнал: {self.journal_details()}")


class Ac8ZonesExtendGateAndJournalTest(TaskSandbox):
    """AC-8 дословно: тест на `zones-extend`, требуемый SPEC как отдельный
    критерий — тот же сценарий, что AC-3, плюс явная проверка того, что
    гейт зон `in_dev -> review` после обновления `zones_extension`
    реально пропускает дифф по расширенным путям."""

    def test_ac8_matching_plan_section_lets_zones_gate_pass_diff_on_extended_path(self):
        """`zones-extend` применила мандат (PLAN несёт раздел «##
        Расширение зон» с тем же путём) — дифф ветки задачи, трогающий
        РОВНО этот путь (вне заявленных `zones`), обязан пройти переход
        `in_dev -> review` без отдельного ANSWER/PLAN шага на самом
        `advance`.

        Ловит мутацию: `zones-extend` пишет `zones_extension` в базу, но
        не тем же форматом, что читает гейт (`fsm_advance.
        _split_zone_paths`/`_touches_zone`) — например, с лишними
        пробелами или в другом регистре пути — гейт зон отказал бы
        переход, несмотря на «мгновенно обновлённый» `zones_extension`."""
        self.enter_in_dev(zones="orchestrator/store.py")
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_WITH_ZONES_EXTENSION.format(
                task=self.TASK, paths="docs/extra_module.md",
                justification="Нужен отдельный модуль документации.")},
            "PLAN")

        self.run_cli("zones-extend", self.TASK, "docs/extra_module.md")
        self.commit_code_file("docs/extra_module.md", "содержимое\n")
        capture_out = capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "review",
            f"гейт зон обязан пропустить путь, добавленный zones-extend "
            f"— вывод advance: {capture_out}")

    def test_ac8_missing_plan_section_journal_and_no_zones_extension_change(self):
        """Без раздела «## Расширение зон» в PLAN.md — `zones_extension`
        не меняется, журнал несёт запись «раздел PLAN отсутствует»
        (тот же сценарий, что AC-3, поставленный AC-8 как отдельный
        обязательный тест этого критерия).

        Ловит мутацию: сверка PLAN.md пропущена (например, замена на
        безусловное «раздела нет» без реального чтения ветки) — тест
        неотличим бы от совпадения по СЛУЧАЙНОЙ причине (PLAN.md ещё не
        закоммичен вовсе), а не по осознанной сверке содержимого."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)},
            "PLAN")

        self.run_cli("zones-extend", self.TASK, "docs/extra_module.md")

        self.assertFalse(self.row()["zones_extension"])
        self.assertTrue(
            any("раздел PLAN отсутствует" in d for d in self.journal_details()))


if __name__ == "__main__":
    unittest.main()
