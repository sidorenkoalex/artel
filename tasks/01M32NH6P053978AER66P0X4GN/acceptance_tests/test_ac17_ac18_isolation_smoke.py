"""AC-17, AC-18: офлайн-смок изоляции `codex` — красный на команде,
лишившейся песочницы/выключения сети/любого `--disable`, и на окружении,
унаследовавшем ambient `HOME`/`CODEX_HOME`; жёлтый с именем чужого
секрета, оставшегося в окружении шага.

Имя носителя смока критерий не называет: берётся провайдерский смок, если
он заведён отдельным именем, иначе общий `doctor.isolation_smoke(role)` —
сегодняшняя точка офлайн-сверки изоляции, которой требование 12 и велит
«сверять того CLI, который реально запустит шаг».

Красен до реализации: роль на провайдере `codex` не собирается вовсе —
`providers.for_role` отказывает `UnknownProviderError`, и смок возвращает
провал не по предмету критерия.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, doctor, keychain, providers, runner, stack  # noqa: E402
from tests.sandbox import DeveloperBriefTmpRootTest  # noqa: E402
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

from _codex import (DISABLED_FEATURES, PROVIDER,  # noqa: E402
                    config_overrides, drop_ambient, value_positions)

ROLE = "developer"
FOREIGN_SECRET_NAME = "CLAUDE_CODE_OAUTH_TOKEN"
FOREIGN_SECRET = "tok-chuzhogo-provaydera"
ALIEN_CODEX_HOME = "/tmp/dom-operatora-ne-roli"


def codex_smoke(role: str):
    """Офлайн-смок изоляции провайдера `codex`: свой носитель, если
    реализация завела его отдельным именем, иначе общий смок `doctor`."""
    for name in ("codex_isolation_smoke", "isolation_smoke_codex"):
        own = getattr(doctor, name, None)
        if own is not None:
            try:
                return own(role)
            except TypeError:
                return own()
    return doctor.isolation_smoke(role)


class IsolationSmokeTest(DeveloperBriefTmpRootTest):
    """Смок изоляции роли, идущей на `codex` (требование 12)."""

    def setUp(self):
        super().setUp()
        path = self.root / "roles-under-test.yaml"
        path.write_text(
            _roles_yaml_text(ROLE, "strong").replace(
                f"  {ROLE}:\n", f"  {ROLE}:\n    provider: {PROVIDER}\n", 1),
            encoding="utf-8")
        self.patch(config, "ROLES", path)
        self.patch(keychain, "token", lambda slot: "tok-test")
        self.patch(runner, "_resolve_declared_tools", self._stub_tools)
        drop_ambient(self, "CODEX_HOME", "OPENAI_API_KEY",
                     FOREIGN_SECRET_NAME, "ANTHROPIC_API_KEY")
        self.provider_class = type(providers.get(PROVIDER))
        self.healthy = providers.get(PROVIDER).command()

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _stub_tools(self) -> dict:
        names = set(stack.DECLARED_TOOLS) | {PROVIDER}
        return {name: f"/artel-test-stub-bin/{name}" for name in names}

    def crippled(self, argv: list):
        """Смок на команде шага, из которой выломан один пункт изоляции."""
        with mock.patch.object(self.provider_class, "command",
                               lambda self, model=None: list(argv)):
            return codex_smoke(ROLE)

    def without(self, value: str) -> list:
        """Команда шага, из которой выломано значение `value` — в любой
        форме записи, которую выбрала реализация (отдельным элементом или
        через `=`)."""
        dropped = set(value_positions(self.healthy, value))
        return [a for i, a in enumerate(self.healthy) if i not in dropped]

    def test_ac17_smoke_is_green_on_the_regular_command_and_red_on_each_gap(self):
        """На штатно собранных команде и окружении смок зелёный; он
        краснеет и называет нарушенный пункт, если из команды пропала
        песочница `workspace-write`, пропало `-c`-выключение сети или
        пропал хотя бы один `--disable`, а также если окружение
        унаследовало ambient `HOME`/`CODEX_HOME`.

        Ловит мутацию: смок сверяет изоляцию по СВОЕЙ копии списка флагов
        (константа рядом с проверкой), а не по реально собранной команде
        шага — выломанный из `command()` флаг смок не замечает, и
        Оператор читает зелёную строку про изоляцию, которой у шага уже
        нет; либо смок смотрит на окружение провайдера по умолчанию, и
        ambient-дом, унаследованный шагом на Codex, остаётся невидимым.
        """
        healthy_check = codex_smoke(ROLE)
        self.assertEqual(healthy_check.status, "ok", healthy_check.detail)

        no_sandbox = self.crippled(self.without("workspace-write"))
        self.assertEqual(no_sandbox.status, "fail", no_sandbox.detail)
        self.assertTrue("workspace-write" in no_sandbox.detail
                        or "песочниц" in no_sandbox.detail.lower(),
                        no_sandbox.detail)

        network_keys = [key for key, value in config_overrides(self.healthy)
                        if value == "false" and "network" in key]
        self.assertTrue(network_keys, self.healthy)
        no_network = self.crippled(
            [a for a in self.healthy if network_keys[0] not in a])
        self.assertEqual(no_network.status, "fail", no_network.detail)
        self.assertTrue("network" in no_network.detail.lower()
                        or "сет" in no_network.detail.lower(),
                        no_network.detail)

        feature = DISABLED_FEATURES[0]
        no_feature = self.crippled(self.without(feature))
        self.assertEqual(no_feature.status, "fail", no_feature.detail)
        self.assertIn(feature, no_feature.detail)

        def leaky(self, role=None, task_id=None):
            return {"HOME": os.environ.get("HOME", ""),
                    "CODEX_HOME": os.environ.get("CODEX_HOME", "")}

        with mock.patch.dict(os.environ, {"CODEX_HOME": ALIEN_CODEX_HOME}), \
                mock.patch.object(self.provider_class, "environment", leaky):
            inherited = codex_smoke(ROLE)

        self.assertEqual(inherited.status, "fail", inherited.detail)
        self.assertIn("HOME", inherited.detail)

    def test_ac18_foreign_provider_secret_is_a_separate_yellow_line(self):
        """При заданной ambient-переменной `CLAUDE_CODE_OAUTH_TOKEN` смок
        называет найденный чужой секрет отдельной жёлтой строкой с именем
        переменной и зелёной строки при этом не печатает.

        Ловит мутацию: чужой секрет в окружении шага под `codex` признан
        нормой (общий белый список манифеста — «так и задумано») и смок
        остаётся зелёным: сужение белого списка по провайдеру в эту
        задачу не входит, и молчание смока — единственное, чем факт
        утечки токена подписки в чужой CLI мог бы остаться незамеченным.
        """
        with mock.patch.dict(os.environ,
                             {FOREIGN_SECRET_NAME: FOREIGN_SECRET}):
            check = codex_smoke(ROLE)

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn(FOREIGN_SECRET_NAME, check.detail)
        self.assertNotIn(FOREIGN_SECRET, check.detail)


if __name__ == "__main__":
    unittest.main()
