"""AC-16: предполётный набор провайдера `codex` — четыре проверки со
своими именами, проверка ключа без печати значения, и все они доходят до
склейки, которую печатает `doctor`.

Красен до реализации: `CodexProvider.preflight(role)` ещё не существует —
`providers.get("codex")` отказывает `UnknownProviderError`.
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, doctor, keychain, providers  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

from _codex import (CLI_MINIMUM_TEXT, PROVIDER,  # noqa: E402
                    drop_ambient, discover_key_slot)

ROLE = "developer"
KEYCHAIN_SECRET = "sekret-kotoryy-nelzya-pechatat"
STUB_CODEX_PATH = "/artel-test-stub-bin/codex"
STALE_CODEX_VERSION = "0.150.0"

# Настоящие `shutil.which`/`subprocess.run` снимаются ДО подмены: оба
# патчатся на самом модуле (`doctor.shutil` — тот же объект `shutil`), и
# делегирование к текущему атрибуту было бы рекурсией.
_REAL_WHICH = shutil.which
_REAL_RUN = subprocess.run


class ProviderPreflightTest(TmpRootTest):
    """Набор `preflight()` провайдера `codex` (требование 12)."""

    def setUp(self):
        super().setUp()
        path = self.root / "roles-under-test.yaml"
        path.write_text(
            _roles_yaml_text(ROLE, "strong").replace(
                f"  {ROLE}:\n", f"  {ROLE}:\n    provider: {PROVIDER}\n", 1),
            encoding="utf-8")
        self.patch(config, "ROLES", path)
        self.patch(keychain, "token", lambda slot: KEYCHAIN_SECRET)
        self.patch(doctor.shutil, "which", self._which)
        self.patch(doctor.subprocess, "run", self._run)
        drop_ambient(self, "OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN",
                     "ANTHROPIC_API_KEY")

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _which(self, name, *args, **kwargs):
        """`codex` «установлен»: без найденного CLI набор провайдера по
        построению короче (версию не считают за отсутствующий CLI), и
        число проверок сказало бы не о составе набора, а об отсутствии
        бинарника на машине прогона."""
        if name == PROVIDER:
            return STUB_CODEX_PATH
        return _REAL_WHICH(name, *args, **kwargs)

    def _run(self, args, **kwargs):
        """Версия установленного `codex` — ниже минимума: критерий требует
        от строки версии ПРЕДУПРЕЖДЕНИЯ именно в этом случае. `claude`
        отвечает пином — иначе набор провайдера по умолчанию, с которым
        сверяются имена, зависел бы от машины прогона."""
        name = Path(str(args[0])).name
        if name == PROVIDER:
            return subprocess.CompletedProcess(
                list(args), 0, f"{STALE_CODEX_VERSION}\n", "")
        if name == "claude":
            return subprocess.CompletedProcess(
                list(args), 0, f"{config.CLI_VERSION_PIN}\n", "")
        return _REAL_RUN(args, **kwargs)

    def test_ac16_four_named_checks_hide_the_secret_and_reach_doctor(self):
        """`preflight(role)` провайдера отдаёт четыре проверки — CLI
        найден (блокирующая), версия CLI (предупреждение при версии ниже
        0.155.1), ключ роли (блокирующая), дом роли; текст проверки ключа
        называет факт и имя слота, но не само значение; ни одно имя не
        совпадает с именем одноимённой проверки Claude, и все четыре
        доходят до склейки, которую печатает `doctor`.

        Ловит мутацию: набор собран переиспользованием проверок Claude
        (`doctor.check_cli_found`/`check_token` как есть) — имена строк
        совпадают, склейка `provider_preflight_checks` схлопывает их как
        дубли, и в выводе `doctor` остаётся ОДНА строка на два CLI:
        отсутствие `codex` или его ключа исчезает за зелёной строкой
        Claude; либо текст проверки ключа печатает сам секрет, и он
        уезжает в лог `doctor`.
        """
        checks = providers.get(PROVIDER).preflight(ROLE)

        self.assertEqual(len(checks), 4, [c.name for c in checks])
        statuses = {c.name: c.status for c in checks}
        details = {c.name: c.detail for c in checks}

        claude_names = {c.name for c in providers.default().preflight(ROLE)}
        self.assertEqual(set(statuses) & claude_names, set(),
                         f"имена совпали с проверками Claude: {statuses}")

        found = [c for c in checks if STUB_CODEX_PATH in c.detail]
        self.assertTrue(found, details)
        self.assertEqual(found[0].status, "ok", found[0].detail)

        stale = [c for c in checks if STALE_CODEX_VERSION in c.detail]
        self.assertTrue(stale, details)
        self.assertEqual(stale[0].status, "warn", stale[0].detail)
        self.assertIn(CLI_MINIMUM_TEXT, stale[0].detail)

        slot = discover_key_slot(self)
        key_checks = [c for c in checks if slot in c.detail]
        self.assertTrue(key_checks, f"проверка ключа не назвала слот {slot}")
        for check in checks:
            with self.subTest(check=check.name):
                self.assertNotIn(KEYCHAIN_SECRET, check.detail)

        grouped = doctor.provider_preflight_checks()
        for check in checks:
            with self.subTest(check=check.name):
                self.assertIn(check.name, grouped, sorted(grouped))


if __name__ == "__main__":
    unittest.main()
