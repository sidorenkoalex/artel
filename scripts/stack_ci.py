#!/usr/bin/env python3
"""CI-обвязка манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H, требования 1-3):
единственное место, читающее `orchestrator/stack.py` и печатающее версию
Python в формате, который принимает `actions/setup-python` как значение
`python-version`. Вся логика чтения манифеста живёт здесь, не в
`.github/workflows/ci.yml` (требование 3/AC-6) — диф-приложение к ci.yml
только вызывает этот скрипт.

Использование:
    python3 scripts/stack_ci.py         # текущая стабильная версия (CI/dev)
    python3 scripts/stack_ci.py --min   # минимальная объявленная версия

Печатает ровно одну строку без постороннего текста — так, как
`actions/setup-python` ожидает значение `python-version` (AC-3).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import stack  # noqa: E402


def minimum_python_version_string() -> str:
    """Нижняя граница матрицы требования 2 — `REQUIRED_PYTHON` манифеста,
    отформатированная так же, как `stack.python_version_string()`."""
    return ".".join(str(part) for part in stack.REQUIRED_PYTHON)


def main(argv: list) -> int:
    version = minimum_python_version_string() if "--min" in argv \
        else stack.python_version_string()
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
