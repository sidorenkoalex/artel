---
task: 01M5D02N3B428V8BWC3PAM9QCT
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G3а-1б: мандат на ослабление по идентификатору теста — маркер, запись ответа, матрица неослабления, независимая проверка

# G3а-1б: мандат на ослабление по идентификатору теста — маркер, запись ответа, матрица неослабления, независимая проверка

## Факты

Вторая часть G3а-1 волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, «Решение» п. 3 — элемент мандата: идентификатор теста компонента или путь файла; п. 6 — гейт неослабления по исходам). Решение Оператора 20.10: деление G3а-1 на G3а-1а (смержена fe751fae: гейт исходов, мандат на файл и на `путь::имя`) и G3а-1б (эта задача).

**Граница задачи одной фразой:** новый маркер действует только на находки гейта исходов (компонент записи `components:` с полем `report`); прежние маркеры, их разбор, проверка, матрица и покрытие находок гейта по тексту, а у артели и при профиле без компонентов — и правила ячеек матрицы, остаются прежними побайтно.

- Мандат: маркеры — `orchestrator/advance_gates/mandate.py:38` (`TEST_WEAKENING_MANDATE_MARKER`), элементы через запятую — `orchestrator/advance_gates/mandate.py:73` (`elements`); проверка элемента — `orchestrator/advance_gates/mandate.py:187` (`_element_refusal`), перебор маркеров — `orchestrator/advance_gates/mandate.py:223` (`refusals`): пробел, двоеточие и « > » отклоняются.
- Матрица неослабления (ADR-0022): `orchestrator/advance_gates/mandate.py:297` (`MATRIX_MANDATE_MARKERS`), `orchestrator/advance_gates/mandate.py:427` (`matrix_refusals`); ячейка «Что меняется» — по токенам, деление по пробелам и запятым — `orchestrator/advance_gates/mandate.py:390` (`_names`); «Чем покрыто после» — только путь `*.py` в области ослабления — `orchestrator/advance_gates/mandate.py:402` (`_covered`); строка таблицы делится по «|» — `orchestrator/advance_gates/mandate.py:351` (`_row_cells`).
- Запись ответа: признак мандата в файле — `orchestrator/answer.py:203` (`_has_mandate_lines`, три прежних маркера); файл без строк мандата в `in_dev`/`review` принимается как указание — `orchestrator/answer.py:250` (`_instruction_text`), раньше проверок и блокировки; элементы для матрицы — `orchestrator/answer.py:127` (`_matrix_mandate_elements`); на гейте SPEC файл без прежнего маркера тестов отклоняется — `orchestrator/answer.py:242` (функция текста ответа на гейте SPEC, отказ без прежнего маркера); строка «Независимая проверка:» требуется только при прежнем маркере — `orchestrator/answer.py:150` (`_matrix_problems`); проверка чужих строк в файле матрицы `zones-extend` — `orchestrator/answer.py:485`; журнал элементов через запятую — `orchestrator/answer.py:426`.
- Аудит SPEC ищет маркеры мандата — `orchestrator/advance_gates/spec_audit.py:52` (`_MANDATE_MARKERS`).
- Гейт исходов собирает мандат через `_answer_mandate` — `orchestrator/advance_gates/outcome_integrity.py:285`; она читает только прежний маркер — `orchestrator/advance_gates/test_integrity.py:1074`; отбраковка автокоммита шага роли — `orchestrator/advance_gates/zones.py:92` (`_answer_commit_is_role_step_autocommit`); подсказка отказа называет только прежний маркер — `orchestrator/advance_gates/test_integrity.py:1536` (`_mandate_hint`).
- Имя теста Vitest — имена блоков через « > », без обрезки — `orchestrator/reporters/pult_vitest_reporter.js:41`; идентификатор — `orchestrator/project_profile.py:440` (`test_id`), разбор — `orchestrator/project_profile.py:449` (`parse_test_id`).

## Требуется

