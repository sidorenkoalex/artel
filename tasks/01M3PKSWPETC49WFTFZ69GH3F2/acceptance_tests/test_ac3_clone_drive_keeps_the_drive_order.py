"""AC-3 — 01M3PKSWPETC49WFTFZ69GH3F2: процесс клона ведёт задачу тем же
порядком, что `_drive_task` до этой задачи.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Процесс клона ведёт задачу тем же порядком, что `_drive_task` до
этой задачи: проход `spec_gate`/`acceptance`/`verifying` помощниками
гейтов, синтетический ответ на эскалацию, однократный подъём потолка,
потолок повторов developer, kill на `merge_gate` — каждый из этих
исходов, проверявшийся существующими тестами канарейки, проверяется и
после переписывания.

Каждый исход прогоняется настоящим `canary.cmd_canary` через процесс клона
(`_clone_drive.py`): подмена `auto.cmd_auto` в коде проверяемого коммита
изображает шаги ролей по сценарию, всё остальное — гейты, синтетический
ANSWER, подъём потолка, повторы developer, kill — делает код ведения
клона. Исход читается из вывода пульта (выдержка журнала и строка сводки,
которые пульт печатает по результату процесса клона) и из строки
`canary_runs`. Тексты `detail` переходов и причин снятия — сегодняшние
тексты помощников гейтов `orchestrator/canary.py`: требование 1 SPEC
велит вести теми же помощниками, и именно по этим строкам Оператор читает
отчёт прогона. Потолки — от `config`, не литералами.

Переписанные тесты `tests/` (требование 8) — отдельно, их полнота по
PLAN сверяется AC-11.

Красен до реализации: ведение идёт в процессе пульта — прогон упирается в
растяжку песочницы на `catalog.cmd_new`, процесса клона нет, ни выдержки
журнала, ни строки `canary_runs` прогон не даёт.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402
from orchestrator import canary, config  # noqa: E402


class _DriveOrderTest(_clone_drive.CloneDriveSandbox):

    SCENARIO = None

    def setUp(self):
        super().setUp()
        self.mark = self.new_marker("метка")
        self.target = self.commit_code(self.SCENARIO, self.mark)
        self.run_canary(self.target)
        self.assert_no_crash()
        self.assert_no_pult_drive()
        rows = self.canary_rows()
        self.assertEqual(len(rows), 1,
                         f"строк canary_runs: {len(rows)} (зерно {self.seed})\n"
                         f"{self.output}")
        self.row = rows[0]
        self.summary = self.summary_line(self.row["task_id"])

    def transitions(self) -> list:
        """(состояние, текст записи) переходов выдержки журнала по порядку."""
        found = []
        for line in self.output.splitlines():
            if ": state -> " not in line:
                continue
            tail = line.split(": state -> ", 1)[1]
            found.append((tail.split(" ", 1)[0], tail))
        return found


class GatesAndSyntheticAnswerTest(_DriveOrderTest):
    """Шаги ролей: spec_writing -> spec_gate, tests_writing -> verifying,
    review -> escalated, review -> acceptance."""

    SCENARIO = _clone_drive.SCENARIO_GATES

    def test_ac3_gates_and_synthetic_answer_in_the_old_order(self):
        """Задача, которую роли по очереди приводят на `spec_gate`, `verifying`,
        в `escalated` и на `acceptance`, проходит их помощниками гейтов в
        прежнем порядке и снимается штатным kill на `merge_gate`.

        Выдержка журнала несёт по порядку: проход гейта SPEC в
        `tests_writing` (SPEC шаблона несёт AC-разметку), синтетический проход
        `verifying` в `review`, возврат из эскалации синтетическим ANSWER в
        `review`, проход приёмки в `merge_gate` и `killed`; строка сводки —
        «исход=killed (штатно)», одна эскалация, test_author посещён.

        Ловит мутацию: процесс клона ведёт задачу своим упрощённым циклом, в
        котором `verifying` не проходится синтетически (задача остаётся в
        `verifying` либо снимается там), эскалация закрывается без ANSWER
        или приёмка ведёт мимо `_pass_acceptance_gate` — выдержка журнала не
        несёт соответствующего перехода либо несёт его не в том порядке.
        """
        got = self.transitions()
        expected = [
            ("tests_writing", "гейт SPEC пройден автоматически"),
            ("review", "verifying пройден синтетически"),
            ("review", "эскалация закрыта синтетическим ANSWER"),
            ("merge_gate", "приёмка пройдена автоматически"),
            ("killed", ""),
        ]
        cursor = 0
        for state, text in got:
            if cursor < len(expected) and state == expected[cursor][0] \
                    and expected[cursor][1] in text:
                cursor += 1
        self.assertEqual(
            cursor, len(expected),
            f"порядок ведения нарушен: найдено {cursor} из {len(expected)} "
            f"ожидаемых переходов {expected}; переходы выдержки {got} "
            f"(зерно {self.seed})\n{self.output}")
        self.assertIn("исход=killed (штатно)", self.summary)
        self.assertIn("эскалаций=1", self.summary)
        self.assertIn("test_author=да", self.summary)


class BudgetCeilingRaisedOnceTest(_DriveOrderTest):
    """Шаг роли каждый раз эскалирует по бюджету."""

    SCENARIO = _clone_drive.SCENARIO_BUDGET

    def test_ac3_budget_escalation_raises_the_ceiling_once_then_exhausts(self):
        """Первая бюджетная эскалация закрывается однократным подъёмом потолка
        (строка подъёма — в отчёте прогона, задача возвращается синтетическим
        ANSWER), вторая снимает задачу исходом «исчерпан потолок задачи» с
        вердиктом строки `canary_runs` `canary.VERDICT_CEILING_EXHAUSTED`.

        Ловит мутацию: процесс клона закрывает бюджетную эскалацию обычным
        синтетическим ANSWER без подъёма потолка (строки подъёма в отчёте
        нет, задача снимается «не сходится» с вердиктом `red`) либо
        поднимает потолок повторно (второй эскалации не хватает для снятия,
        исход не «исчерпан потолок задачи»).
        """
        self.assertIn("потолок канареечной задачи поднят однократно", self.output,
                      f"строки подъёма потолка нет (зерно {self.seed})\n{self.output}")
        self.assertIn("исчерпан потолок задачи", self.summary)
        self.assertEqual(self.row["verdict"], canary.VERDICT_CEILING_EXHAUSTED)
        self.assertEqual(self.row["escalations"], 2)
        backs = [t for s, t in self.transitions()
                 if "эскалация закрыта синтетическим ANSWER" in t]
        self.assertEqual(len(backs), 1,
                         f"возвратов из эскалации: {len(backs)}\n{self.output}")


class EscalationCapTest(_DriveOrderTest):
    """Шаг роли каждый раз эскалирует по вопросу, не по бюджету."""

    SCENARIO = _clone_drive.SCENARIO_ESCALATION_CAP

    def test_ac3_repeated_escalations_are_capped(self):
        """Каждая эскалация закрывается синтетическим ANSWER, пока их не больше
        `config.CANARY_MAX_ESCALATION_CYCLES`; следующая снимает задачу как
        «не сошлась» с числом повторных эскалаций в причине, вердикт — не
        `green`.

        Ловит мутацию: процесс клона не держит потолок повторных эскалаций
        (задача крутится до другого предела — число возвратов синтетическим
        ANSWER больше потолка, причины «повторных эскалаций подряд» в
        сводке нет) либо считает его со сдвигом на единицу.
        """
        cap = config.CANARY_MAX_ESCALATION_CYCLES
        backs = [t for s, t in self.transitions()
                 if "эскалация закрыта синтетическим ANSWER" in t]
        self.assertEqual(len(backs), cap,
                         f"возвратов синтетическим ANSWER {len(backs)}, потолок "
                         f"{cap} (зерно {self.seed})\n{self.output}")
        self.assertIn(f"не сошлась: canary: {cap} повторных эскалаций подряд",
                      self.summary)
        self.assertEqual(self.row["escalations"], cap + 1)
        self.assertNotEqual(self.row["verdict"], "green")


class DeveloperRetryCapTest(_DriveOrderTest):
    """Шаг роли уводит задачу в in_dev, затем каждый раз журналирует отказ
    advance по красной приёмочной планке."""

    SCENARIO = _clone_drive.SCENARIO_DEV_RETRY

    def test_ac3_developer_retries_on_red_plank_are_capped(self):
        """Отказ `in_dev` по красной планке даёт developer повторный шаг, пока
        повторов не больше `config.CANARY_MAX_DEV_RETRIES`; следующий отказ
        снимает задачу как «не сошлась» с причиной о повторах developer, а
        сводка несёт их число.

        Ловит мутацию: процесс клона не повторяет developer на красной
        планке (задача снимается прежней стагнацией или ведётся дальше —
        «повторов developer=» не равно потолку, причины о красной планке
        нет) либо держит потолок со сдвигом на единицу.
        """
        cap = config.CANARY_MAX_DEV_RETRIES
        self.assertIn(f"повторов developer={cap}", self.summary,
                      f"(зерно {self.seed})\n{self.output}")
        self.assertIn(f"не сошлась: canary: {cap} повторов developer на "
                      "красной планке", self.summary)
        self.assertNotEqual(self.row["verdict"], "green")


if __name__ == "__main__":
    unittest.main()
