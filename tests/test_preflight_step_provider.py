"""Юнит-тесты предполёта шага по провайдеру шага (SPEC
01M3YXYAX5PW9BM67MB4GK85D1): углы, не закрытые долгоживущим файлом задачи
(`tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`), —
провал без набора не дописывается набором, расхождение боевой цепочки
роли не останавливает шаг набора, провайдер наборов, уже спрошенный за
роль карты, в `doctor` второй раз не спрашивается.

Провайдеры — заглушки с тем же интерфейсом предполёта (`check_cli_found`,
`check_token`, `check_cli_version`, `preflight`): предмет — выбор и
склейка проверок, а не тела проверок CLI.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import doctor  # noqa: E402
from orchestrator.doctor import preflight  # noqa: E402

ROLE = "developer"
TARGET = "self"


class FakeProvider:
    """Провайдер с заданными исходами `check_cli_found`/`check_token` и
    журналом вызовов `preflight`."""

    def __init__(self, name, cli="ok", token="ok"):
        self.name = name
        self.cli = cli
        self.token = token
        self.asked = []

    def check_cli_found(self):
        return doctor.Check(f"{self.name}-cli-found", self.cli,
                            f"{self.name} cli")

    def check_token(self, role):
        return doctor.Check(f"{self.name}-token", self.token,
                            f"{self.name} вход роли {role}")

    def check_cli_version(self):
        return doctor.Check(f"{self.name}-cli-version", "ok", "версия")

    def preflight(self, role):
        self.asked.append(role)
        return [self.check_cli_found(), self.check_token(role)]


class PreflightChecksTest(unittest.TestCase):

    def setUp(self):
        self.combat_chain = []

        def model_provider_cli(role, *, combat_chain=True):
            self.combat_chain.append(combat_chain)
            return doctor.Check("model-provider-cli", "ok", "ok")

        for attr, value in (
                ("check_model_provider_cli", model_provider_cli),
                ("check_disk_space",
                 lambda: doctor.Check("disk-space", "ok", "ok")),
                ("check_target_layout",
                 lambda target: doctor.Check("target-layout", "ok", "ok")),
                ("check_git_identity",
                 lambda: doctor.Check("git-identity", "ok", "ok"))):
            patcher = mock.patch.object(doctor, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_set_step_names_provider_role_set_only_on_failures(self):
        """Провал шага набора дописан провайдером, ролью и набором; зелёные
        строки того же предполёта остаются как есть.

        Ловит мутацию: пометка набора приписывается ко всем строкам либо
        не приписывается к провалу вовсе (Оператор не видит, что CLI
        требует набор задачи)."""
        step = FakeProvider("codex", token="fail")

        checks = doctor.preflight_checks(ROLE, TARGET, provider=step,
                                         task_set="nabor-x")

        by_name = {c.name: c for c in checks}
        failed = by_name["codex-token"].detail
        for word in ("codex", ROLE, "nabor-x"):
            self.assertIn(word, failed)
        self.assertEqual(by_name["codex-cli-found"].detail, "codex cli")
        self.assertEqual(self.combat_chain, [False])

    def test_without_set_failures_and_chain_are_as_before(self):
        """Задача без набора: провайдер роли (`providers.for_role`),
        текст провала байт-в-байт прежний, расхождение боевой цепочки
        спрашивается.

        Ловит мутацию: пометка набора или пропуск боевой цепочки
        протекает на шаг без набора — `combat_chain=False` либо хвост
        «набор задачи» в тексте провала соседней задачи."""
        combat = FakeProvider("claude", cli="fail")
        with mock.patch.object(doctor.providers, "for_role",
                               lambda role: combat):
            checks = doctor.preflight_checks(ROLE, TARGET)

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["claude-cli-found"].detail, "claude cli")
        self.assertEqual(self.combat_chain, [True])


class ModelProviderCliCombatChainTest(unittest.TestCase):

    def test_set_step_skips_combat_chain_mismatch_only(self):
        """Расхождение «провайдер роли ≠ провайдер её модели» боевой
        цепочки останавливает шаг на боевой модели и не останавливает шаг
        на модели набора; ненайденный CLI останавливает оба.

        Ловит мутацию: `combat_chain` не учитывается (шаг набора отклонён
        за чужую ему боевую цепочку) либо отключает и половину
        ненайденного CLI."""
        mismatch = [(ROLE, "claude", "codex", "gpt-x")]
        with mock.patch.object(doctor, "model_provider_mismatches",
                               lambda role: mismatch), \
                mock.patch.object(doctor.stack, "demanded_optional_tools",
                                  lambda: []):
            combat = doctor.check_model_provider_cli(ROLE)
            on_set = doctor.check_model_provider_cli(ROLE,
                                                     combat_chain=False)
        self.assertEqual(combat.status, "fail")
        self.assertEqual(on_set.status, "ok")

        with mock.patch.object(doctor, "model_provider_mismatches",
                               lambda role: []), \
                mock.patch.object(doctor.stack, "demanded_optional_tools",
                                  lambda: ["codex"]), \
                mock.patch.object(doctor.shutil, "which", lambda name: None):
            on_set = doctor.check_model_provider_cli(ROLE,
                                                     combat_chain=False)
        self.assertEqual(on_set.status, "fail")
        self.assertIn("codex", on_set.detail)


class ProviderPreflightLiveSetsTest(unittest.TestCase):

    def run_glue(self, live: set) -> dict:
        self.claude = FakeProvider("claude")
        self.codex = FakeProvider("codex")
        registry = {"claude": self.claude, "codex": self.codex}
        with mock.patch.object(preflight, "agent_roles_or_empty",
                               lambda: ["analyst", ROLE]), \
                mock.patch.object(doctor.providers, "for_role",
                                  lambda role: self.claude), \
                mock.patch.object(doctor.providers, "get",
                                  lambda name: registry[name]), \
                mock.patch.object(doctor.models, "live_task_set_providers",
                                  lambda: set(live)):
            return doctor.provider_preflight_checks()

    def test_live_set_provider_asked_per_role_combat_not_twice(self):
        """Провайдер набора задачи в работе, которого нет у ролей карты, —
        опрошен по каждой agent-роли; провайдер, уже идущий за роль карты,
        вторым кругом не опрашивается.

        Ловит мутацию: добавка наборов спрашивает и боевых провайдеров
        (вдвое больше подпроцессов `doctor`) либо спрашивает провайдера
        набора не по ролям."""
        grouped = self.run_glue({"claude", "codex"})

        self.assertEqual(self.claude.asked, ["analyst", ROLE])
        self.assertEqual(self.codex.asked, ["analyst", ROLE])
        self.assertEqual(len(grouped["codex-token"]), 2)

    def test_no_live_sets_glue_as_before(self):
        """Без наборов в работе склейка — только провайдеры ролей карты.

        Ловит мутацию: провайдер реестра спрашивается без источника
        `live_task_set_providers` (строки Codex на пульте без Codex)."""
        grouped = self.run_glue(set())

        self.assertEqual(self.codex.asked, [])
        self.assertNotIn("codex-cli-found", grouped)


if __name__ == "__main__":
    unittest.main()
