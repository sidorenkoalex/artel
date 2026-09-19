"""Приёмочный тест AC-8 задачи 01M2XFSNVGWA2VX5XFEYR93Y4Z: сценарий
инцидента 13.09 целиком — мандат в `ANSWER-*.md`, PLAN.md без раздела
«## Расширение зон», `auto` в `in_dev`.

Здесь `fsm.cmd_advance` подменён не литеральным отказом (как в файле
AC-5/AC-6), а мини-FSM поверх НАСТОЯЩЕГО гейта зон: отказал гейт — цикл
не двигается, прошёл — задача уходит в `review`. Так проверяется именно
стык «гейт зон -> класс отказа в auto -> бриф роли», из-за расхождения в
котором задача 01M2CYQR03 простояла час.

Красен до реализации: гейт зон сегодня журналирует для этого сценария
обычное «переход отклонён: гейт зон», который `auto._pre_advance_step`
относит к классу «нужны руки Оператора» — цикл встаёт на ВТОРОМ отказе,
не запустив developer ни разу; падают
`test_ac8_incident_runs_one_developer_step_with_mandate_paths_in_the_brief`
и `test_ac8_step_writing_the_plan_section_advances_to_review` (до
шага роли дело не доходит вовсе). Зелёный с рождения —
`test_ac8_without_a_mandate_stops_without_running_the_role`: та же
ветка сценария без мандата обязана вести себя как сегодня.

Половина критерия «тест живёт в `tests/`» относится к диффу разработчика
(требование 7 SPEC) и сверяется ревьювером — тестом из каталога планки
собственное местоположение чужого файла не доказывается; сам сценарий,
который тот файл обязан воспроизводить, проверяется здесь целиком.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, config, fsm, runner, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (OLD_ZONES_REFUSAL_ACTION,  # noqa: E402
                      OUT_OF_ZONE_PATH, ScriptedRun, ZonesMandateSandbox)


class _GateDrivenAdvance:
    """Подмена `fsm.cmd_advance`: в `in_dev` спрашивает НАСТОЯЩИЙ гейт
    зон и, если тот пропустил, переводит задачу в `review`; в остальных
    состояниях — холостой вызов без записи в журнал (роль запускается
    как обычно). Возвращает `False` — guard артефакта здесь не предмет."""

    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.calls = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> bool:
        self.calls += 1
        conn = store.db()
        if store.get_task(conn, task_id)["state"] != "in_dev":
            return False
        refuses, _out = self.sandbox.run_zones_gate()
        if not refuses:
            store.set_state(conn, task_id, "review", "fsm",
                            expected_state="in_dev",
                            detail="гейт зон пройден")
        return False


class _IncidentSandbox(ZonesMandateSandbox):
    """Предусловие инцидента: путь вне зон закоммичен, PLAN.md без
    раздела «## Расширение зон», задача в `in_dev` после легитимного
    входа из `tests_writing`."""

    def setUp(self):
        super().setUp()
        self.commit_out_of_zone_file()
        self.commit_plan(extension_paths=None)
        self.enter_in_dev("приёмочные тесты готовы — трассируемость AC пройдена")
        self.advance = _GateDrivenAdvance(self)

    def run_auto(self, run: ScriptedRun) -> str:
        with mock.patch.object(fsm, "cmd_advance", self.advance), \
             mock.patch.object(runner, "cmd_run", run):
            return self.capture(auto.cmd_auto, self.TASK)

    def first_refusal_action(self) -> str:
        """Действие ПЕРВОГО отказа, журналированного настоящим гейтом
        внутри прогона цикла."""
        actions = [a for a, _d in self.refusals()]
        self.assertTrue(actions, "гейт зон не журналировал ни одного отказа")
        return actions[0]

    def patch_max_steps(self, value: int) -> None:
        patcher = mock.patch.object(config, "AUTO_MAX_STEPS", value)
        patcher.start()
        self.addCleanup(patcher.stop)


class Ac8IncidentWithMandateTest(_IncidentSandbox):
    """AC-8, ветка «мандат выдан»."""

    def setUp(self):
        super().setUp()
        self.commit_mandate(OUT_OF_ZONE_PATH)

    def test_ac8_incident_runs_one_developer_step_with_mandate_paths_in_the_brief(self):
        """Шаг developer запускается (ровно один — раздел он так и не
        оформил), история отказа с путями мандата доезжает до его брифа,
        а повтор того же отказа после шага останавливает цикл.

        Ловит мутацию: различение причины сделано в гейте (AC-1), но
        `auto._pre_advance_step` по-прежнему считает новое действие
        отказом класса «нужны руки Оператора» — `run.calls` останется
        пустым, ровно как 13.09, когда developer не запустился ни разу.
        """
        run = ScriptedRun(limit=3, script=[lambda: None])

        out = self.run_auto(run)

        self.assertEqual(
            len(run.calls), 1,
            f"шагов developer сделано {len(run.calls)}, ожидался ровно один "
            f"гарантированный:\n{out}")
        action = self.first_refusal_action()
        self.assertNotEqual(
            action, OLD_ZONES_REFUSAL_ACTION,
            "гейт зон ещё не различает причину отказа (AC-1)")
        self.assertIn(action, run.briefs[0],
                      f"действие отказа не доехало до брифа шага: "
                      f"{run.briefs[0]!r}")
        self.assertIn(OUT_OF_ZONE_PATH, run.briefs[0],
                      f"пути мандата не доехали до брифа шага: "
                      f"{run.briefs[0]!r}")
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("auto остановлен", out)

    def test_ac8_step_writing_the_plan_section_advances_to_review(self):
        """Шаг developer оформил раздел «## Расширение зон» с путями
        мандата — следующий предварительный advance проходит гейт зон и
        задача уходит в `review`.

        Потолок шагов цикла поднят не будет: `config.AUTO_MAX_STEPS`
        подменяется на 2, иначе после перехода в `review` цикл гонял бы
        реценьювера до штатных 30 шагов — предмет теста кончается на
        самом переходе.

        Ловит мутацию: новая ветка отказа перехватывает и случай, когда
        раздел PLAN УЖЕ совпал с мандатом (например, проверка «раздел
        оформлен» осталась только на `extension_paths is None`) — задача
        не вышла бы в `review` даже после честно оформленного раздела.
        """
        self.patch_max_steps(2)
        run = ScriptedRun(
            limit=3,
            script=[lambda: self.commit_plan(extension_paths=OUT_OF_ZONE_PATH)])

        out = self.run_auto(run)

        self.assertEqual(self.state(), "review", out)
        self.assertGreaterEqual(len(run.calls), 1,
                                "шаг developer не запускался вовсе")


class Ac8IncidentWithoutMandateTest(_IncidentSandbox):
    """AC-8, ветка «мандата нет»."""

    def test_ac8_without_a_mandate_stops_without_running_the_role(self):
        """Мандата в `ANSWER-*.md` нет — цикл останавливается решением
        Оператора, не запустив роль ни разу (поведение как до задачи).

        Ловит мутацию: мягкий класс отказа применён к любому отказу
        гейта зон — без мандата задача начала бы гонять developer по
        пути, который Оператор не разрешал.
        """
        run = ScriptedRun(limit=2)

        out = self.run_auto(run)

        self.assertEqual(run.calls, [], f"роль запущена без мандата:\n{out}")
        self.assertEqual(self.first_refusal_action(), OLD_ZONES_REFUSAL_ACTION)
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("auto остановлен", out)


if __name__ == "__main__":
    unittest.main()
