"""Приёмочные тесты 01M28NX0M2WTVC38XVN75N01XD — AC-4, AC-5 (SPEC.md).

Красен до реализации: `config.AUTO_STOP_ZONE_WAIT` называет только
`status`/`zone-release`, а `config.AUTO_STOP["spec_gate"/"acceptance"/
"merge_gate"/"escalated"]` — только `approve`/`log`; ни одна из этих
подсказок сегодня не упоминает `stop`/`kill` вовсе — тесты ниже ищут
буквальную фразу SPEC «stop <id> — остановить цикл; kill <id> —
ликвидировать задачу» и падают на сегодняшнем тексте.

AC-5 гоняется через настоящий `auto.cmd_auto` (песочница `AutoCycleTest`
из `tests/test_auto_cycle.py`, тот же приём, что уже кроет соседний
критерий этого же словаря — `test_stop_names_the_reason_and_the_next_
command`) — так тест бьёт по факту напечатанной строки «дальше:», не
только по значению константы. AC-4 (занятость зоны) в эту песочницу не
входит: `runner.cmd_run` там подменён (`FakeRun`), а отказ по зоне
рождается ВНУТРИ настоящего `cmd_run` — воспроизвести его пришлось бы
через отдельный, самим этим тестом заведённый конфликт зон (второй
"занявший" — task, реальный `runner.cmd_run`, реальный `zone_lock`),
что дублирует уже существующий приёмочный контур соседней задачи
(`tasks/01M1P9QAG65GVF69YJEV0V18D9/acceptance_tests/
test_ac1_ac2_ac3_zone_conflict_precondition.py`). `config.
AUTO_STOP_ZONE_WAIT[1].format(id=...)` — единственное и достаточное
место, где рождается печатаемый текст (`orchestrator/auto.py`, отказ
занятости зоны без `--wait-zone`, строки вокруг `_run_zone_wait_
refusal`): между константой и печатью нет отдельной трансформации,
которая могла бы разойтись с этим тестом.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest  # noqa: E402

_BOTH_COMMANDS = "stop {id} — остановить цикл; kill {id} — ликвидировать задачу"


class Ac4ZoneWaitHintNamesStopAndKillTest(AutoCycleTest):
    """AC-4: подсказка «дальше:» задачи, чей цикл ждёт зону, называет
    stop и kill с их назначением."""

    def test_ac4_zone_wait_hint_names_both_commands(self):
        """`config.AUTO_STOP_ZONE_WAIT[1]` — источник, который `auto.
        _role_run_step` форматирует и печатает строкой «дальше:» при
        занятости зоны без `--wait-zone`.

        Ловит мутацию: подсказка ждёт зоны продолжает называть только
        `artel.py status`/`zone-release`, без stop/kill — тест красен
        на отсутствии требуемой фразы.
        """
        hint = config.AUTO_STOP_ZONE_WAIT[1].format(id=self.TASK)

        self.assertIn(_BOTH_COMMANDS.format(id=self.TASK), hint,
                     f"подсказка ждёт зоны: {hint!r}")


class Ac5ManualGateHintNamesStopAndKillTest(AutoCycleTest):
    """AC-5: подсказка «дальше:» задачи, чей цикл стоит на ручном гейте
    (spec_gate, acceptance, merge_gate, escalated), называет те же обе
    команды тем же текстом."""

    def test_ac5_manual_gates_name_both_commands(self):
        """Проходит по всем четырём гейтам требования 4 (spec_gate,
        acceptance, merge_gate, escalated без блокировки по бюджету —
        `cmd_new` заводит задачу со свежим бюджетом, эскалация здесь не
        по потолку, `AUTO_STOP_BUDGET` не подставляется) и гоняет
        настоящий `auto.cmd_auto`: печатаемая строка «дальше:» обязана
        нести обе команды на КАЖДОМ из них.

        Ловит мутацию: правка `config.AUTO_STOP` добавляет фразу только
        части состояний (например, `spec_gate`/`merge_gate`, но не
        `acceptance`/`escalated`) — `subTest` довалит именно тот гейт,
        где фразы не хватило, вместо того чтобы потонуть в первом же
        прошедшем состоянии.
        """
        for state in ("spec_gate", "acceptance", "merge_gate", "escalated"):
            with self.subTest(state=state):
                self.set_state(state)

                out = self.auto()

                self.assertIn(_BOTH_COMMANDS.format(id=self.TASK), out,
                             f"[{state}] дальше: {out!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
