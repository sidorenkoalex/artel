---
task: 01M5EDW6KD1ESCEVRSV2WPNXAP
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G3а-2б-1: ошибка уровня файла в отчёте и «новый модуль» в честном FAIL_TO_PASS

# G3а-2б-1: ошибка уровня файла в отчёте и «новый модуль» в честном FAIL_TO_PASS

## Факты

Пятая часть G3а волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, «Решение» п. 5 — ошибка уровня файла засчитывается красным только при новом модуле в зонах, показывается отдельной строкой). Решения Оператора 19.10 (вынос засчитывания ошибки уровня файла из G2б в G3а) и 21.10 (деление G3а-2б на G3а-2б-1 — эта задача — и G3а-2б-2; засчитывание показывается ревьюверу строкой пакета). Переносы 10 и 15 — замечания независимых проверок приёмок G2б-2.

**Граница задачи одной фразой:** новое поведение — только у профиля, для которого `in_outcome_bounds` истинно; у артели и у записи `test_profile` разбор, исходы, гейты и пакет ревьювера прежние побайтно (новые поля записи — со значениями по умолчанию).

- Отчётчик Vitest пишет только тесты модулей — `orchestrator/reporters/pult_vitest_reporter.js:82` (`onTestRunEnd`, обход `allTests` на `orchestrator/reporters/pult_vitest_reporter.js:86`): ошибка модуля (импорт, сбор) в отчёт не попадает, файл пропадает. Исполнение отчётчика в `tests/` сегодня не проверяется ни одним тестом.
- Разбор JUnit — `orchestrator/reporters/outcome.py:132` (`parse_junit`), путь записи без `file` — `orchestrator/reporters/outcome.py:93` (`_junit_location`). Запись сбора pytest (xunit2): `classname=""`, `name` — точечный путь модуля от `workdir`, `message="collection failure"`, трассировка — в тексте элемента; `_junit_failure` текст отбрасывает. `parse_junit` читает и записи `test_profile` с `runner: pytest-own` и `report` (`project_profile.reported`). Разбор Vitest — `orchestrator/reporters/outcome.py:190` (`parse_vitest`); вердикт — `orchestrator/reporters/outcome.py:222` (`verdict`): запись `error` уже даёт красный.
- Гейт честного FAIL_TO_PASS — `orchestrator/advance_gates/tests_writing.py:885` (`_tests_writing_fail_to_pass_gate`): ошибка уровня файла на базе — находка `orchestrator/advance_gates/tests_writing.py:634` (`FILE_LEVEL_FINDING`) из `orchestrator/advance_gates/tests_writing.py:805` (`_file_level_findings`; второе правило — файл Vitest без записей); классификатор провала проверки — `orchestrator/advance_gates/tests_writing.py:752` (`_check_failure_kind`); строка «дальше:» вписана в деталь отказов на `orchestrator/advance_gates/tests_writing.py:393`, `:404`, `:414` и `:961` (последняя — отказ FAIL_TO_PASS).
- Проверка ветки на `in_dev → review` — `orchestrator/advance_gates/acceptance.py:378` (`branch_criterion_problems`): отказ «теста нет в отчёте прогона ветки».
- Сравнение отчётов гейта исходов — `orchestrator/advance_gates/outcome_integrity.py` (`compare`, G3а-1а): запись уровня файла в нём стала бы мнимым идентификатором («исчез» после исправления ошибки на ветке).
- Пакет ревьювера — `orchestrator/review.py` (`_changed_assertions_part`, строки гейта исходов — `_outcome_gate_lines`, G3а-2а).

## Требуется

