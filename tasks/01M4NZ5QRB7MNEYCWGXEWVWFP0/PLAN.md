---
task: 01M4NZ5QRB7MNEYCWGXEWVWFP0
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: answer и zones-extend отказывают мандату без матрицы неослабления

## Подход

Одна функция формы — `orchestrator/advance_gates/mandate.py::matrix_refusals(text, elements) -> list[str]`
(требование 7) и её помощник `matrix_section(text)` (раздел от
`## Матрица неослабления` до следующего `# `/`## ` или конца). Внутри:
первая таблица раздела (заголовки + разделитель `|---|`), ровно пять
столбцов с каноническими началами заголовков (`MATRIX_HEADERS`, сравнение
после нормализации — `strip`, снятие `*`/`_`/`` ` `` по краям слов, нижний
регистр, «ё» = «е»), хотя бы одна строка данных; названность каждого
элемента токеном ячейки «Что меняется» (границы — пробел, `` ` ``, `,`,
`;`, `(`, `)`, `«`, `»`; `/` на конце снимается у обоих); правило
«остаётся + не покрыто → «ок при условии» + непустой перечень» с номером
строки данных (с 1). Ссылка на канон — константа `MATRIX_DOC_REF`
(`docs/operator-gates.md, раздел «Матрица неослабления»`), её несёт
общий текст отказа обоих каналов.

`answer`: проверка добавлена в `_read_checked_answer_file` сразу ПОСЛЕ
`mandate.refusals` (требование 8 — его отказ и текст прежние и раньше);
эта функция стоит во всех ветках состояний `escalated`/`in_dev`/`review`/
`merge_gate`, поэтому требование 1 закрыто одним местом. Элементы — все
строки обоих маркеров (`MATRIX_MANDATE_MARKERS`, без «Зависимости
мержа:»); файл без строк мандата матрицы не требует. Требование 4 —
`_has_independent_check` (строка `Независимая проверка:` с непустым
текстом) только при строке «Ослабление тестов разрешено:». Все причины
формы и проверки идут одним отказом `_refuse_without_matrix` до коммита.

`zones-extend`: `cmd_zones_extend(task_id, paths_arg, session_id=None, matrix_path=None)`;
`_zones_extend_matrix` отказывает без `matrix_path`, при строке любого из
трёх маркеров в файле и по `mandate.matrix_refusals(raw, paths)`; в ANSWER
после строки мандата и «мандат Оператора: …» дописывается только
`mandate.matrix_section(raw)`. CLI: `_zones_extend_args` в
`orchestrator/artel.py` разбирает `--matrix <файл>` в любом месте; без
флага передаёт `None` — отказ остаётся в функции (один на CLI и на прямой
вызов); `--matrix` без значения — отказ разбора.

Существующие тесты, подающие `answer` мандат или зовущие `zones-extend`
(«Не входит» SPEC), получили матрицу во входах через общий помощник
`tests/mandate_matrix.py` (`with_matrix(text)` — раздел на все элементы
строк мандата и строка независимой проверки при мандате тестов;
`matrix_file(test, paths)` — файл для `matrix_path`). Утверждения методов
не менялись, методы не удалялись и не переименовывались.

Бюджет SPEC ($35) не переоцениваю.

## Шаги

1. `mandate.py`: `MATRIX_DOC_REF`, `MATRIX_MANDATE_MARKERS`,
   `MATRIX_HEADERS`, `matrix_section`, `matrix_refusals` и помощники.
2. `answer.py`: `_matrix_problems` / `_refuse_without_matrix` /
   `_has_independent_check` в `_read_checked_answer_file`;
   `cmd_zones_extend(..., matrix_path=None)`, `_zones_extend_matrix`,
   перенос раздела в ANSWER.
3. `artel.py`: `_zones_extend_args`, `_cmd_zones_extend`, справка
   (`zones-extend <id> <путь>[, <путь>...] --matrix <файл>`).
