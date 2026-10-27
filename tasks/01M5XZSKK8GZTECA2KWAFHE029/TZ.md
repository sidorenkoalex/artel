---
task: 01M5XZSKK8GZTECA2KWAFHE029
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab В1.1: источник полного набора full_suite (local|ci|both) на приёмке

Родительская задача: 01M5XX9PW3K206Q3EKQCT649QF — GitLab В1: источник полного набора full_suite (local|ci|both), исходы из отчёта задания CI
Зоны: orchestrator/targets.py, orchestrator/project_profile.py, orchestrator/acceptance.py, orchestrator/fsm_autogate.py, orchestrator/ci.py, tests/
Порядок: после 01M5WDB7JY0VJGHVKCABA2QC5T
Рамка: $45

Часть 1 из 2 задачи 01M5XX9PW3K206Q3EKQCT649QF (GitLab В1). Требования,
критерии и границы — SPEC родителя 01M5XX9PW3K206Q3EKQCT649QF: требования
1, 2, 3, 4, 7 и критерии AC-1…AC-13 его SPEC; разделы «Контекст», «Матрица
неослабления» и «Не входит» родителя действуют и здесь (ответы Оператора
ANSWER-1, ANSWER-2 и ANSWER-3 родителя).

Факты: ADR-0029 п. 9; инвариант 41 (`reporters/outcome.py:250` `verdict`,
`acceptance.py:384` `is_unknown`, `UNKNOWN_PREFIX` `acceptance.py:355`,
`acceptance.py:1399-1405`). Полный набор на приёмке: `fsm.py:1508`
`_acceptance_full_suite_ok` → `acceptance.acceptance_suite`
(`acceptance.py:3368`) → `_acceptance_suite_run` (`acceptance.py:3414`);
выбор «итог CI или локально» и три условия — `acceptance.py:3421-3457`;
итог CI сейчас только у артели — `ci.accepted_full_suite` (`ci.py:1269`);
порядок незелёных итогов — `components_full_suite` (`acceptance.py:3358-3359`);
`approve` отказывает любому `FULL_SUITE_NOT_STARTED` до `--accept-red` —
`fsm.py:1573-1582`. Тесты задачи (планка, долгоживущие файлы) гоняются на
`in_dev → verifying` (`fsm_advance.py:874`), не внутри `acceptance_suite`.
Автогейт узнаёт итог CI по подстроке «принят итог CI» в детали
(`fsm_autogate.py:426`). Поля
компонента — `targets.COMPONENT_FIELDS` (`targets.py:95`),
`_check_components` (`:988`), `_component_value_error` (`:1207`); профиль —
`project_profile.Profile` (`project_profile.py:66`), `_with_component_fields`
(`:434`). `targets.py` не импортирует `forge`, а `forge` импортирует
`targets` на верхнем уровне.

Требуется:
1. Поля компонента `full_suite: local | ci | both` (по умолчанию `local`) и
   `ci_job` (обязательно при `ci`/`both`, запрещено при `local`); `ci`/`both`
   — только у записи, у которой реализация хостинга в реестре `forge` имеет
   `job_test_report`, без сравнения с литералом хостинга (сторож А0), и
   только с полем `report`; отказ загрузки называет поле; поля доходят до
   `project_profile.Profile`.
2. Режим `ci`: итог полного набора — из задания `ci_job` в конвейере sha
   головы (`forge.job_result` + `forge.job_test_report`) при тех же трёх
   условиях, что у артели (дерево гейта = дерево головы, свежесть
   относительно `origin/<базовая ветка>`; невыполненное — «неизвестно» с
   причиной, не локальный прогон; `--fresh-suite` заново читает итог CI).
   Зелёный — задание есть, без права падать, `success`, отчёт разобран, не
   пуст, без `failed`/`error`; `failed`/`error` — красный; нет задания,
   пропущено, ручное, идёт, с правом падать, отчёт `None` или пуст —
   «неизвестно» в форме `acceptance.is_unknown` с именованной причиной.
   Задание в завершённом статусе, отличном от `success` (`failed`,
   `canceled`, иной), — «неизвестно» с причиной независимо от содержимого
   отчёта; `--accept-red` его не принимает (гейт SPEC родителя 27.10, П1).
   Запись журнала: «полный набор: итог задания CI <ci_job>, задание
   <job id>, sha <sha>, тестов <n>» (<job id> — наибольший `id` попыток
   `ci_job` из `forge.pipeline_status(sha).jobs`). Локально в режиме `ci`
   полный набор компонента на приёмке не гоняется; тесты задачи — как
   сейчас, на `in_dev → verifying` (ANSWER-3, вопрос 3).
3. Режим `both`: зелёный только при зелёных локальном прогоне и итоге CI;
   «неизвестно» старше красного (как `components_full_suite`).
4. Автогейт приёмки распознаёт эту запись как итог CI полного набора.
5. Компонент `local` и артель — поведение, записи журнала и существующие
   тесты прежние.

Только чтение: `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`,
`orchestrator/fsm_advance.py`, `orchestrator/forge.py`,
`orchestrator/gitlab_adapter.py`, `orchestrator/advance_gates/outcome_integrity.py`,
`orchestrator/reporters/outcome.py`, `docs/adr/0029-external-delivery-via-mr.md`,
`docs/adr/0026-*.md`. В `targets.py` — только поля `full_suite`/`ci_job` и их
проверка; блок полей `policy` держит параллельная Б2.1.

Существующие тесты: правка — по мандату Оператора 26.10 на тесты, которые
меняет ADR-0029 (без ослабления, с матрицей и независимой проверкой) через
гейт SPEC; ожидается — нет. Иное — эскалация.

Не входит: гейт по исходам в режиме `ci` (часть 2); профиль `verify` (В2);
`awaiting_human` и MR (Б2.1); открытие `SUPPORTED_FORGES` (Б2.3); локальный
полный набор гейта мержа после приложений (`fsm_merge_gate.py:1084-1093`) —
остаётся как есть решением Оператора (ANSWER-2, вопрос 1).