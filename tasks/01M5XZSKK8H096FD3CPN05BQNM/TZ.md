---
task: 01M5XZSKK8H096FD3CPN05BQNM
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab В1.2: гейт неослабления по исходам из отчётов задания CI

Родительская задача: 01M5XX9PW3K206Q3EKQCT649QF — GitLab В1: источник полного набора full_suite (local|ci|both), исходы из отчёта задания CI
Зоны: orchestrator/advance_gates/outcome_integrity.py, orchestrator/reporters/outcome.py, tests/
Порядок: после части 1, 01M5WDB7JY0VJGHVKCABA2QC5T
Рамка: $40

Часть 2 из 2 задачи 01M5XX9PW3K206Q3EKQCT649QF (GitLab В1). Требования,
критерии и границы — SPEC родителя 01M5XX9PW3K206Q3EKQCT649QF: требования
5, 6, 7 и критерии AC-14…AC-24 его SPEC; разделы «Контекст», «Матрица
неослабления» и «Не входит» родителя действуют и здесь (ответы Оператора
ANSWER-1, ANSWER-2 и ANSWER-3 родителя). Опирается на поля
`full_suite`/`ci_job` профиля компонента из части 1.

Точка входа по отчётам CI — только гейт мержа (`merge_gate_escalates`), в
том числе у проектов с `target-human`. На `in_dev → verifying` гейт
компонента `ci` судит по локальным выпискам, как сейчас: в этой точке
голова ещё не сжата и не отправлена на origin (`fsm_advance.py:843` против
`:855-856`, `:868`), конвейера у неё нет (ANSWER-3, вопрос 1).

Факты: ADR-0026 п. 6; инвариант 41. Гейт — `advance_gates/outcome_integrity.py`:
точки входа `_outcome_integrity_gate_refuses` (`:1143`, вызов
`fsm_advance.py:843`) и `merge_gate_escalates` (`:1153`, вызов через обёртку
`_outcome_integrity_merge_gate` `fsm_merge_gate.py:1380-1390`, её вызов
`:1517`); тело `_judge` (`:925`); исходы — локальные прогоны выписок
(`_checkouts` `:769`, `_full_runs`/`_full_run` `:388`/`:395`, `_rerun` `:407`,
`_redness`, `_prior_checkout` `:672`); база — `_diff_base` (`:785`),
`_merge_base_of` (`:793`); сравнение — `compare` (`:185`; красноту
`PASS_TO_PASS` он не судит — это делают `_rerun`/`_redness`); замены —
`_replacement_findings` (`:739`, без третьей выписки бросает `_Prepare`
`:753-756`); доказательство — `_component_key` (`:813`), `_proven` (`:897`).
Форма исходов — `CaseResult` (`reporters/outcome.py:43`), идентификатор —
`project_profile.test_id` (`project_profile.py:623`); разбор JUnit —
`parse_junit` (`reporters/outcome.py:145`), правило пути — `_junit_location`
(`:106`), `_root_path` (`:80`). `forge.TestReport` — `<classname>::<name>` →
статус GitLab, без атрибута `file`. Дерево коммита слияния в базе совпадает
с деревом второго родителя — перебазированной головы влитого MR, у которой
конвейер с отчётом есть.

Требуется (для компонента `full_suite: ci`; сигнатуры точек входа не
меняются):
1. На гейте мержа исходы головы и базы — из отчётов задания `ci_job`, не
   из локальных выписок (выписок базы/головы, перепрогона красных, третьей
   выписки нет). Отчёт стороны (голова и база) годен только при
   завершённом задании: `success`, либо `failed` без права падать (исходы —
   из отчёта), и разобранном отчёте; идёт, не начато, отменено, ручное,
   пропущено, иной статус, отчёт не разобран — не годен. Отчёт головы —
   конвейер ровно sha головы; нет годного отчёта головы — сбой подготовки
   (`MERGE_PREPARE_ACTION` с причиной, задача на `merge_gate`, отправки
   нет), не пропуск и не эскалация. На `in_dev → verifying` — локальные
   выписки, как сейчас.
2. Отчёт базы — конвейер точки ответвления (`_diff_base`/`_merge_base_of`);
   нет у неё задания `ci_job` с годным отчётом — конвейер её родителя
   (`git rev-list --parents -n1`) с тем же деревом (`git rev-parse
   <c>^{tree}`), только чтением, без поиска MR через хостинг. Найден —
   запись журнала «отчёт базы: задание <job id> коммита <sha> (дерево
   совпадает с <точка>)» (<job id> — наибольший `id` попыток `ci_job` из
   `forge.pipeline_status(<sha>).jobs`). Не найден — сбой подготовки
   «нет отчёта базы» (`MERGE_PREPARE_ACTION`), не пропуск и не эскалация.
3. Зелёный в базе и красный в отчёте головы — находка BROKEN с прежним
   действием отказа (`MERGE_REFUSAL_ACTION`, `escalated`); пропавший в
   голове — находка `compare`.
4. Утверждённая замена: REPLACED_MISSING/REPLACED_NOT_GREEN по отчёту базы
   как раньше, иначе — отказ гейта (`MERGE_REFUSAL_ACTION`) с причиной
   «замена теста не проверяема в режиме ci», не сбой подготовки.
5. На мерже `_proven` в режиме `ci` не используется: отчёты базы и головы
   читаются и сравниваются заново. Находки G3б-2 (`_strict_findings`/
   `_code_exception_findings`) в режиме `ci` остаются: дифф читается git
   без выписок. Запись `PASSED_ACTION` в режиме `ci` — с ключом по дереву
   головы (`git rev-parse <sha>^{tree}`) и `id` заданий головы и базы, без
   сумм файлов блокировки.
6. Перевод отчёта в `CaseResult` — правило требования 6 SPEC родителя
   (ключ по первому `::`; `classname` с `/` — путь; точечный — самый
   длинный префикс, дающий файл `.py` в дереве коммита отчёта, остаток —
   класс с `::`; путь от корня — как `_root_path`; статусы
   `success`/`failed`/`skipped`/`error` → `passed`/`failed`/`skipped`/`error`).
   Неоднозначный перевод (модуль не найден, статус вне перечня, два ключа
   с одним идентификатором) — «неизвестно» для теста, не совпадение.
7. Компонент `local` и артель — поведение, записи журнала и существующие
   тесты прежние.

Только чтение: `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`,
`orchestrator/fsm_advance.py`, `orchestrator/forge.py`,
`orchestrator/gitlab_adapter.py`, `orchestrator/targets.py`,
`orchestrator/project_profile.py`, `orchestrator/acceptance.py`,
`orchestrator/advance_gates/acceptance.py`,
`docs/adr/0029-external-delivery-via-mr.md`, `docs/adr/0026-*.md`.

Существующие тесты: правка — по мандату Оператора 26.10 на тесты, которые
меняет ADR-0029 (без ослабления, с матрицей и независимой проверкой) через
гейт SPEC; ожидается — нет. Иное — эскалация.

Не входит: профиль `verify` (В2); `awaiting_human` и MR (Б2.1); открытие
`SUPPORTED_FORGES` (Б2.3); проверка прежних версий тестов (PRIOR_RED/
PRIOR_UNSTABLE) в режиме `ci` на гейте мержа — выключена по ТЗ; чтение
отчётов CI на `in_dev → verifying` и перенос гейта за сжатие и отправку
головы — отдельная задача после Б2.1 (ANSWER-3, вопрос 1); ожидание CI
гейтом исходов на мерже — гейт идёт до ожидания CI, «задание идёт» у
свежей головы — сбой подготовки (fail-closed), повтор `approve`.