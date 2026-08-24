"""Чтение токенов из macOS keychain.

Отдельный модуль по той же причине, что и gitcmd: тесты runner'а
подменяют `runner.subprocess.Popen` целиком, и системный вызов,
живущий в runner, попадал бы под подмену агентского CLI.
"""
import subprocess


def token(slot: str) -> str | None:
    """Токен по имени слота; None — не нашёлся.

    Любой отказ (нет `security` вне macOS, нет записи, таймаут) — None,
    не исключение: решает и отчитывается вызывающий, у которого есть
    журнал и задача.
    """
    try:
        res = subprocess.run(
            ["security", "find-generic-password", "-s", slot, "-w"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None
