"""Шаг опроса `suite-run --wait` и `mutation-run --wait` — `config.SUITE_RUN_POLL_SEC`.

Группа: долгоживущий
Красен до реализации: константы `config.SUITE_RUN_POLL_SEC` ещё нет — `mock.patch.object(config, "SUITE_RUN_POLL_SEC", …)` падает AttributeError, а опрос спит собственным шагом модуля 1 с, не значением config.

Связка, которую держит файл: публичная команда (`suite_run.cmd_suite_run`
с `--wait`, `suite_run.wait_request`, `mutation_run.cmd_mutation_run` с
`--wait`) — файлы хозяйства прогона под `suite_lock.directory()` — пауза
опроса. Прогон «идёт»: файл прогона называет pid процесса теста, отчёта
нет. Пауза подменена `tests/sandbox.py::patch_sleep` у обоих модулей
(`suite_run`, `mutation_run`): подмена записывает длительность первой паузы
и обрывает ожидание исключением — время по-настоящему не идёт. Шаг в
`config` — случайный от зерна на каждом прогоне; зерно печатается и входит
в текст провала.
"""
import contextlib
import json
import os
import random

import pytest
from unittest import mock

from orchestrator import config, mutation_run, store, suite_lock, suite_run
from tests.sandbox import patch_sleep

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class PollStopped(Exception):
    """Подменённая пауза обрывает ожидание после первой паузы."""


def new_task(rng) -> str:
    task_id = "01M" + "".join(rng.choice(ALPHABET) for _ in range(23))
    store.insert_task(store.db(), task_id, "Фикстура шага опроса", "in_dev",
                      f"task-{task_id.lower()}-poll", config.DEFAULT_TARGET,
                      25.0)
    return task_id


def write_state(task_id: str, name: str) -> None:
    """Файл идущего прогона задачи: pid — живой процесс теста, отчёта нет."""
    folder = suite_lock.directory() / task_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps({
        "run": 1, "pid": os.getpid(), "log": str(folder / "run-1.log"),
        "mode": "full", "started": 0}), encoding="utf-8")


def first_pause(call, step: float) -> list:
    """Длительности пауз до обрыва: `call()` под шагом `step` в config."""
    pauses = []

    def sleep(seconds):
        pauses.append(seconds)
        raise PollStopped()

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(config, "SUITE_RUN_POLL_SEC",
                                              step))
        stack.enter_context(patch_sleep(suite_run, sleep))
        stack.enter_context(patch_sleep(mutation_run, sleep))
        with pytest.raises(PollStopped):
            call()
    return pauses


@pytest.mark.parametrize("entry", ["suite-run --wait", "wait_request"])
def test_ac1_suite_run_wait_sleeps_config_step(initialized_tmp_root, entry):
    """Опрос `suite-run --wait` спит ровно шагом, заданным в config.

    Сценарий: у задачи идёт прогон (`--wait` — файл прогона без запроса,
    опрос `_wait`; `wait_request` — запрос роли без итога). Ожидание на
    минуту запускается трижды, каждый раз с новым случайным шагом в
    `config.SUITE_RUN_POLL_SEC`; первая пауза опроса равна этому шагу.

    Ловит мутацию: опрос спит собственной константой модуля или литералом
    `1.0` — пауза 1.0 вместо подменённого шага; шаг читается из config один
    раз при импорте — вторая и третья подмены не меняют паузу.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    task_id = new_task(rng)
    if entry == "suite-run --wait":
        write_state(task_id, "run.json")

        def call():
            suite_run.cmd_suite_run([task_id, "--wait", "1"])
    else:
        def call():
            suite_run.wait_request(task_id, 1 + rng.randrange(50), 1,
                                   f"[{task_id}] suite-run", "suite-run")
    for _ in range(3):
        step = round(rng.uniform(0.05, 7.0), 3)
        pauses = first_pause(call, step)
        assert pauses == [step], (f"{entry}: паузы {pauses} при шаге {step}; "
                                  f"зерно: {seed}")


def test_ac2_mutation_run_wait_sleeps_config_step(initialized_tmp_root):
    """Опрос `mutation-run --wait` спит ровно шагом, заданным в config.

    Сценарий: у задачи идёт прогон `mutation-run` (файл прогона с pid
    процесса теста, отчёта нет). `mutation-run <id> --wait 1` запускается
    трижды с новым случайным шагом в `config.SUITE_RUN_POLL_SEC`; первая
    пауза опроса равна этому шагу.

    Ловит мутацию: `mutation_run` спит прежним шагом `suite_run` или своим
    литералом — пауза 1.0 вместо подменённого шага; опрос берёт шаг
    ожидания замка машины — пауза 10.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    task_id = new_task(rng)
    write_state(task_id, "mutation-run.json")
    for _ in range(3):
        step = round(rng.uniform(0.05, 7.0), 3)
        pauses = first_pause(
            lambda: mutation_run.cmd_mutation_run([task_id, "--wait", "1"]),
            step)
        assert pauses == [step], (f"паузы {pauses} при шаге {step}; "
                                  f"зерно: {seed}")
