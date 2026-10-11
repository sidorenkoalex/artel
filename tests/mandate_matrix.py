"""Матрица неослабления во входах тестов, подающих `answer` мандат или
зовущих `zones-extend` (SPEC 01M4NZ5QRB7MNEYCWGXEWVWFP0, «Не входит»:
существующие сценарии получают матрицу во входных данных, их утверждения
не меняются).

Годная по форме матрица — пять канонических столбцов
(`docs/operator-gates.md`, «Матрица неослабления»), одна строка данных,
называющая все элементы мандата, свойство покрыто ссылкой на тест.
"""
import tempfile
from pathlib import Path

ZONES_MARKER = "Расширение зон разрешено:"
WEAKENING_MARKER = "Ослабление тестов разрешено:"
INDEPENDENT_CHECK_LINE = "Независимая проверка: матрица подтверждена"

HEADERS = ("Что меняется",
           "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
           "Остаётся ли свойство после изменения",
           "Чем покрыто после (тест файл:строка) или «не покрыто»",
           "Решение")


def matrix(elements) -> str:
    """Раздел `## Матрица неослабления`, называющий все `elements`."""
    row = (", ".join(f"`{e}`" for e in elements),
           "фикстура теста — tests/mandate_matrix.py:1", "да",
           "tests/mandate_matrix.py:1", "ок")
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(HEADERS) + " |\n"
            + "|" + "---|" * len(HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")


def _elements(text: str, marker: str) -> list[str]:
    found = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker):
            found += [e.strip() for e in stripped[len(marker):].split(",")
                      if e.strip()]
    return found


def with_matrix(text: str) -> str:
    """`text` файла `answer` с матрицей на все элементы его строк мандатов
    зон и тестов (и строкой независимой проверки при мандате тестов);
    без строк мандата — `text` как есть."""
    lines = [line.strip() for line in text.splitlines()]
    has_weakening = any(line.startswith(WEAKENING_MARKER) for line in lines)
    if not has_weakening and not any(line.startswith(ZONES_MARKER)
                                     for line in lines):
        return text
    elements = _elements(text, ZONES_MARKER) + _elements(text, WEAKENING_MARKER)
    tail = f"\n{INDEPENDENT_CHECK_LINE}\n" if has_weakening else ""
    return text.rstrip("\n") + "\n" + tail + "\n" + matrix(elements)


def matrix_file(test, paths_arg: str) -> str:
    """Файл матрицы для `zones-extend` на пути `paths_arg` (через запятую);
    удаляется по окончании теста `test`."""
    paths = [p.strip() for p in paths_arg.split(",") if p.strip()]
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                    encoding="utf-8")
    f.write(matrix(paths))
    f.close()
    test.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
    return f.name
