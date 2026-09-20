"""Тонкая надстройка сценария «провайдер роли» над песочницами `tests/`.

Своих копий песочниц здесь нет (скил test-authoring, роадмап §4): шаг
роли берётся готовым из `tests/test_runner_model_preflight.py`
(`_StepSandbox` — настоящий путь `runner.cmd_run`/`auto.cmd_auto` с
подменённым процессом агента), окружение `doctor` — из
`tests/test_doctor.py` (`_DoctorTmpRootTest`: временный `config`-корень
со `skills/`/`templates/` и подменённым keychain). Здесь — только то,
чего в них нет: поле `provider:` в `roles.yaml` шага и набор подмен, под
которыми `doctor` не зовёт живой CLI.
"""
import contextlib
from unittest import mock

from orchestrator import config, doctor, runner
from tests.sandbox import claude_only_popen, claude_only_run
from tests.test_doctor import (FakeLiveSmokeProc,  # noqa: F401
                               TmpRootTest as DoctorSandbox, result_event)
from tests.test_runner_model_preflight import TABLE_MODEL, _StepSandbox
from tests.test_runner_role_model import _roles_yaml_text

# Имя провайдера, которого нет и не будет в реестре (AC-4).
UNKNOWN_PROVIDER = "provider-kotorogo-net-v-reestre"


def roles_yaml_with_provider(role: str, provider_name: str,
                             model: str | None) -> str:
    """Реальный `roles.yaml` репозитория с полем `provider:` у роли
    `role` (и `model:` — тем же приёмом, что `_roles_yaml_text`).
    `provider_name=None` — поле не вставляется (роль без провайдера)."""
    text = _roles_yaml_text(role, model)
    if provider_name is None:
        return text
    anchor = f"  {role}:\n"
    if anchor not in text:
        raise AssertionError(f"роль {role!r} не найдена в roles.yaml")
    return text.replace(anchor, anchor + f"    provider: {provider_name}\n", 1)


class ProviderStepSandbox(_StepSandbox):
    """Шаг роли `developer` с управляемым полем `provider:` роли."""

    def set_provider(self, provider_name, model: str = TABLE_MODEL) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(roles_yaml_with_provider(self.ROLE, provider_name,
                                                 model), encoding="utf-8")
        self.patch(config, "ROLES", path)

    def refusal_text(self, printed: str) -> str:
        """Всё, что шаг сказал Оператору: stdout плюс текст `sys.exit` —
        отказ до старта агента оформлен то одним, то другим (`return`
        против `sys.exit`), а критерий говорит про строку отказа."""
        return f"{printed}\n{self.exit_message or ''}"


def doctor_patchers(popen=None) -> list:
    """Подмены, под которыми `doctor` остаётся офлайн: живой смоук не
    зовёт настоящий CLI, `claude --version` отвечает пином, keychain
    отдаёт токен. Тот же набор, что `tests/test_doctor.py` уже применяет
    к `all_checks`."""
    proc = FakeLiveSmokeProc(result_event(0.01))
    return [
        mock.patch.object(doctor.subprocess, "Popen",
                          popen if popen is not None
                          else claude_only_popen(proc)),
        mock.patch.object(doctor.subprocess, "run", claude_only_run(
            f"{config.CLI_VERSION_PIN} (Claude Code)\n")),
        mock.patch.object(runner.keychain, "token", lambda slot: "tok-test"),
    ]


@contextlib.contextmanager
def offline_doctor(popen=None):
    """Контекст всех подмен `doctor_patchers` разом."""
    with contextlib.ExitStack() as stack:
        for patcher in doctor_patchers(popen):
            stack.enter_context(patcher)
        yield


def rendered_checks(checks) -> str:
    """Проверки строками ровно так, как их печатает `cmd_doctor`
    (`orchestrator/doctor/cli.py`) — вывод команды без её побочных
    эффектов."""
    return "\n".join(f"  [{doctor.LABELS[c.status]}] {c.name}: {c.detail}"
                     for c in checks)
