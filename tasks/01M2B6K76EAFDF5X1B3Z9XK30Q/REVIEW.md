---
task: 01M2B6K76EAFDF5X1B3Z9XK30Q
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Приёмка: печать того, что проверит `approve`

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (единая запись «приёмка: что проверит approve» на входе в acceptance) | OK | `fsm_autogate._log_acceptance_checklist`, вызвана из `_maybe_autogate_acceptance` — единственная точка входа в acceptance (`fsm_advance._review_approved`, подтверждено единственным вызывающим местом). Покрывает и остановку `auto`, и `advance` без `auto` — `auto.py` не заводит свой путь в acceptance, а зовёт тот же `fsm.cmd_advance`. |
| 2 (текст групп получен из тех же функций, что реально проверяют) | OK, с оговоркой | Группа «б» действительно вычислена через `guard.scan_ac_content` (`_acceptance_manual_criteria`) — подтверждено юнит- и приёмочным тестом (мок `scan_ac_content` меняет вывод). Группа «а» — фиксированный литеральный список 4 пунктов (AC-2 требует ровно эти 4 пункта текстом, что и оправдывает фиксацию текста); источник (ветка+sha) и суммы бюджета взяты из тех же примитивов (`artifact_source.resolve`/`gitcmd.branch_head_sha`/`t['budget_usd']`), что использует `_autogate_conditions`, но сама функция `_autogate_conditions` для группы «а» не вызывается и не может — она не проверяет «свежесть против origin» вовсе (эта проверка происходит позже, в merge_gate). Формально буквальное «текст получен из `_autogate_conditions`» не выполнено для группы «а», но это неизбежное следствие несовместимости с AC-2 (там нужен фиксированный список из 4 пунктов, а `_autogate_conditions` возвращает динамический список произвольной длины) — не завожу отдельным замечанием. |
| 3 (хинт `AUTO_STOP["acceptance"]` ссылается на запись) | OK | `orchestrator/config.py:584` — текст хинта содержит `см. «приёмка: что проверит approve» в artel.py log {id}`; проверено импортом модуля. |
| 4 (unified diff `docs/operator-gates.md` приложением к PLAN, с проверкой `git apply --check`) | НЕ РЕАЛИЗОВАНО КОРРЕКТНО | Diff приложен, но не применяется — см. замечание R1-F1. PLAN.md заявляет, что применимость проверена, однако `git apply --check` на чистом дереве этой ветки завершается ошибкой `corrupt patch at line 33`. |

## Замечания

- major — `tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/PLAN.md:106-146` (приложение unified diff `docs/operator-gates.md`) — заголовок второго хунка (`@@ -93,11 +102,7 @@`) не совпадает с телом хунка: в реальном `docs/operator-gates.md` (база `9f1565914c3247513caa33a08e1c44c176a6a851`) раздел «Гейт приёмки» после строки «не менялись (правило T015).» несёт ещё одну строку контекста — пустую строку (строка 103 файла) — перед следующим `## Гейт merge`; в приложенном диффе эта строка контекста отсутствует, из-за чего заявленные счётчики (11 старых / 7 новых строк) на 1 больше фактических (10/6). Воспроизведено: `git apply --check <файл-с-диффом>` на HEAD этой ветки даёт `error: corrupt patch at line 33`; с флагом `--recount` патч применяется, то есть тело диффа семантически верно, но заголовок хунка — нет. PLAN.md (раздел «Влияние на систему» и подпись под приложением) утверждает, что «применимость проверена `git apply --check` на чистом дереве» — по факту эта проверка либо не была прогнана против актуального `docs/operator-gates.md`, либо её результат не был учтён. Это тот же класс дефекта, что уже дважды ловился в этом пуле (T046/T047, `skills/conventions-core.md`). Предложение: пересобрать diff (например, `git diff` реального изменения файла или ручная правка заголовка на `@@ -93,10 +102,6 @@`) и заново прогнать `git apply --check` без `--recount` перед сдачей.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/PLAN.md:118-145 | Заголовок 2-го хунка приложенного unified diff `docs/operator-gates.md` не совпадает с реальным диапазоном файла (`corrupt patch`) | Оператор не сможет применить diff командой `git apply` как предписывает требование 4 — придётся чинить вручную, вместо готового патча | Пересобрать diff с верным заголовком хунка (или через `--recount`/фактический `git diff`), подтвердить `git apply --check` (без `--recount`) на чистом дереве и обновить приложение PLAN.md |

## Вердикт

changes_requested — единственное необходимое исправление: пересобрать unified diff `docs/operator-gates.md` в приложении PLAN.md так, чтобы он реально проходил `git apply --check` на чистом дереве (см. R1-F1). Код `orchestrator/fsm_autogate.py`/`orchestrator/config.py` и тесты замечаний не вызвали.

## Проверено исполнением

- `python3 -m unittest tests.test_fsm_autogate -v` — 17 тестов, все зелёные (включая 6 новых классов задачи).
- `python3 -m unittest tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/acceptance_tests/test_ac1_ac2_ac3_ac7_manual_marker_report.py tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/acceptance_tests/test_ac4_ac8_no_marker_report.py tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/acceptance_tests/test_ac5_content_reuses_condition_functions.py tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/acceptance_tests/test_ac6_auto_stop_hint_references_log.py tasks/01M2B6K76EAFDF5X1B3Z9XK30Q/acceptance_tests/test_ac9_existing_suites_stay_green.py -v` — 10 тестов, все зелёные (планка задачи полностью, AC-1..AC-9).
- `python3 scripts/codebase_map.py --check` — карта актуальна (без расхождений, кроме законной строки `built_at_sha`).
- `python3 -c "from orchestrator import config; print(config.AUTO_STOP['acceptance'])"` — подтверждён текст хинта AC-6.
- `grep -n "_maybe_autogate_acceptance\|_review_approved" orchestrator/fsm_advance.py` и просмотр `orchestrator/auto.py` — подтверждена единственная точка входа в acceptance (требование 1).
- Diff `tests/test_fsm_autogate.py` просмотрен построчно — существующие тесты не изменены и не удалены (AC-9), только новые классы дописаны в конец файла; импорт в шапке расширен.
- `git apply --check <приложенный diff docs/operator-gates.md>` на HEAD ветки — ошибка `error: corrupt patch at line 33`; с `--recount` — применяется (см. замечание R1-F1).
- CI коммита 9785303d (из ревью-пакета) — зелёный, 7 проверок.

## Предложения системе

- `skills/conventions-core.md` требует `git apply --check` перед сдачей unified diff по защищённому пути, но диффы по `docs/` (не защищённый путь, но тоже приложение к PLAN) страдают тем же классом дефекта (несовпадающий заголовок хунка) — стоит явно распространить это требование на любой unified-diff-приложение к PLAN.md, а не только на защищённые пути (класс подтверждён третий раз подряд: T046, T047, эта задача).
