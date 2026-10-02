"""AC-2: test_missing_cli_is_not_retried не зависит от CLI `claude` машины.

Группа: разовый
Красен до реализации: тест не изолирует предполётную сверку модели от настоящего `claude --version` — поддельный CLI со старой версией даёт отказ сверки до `spawn_agent`, и «один вызов» падает.

Тест целиком гоняется отдельным процессом pytest в окружениях, где CLI
провайдера (имя — из реестра провайдеров) отсутствует в PATH, отвечает
отказом, печатает нераспознанную версию, печатает заведомо старую
версию и печатает свежую версию. Во всех окружениях тест обязан быть
зелёным: свойство «не зависит от окружения машины, названного причиной».
"""
# AC-1: manual — верность установленной причины падения и того, что команда воспроизведения из PLAN.md на коде до исправления роняет именно названное утверждение, — вердикт по существу: SPEC не задаёт машинного формата причины и команды (свободный текст, команда может требовать подготовки окружения — порядка модулей, поддельного CLI), поэтому детерминированно извлечь и исполнить её тестом нельзя; детерминированное воспроизведение причины кодом держит AC-4.
import tempfile
import unittest
from pathlib import Path

from _plank import TARGET_NODE, env_with_fake_cli, run_pytest, tail


class IndependentOfCliEnvTest(unittest.TestCase):
    """Целевой тест зелёный при любом состоянии CLI `claude` в PATH."""

    def _assert_green(self, script_body):
        with tempfile.TemporaryDirectory() as tdir:
            env = env_with_fake_cli(Path(tdir), script_body)
            res = run_pytest([TARGET_NODE], env=env)
        self.assertEqual(res.returncode, 0,
                         f"{TARGET_NODE} не зелёный при CLI "
                         f"{script_body!r}:\n{tail(res)}")

    def test_ac2_green_without_cli_in_path(self):
        """CLI провайдера нет в PATH — целевой тест зелёный.

        Ловит мутацию: исправление подменяет только вывод настоящего
        `claude --version`, а не сам вызов — без CLI в PATH сверка идёт
        по другой ветке, и прогон отличается от окружения с CLI.
        """
        self._assert_green(None)

    def test_ac2_green_when_cli_refuses(self):
        """CLI отвечает отказом (код 1, пустой stdout) — целевой тест зелёный.

        Ловит мутацию: подмена сверки снята или стоит не там — отказ
        CLI доходит до предполёта, и шаг завершается иначе, чем ждёт тест.
        """
        self._assert_green('echo "boom" >&2; exit 1')

    def test_ac2_green_when_cli_version_unrecognized(self):
        """CLI печатает нераспознаваемую версию — целевой тест зелёный.

        Ловит мутацию: изоляция держит только случай «CLI есть и
        отвечает версией» — мусорный вывод уводит сверку в иную ветку.
        """
        self._assert_green('echo "claude: version unknown"; exit 0')

    def test_ac2_green_when_cli_version_is_old(self):
        """CLI печатает заведомо старую версию 0.0.1 — целевой тест зелёный.

        Ловит мутацию: тест по-прежнему зовёт настоящий `claude
        --version` — сверка модели отказывает до `spawn_agent`,
        `popen.call_count` равен 0, и прогон красный.
        """
        self._assert_green('echo "0.0.1 (Claude Code)"; exit 0')

    def test_ac2_green_when_cli_version_is_fresh(self):
        """CLI печатает заведомо свежую версию 999.0.0 — целевой тест зелёный.

        Ловит мутацию: исправление ломает сам тест (например, подмена
        уводит шаг мимо `spawn_agent`) — красный и в «хорошем» окружении.
        """
        self._assert_green('echo "999.0.0 (Claude Code)"; exit 0')


if __name__ == "__main__":
    unittest.main()
