"""Venv пульта: `.artel/venv`, создаётся идемпотентно средствами
стандартной библиотеки (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 2).

Интерпретатор venv — тот же `sys.executable`, которым запущен сам пульт
(`orchestrator.stack.REQUIRED_PYTHON`), не `python3` из PATH, который на
многоверсийной машине может указывать на другой интерпретатор (та же
причина 217 логов шагов со случайным pytest из pyenv Оператора, что и у
`runner.role_env`, SPEC «Контекст»).
"""
import subprocess
import sys
from pathlib import Path

from . import config


def _is_venv(target: Path) -> bool:
    """`pyvenv.cfg` — маркер, который `python -m venv` кладёт в корень
    созданного окружения; его наличие и есть «venv уже создан»."""
    return (target / "pyvenv.cfg").exists()


def sync(target: Path, lock_file: Path) -> None:
    """Создаёт `target` (если он ещё не venv) командой `python -m venv`
    тем же интерпретатором, что и сам пульт, затем ставит зависимости из
    `lock_file` внутрь него.

    Идемпотентно (AC-5): повторный вызов на уже созданном venv не зовёт
    `python -m venv` заново — только переустанавливает пакеты из
    `lock_file` (безвредно при уже согласованных версиях).
    """
    target = Path(target)
    lock_file = Path(lock_file)
    if not _is_venv(target):
        subprocess.run([sys.executable, "-m", "venv", str(target)], check=True)
    python = target / "bin" / "python"
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(lock_file)],
                   check=True)


def cmd_venv_sync() -> None:
    """`artel.py venv-sync` — синхронизирует `.artel/venv` с
    `requirements.lock` (требование 2, AC-4)."""
    sync(config.VENV_DIR, config.REQUIREMENTS_LOCK)
    print(f"venv синхронизирован: {config.VENV_DIR}")