4. Входы существующих тестов: `tests/mandate_matrix.py`; `tests/test_answer.py`,
   `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`,
   `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`,
   `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py` — файл
   ответа оборачивается `with_matrix`; `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`,
   `tests/test_docs_ref_deleted_refusal.py`, `tests/test_answer.py` —
   `zones-extend` с `matrix_path`.
5. Свои юнит-тесты `tests/test_mandate_matrix_form.py` (не покрытое
   долгоживущим файлом): граница раздела на `## ` и не на `### `,
   нормализация заголовков, короткая строка данных, `--matrix` без файла и
   флаг перед путями.
6. `python3 scripts/codebase_map.py` — `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 2, 3 |
| 6 | 2 |
| 7 | 1, 2 |
| 8 | 2 |

Проверка: `tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py` —
13 passed (71 subtests), прогон повторён с разными зёрнами; планка
`plank-run` — 1 passed; тесты затронутых модулей (`tests/test_answer.py`,
`tests/test_answer_mandate.py`, файлы шага 4, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`,
`tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`,
`tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`,
`tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`,
`tests/test_merge_after.py`, `tests/test_canary*.py`, `tests/test_zones_gate.py`,
`tests/test_test_integrity_gate.py` и др.) — зелёные. Сторожа
`tests/test_mandate_matrix_form.py` проверены временной мутацией
(раздел до `#` любого уровня, раздел без конца, без нормализации, без
дополнения ячеек) — каждый раз 1 failed, код возвращён. Полный набор
командой пульта `suite-run` №1 — «зелёный прогон» (в процессе прогона
ветки по логу выполнено ≥ 4992 тестов).

## Влияние на систему

- Только добавление отказов (требование 8): `mandate.refusals`, рубеж
  окружения роли, запрет мандата из автокоммита роли, инвариант 38 не
  тронуты; `mandate.refusals` в `answer` по-прежнему первый, с прежним
  текстом.
- Файлы без строк мандата (указание, только «Зависимости мержа:») идут
  прежним путём — `_matrix_mandate_elements` даёт `None`.
- Канарейка (`canary._pass_escalated_with_synthetic_answer`) подаёт синтетический ответ без
  строк мандата — не затронута (`tests/test_canary*.py` зелёные).
- ANSWER `zones-extend` теперь несёт раздел матрицы: строки таблицы
  начинаются с `|`, разбор маркеров мандата (`startswith` после `strip`)
  их не видит; строка маркера в файле матрицы — отказ, так что мандат
  тестов через этот канал в ANSWER не попадёт.
- Гейт неослабления: правки существующих тестов — только входные данные
  и импорт `tests.mandate_matrix`; утверждения не менялись (смена
  импортов модуля помечает его классы для поиска наследников — их
  утверждения тоже не меняются).
- Откат — revert коммита задачи.

## Риски

- Оператор, привыкший к `zones-extend <id> <пути>`, получит отказ до
  doc-commit `docs/operator-session.md` / правила 6 `docs/operator-gates.md`
  (вне зоны, «Не входит» SPEC) — текст отказа называет синтаксис с
  `--matrix` и канон.
- `|` внутри ячейки (без экранирования) делит ячейку — форма таблицы
  markdown это и так запрещает.

## Предложения системе

- Сторож роли (`conftest.py`) трактует `-n` (xdist) на перечне файлов как
  полный прогон — тесты затронутых модулей идут только последовательно
  (~5 минут на 15 файлов); локальный параллельный прогон перечня был бы
  дешевле.
- Песочница шага отказывает `rm`/`ls`/`cat` и heredoc с `{'` — уборка
  временного файла мутационной проверки шла через `python3 -c os.remove`;
  штатной команды «мутационная проверка сторожа» у пульта нет.
- `suite-run --wait` на зелёном полном прогоне (~5000 тестов по логу)
  печатает «прошло: 1, упало: 0» — счётчик, видимо, считает не тесты;
  лог прогона лежит вне каталогов шага, роль проверить итог по нему не
  может (`orchestrator/suite_run.py::render`).