1. **Запись уровня файла.** `CaseResult` получает поля `file_level: bool = False` и `detail: str = ""`; прежние поля всех записей и разбор у артели и `test_profile` не меняются. Отчётчик для модуля с непустым `errors()` пишет в `tests` запись `{file, name: "<ошибка уровня файла>", state: "fail", file_level: true, error_name, error_message}`; `parse_vitest` даёт `CaseResult` с исходом `error`, `file_level=True`, `failure=error_name`, `detail=error_message`. `parse_junit` у записи с `message="collection failure"` ставит `file_level=True` и `detail` — текст элемента (первые 2000 символов); `id`, `outcome`, `failure` — прежние. Путь файла записи сбора гейт сопоставляет по точечному имени с файлами планки прогона; не сопоставлен — прежняя находка. Второе правило `_file_level_findings` (файл Vitest без записей) остаётся запасным. В `outcome_integrity.compare` записи `file_level` идентификаторами тестов не считаются.
2. **Новый модуль.** В гейте честного FAIL_TO_PASS запись `file_level` файла планки без маркера «Зелёный с рождения:» засчитывается красным, только если:
   - (а) существует путь P — элемент `zones` задачи, равный пути файла буквально (элементы-каталоги не считаются), отсутствующий в дереве `diff_base` кодовой ветки (ветки нет — в HEAD рабочей копии прогона; git не ответил — отказ подготовки);
   - (б) ошибка — неразрешённый импорт именно P: у Python `detail` несёт `ModuleNotFoundError: No module named '<M>'`, где M — путь P от `workdir` без `.py` через точки (или `__init__.py` пакета P); у Vitest спецификатор из сообщения, разрешённый от каталога файла в выкладке `plank_layout`, равен P без расширения или `P/index`.

   Засчитанный файл не даёт ни находки уровня файла, ни находок «теста нет в отчёте» по критериям, все файлы которых засчитаны. Долгоживущие файлы — прежняя находка. Запись журнала «ошибка уровня файла засчитана красным: новый модуль <P> (файл <имя>)». Условие ADR «все тесты `AC-<n>` файла на ветке присутствуют и зелёные» исполняет существующая проверка ветки на `in_dev → review` (`branch_criterion_problems`, не меняется) — закрепить тестом: засчитанный файл; тест критерия на ветке отсутствует — отказ «переход отклонён: приёмочные тесты — тест критерия не в отчёте» с деталью «AC-<n> — теста нет в отчёте прогона ветки»; тест красный — тот же отказ с деталью «AC-<n> — тест критерия не прошёл на ветке».
3. **Пакет ревьювера.** Для профиля в границе раздел строк гейта исходов дополняется по одной строке на каждый различный текст записи журнала задачи «ошибка уровня файла засчитана красным: …» (дословно, без повторов); записей нет — строки нет. Вне границы — прежнее побайтно.
4. **Переносы из приёмок:**
   - (10) тест: у `junit-xml` `failed` с `TypeError` при списке `[AssertionError]` — не провал проверки, отказ гейта FAIL_TO_PASS;
   - (15) только в отказе `FAIL_TO_PASS_REFUSAL_ACTION` (`tests_writing.py:961`) деталь журнала не несёт «\nдальше:», подсказка печатается один раз через `hint`; строки 393, 404, 414 — прежние.
5. Тесты детерминированы, без сети и без Node: форма записи уровня файла закреплена тестом `parse_vitest` на фикстуре JSON; исполнение `pult_vitest_reporter.js` на Vitest подтверждает проба на sled (этап 2 плана), не тесты пульта. Разбор JUnit с записью сбора (xunit2) — поля `file_level`, `detail`, прежние `id`/`outcome`/`failure`; «новый модуль» — каждое условие (а) и (б) отдельно ломает засчитывание (каталог в зонах, путь есть в базе, другое имя модуля, другая ошибка, маркер «Зелёный с рождения:», долгоживущий файл); подавление находок «теста нет в отчёте» только по полностью засчитанным критериям; отказ на ветке по `branch_criterion_problems`; запись `file_level` вне идентификаторов `compare`; строка пакета ревьювера и её отсутствие вне границы. У артели и записи `test_profile` — разбор и исходы прежние; существующие тесты без правок и зелёные.

Зоны: orchestrator/reporters/pult_vitest_reporter.js, orchestrator/reporters/outcome.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/outcome_integrity.py, orchestrator/review.py, tests/

Ограничение зон по смыслу: в `orchestrator/advance_gates/outcome_integrity.py` — только `compare` и, если строка пакета собирается там, `review_lines`; в `orchestrator/review.py` — только строки засчитывания в разделе гейта исходов.

Только чтение: docs/adr/0026-project-components-and-outcome-gates.md, orchestrator/project_profile.py, orchestrator/advance_gates/acceptance.py, orchestrator/acceptance.py, orchestrator/gitcmd.py, orchestrator/advance_gates/mandate.py (`_split_zone_paths`), orchestrator/store.py. Вызывающие `parse_junit`, `parse_vitest`, `verdict`, `compare` и `CaseResult` других модулей (orchestrator/acceptance.py, orchestrator/advance_gates/two_sided.py, orchestrator/suite_run.py, orchestrator/plank_run.py, orchestrator/canary.py, orchestrator/role_prompt.py) и гейтов `tests_writing` (orchestrator/fsm_advance.py, orchestrator/preflight.py), а также одноимённая `compare` в scripts/guard.py — только чтение: подписи не меняются.

Не входит: запрет плагинов повторов pytest, переносы 11, 18, 20–23 (G3а-2б-2); строка в `docs/operator-session.md` о правке SPEC.md после эскалации (перенос 12 — `doc-commit` Оператора); шаблонная таблица `it.each` и `suite('AC-n: …')` в запретах (перенос 13 — G3б); облегчённый стенд медленных долгоживущих файлов (переносы 17 и 24 — бэклог ускорения набора); записи по тестам в кэше итога (бэклог); выбор компонентов по диффу, заменяемые тесты (G3б).

Бюджет: $35–45.
