"""Существующий тест формы `--from-file` задачи 01M6QZ4RR80B2BYM9AXG5ZMAS4 проходит на коде задачи без правки файла теста.

Группа: разовый
Зелёный с рождения: на базе ветки файл теста не тронут и зелен (перечень проверяется вхождением прежнего литерала), критерий держит, что дописывание `machine.commit_author` в конец `BLOCK_PATHS` его не ломает и файл не правится; проверено на временном стабе — зелен и с ним.

Факт задачи: путь файла теста не входит в пути задачи (`changed_paths()`
помощника пульта — закоммиченный дифф от базы и неотслеживаемые файлы), а
прогон файла тем же pytest с теми же флагами из корня рабочей копии
(`CODE_ROOT`) кончается кодом 0. Дочерний процесс — в своей группе
процессов с пределом времени; по пределу группа снимается целиком.
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

EXISTING = "tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py"
LIMIT = 100


def test_ac5_existing_block_test_unchanged_and_green():
    """Файл теста формы `--from-file` не тронут задачей, и его прогон на коде задачи зелен.

    Сценарий: путь `tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py`
    есть в рабочей копии и не входит в `changed_paths()`; `python3 -m pytest
    <файл> -p no:cacheprovider -p timeout -o timeout=120` из `CODE_ROOT`
    кончается кодом 0.

    Ловит мутацию: перечень `BLOCK_PATHS` переписан не дописыванием в конец
    (новый путь вставлен в середину или прежний текст изменён) — `test_ac4`
    существующего файла краснеет; разработчик подогнал файл теста под код
    (путь входит в пути задачи); путь `machine.*` принят шире — отказ
    `machine.submodule_tokens` в существующем `test_ac4` пропал.
    """
    root = Path(CODE_ROOT)
    assert (root / EXISTING).is_file(), EXISTING
    assert EXISTING not in changed_paths(), changed_paths()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", EXISTING, "-p", "no:cacheprovider",
         "-p", "timeout", "-o", "timeout=120", "-q"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=LIMIT)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        raise AssertionError(f"прогон {EXISTING} не кончился за {LIMIT} с:\n{out}")
    assert proc.returncode == 0, out[-4000:]