1. **Маркер** «Ослабление теста по идентификатору разрешено:» — ровно один идентификатор на строку: остаток строки после маркера дословно (без деления по запятым). Разбор — отдельной функцией в `mandate.py`; прежний маркер и `elements` не меняются. `refusals`, `_matrix_mandate_elements`, `_has_mandate_lines` и проверка чужих строк в файле матрицы `zones-extend` обрабатывают новый маркер этой функцией; строка нового маркера в файле матрицы `zones-extend` — отказ, как строки прежних маркеров.
2. **Проверка при записи ответа:** идентификатор разбирается `parse_test_id`; компонент есть в записи проекта и имеет поле `report`; путь — в области `weakening_scope` компонента. Идентификатор с обратной кавычкой, с «|», с пробелом по краям имени или с переводом строки — отказ с причиной «такой тест покрывается мандатом на путь файла». Иначе — отказ записи ответа, ANSWER не создаётся.
3. **Состояния и путь записи:** новый маркер входит в `_has_mandate_lines` — файл с его строкой указанием не считается и идёт путём мандата под блокировкой задачи; принимается в `in_dev` и прочих состояниях инструкций, в `escalated` и на гейте SPEC (`_spec_gate_answer_text` принимает и строку нового маркера); строка только с новым маркером — достаточное основание ответа в `in_dev`. Журнал приёма — отдельная запись «мандат на ослабление теста по идентификатору:», каждый идентификатор в «».
4. **Матрица и независимая проверка:** новый маркер — в `MATRIX_MANDATE_MARKERS` (через функцию разбора п. 1) и в `_MANDATE_MARKERS` аудита SPEC; при нём строка «Независимая проверка: <вердикт>» обязательна. Ячейка «Что меняется» называет идентификатор целиком между парой одинарных обратных кавычек, сверка содержимого — побайтно. «Чем покрыто после» признаёт и идентификатор теста или путь в области `weakening_scope` компонента — только при профиле компонента с `report`; у артели и при профиле `None` — прежнее правило побайтно.
5. **Покрытие в гейте исходов:** собственная функция сбора в `outcome_integrity.py` — тот же перебор `ANSWER-n.md` ссылки документов, отбраковка через `zones._answer_commit_is_role_step_autocommit` (импорт, файл не правится); отдельный набор, покрытие — только точное равенство идентификатора (с `#n`), префиксное правило к новым элементам не применяется. Подсказка отказа гейта исходов — своя, называет оба маркера. `test_integrity.py` не меняется.
6. Тесты детерминированы: запись ответа с идентификатором Vitest (пробел внутри, « > », запятая) и pytest — принята; неразборчивый идентификатор, чужой компонент, компонент без `report`, путь вне `weakening_scope`, обратная кавычка, «|», пробел по краям — отказ; ответ в `in_dev` только с новым маркером без матрицы — отказ, ANSWER не создан; с матрицей и независимой проверкой — принят; строка нового маркера в файле матрицы `zones-extend` — отказ; гейт SPEC принимает новый маркер; ANSWER с мандатом, закоммиченный автокоммитом шага роли, находку не снимает; находка гейта исходов снята мандатом по идентификатору с `#n` и не снята мандатом на другой вариант; прежние тесты мандата, матрицы и `zones-extend` — без правок и зелёные.

Зоны: orchestrator/advance_gates/mandate.py, orchestrator/answer.py, orchestrator/advance_gates/spec_audit.py, orchestrator/advance_gates/outcome_integrity.py, tests/

Только чтение: docs/adr/0026-project-components-and-outcome-gates.md, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/zones.py, orchestrator/project_profile.py, orchestrator/targets.py, orchestrator/reporters/pult_vitest_reporter.js. Вызывающие `elements`, `refusals`, `test_id`, `parse_test_id` и одноимённые `_names`, `_row_cells` других модулей (orchestrator/merge_after.py, orchestrator/catalog.py, orchestrator/tz_check.py, orchestrator/doctor/project_checks.py, orchestrator/stack.py, orchestrator/notes.py, orchestrator/reporters/outcome.py, orchestrator/acceptance.py, orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/two_sided.py) — только чтение: подписи не меняются.

Не входит: гейт мержа по исходам, пакет ревьювера (`review.py`), `fsm_merge_gate` и прочее G3а-2; мандат по идентификатору для гейта по тексту (слой python-ast покрывается прежним маркером); шаблоны `templates/` (документ ANSWER строит сама команда); документ `docs/operator-gates.md` о новом маркере (G5).

Бюджет: $30–35.
