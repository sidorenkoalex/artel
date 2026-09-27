"""AC-4 (SPEC 01M3H3K73XBMJMD0EPXZX6HYY9): офлайн-смок
`codex-isolation-smoke` и проверка `foreign-provider-secrets` остаются
зелёными без изменения их ожиданий, а в окружение команд шага не
добавляются переменные вне белого списка манифеста и секреты чужих
провайдеров.

Зелёный с рождения: критерий — сохранение уже существующей изоляции
(«остаются зелёными», «не добавляются»), поэтому до реализации он зелен по
построению; ломается он ровно тогда, когда решение задачи ослабляет один
из двух рубежей — снимает ожидание смока либо открывает шагу ambient-мир
Оператора.

Чтение критерия, зафиксированное планкой: «не добавляются переменные вне
белого списка манифеста» — про переменные ОПЕРАТОРА (ambient) и секреты
чужих исполнителей, которые собранное окружение шага обязано отбрасывать.
Запрета на штатные каналы (накладка провайдера, ключ курируемого конфига
CLI) критерий не несёт — иначе он запрещал бы любое решение требования 1,
включая уже существующий `CODEX_HOME`; про сами эти каналы отвечает AC-3
симметрией половин.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import doctor, providers, roles, runner, stack  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

from _step_env import (AMBIENT_OUTSIDE_ALLOWLIST, AMBIENT_VALUE,  # noqa: E402
                       ProviderStepEnvSandbox)

SECRET_VALUE = "tokenchik-podpiski-operatora"

# AC-7: ci — три названных файла tests/ исполняет CI кодовой ветки и автогейт приёмки, планка их не дублирует.
# Критерий целиком про существующие tests/test_providers_codex.py,
# tests/test_providers.py и tests/test_provider_scoped_step_env.py
# («остаются зелёными без ослабления существующих проверок»): прогонять
# их же копией внутри планки нечем, а «без ослабления» сверяет ревьювер по
# диффу, прогон этого не видит. Пометка стоит в файле AC-4: тот же
# предмет — сохранение уже существующих проверок без их правки.


class CodexIsolationStaysGreenTest(ProviderStepEnvSandbox):

    def test_ac4_isolation_smoke_and_foreign_secrets_line_stay_green(self):
        """Обе строки `doctor` на собранном окружении шага Codex — не
        красные и не пропущенные: смок изоляции сверяет реальную команду и
        реальное окружение шага, строка чужих секретов — собранное
        окружение шагов ролей, и токен подписки Claude, заданный
        Оператором ambient, до шага Codex не доходит.

        Ловит мутацию: ключ или файл решения кладётся в окружение шага
        каналом, который смок читает как утечку (например переписан
        `CODEX_HOME` мимо курируемого дома либо в окружение вернулось одно
        из имён ключа API) — строка смока станет `fail`, и утверждение
        откажет, назвав причину текстом самой строки.
        """
        foreign = providers.get(providers.DEFAULT_PROVIDER).secret_env_names()
        self.assertTrue(foreign, "у провайдера по умолчанию нет имён секрета")

        with mock.patch.object(roles, "provider",
                              lambda role: codex_provider.CLI_NAME), \
             mock.patch.dict(os.environ,
                             {name: SECRET_VALUE for name in foreign}):
            smoke = doctor.codex_isolation_smoke("developer")
            secrets_line = doctor.check_foreign_provider_secrets()

        self.assertEqual(doctor.CODEX_SMOKE_CHECK, smoke.name)
        self.assertIn(smoke.status, ("ok", "warn"), smoke.detail)
        self.assertEqual(doctor.FOREIGN_SECRETS_CHECK, secrets_line.name)
        self.assertEqual("ok", secrets_line.status, secrets_line.detail)

    def test_ac4_isolation_smoke_expectations_still_bite(self):
        """Ожидания смока не ослаблены: стоит команде шага потерять
        песочницу `workspace-write` — та же строка отвечает `fail` и
        называет песочницу.

        Ловит мутацию: паритет окружения достигнут ценой ожидания смока
        (например проверка песочницы снята, чтобы пропустить новый флаг
        команды) — смок остаётся зелёным на команде без песочницы, и
        утверждение об отказе не сработает.
        """
        provider = providers.get(codex_provider.CLI_NAME)
        without_sandbox = [item for item in provider.command()
                           if item != codex_provider.SANDBOX_MODE]

        with mock.patch.object(type(provider), "command",
                              lambda self, model=None: list(without_sandbox)):
            smoke = doctor.codex_isolation_smoke("developer")

        self.assertEqual("fail", smoke.status, smoke.detail)
        self.assertIn(codex_provider.SANDBOX_MODE, smoke.detail)

    def test_ac4_ambient_variables_and_foreign_secrets_do_not_reach_the_step(self):
        """Собранное окружение шага Codex не несёт ни переменной Оператора
        вне белого списка манифеста, ни одного имени секрета чужого
        провайдера — при том, что оба заданы ambient.

        Ловит мутацию: ради паритета PATH окружение шага собирается копией
        `os.environ` (или белый список расширен префиксом «на всякий
        случай») — синтетическая переменная Оператора окажется в шаге, и
        утверждение откажет.
        """
        foreign = sorted(runner.foreign_secret_env_names(
            providers.get(codex_provider.CLI_NAME)))
        self.assertTrue(foreign, "чужих секретов в реестре нет — "
                                 "предпосылка критерия не воспроизведена")
        self.assertNotIn(AMBIENT_OUTSIDE_ALLOWLIST, stack.ROLE_ENV_ALLOWLIST)

        ambient = {name: SECRET_VALUE for name in foreign}
        ambient[AMBIENT_OUTSIDE_ALLOWLIST] = AMBIENT_VALUE
        env = self.step_env(codex_provider.CLI_NAME, ambient=ambient)

        self.assertNotIn(AMBIENT_OUTSIDE_ALLOWLIST, env, sorted(env))
        for name in foreign:
            self.assertNotIn(name, env, sorted(env))
        self.assertNotIn(AMBIENT_VALUE, set(env.values()))
        self.assertNotIn(SECRET_VALUE, set(env.values()))


if __name__ == "__main__":
    unittest.main()
