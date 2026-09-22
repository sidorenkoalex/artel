"""AC-12, AC-13, AC-19: `codex` — инструмент НЕОБЯЗАТЕЛЬНЫЙ, пока ни один
ярус agent-роли не разрешается в его модель, и обязательный, как только
разрешается; живой смок `codex` обычным прогоном `doctor` не запускается.

Раздел `codex` каталога здесь синтетический, а не боевой: предмет
критериев — ОБЯЗАТЕЛЬНОСТЬ инструмента при разрешимой цепочке роли, а не
прейскурант (его сверяет планка AC-14).

Красен до реализации: провайдера `codex` нет в реестре — разбор каталога
с его разделом отказывает `UnknownProviderError` ещё на чтении слоёв.
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, doctor, providers, runner, stack, store  # noqa: E402
from tests.sandbox import claude_only_popen  # noqa: E402
from tests.test_doctor import FakeLiveSmokeProc, result_event  # noqa: E402
from tests.test_runner_model_preflight import _StepSandbox  # noqa: E402
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

from _codex import CLI_MINIMUM_TEXT, PROVIDER, STEP_MODEL  # noqa: E402

CLAUDE_MODEL = "claude-opus-5"
TIER = "strong"

# Настоящие `check_stack`/`preflight_checks` снимаются ДО песочницы:
# `tests/sandbox.py::TmpRootTest` подменяет первый заглушкой, а
# `_StepSandbox` гасит второй пустым списком — обе подмены сняли бы как
# раз тот сигнал, который называют критерии (строка `doctor` про
# инструмент и отказ шага до старта агента).
REAL_CHECK_STACK = stack.check_stack
REAL_PREFLIGHT_CHECKS = doctor.preflight_checks


def _tool_name(args) -> str:
    if not args or isinstance(args, (str, bytes)):
        return ""
    return Path(str(args[0])).name


def claude_pinned_run(inner):
    """`claude --version` отвечает пином, остальное — прежнему `run`:
    исход строк CLI не должен зависеть от того, что стоит на машине
    прогона."""
    def run(args, *rest, **kwargs):
        if _tool_name(args) == "claude":
            return subprocess.CompletedProcess(
                list(args), 0, f"{config.CLI_VERSION_PIN} (Claude Code)\n", "")
        return inner(args, *rest, **kwargs)
    return run


def codex_hidden_which(inner):
    """`codex` не найден в PATH — сценарий обоих критериев. Codex CLI
    может быть УСТАНОВЛЕН на машине Оператора (SPEC «Контекст»: живой
    запуск 0.155.1), и без этой подмены критерий проверял бы состояние
    машины, а не пульта."""
    def which(name, *rest, **kwargs):
        if name == PROVIDER:
            return None
        return inner(name, *rest, **kwargs)
    return which


def codex_missing_run(inner):
    """`codex --version` не выполняется — тот же сценарий, но для
    манифеста стека, который спрашивает версию подпроцессом."""
    def run(args, *rest, **kwargs):
        if _tool_name(args) == PROVIDER:
            raise FileNotFoundError(f"{PROVIDER} не найден")
        return inner(args, *rest, **kwargs)
    return run

CATALOG_YAML = """providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      {claude_model}:
        min_cli_version: 1.0.0
        status: supported
        list_price_usd_per_mtok:
          input: 5.0
          output: 25.0
          cache_write: 6.25
          cache_read: 0.50
        price_date: 2026-09-21
  {provider}:
    cli: {provider}
    min_cli_version: {minimum}
    cost_from_cli: false
    models:
      {codex_model}:
        min_cli_version: {minimum}
        status: experimental
        list_price_usd_per_mtok:
          input: 2.0
          output: 12.0
          cache_write: 2.0
          cache_read: 0.20
        price_date: 2026-09-21
"""

LOCAL_YAML = """tiers:
  {tier}: {model}
allow_experimental:
  {model}: true
