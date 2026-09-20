"""AC-7: вердикт совместимости модели — через `model_verdict(model)`
провайдера; отказы до старта агента по модели, CLI и секрету — прежние.

Красен до реализации: реестра провайдеров ещё нет, подменять вердикт не
на чем — часть файла про отказы по CLI и секрету проверяет сохранение
существующего поведения и зелена уже сегодня.
"""
import inspect
import unittest
from unittest import mock

from orchestrator import config, doctor, runner, stack
from _sandbox import DoctorSandbox, ProviderStepSandbox
from _providers import patch_target
from tests.test_runner_model_preflight import TABLE_MODEL

VERDICT_DETAIL = (f"{stack.MODEL_UNSUPPORTED_PREFIX}: вердикт подменён "
                  f"планкой на стороне провайдера")


def fake_verdict(*args, **kwargs):
    """Вердикт провайдера, подменённый планкой: форма та же, что у
    сегодняшнего `stack.model_cli_verdict`."""
    return stack.ModelCliVerdict("fail", VERDICT_DETAIL)


class ProviderVerdictStepTest(ProviderStepSandbox):
    """Роль `developer` без поля `provider:` (то есть на `claude`) с
    моделью из таблицы совместимости и заведомо свежим CLI."""

    def setUp(self):
        super().setUp()
        self.set_provider(None, TABLE_MODEL)
        self.set_cli_version("9.9.9")

    def test_ac7_refusal_before_start_takes_the_verdict_from_the_provider(self):
        """Провайдер сказал `fail` — шаг отказывает его текстом и не
        запускает агента, хотя версия CLI заведомо выше минимума.

        Ловит мутацию: `_refuse_before_start` по-прежнему зовёт
        `stack.model_cli_verdict` напрямую — подменённый вердикт
        провайдера ни на что не влияет, шаг спокойно стартует агента
        (а роль на другом CLI получила бы сверку по чужой таблице).
        """
        with mock.patch.object(patch_target(), "model_verdict", fake_verdict):
            out = self.run_step()

        self.spawn.assert_not_called()
        self.assertIn(VERDICT_DETAIL, self.refusal_text(out))

    def test_ac7_resolved_role_model_keeps_its_contract(self):
        """`_resolved_role_model(role)` остаётся с прежней сигнатурой и
        отдаёт модель роли из `roles.yaml`.

        Ловит мутацию: функция переписана под провайдера и стала
        возвращать вердикт (или принимать провайдера параметром) — 101
        патч по имени модуля в тестах попытки шага перестаёт совпадать,
        а `--model` в argv попытки собирается из другого источника.
        """
        self.assertEqual(
            list(inspect.signature(runner._resolved_role_model).parameters),
            ["role"])
        self.assertEqual(runner._resolved_role_model(self.ROLE), TABLE_MODEL)


class PreStartRefusalsTest(DoctorSandbox):
    """Отказы предполёта, останавливающие шаг до агента, — по секрету и
    по найденности CLI."""

    ROLE = "developer"

    def failed_names(self) -> list:
        checks = doctor.preflight_checks(self.ROLE, config.DEFAULT_TARGET)
        return [c.name for c in checks if c.status == "fail"]

    def test_ac7_missing_secret_still_refuses_before_the_agent(self):
        """Токена роли нет ни в окружении, ни в keychain — предполёт
        даёт блокирующий провал `token`.

        Ловит мутацию: проверка секрета переехала в провайдера и
        потеряла блокирующий статус (стала `warn`) — шаг стартует агента
        без токена и платит попыткой за отказ CLI.
        """
        with mock.patch.object(runner.keychain, "token", lambda slot: None):
            self.assertIn("token", self.failed_names())

    def test_ac7_missing_cli_still_refuses_before_the_agent(self):
        """CLI не найден в PATH — предполёт даёт блокирующий провал
        `cli-found`.

        Ловит мутацию: проверка найденности CLI переехала в провайдера,
        но её исход перестал блокировать шаг (или потерял имя) — шаг
        уходит в попытку, которая заведомо не состоится.
        """
        which = doctor.shutil.which
        with mock.patch.object(
                doctor.shutil, "which",
                lambda name, *a, **kw: None if name == "claude"
                else which(name, *a, **kw)):
            self.assertIn("cli-found", self.failed_names())


if __name__ == "__main__":
    unittest.main()
