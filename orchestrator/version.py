"""Команда `version`: пин CLI, фактическая версия, версия схемы артефактов
(T030, SPEC.md), версия Python исполнителя и результат объявленного
стека (SPEC 01M1RDCAFENSW2VVAPECHCVGMM, требование 6) — read-only,
ничего не пишет.
"""
import sys

from . import config, doctor, stack
from scripts import guard


def cmd_version() -> None:
    pin = config.CLI_VERSION_PIN
    installed = doctor.cli_version()
    installed_display = installed if installed is not None else "не определилась"

    print(f"CLI (пин из конфига): {pin}")
    print(f"CLI (установлена):    {installed_display}")
    print(f"Схема артефактов:     {guard.SUPPORTED_SCHEMA_VERSION}")
    if installed is not None and installed != pin:
        print(f"РАСХОЖДЕНИЕ: установлена {installed}, пин {pin} — "
              f"обновление пина (config.CLI_VERSION_PIN) — осознанный шаг "
              f"Оператора, не автоматика")

    running_python = ".".join(str(part) for part in sys.version_info[:3])
    print(f"Python (фактическая): {running_python}")
    for check in stack.check_stack():
        label = doctor.LABELS.get(check.status, check.status)
        print(f"Стек [{label}] {check.name}: {check.detail}")
