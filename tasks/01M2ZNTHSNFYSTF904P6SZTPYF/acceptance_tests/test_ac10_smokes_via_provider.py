"""AC-10: офлайн-смок изоляции и живой смок берут argv и окружение через
провайдера; офлайн-часть обоих зелёная.

Красен до реализации: подменить провайдерскую сборку команды и окружения
не на чем — реестра провайдеров ещё нет; проверка зелени офлайн-части
обоих смоуков зелена уже сегодня.
"""
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import doctor
from _providers import patch_target
from _sandbox import DoctorSandbox, FakeLiveSmokeProc, offline_doctor, result_event

STUB_CLI = "/artel-planka-stub/claude"
STUB_ARGV = [STUB_CLI, "-p", "--output-format", "stream-json", "--verbose",
             "--strict-mcp-config"]
ENV_MARKER = "ARTEL_PLANKA_PROVIDER_ENV"


def stub_command(*args, **kwargs):
    """Команда шага, собранная «провайдером» планки: заведомо не та, что
    собрал бы сегодняшний литерал."""
    return list(STUB_ARGV)


def stub_environment(*args, **kwargs):
    """Провайдерская часть окружения роли с опознаваемой меткой."""
    return {ENV_MARKER: "1"}


def command_without_strict_mcp(*args, **kwargs):
    """Та же команда, но без `--strict-mcp-config` — смок изоляции обязан
    это заметить, если читает argv у провайдера."""
    return [flag for flag in STUB_ARGV if flag != "--strict-mcp-config"]


class SmokesViaProviderTest(DoctorSandbox):
    """Оба смоука `orchestrator/doctor/` в офлайн-песочнице."""

    ROLE = "developer"

    def test_ac10_offline_part_of_both_smokes_is_green(self):
        """Смок изоляции зелёный, и офлайн-часть живого смоука (разбор
        кода возврата и стоимости на подменённом процессе) — тоже.

        Ловит мутацию: переезд сборки argv/окружения к провайдеру
        оставил смок изоляции без HOME курируемого слоя или без
        `--strict-mcp-config` — проверка, которая обязана быть зелёной на
        здоровом пульте, краснеет на ровном месте; либо живой смок
        перестал находить событие стоимости в потоке.
        """
        with offline_doctor():
            isolation = doctor.isolation_smoke(self.ROLE)
            live = doctor._live_smoke_run(self.ROLE)

        self.assertEqual(isolation.status, "ok", isolation.detail)
        self.assertEqual(live.status, "ok", live.detail)

    def test_ac10_isolation_smoke_reads_argv_from_the_provider(self):
        """Провайдер вернул команду без `--strict-mcp-config` — смок
        изоляции краснеет и называет MCP-вектор.

        Ловит мутацию: смок изоляции сверяет собственную копию флагов
        (или константу), а не argv провайдера — подменённая команда его
        не трогает, и на другом провайдере он проверял бы изоляцию
        чужого, не запускаемого шагом CLI.
        """
        with offline_doctor(), mock.patch.object(
                patch_target(), "command", command_without_strict_mcp):
            check = doctor.isolation_smoke(self.ROLE)

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("MCP", check.detail)

    def test_ac10_live_smoke_takes_argv_and_env_from_the_provider(self):
        """Живой смок запускает процесс тем argv и тем окружением,
        которые отдал провайдер.

        Ловит мутацию: живой смок по-прежнему собирает свой список
        (`["claude", "-p", ...]`) и зовёт `role_env` мимо провайдера —
        на другом провайдере он проверял бы живость не того CLI, что
        реально исполняет шаг.
        """
        recorded = []
        real_popen = doctor.subprocess.Popen

        def spy(cmd, *args, **kwargs):
            # Подмена `Popen` глобальна на модуль: `git config` внутри
            # сборки окружения обязан уйти в настоящий процесс, иначе
            # тест падал бы на собственной заглушке, а не на предмете.
            if cmd and Path(str(cmd[0])).name == "git":
                return real_popen(cmd, *args, **kwargs)
            recorded.append((list(cmd), dict(kwargs.get("env") or {})))
            return FakeLiveSmokeProc(result_event(0.01))

        with offline_doctor(popen=spy), \
                mock.patch.object(patch_target(), "command", stub_command), \
                mock.patch.object(patch_target(), "environment",
                                  stub_environment):
            check = doctor._live_smoke_run(self.ROLE)

        self.assertEqual(len(recorded), 1, recorded)
        cmd, env = recorded[0]
        self.assertEqual(cmd[0], STUB_CLI, cmd)
        self.assertIn(ENV_MARKER, env)
        self.assertEqual(check.status, "ok", check.detail)


if __name__ == "__main__":
    unittest.main()
