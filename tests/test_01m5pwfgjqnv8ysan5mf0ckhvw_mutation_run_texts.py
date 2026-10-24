"""Тексты команды `mutation-run`: справка, строка «Команды:», модульный докстринг, имя копии таблицы.

Группа: долгоживущий
Красен до реализации: `USAGE` модуля `orchestrator/mutation_run.py` и запись `mutation-run` блока «Команды:» докстринга `orchestrator/artel.py` не называют `--wait-lock`, `--copy-table` и `--workers`, а модульный докстринг ещё говорит «занятый замок — отказ сразу» и «Документы задачи, её ветка и рабочая копия командой не меняются»; тест AC-14 держит прежнее свойство guard и зелен с рождения.

Свойства без песочницы: чтение докстрингов, константы `USAGE` и вызов
чистой функции guard. Пробелы и переводы строк докстрингов сжимаются до
одного пробела перед поиском фраз — перенос строки фразу не прячет.
"""
import random
import re

import pytest

from orchestrator import artel, mutation_run
from scripts import guard

FLAGS = ("--wait-lock", "--copy-table", "--workers")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def commands_entry() -> str:
    """Запись `mutation-run` блока «Команды:» докстринга `artel.py` с её
    строками продолжения (отступ глубже двух пробелов)."""
    doc = artel.__doc__ or ""
    head = doc.index("Команды:")
    lines = doc[head:].split("\n")
    for index, line in enumerate(lines):
        if line.lstrip().startswith("mutation-run"):
            entry = [line]
            for more in lines[index + 1:]:
                if not more.startswith("   "):
                    break
                entry.append(more)
            return "\n".join(entry)
    return ""


@pytest.mark.parametrize("flag", FLAGS)
def test_ac15_usage_and_commands_entry_name_flag(flag):
    """Справка `USAGE` и запись `mutation-run` блока «Команды:» называют флаг.

    Сценарий: для каждого из `--wait-lock`, `--copy-table`, `--workers`
    флаг ищется в константе `mutation_run.USAGE` и в записи `mutation-run`
    блока «Команды:» модульного докстринга `orchestrator/artel.py` (строка
    записи и её строки продолжения).

    Ловит мутацию: флаг разобран командой, но не добавлен в `USAGE` — его
    нет в справке; строка «Команды:» `artel.py` не обновлена — флага нет в
    записи `mutation-run`; флаг вписан в запись другой команды
    (`suite-run`) вместо `mutation-run`.
    """
    entry = commands_entry()
    assert entry, "в блоке «Команды:» докстринга artel.py нет записи mutation-run"
    assert flag in mutation_run.USAGE, mutation_run.USAGE
    assert flag in entry, entry


def test_ac18_module_docstring_describes_new_behaviour():
    """Модульный докстринг `mutation_run` называет новые флаги и не несёт двух прежних фраз.

    Сценарий: докстринг модуля `orchestrator/mutation_run.py` со сжатыми
    пробелами содержит `--wait-lock` и `--copy-table` и не содержит фраз
    «занятый замок — отказ сразу» и «Документы задачи, её ветка и рабочая
    копия командой не меняются».

    Ловит мутацию: докстринг не переписан — прежние фразы остались; флаги
    добавлены только в `USAGE`, а докстринг их не называет; переписана
    одна из двух фраз, вторая осталась.
    """
    doc = flat(mutation_run.__doc__)
    assert "--wait-lock" in doc, doc
    assert "--copy-table" in doc, doc
    assert "занятый замок — отказ сразу" not in doc, doc
    assert ("Документы задачи, её ветка и рабочая копия командой не меняются"
            not in doc), doc


def test_ac14_copy_table_name_not_extraneous():
    """Имя копии `mutation-run-<n>.tsv` первого уровня каталога задачи guard не считает посторонним.

    Сценарий: `guard.is_extraneous_task_root_file` для
    `mutation-run-3.tsv` и для имён с номерами от зерна возвращает ложь.

    Ловит мутацию: guard начинает считать посторонними файлы первого
    уровня вне перечня `.md` (например, всё, что не `.md`/`.diff`), — имя
    копии таблицы становится посторонним, и пульт откажет шагу
    «посторонние файлы».
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    names = ["mutation-run-3.tsv"] + [f"mutation-run-{rng.randint(1, 999)}.tsv"
                                      for _ in range(3)]
    for name in names:
        assert guard.is_extraneous_task_root_file(name) is False, \
            f"зерно: {seed}; {name}"
