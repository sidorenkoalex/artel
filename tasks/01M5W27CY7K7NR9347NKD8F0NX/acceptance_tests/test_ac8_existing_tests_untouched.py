"""AC-8: ветка задачи не меняет существующие тесты `tests/test_*.py`, в том числе файлы из «Контекста» SPEC, заводящие записи `gitlab`/`target-human`.

Группа: разовый
Зелёный с рождения: до реализации ветка задачи не трогает ни одного существующего файла `tests/` — тест держит это свойство до мержа (краснеет, если разработчик правит, переименует или удалит существующий тест).

Дифф задачи — `branch_diff()` помощника пульта `_pult.py` (база — точка
расхождения с `origin`, `DIFF_BASE`): блок файла с `new file mode` —
добавленный файл (долгоживущие файлы задачи законны), любой иной блок по
пути `tests/test_*.py` — правка, удаление или переименование
существующего теста. Поведение `new`/`run`/`approve` поддержанного
проекта держат сами существующие тесты этих команд на полном наборе;
отдельный позитивный тест `new` — в долгоживущем файле задачи
(`test_ac8_supported_project_new_is_not_refused`).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import branch_diff  # noqa: E402

# Файлы «Контекста» SPEC, заводящие записи `gitlab`/`target-human` как данные.
CONTEXT_FILES = (
    "tests/test_coldstart.py",
    "tests/test_multitarget.py",
    "tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py",
    "tests/test_doctor.py",
    "tests/test_github_adapter.py",
    "tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py",
)
HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)
EXISTING_TEST = re.compile(r"^tests/(.+/)?test_[^/]*\.py$")


def touched_existing_tests(diff: str) -> list[str]:
    """Пути существующих `tests/test_*.py`, которые дифф правит, удаляет
    или переименовывает (блок без `new file mode`)."""
    headers = list(HEADER.finditer(diff))
    touched = []
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(diff)
        block = diff[match.end():end]
        head = block.split("\n@@", 1)[0]
        if "\nnew file mode" in head:
            continue
        for path in (match.group(1), match.group(2)):
            if EXISTING_TEST.match(path) and path not in touched:
                touched.append(path)
    return touched


def test_ac8_existing_tests_not_changed_by_branch():
    """Закоммиченный дифф задачи не правит ни одного существующего `tests/test_*.py`.

    Сценарий: дифф ветки задачи от базы разбирается по блокам файлов;
    блоки добавленных файлов пропускаются, прочие блоки по путям тестов
    собираются. Список пуст; файлы «Контекста» SPEC в нём не встречаются
    (проверка названа отдельно, чтобы провал называл их явно).

    Ловит мутацию: разработчик подгоняет существующий тест под отказ
    (`tests/test_multitarget.py` заводит запись `merge_gate: target-human`
    и вызывает `new` — правка такого теста вместо сохранения поведения)
    — путь появится в списке, тест покраснеет.
    """
    touched = touched_existing_tests(branch_diff())
    context = [p for p in touched if p in CONTEXT_FILES]
    assert context == [], f"файлы «Контекста» SPEC изменены веткой: {context}"
    assert touched == [], f"существующие тесты изменены веткой: {touched}"
