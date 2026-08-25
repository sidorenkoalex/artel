"""Команда `version`: пин CLI, фактическая версия, версия схемы артефактов
(T030, SPEC.md) — read-only, ничего не пишет.
"""
from . import config, doctor
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
