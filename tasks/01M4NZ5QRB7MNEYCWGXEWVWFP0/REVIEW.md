---
task: 01M4NZ5QRB7MNEYCWGXEWVWFP0
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: answer и zones-extend отказывают мандату без матрицы неослабления (ADR-0022 п.4)

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–3 (код), шаг 4 —
  входы существующих тестов по «Не входит» SPEC, шаг 5 — свои юнит-тесты,
  шаг 6 — карта. Шаги проверяемы и размером с MR.
- Подход не расходится с архитектурой: одна функция формы в
  `advance_gates/mandate.py` (рядом с `elements`/`refusals`), вызов в
  `_read_checked_answer_file` — единственной точке чтения файла во всех
  принимающих ветках `_cmd_answer` (`escalated` :332, `in_dev`/`review`
  :337, `merge_gate` :351) — требование 1 закрыто одним местом.
- «Влияние на систему» сверено с diff: изменены ровно `mandate.py`,
  `answer.py`, `artel.py`, карта и `tests/` (входы + 2 новых файла);
  зоны SPEC не превышены, защищённые пути не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `mandate.matrix_refusals`: раздел (`matrix_section`, конец на `# `/`## `), первая таблица, ровно 5 столбцов с каноническими началами после нормализации (`_headers_ok`), ≥1 строка данных. Проверка в `_read_checked_answer_file` ⇒ все четыре состояния; файл без строк мандата — `_matrix_mandate_elements` → `None`, путь прежний. |
| 2 | OK | Элементы — все строки обоих маркеров (`_matrix_mandate_elements`, без «Зависимости мержа:»); `_names` — токены по `[\s`,;()«»]+`, посимвольно, `/` на конце снят у обоих; отказ перечисляет все неназванные. |
| 3 | OK | `_remains`/`_covered`/`_conditional_with_replacements` по правилам SPEC; «не покрыто»/«нет»/тире побеждают ссылку на тест; номер строки с 1; короткая строка дополняется пустыми ячейками. |
| 4 | OK | `_has_independent_check` — только при строке мандата тестов, непустой вердикт после двоеточия. |
| 5 | OK | `cmd_zones_extend(task_id, paths_arg, session_id=None, matrix_path=None)`; отказ без `matrix_path` в самой функции; строка любого из трёх маркеров в файле — отказ; в ANSWER — только `matrix_section(raw)`. CLI `--matrix` в любом месте, без значения — отказ разбора. |
| 6 | OK | `_refuse_without_matrix` — `sys.exit` до `stop_on_ref_drift`/коммита; текст несёт `MATRIX_DOC_REF` («docs/operator-gates.md, раздел «Матрица неослабления»»). |
| 7 | OK | Оба канала зовут `mandate.matrix_refusals` (AC-12 и планка с подменой — зелёные). |
| 8 | OK | `mandate.refusals` и его текст не тронуты, вызывается первым (`answer.py:113-118`), отказ матрицы — после. |

## Замечания

Блокеров, major и minor нет. Наблюдения без замечания:
- `**docs/a.md**` в «Что меняется» элемент не называет (`*` — не граница
  токена по требованию 2) — соответствует букве SPEC; отказ при этом
  внятный и называет элемент.
- `_zones_extend_args` молча отбрасывает лишние позиционные аргументы
  (например, неэкранированный список путей через пробел) — то же
  поведение, что прежний `rest[1]`; не регрессия.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний этой итерации нет; прошлых итераций нет.

## Вердикт

approved

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4NZ5QRB7MNEYCWGXEWVWFP0` —
  `1 passed in 15.43s`, код выхода pytest 0.
- `python3 -m pytest -q tests/test_mandate_matrix_form.py tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py` —
  `19 passed, 71 subtests passed in 56.71s`.
- `python3 -m pytest -q tests/test_answer.py tests/test_answer_mandate.py tests/test_docs_ref_deleted_refusal.py tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py` —
  `71 passed, 53 subtests passed`.
- `pytest tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py -k OperatorCommandsAfterRoleMove` — 3 passed.
- Временная мутация в памяти (`mock.patch` `mandate._headers_ok` на
  сравнение без нормализации) — `MatrixHeaderNormalizationTest` красный;
  заявка сторожа подтверждена, файлы не правились.
- Пробы `mandate.matrix_refusals` напрямую: «ок при условии —» при
  «да/не покрыто» → отказ «строка данных 1»; «Ок при условии: X» →
  проход; `docs/a.md/` при токене `docs/a.md` → проход; строка после
  пустой строки (вторая таблица) не учитывается.
- Сверка неослабления: `git diff 85e0fa86 -- tests/ | grep '^-'` — удалены
  только строки входов (`write_text`/`f.write`/вызовы `cmd_zones_extend`),
  ни одного `assert`; утверждения существующих методов не менялись.
- Карта: `python3 scripts/codebase_map.py` + `git diff` — расхождение
  только в `built_at_sha`; файл возвращён `git checkout`.
- CI коммита 560658f4 — зелёный (16 проверок, по пакету).

## Предложения системе

- Песочница шага отказывает heredoc с перенаправлением (`python3 - <<EOF … 2>&1`)
  как «file_redirect» — пробы в памяти пришлось гнать через `python3 -c`;
  тот же класс, что отметил разработчик в PLAN (уборка через `os.remove`).
