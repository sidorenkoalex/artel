"""AC-3/AC-4 задачи 01M2DTT96FS25SHXP0HDTWARQH: флаг `--model` в команде
шага роли — присутствует ровно один раз (со значением `roles.model(role)`)
и не трогает порядок существующих флагов, когда модель задана; полностью
отсутствует, когда не задана — и тогда в журнал шага уходит ровно одно
предупреждение «модель роли не задана — дефолт CLI», без остановки шага.

Красен до реализации: `runner.role_cmd`/`run_agent_once` не читают
`roles.model` вовсе — argv не несёт `--model` ни при каком `roles.yaml`,
а предупреждение в журнал никто не пишет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pipeline import ModelFlagPipelineTest  # noqa: E402

# Порядок флагов `role_cmd()` до этой задачи (`orchestrator/runner.py`) —
# AC-3 требует, чтобы вставка `--model` его не переставляла.
_KNOWN_FLAGS_IN_ORDER = (
    "--permission-mode", "--output-format", "--allowedTools",
    "--setting-sources", "--strict-mcp-config",
)


class CommandModelFlagTest(ModelFlagPipelineTest):

    def test_ac3_model_flag_appears_once_with_the_configured_identifier(self):
        """Роль `developer` несёт `model: claude-opus-5` в `roles.yaml` —
        argv команды шага несёт `--model claude-opus-5` ровно один раз, а
        существующие флаги остаются в прежнем относительном порядке.

        Ловит мутацию: `--model` добавляется дважды (например, и в
        `role_cmd`, и повторно на пути `run_agent_once`), значение
        подставляется не то, либо вставка `--model` сдвигает порядок
        существующих флагов.
        """
        self.set_roles_yaml(developer="claude-opus-5")

        argv = self.argv_of(self.run_agent("developer"))

        self.assertEqual(argv.count("--model"), 1,
                         f"--model встречается не один раз: {argv}")
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-5")
        positions = [argv.index(flag) for flag in _KNOWN_FLAGS_IN_ORDER]
        self.assertEqual(positions, sorted(positions),
                         f"порядок существующих флагов нарушен: {argv}")

    def test_ac3_model_flag_uses_the_role_specific_identifier(self):
        """Модель — своя у каждой роли: шаг `reviewer` с `model:
        claude-opus-5` несёт именно это значение, не модель какой-то
        другой захардкоженной роли.

        Ловит мутацию: `role_cmd` всегда подставляет модель ОДНОЙ роли
        (например, всегда `developer`) независимо от того, чей это шаг.
        """
        self.set_roles_yaml(reviewer="claude-opus-5")

        argv = self.argv_of(self.run_agent("reviewer"))

        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-5")

    def test_ac4_no_model_flag_when_the_field_is_absent(self):
        """`roles.yaml` роли `developer` без поля `model` (как до этой
        задачи) — argv команды шага не несёт `--model` вовсе.

        Ловит мутацию: `--model` подставляется безусловно с пустым или
        дефолтным значением вместо пропуска флага при отсутствии поля.
        """
        self.set_roles_yaml(developer=None)

        argv = self.argv_of(self.run_agent("developer"))

        self.assertNotIn("--model", argv)

    def test_ac4_missing_model_warns_exactly_once_without_failing_the_step(self):
        """Поле `model` роли `developer` не задано — шаг завершается
        обычным успехом (нет `agent run FAILED`/`SKIPPED`/`TIMEOUT`), а в
        журнал шага уходит РОВНО одна запись с текстом «модель роли не
        задана — дефолт CLI».

        Ловит мутацию: предупреждение не пишется вовсе, пишется на каждую
        попытку повторно (не «одной записью на шаг»), либо отсутствие
        поля ошибочно останавливает/проваливает шаг.
        """
        self.set_roles_yaml(developer=None)

        self.run_agent("developer")

        rows = self.all_step_rows()
        warnings = [r for r in rows
                   if "модель роли не задана — дефолт CLI" in r["detail"]]
        self.assertEqual(len(warnings), 1,
                         f"должна быть ровно одна запись предупреждения: "
                         f"{[(r['action'], r['detail']) for r in rows]}")
        self.assertFalse(
            any(r["action"] in ("agent run FAILED", "agent run SKIPPED",
                                "agent run TIMEOUT") for r in rows),
            f"шаг не должен останавливаться из-за отсутствия model: "
            f"{[(r['action'], r['detail']) for r in rows]}")
        self.assertTrue(any(r["action"] == "agent run started" for r in rows))


if __name__ == "__main__":
    unittest.main()
