"""AC-2: вторая правка `target-set` в ту же секунду не затирает первую копию прежнего файла.

Группа: разовый
Красен до реализации: функции-шва `projects._backup_stamp` и команды `target-set` ещё нет — подмена шва падает `AttributeError`.

Почему файл в планке, а не в `tests/`: критерий проверяется подменой
закрытого шва `projects._backup_stamp`, который SPEC (требование 6)
называет именно для этого теста, а долгоживущему файлу подмена закрытых
имён `orchestrator` запрещена. Само свойство «копия создаётся без
перезаписи» держат и долгоживущие тесты задачи
(`tests/test_<id>_target_set.py`, AC-1: ровно одна копия с байтами
прежнего файла).

Песочница — `initialized_tmp_root` (`tests/fixtures.py`): пути `config`
(`TARGETS`, `LOGS`, `DB`) во временном каталоге, БД со схемой; настоящий
локальный слой пульта не читается и не пишется. Команда зовётся как из
командной строки: `sys.argv` подменён, `artel.main()`.
"""
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, projects
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
STAMP = "20261104T120000Z"


def word(rng) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(6))


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def record(name: str) -> str:
    return (f"targets:\n  {name}:\n"
            f"    description:\n      base: main\n      components:\n"
            f"        app:\n          runner: pytest-own\n"
            f"          command: [python3, -m, pytest]\n"
            f"          report: junit-xml\n          paths: ^app/\n"
            f"          long_lived: app/tests/test_<id>_<name>.py\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


@pytest.fixture
def cli(initialized_tmp_root, capsys):
    """Вызов команды как из командной строки в песочнице `config`."""

    def run(*argv) -> tuple:
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        out = capsys.readouterr()
        return code in (0, None), f"{code}\n{out.out}\n{out.err}"

    return run


def test_ac2_second_edit_same_second_keeps_first_copy(cli):
    """Две правки при одном и том же времени шва — в `config.LOGS` две копии, первая байт в байт прежний файл.

    Сценарий: локальный слой — запись `sandbox`; `projects._backup_stamp`
    подменена и возвращает одно время. Первая правка `policy.sandbox`,
    затем вторая другим значением; обе успешны. В `config.LOGS` ровно две
    копии `targets-*.yaml`: одна — байты файла до первой правки, другая —
    байты файла после первой правки (до второй).

    Ловит мутацию: копия пишется открытием на запись с перезаписью (`w`,
    `shutil.copy`) — вторая правка затирает первую копию, и в `config.LOGS`
    остаётся одна копия с текстом после первой правки.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    local_file().parent.mkdir(parents=True, exist_ok=True)
    local_file().write_text(record("sandbox"), encoding="utf-8")
    original = local_file().read_bytes()
    with mock.patch.object(projects, "_backup_stamp", return_value=STAMP):
        ok, out = cli("target-set", "sandbox", "policy.sandbox", "a" + word(rng))
        assert ok, f"зерно: {seed}; {out}"
        middle = local_file().read_bytes()
        ok, out = cli("target-set", "sandbox", "policy.sandbox", "b" + word(rng))
        assert ok, f"зерно: {seed}; {out}"
    found = sorted(config.LOGS.glob("targets-*.yaml"))
    assert len(found) == 2, f"зерно: {seed}; {found}"
    contents = sorted(path.read_bytes() for path in found)
    assert contents == sorted([original, middle]), f"зерно: {seed}"