"""


class _CodexTierSandbox(_StepSandbox):
    """Шаг роли `developer` на каталоге с двумя провайдерами; какой
    моделью разрешается ярус — выбирает тест."""

    def use_tier(self, model: str, on_codex: bool = False) -> None:
        catalog_path = self.root / "catalog-two-providers" / "models.yaml"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            CATALOG_YAML.format(claude_model=CLAUDE_MODEL, provider=PROVIDER,
                                codex_model=STEP_MODEL,
                                minimum=CLI_MINIMUM_TEXT),
            encoding="utf-8")
        self.patch(config, "MODELS", catalog_path)
        config.MODELS_LOCAL.write_text(
            LOCAL_YAML.format(tier=TIER, model=model), encoding="utf-8")
        text = _roles_yaml_text(self.ROLE, TIER)
        if on_codex:
            text = text.replace(f"  {self.ROLE}:\n",
                                f"  {self.ROLE}:\n    provider: {PROVIDER}\n",
                                1)
        roles_path = self.root / "roles-under-test.yaml"
        roles_path.write_text(text, encoding="utf-8")
        self.patch(config, "ROLES", roles_path)
        self.patch(doctor, "preflight_checks", REAL_PREFLIGHT_CHECKS)
        self.patch(subprocess, "run", claude_pinned_run(subprocess.run))

    def hide_codex(self) -> None:
        self.patch(shutil, "which", codex_hidden_which(shutil.which))
        self.patch(subprocess, "run", codex_missing_run(subprocess.run))

    def stub_declared_tools(self) -> None:
        self.patch(runner, "_resolve_declared_tools", lambda: {
            name: f"/artel-test-stub-bin/{name}"
            for name in set(stack.DECLARED_TOOLS) | {PROVIDER}})

    def doctor_checks(self, real_stack: bool = True) -> list:
        """Полный прогон `doctor`; живой смок подменён.

        `real_stack=False` оставляет манифест стека заглушкой песочницы:
        она же отвечает за венв-сверку внутри `runner.role_env`, а без
        готового венва окружение роли не собирается вовсе — сценарии,
        которым нужен ДОШЕДШИЙ до провайдера смок, иначе проверяли бы
        отказ сборки окружения вместо своего предмета.
        """
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")
        checks = REAL_CHECK_STACK if real_stack else stack.check_stack
        with mock.patch.object(stack, "check_stack", checks), \
                mock.patch.object(doctor.subprocess, "Popen", claude_only_popen(
                    FakeLiveSmokeProc(result_event(0.01)))):
            return doctor.all_checks(store.db())

    @staticmethod
    def mentions_codex(check) -> bool:
        return PROVIDER in f"{check.name} {check.detail}"

    @staticmethod
    def names_missing_tool(text: str) -> bool:
        """Текст называет инструмент `codex` НЕНАЙДЕННЫМ — не просто
        упоминает слово `codex`: до регистрации провайдера про него
        говорит совсем другой отказ («не зарегистрирован»), и критерий
        AC-13 проходил бы на нём, ничего не проверив."""
        lowered = text.lower()
        return PROVIDER in lowered and any(
            marker in lowered for marker in
            ("не найден", "not found", "не установлен", "отсутств"))

    def stack_checks(self) -> list:
        return REAL_CHECK_STACK()


class CodexNotRequiredTest(_CodexTierSandbox):
    """Ни один ярус не разрешается в модель `codex` — требование 6, AC-12."""

    def setUp(self):
        super().setUp()
        self.use_tier(CLAUDE_MODEL)
        self.hide_codex()

    def test_ac12_missing_codex_keeps_the_stack_green_and_the_claude_step_running(self):
        """При отсутствующем бинарнике `codex` и ярусах, разрешающихся
        только в модели Claude: `check_stack()` не даёт ни одной строки
        `fail` из-за `codex`, `doctor` не краснеет из-за `codex`, а шаг
        роли на Claude запускается как сегодня.

        Ловит мутацию: запись `codex` внесена в манифест стека
        безусловно (`REQUIRED_TOOLS`/`DECLARED_TOOLS` собираются по всему
        реестру провайдеров как раньше) — пульт БЕЗ Codex краснеет
        `doctor` и перестаёт запускать шаги вовсе: резолв объявленных
        инструментов отказывает `OSError` на каждом `role_env`, то есть
        регистрация второго провайдера ломает работу первого.
        """
        red = [c for c in self.stack_checks()
               if c.status == "fail" and self.mentions_codex(c)]
        self.assertEqual([(c.name, c.detail) for c in red], [])

        red_doctor = [c for c in self.doctor_checks()
                      if c.status == "fail" and self.mentions_codex(c)]
        self.assertEqual([(c.name, c.detail) for c in red_doctor], [])

        self.run_step()

        self.spawn.assert_called_once()
        self.assertEqual(self.state(), "in_dev")


class CodexRequiredTest(_CodexTierSandbox):
    """Ярус agent-роли разрешается в модель `codex` — требование 6, AC-13."""

    def setUp(self):
        super().setUp()
        self.use_tier(STEP_MODEL)
        self.hide_codex()

    def test_ac13_missing_codex_refuses_the_step_and_reddens_doctor(self):
        """Тот же отсутствующий бинарник, но ярус agent-роли разрешается в
        модель провайдера `codex`: `run` отказывает ДО старта агента с
        причиной, называющей ненайденный инструмент `codex`, и `doctor`
        несёт красную строку про него.

        Ловит мутацию: инструмент второго провайдера остался
        необязательным ВСЕГДА (условие обязательности написано, но
        смотрит на провайдера роли из `roles.yaml`, а не на разрешение
        яруса в модель) — шаг стартует, платит токенами и падает на
        отсутствующем CLI внутри попытки вместо бесплатного отказа до
        старта агента.
        """
        out = self.run_step()

        self.spawn.assert_not_called()
        said = f"{out}\n{self.exit_message or ''}\n" + "\n".join(
            self.entries_containing(PROVIDER))
        self.assertTrue(self.names_missing_tool(said),
                        f"отказ не назвал ненайденный инструмент: {said}")

        red = [c for c in self.doctor_checks()
               if c.status == "fail"
               and self.names_missing_tool(f"{c.name} {c.detail}")]
        self.assertTrue(red, "doctor не покраснел из-за отсутствующего codex")


class LiveSmokeCommandTest(_CodexTierSandbox):
    """Живой смок `codex` — требование 12, AC-19."""

    def setUp(self):
        super().setUp()
        self.use_tier(STEP_MODEL, on_codex=True)
        self.stub_declared_tools()
        self.calls = []
        self.provider = providers.get(PROVIDER)
        # Настоящая сборка снимается ДО подмены шпионом: шпион нужен
        # только второй половине критерия («doctor его не зовёт»), а argv
        # сверяется с тем, что провайдер собирает на самом деле.
        self.real_live_smoke = type(self.provider).live_smoke_command
        self.patch(type(self.provider), "live_smoke_command", self._spy)
        self.patch(runner, "declared_tool_path",
                   lambda name: f"/artel-test-stub-bin/{name}")

    def _spy(self, prompt):
        self.calls.append(prompt)
        return [f"/artel-test-stub-bin/{PROVIDER}", prompt]

    def test_ac19_live_smoke_argv_is_the_step_binary_and_doctor_does_not_run_it(self):
        """`live_smoke_command(<промпт>)` отдаёт argv, где argv[0]
        совпадает с argv[0] команды шага, есть `--json` и
        `--skip-git-repo-check`, а промпт стоит аргументом; обычный прогон
        `doctor` живой смок `codex` не запускает.

        Ловит мутацию: смок собран на литерале `codex` вместо argv[0]
        команды шага — проверялась бы живость тёзки с PATH, а не того
        бинарника, который реально исполнит шаг (инцидент 06.09); либо
        живой смок второго провайдера попал в обычный `doctor`, и каждый
        прогон диагностики начинает платить деньги за вызов платного CLI.
        """
        argv = self.real_live_smoke(self.provider, "проверка")

        self.assertEqual(argv[0], self.provider.command()[0])
        self.assertIn("--json", argv)
        self.assertIn("--skip-git-repo-check", argv)
        self.assertIn("проверка", argv)
        self.assertNotEqual(argv[-1], "-")

        self.doctor_checks(real_stack=False)

        self.assertEqual(self.calls, [],
                         "обычный doctor запустил живой смок codex")


if __name__ == "__main__":
    unittest.main()
