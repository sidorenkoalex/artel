"""Сборка `tests/test_merge_after_module.py` волны 3м-2б: модуль базы (HEAD
ветки до свода) + абзац докстринга + недостающие импорты + `sections.txt`
(`convert.py`) с переписанными заявками; удаление шести файлов волны.

Запуск из рабочей копии задачи: python3 <путь>/assemble.py
"""
import pathlib
import re
import subprocess

DOCS = pathlib.Path(__file__).resolve().parent
MODULE = "tests/test_merge_after_module.py"
BASE = "ad3608c6d2ceedd43f2d91ad569a6b8684804782"
FILES = [
    "tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py",
    "tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py",
    "tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py",
    "tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py",
    "tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py",
    "tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py",
]

PARAGRAPH = '''
Волна 3м-2б (SPEC 01M5RHGRH3YJV8VBFH3QCHD8X0) дописала в конец модуля
свод шести долгоживущих файлов, по разделу на файл:
- `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py` — мандат
  Оператора «Зависимости мержа: …» в ANSWER-n.md (`escalated`,
  `merge_gate`, отказ до коммита);
- `tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py` — форма
  поля `merge_after` SPEC в guard;
- `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py` — канал PLAN
  на переходе `in_dev -> verifying`;
- `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py` —
  проверка значения по БД на `approve` гейта SPEC;
- `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py` —
  добавка «[ждёт мержа: …]» `status` и строка зависимостей `show`
  (эти пять — SPEC 01M44EP0D47F498TEE08MNGBYT);
- `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py` —
  заявление зависимостей строкой ТЗ «Порядок: после …» при `new --tz`
  (SPEC 01M45D29BQJE8FJYJA4JQWSYFZ).

Стенды этих разделов — фикстуры с телами прежних `setUp`: `answer_stand`,
`guard_stand`, `plan_stand`, `spec_gate_stand`, `status_show_stand`,
`new_declares_stand`; методы песочниц — функции с префиксом имени
прежнего файла. Подслучаи `subTest` — прежними циклами с ярлыком в тексте
сообщения каждого утверждения.
'''

CLAIMS = {
    "test_ac11_escalated_answer_sets_and_clears_value": """\
    Ловит мутацию: значение строки мандата не применяется
    (`merge_after.mandate_value` отдаёт перечень причин `check` вместо
    полных id) либо «нет» читается как id задачи — колонка расходится с
    ожидаемой или ANSWER отказан.""",
    "test_ac9_justified_plan_value_replaces_db_value": """\
    Ловит мутацию: значение PLAN, отличное от БД, не применяется
    (сравнение с прежним значением перевёрнуто) или запись журнала «было →
    стало» не называет новое значение — колонка расходится с полными id
    либо записи, называющей прежние и новые id, нет.""",
    "test_ac9_plan_without_field_keeps_db_value": """\
    Ловит мутацию: отсутствие поля в PLAN снимает зависимости (колонка
    очищается) — колонка не равна прежнему перечню.""",
    "test_ac4_cycle_through_existing_values_refused": """\
    Ловит мутацию: проверка цикла снята — значение с циклом записывается
    в колонку, задача уходит с гейта.""",
    "test_ac5_prefixes_written_as_full_ids_in_spec_order": """\
    Ловит мутацию: `approve` гейта SPEC не пишет проверенное значение в
    колонку — перечень колонки пуст вместо полных id в порядке SPEC.""",
    "test_ac13_status_suffix_lists_unfinished_and_disappears_after_done": """\
    Ловит мутацию: состояния зависимостей кэшируются (не читаются из БД
    на каждый вызов) либо добавка включает и завершённые зависимости —
    после перевода в `done` добавка остаётся.""",
    "test_ac13_no_suffix_without_field_or_all_done": """\
    Ловит мутацию: условие «есть зависимости не в done» снято — добавка
    печатается и с пустым перечнем незавершённых.""",
    "test_ac1_order_line_declares_full_ids_in_line_order": """\
    Ловит мутацию: заявленное значение не пишется в колонку либо порядок
    id обращён — перечень колонки расходится с ожидаемым; либо запись
    журнала не делается — записи с действием нет.""",
    "test_ac2_list_ends_at_parenthesis_or_dot": """\
    Ловит мутацию: перечень берётся до конца строки (ни скобка, ни точка
    не режут хвост) — `new` отказывает элементом «(пояснение …».""",
    "test_ac5_repeated_order_line_refused_without_traces": """\
    Ловит мутацию: повтор строки не сверяется и берётся первая либо
    последняя строка — задача заводится.""",
}


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True).stdout


def main():
    text = git("show", f"{BASE}:{MODULE}")
    end = text.index('"""', 3)
    text = text[:end] + PARAGRAPH + text[end:]
    for old, new in (("import random\n", "import random\nimport re\n"),
                     ("import sqlite3\n", "import sqlite3\nimport subprocess\n"),
                     ("                          schema, store)\n",
                      "                          schema, store)\n"
                      "from orchestrator import github_adapter, workspace\n"),
                     ("from orchestrator.advance_gates import mandate\n",
                      "from orchestrator.advance_gates import mandate\n"
                      "from scripts import guard\n")):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    sections = (DOCS / "sections.txt").read_text(encoding="utf-8")
    for name, claim in CLAIMS.items():
        pattern = re.compile(rf"(def {name}\(.*?\n)    Ловит мутацию:.*?(\n    \"\"\")",
                             re.S)
        sections, count = pattern.subn(lambda m: m.group(1) + claim + m.group(2),
                                       sections, count=1)
        assert count == 1, name
    pathlib.Path(MODULE).write_text(text.rstrip("\n") + "\n\n\n" + sections,
                                    encoding="utf-8")
    for path in FILES:
        p = pathlib.Path(path)
        if p.exists():
            p.unlink()
    print("собрано")


if __name__ == "__main__":
    main()
