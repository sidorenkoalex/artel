"""Общая песочница приёмочных тестов T101 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

## Почему отдельный процесс на сценарий

Требование 3/AC-6 говорит о кэшировании «в рамках ОДНОГО процесса
оркестратора». Тесты этого набора управляют доступностью git/claude
(доступны/недоступны/таймаут) через подмену `subprocess.run` — если бы все
сценарии шли в одном процессе `unittest discover`, сценарий «git недоступен»
рисковал бы унаследовать уже закэшированное значение сценария «git доступен»
из другого теста ТОГО ЖЕ процесса (независимо от того, в каком именно модуле
разработчик разместит кэш — `agent_log.py`/`acceptance.py`/`runner.py`,
SPEC требование 6 оставляет это ему). Каждый сценарий поэтому запускается
отдельным `python3`-подпроцессом (`run_driver` ниже) — так вопрос «где
живёт кэш» не встаёт вовсе, а гарантия «один процесс» проверяется буквально.

## Допущение об интерфейсе

Сбор версии git/claude CLI предположительно идёт тем же приёмом, что уже
есть в кодовой базе для claude (`orchestrator/doctor.py::cli_version` —
прямой `subprocess.run([<бинарь>, "--version"], capture_output=True,
text=True, timeout=<секунды>)`, без обращения к `gitcmd.git` — тот
привязан к `cwd=config.ROOT` и создан для операций над репозиторием
пульта, а не для разовой проверки версии внешнего инструмента). Проверки
ниже нацелены на глобальный `subprocess.run` (мокается по образцу
`tests/test_brief.py`/`tests/test_fsm_map_regen.py`,
`mock.patch("subprocess.run", ...)` — перехватывает вызов из ЛЮБОГО
модуля, независимо от того, где разработчик разместит саму функцию сбора),
а не на конкретное имя функции/модуля сборщика — SPEC требование 6 отдаёт
выбор модуля (`acceptance.py`/`agent_log.py`) разработчику, тесты не
должны ломаться от этого выбора.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DRIVERS_DIR = Path(__file__).resolve().parent

# Таймаут ОБЁРТКИ подпроцесса-драйвера — не тот таймаут, что проверяет
# AC-2 (тот — внутри самого сбора fingerprint, единицы секунд). Это —
# страховка теста: если реализация не передаст `timeout=` во внешний
# вызов вовсе (дефект AC-2), сценарий "timeout" не зависнет навечно, а
# уронит тест по этой явной внешней границе.
DRIVER_WALL_CLOCK_TIMEOUT_SEC = 45


def run_driver(driver_name: str, *args: str,
               timeout: int = DRIVER_WALL_CLOCK_TIMEOUT_SEC) -> dict:
    """Прогоняет `_driver_<driver_name>.py` отдельным процессом python3,
    разбирает последнюю строку его stdout как JSON.

    Ошибка процесса (ненулевой rc, не-JSON, таймаут обёртки) — явный
    провал теста с полным stdout/stderr в сообщении, не тихий `{}`:
    драйверы этого набора гоняют настоящий код оркестратора, их
    собственный traceback — самая частая причина падения теста, и он
    обязан быть виден.
    """
    driver_path = DRIVERS_DIR / f"_driver_{driver_name}.py"
    try:
        res = subprocess.run(
            [sys.executable, str(driver_path), *args],
            capture_output=True, text=True, timeout=timeout, cwd=REPO_ROOT)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"драйвер {driver_name} не уложился в {timeout}с обёртки теста "
            f"(похоже, реализация не передаёт короткий timeout= во внешний "
            f"вызов, AC-2) — stdout так далеко: {exc.stdout!r}") from exc
    if res.returncode != 0:
        raise AssertionError(
            f"драйвер {driver_name} упал (rc={res.returncode}):\n"
            f"--- stdout ---\n{res.stdout}\n--- stderr ---\n{res.stderr}")
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    if not lines:
        raise AssertionError(f"драйвер {driver_name} не напечатал JSON; "
                             f"stderr: {res.stderr}")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"драйвер {driver_name}: последняя строка stdout — не JSON "
            f"({exc}): {lines[-1]!r}") from exc
