"""AC-2..AC-5: команда шага роли на `codex` — состав argv, порядок
глобальных флагов относительно подкоманды, выключение одиннадцати
функций и `-c`-переопределения, дословно сверенные с курируемым
`config.toml`.

Красен до реализации: `CodexProvider.command(...)` ещё не существует —
`providers.get("codex")` отказывает `UnknownProviderError`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import providers, runner  # noqa: E402

from _codex import (DISABLED_FEATURES, PROVIDER, STEP_MODEL,  # noqa: E402
                    carries_disable, carries_flag_value, config_overrides,
                    flag_positions, normalized, role_home_reference_dir,
                    toml_pairs, value_positions)

#: Путь, который отдаёт подменённый резолв манифеста: предмет критерия —
#: ОТКУДА провайдер берёт argv[0] и под каким ИМЕНЕМ спрашивает, а не то,
#: где лежит бинарник на машине прогона (он там может и отсутствовать).
STUB_TOOL_DIR = "/artel-test-stub-bin"

#: Флаги подкоманды `exec` (AC-3): каждый обязан стоять ПОСЛЕ неё.
SUBCOMMAND_FLAGS = ("--json", "-m", "--ephemeral", "--ignore-rules")

#: Глобальные флаги (AC-3): каждый обязан стоять ПЕРЕД подкомандой.
GLOBAL_FLAGS = ("--disable", "-c")


class StepCommandTest(unittest.TestCase):
    """Argv шага роли `codex` (требования 2-3)."""

    def setUp(self):
        self.resolved = []
        patcher = mock.patch.object(runner, "declared_tool_path",
                                    self._stub_tool_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.argv = providers.get(PROVIDER).command(STEP_MODEL)

    def _stub_tool_path(self, name: str) -> str:
        self.resolved.append(name)
        return f"{STUB_TOOL_DIR}/{name}"

    def test_ac2_argv_carries_exec_json_model_sandbox_and_stdin_prompt(self):
        """Команда шага: argv[0] — абсолютный путь инструмента `codex` из
        резолва манифеста, дальше подкоманда `exec`, `--json`,
        `-m <модель>`, песочница `workspace-write`, `--ephemeral`,
        `--ignore-rules`, а замыкает список позиционный `-` — промпт со
        стандартного входа; ни `--ignore-user-config`, ни `-C`, ни текста
        промпта в argv нет.

        Ловит мутацию: argv[0] оставлен литералом `codex` (резолв
        манифеста не спрошен — по PATH роли нашёлся бы одноимённый
        бинарник соседнего инструмента, инцидент 06.09) либо спрошен на
        имя `claude` (копипаста провайдера по умолчанию); либо модель
        передана не флагом `-m`, и шаг уходит на модель по умолчанию CLI
        молча.
        """
        self.assertEqual(self.resolved, [PROVIDER])
        self.assertEqual(self.argv[0], f"{STUB_TOOL_DIR}/{PROVIDER}")
        self.assertTrue(Path(self.argv[0]).is_absolute(), self.argv[0])

        self.assertIn("exec", self.argv)
        self.assertIn("--json", self.argv)
        self.assertTrue(carries_flag_value(self.argv, "-m", STEP_MODEL),
                        self.argv)
        self.assertTrue(value_positions(self.argv, "workspace-write"),
                        self.argv)
        self.assertIn("--ephemeral", self.argv)
        self.assertIn("--ignore-rules", self.argv)
        self.assertEqual(self.argv[-1], "-")

        self.assertNotIn("-C", self.argv)
        self.assertEqual([a for a in self.argv
                          if a.startswith("--ignore-user-config")], [])

    def test_ac3_global_flags_stand_before_exec_and_subcommand_flags_after(self):
        """Тот же argv: каждый `--disable`/`-c` стоит по индексу МЕНЬШЕ
        подкоманды `exec`, а `--json`/`-m`/песочница/`--ephemeral`/
        `--ignore-rules` — по индексу больше.

        Ловит мутацию: флаги собраны одним списком после `exec` («так
        читается ровнее») — 0.155.1 разбирает глобальные флаги только до
        подкоманды, и шаг падал бы разбором аргументов либо, хуже,
        молча терял бы выключение функций.
        """
        exec_at = self.argv.index("exec")

        for flag in GLOBAL_FLAGS:
            positions = flag_positions(self.argv, flag)
            with self.subTest(flag=flag):
                self.assertTrue(positions, f"{flag} нет в команде шага")
                self.assertLess(max(positions), exec_at, self.argv)

        for flag in SUBCOMMAND_FLAGS:
            positions = flag_positions(self.argv, flag)
            with self.subTest(flag=flag):
                self.assertTrue(positions, f"{flag} нет в команде шага")
                self.assertGreater(min(positions), exec_at, self.argv)

        sandbox_at = value_positions(self.argv, "workspace-write")
        self.assertTrue(sandbox_at, self.argv)
        self.assertGreater(min(sandbox_at), exec_at, self.argv)

    def test_ac4_every_one_of_the_eleven_features_is_disabled(self):
        """Тот же argv несёт `--disable <имя>` на каждую из одиннадцати
        функций, включённых в 0.155.1 по умолчанию.

        Ловит мутацию: список выключаемых функций набран частично
        («браузерные и так не нужны») — уцелевшая `computer_use` тем же
        путём, что и в живом запуске 0.155.1, позвала бы MCP-сервер и
        полезла открывать браузер на машине Оператора.
        """
        missing = [name for name in DISABLED_FEATURES
                   if not carries_disable(self.argv, name)]

        self.assertEqual(missing, [], self.argv)

    def test_ac5_network_and_approval_overrides_match_the_curated_config(self):
        """Тот же argv несёт `-c`-переопределение, выключающее сеть
        песочницы, и `-c`-переопределение политики подтверждений
        «никогда»; ключ и значение каждого дословно совпадают с
        соответствующей парой `docs/reference/role-home/codex/config.toml`.

        Ключи не зашиты литералом: имена сверяются со справкой
        установленной 0.155.1, и SPEC разрешает фактическим именам
        отличаться — предмет критерия в том, что команда и курируемый дом
        говорят ОДНО И ТО ЖЕ, а не в конкретном написании ключа.

        Ловит мутацию: `config.toml` поправили (переименовали ключ,
        сменили значение), а команду шага — нет; половинки изоляции
        разъезжаются молча, и роль идёт с сетью песочницы, включённой
        ровно там, где дом роли обещает её выключенной.
        """
        curated = {key: normalized(value) for key, value
                   in toml_pairs((role_home_reference_dir() / "config.toml")
                                 .read_text(encoding="utf-8"))}
        overrides = config_overrides(self.argv)

        network = [(k, v) for k, v in overrides
                   if v == "false" and "network" in k]
        approval = [(k, v) for k, v in overrides if v == "never"]

        self.assertTrue(network, f"нет -c, выключающего сеть: {overrides}")
        self.assertTrue(approval,
                        f"нет -c политики подтверждений: {overrides}")
        for key, value in network + approval:
            with self.subTest(key=key):
                self.assertIn(key, curated,
                              f"ключа {key} нет в курируемом config.toml")
                self.assertEqual(curated[key], value)


if __name__ == "__main__":
    unittest.main()
