---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Рефакторинг fsm_advance.py — гейты в пакет orchestrator/advance_gates/

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (пакет `orchestrator/advance_gates/` дословным переносом; с поправкой ANSWER-1/2 на имя пакета) | OK | Проверено программно: AST-сравнение КАЖДОГО перенесённого имени (`GateRefusal`, `_run_gates`, `_zones_gate`+помощники, `_capacity_gate`+помощники, `_review_escalation_sha_gate`/`_mutation_claim_gate`/`_review_rework_gate`+помощники, `_acceptance_lock_refuses`/`_acceptance_run_refuses`, `_tests_writing_*`/`_origin_push_gate`/`_registry_gate`/`_freshness_refuses`) между старым `fsm_advance.py` (sha 2b0c6679) и новым файлом-назначением — тексты байт-в-байт идентичны для всех 34 перенесённых определений. Файлы `__init__.py`, `_base.py`, `zones.py`, `capacity.py`, `review.py`, `acceptance.py`, `tests_writing.py` на месте. |
| 2 (обработчики/эффекты остаются в fsm_advance.py, алиасы на все перенесённые имена, `answer.py` не правится) | OK | AST-сравнение подтверждает: `spec_writing`, `tests_writing`, `review`, `verifying`, `in_dev`, `_review_approved`, `_review_changes_requested`, `_review_escalate`, `_in_dev_plan_escalate`, `_apply_plan_budget` остались в fsm_advance.py байт-в-байт. `orchestrator/answer.py` не входит в diff (git diff --stat подтверждает), три нужных ему имени (`_split_zone_paths`, `_plan_zones_extension_paths`, `_ZONES_MANDATE_MARKER`) импортированы в fsm_advance.py и являются тем же объектом, что в `advance_gates.zones` (акцептанс-тест `test_ac2_...` подтверждает `is`-идентичность). |
| 3 (поведение не меняется; обход `_run_gates` у `_acceptance_run_refuses` сохранён; полный набор `tests/` зелёный) | OK | Байт-в-байт идентичность (см. п.1) исключает изменение текстов отказов/журнала/кодов выхода. `_run_gates` отсутствует в `co_names` `_acceptance_run_refuses` (проверено акцептанс-тестом и вручную) — обход сохранён. Прогнаны все 9 тестов требования 4 + смежные (см. «Проверено исполнением») — зелёные. |
| 4 (только импорты/пути патчей в 9 тестовых файлах) | OK | `git diff --stat` не содержит ни одного файла `tests/` вовсе — PLAN честно фиксирует «по факту не потребовалось ни одного» (шаг 3), проверено: все 9 файлов патчат сами модули-коллабораторы (`gitcmd`/`github_adapter`/...) и зовут `fsm_advance.<имя>` напрямую — оба класса обращений живы после переноса без правки. |
| 5 (`docs/codebase-map.md` тем же коммитом; диф ёмкости < 256 КиБ) | OK | `python3 scripts/codebase_map.py --check` проходит без расхождений. Диф уже прошёл гейт ёмкости на переходе `in_dev -> review` (задача сейчас в verifying, CI зелёный) — фактическое подтверждение потолка. |
| 6 (PLAN несёт таблицу переносов, откат, смоук до/после) | OK | Таблица переносов PLAN.md сверена построчно с фактическим AST-диффом — расхождений нет (ни одного перенесённого имени сверх таблицы, ни одного из таблицы не перенесённого). Способ отката (revert одного merge-коммита) корректен: коммит 952ad801 — единственный, создающий `advance_gates/` и правящий `fsm_advance.py`+`codebase-map.md`. Смоук до/после описан конкретными командами, а не словом «совпало»; независимо воспроизведено (см. ниже) — совпадает. |

## Замечания

(нет)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| (пусто) | — | — | — | — | — |

## Вердикт

approved

## Проверено исполнением

- AST-сравнение (питон-скрипт, `ast.parse` + `difflib`) каждого
  top-level имени старого `orchestrator/fsm_advance.py` (sha
  2b0c6679998a4a3c424b63cf2ae748af4d037d6fd, 1564 строки) против
  соответствующего имени в новых `orchestrator/advance_gates/_base.py`,
  `acceptance.py`, `capacity.py`, `review.py`, `tests_writing.py`,
  `zones.py` — все 34 перенесённых определения байт-в-байт идентичны;
  10 оставшихся в fsm_advance.py имён (обработчики состояний + эффекты
  вердиктов) также байт-в-байт идентичны себе прежним.
- `python3 -c "import orchestrator.fsm, orchestrator.fsm_advance,
  orchestrator.advance_gates, orchestrator.gates"` — импорт проходит
  без ошибок (циклический импорт `fsm -> fsm_advance ->
  advance_gates.acceptance -> fsm` не ломается, лениво резолвится через
  sys.modules); `orchestrator.gates.__file__` указывает на `gates.py`
  (флэт-модуль политики не затенён новым пакетом).
- `python3 scripts/codebase_map.py --check` — без расхождений (карта
  свежая).
- `python3 -m pytest tests/test_fsm_advance_gate_smoke.py
  tests/test_zones_gate.py tests/test_capacity_gate.py
  tests/test_mutation_claim_gate.py
  tests/test_fsm_review_rework_gate.py
  tests/test_fsm_review_rework_sha_gate.py
  tests/test_protected_paths_gate.py
  tests/test_fsm_advance_gate_framework.py
  tests/test_review_registry_gate.py tests/test_gates.py
  tests/test_answer.py -p no:cacheprovider -q` — 114 passed (включая
  все 9 тестовых файлов требования 4, плюс `test_gates.py`/
  `test_answer.py`, подтверждающие отсутствие коллизии имени и
  сохранность `answer.py`).
- `python3 -m pytest tasks/01M2CYQR0357VAQFZ5VACJD9TD/acceptance_tests
  -p no:cacheprovider -q` — 7 passed (AC-1/AC-2/AC-3 планки этой
  задачи).
- `python3 -m pytest tests/test_git_fixation.py
  tests/test_fsm_advance_tests_writing_dry_collect.py
  tests/test_acceptance_tests_flow.py tests/test_agent_log.py
  tests/test_amend.py tests/test_checkpoint_zone_filter.py
  tests/test_gitcmd_check_ignore.py tests/test_invariants.py
  tests/test_split_assessment_merge_gate.py
  tests/test_step_refixation.py -p no:cacheprovider -q` — 309 passed,
  222 subtests passed (модули, чьи тесты по codebase-map импортируют
  затронутые модули/используют `fsm_advance`/`gitcmd` в связке с
  гейтами).
- `git diff --stat 2b0c667998a4a3c424b63cf2ae748af4d037d6fd...HEAD` —
  подтверждено: изменения строго в `docs/codebase-map.md`,
  `orchestrator/fsm_advance.py`, `orchestrator/advance_gates/*` — как
  заявлено в PLAN «Влияние на систему»; `orchestrator/gates.py`,
  `orchestrator/fsm_autogate.py`, `tests/test_gates.py`,
  `orchestrator/answer.py` не тронуты.
- CI коммита 952ad801 — зелёный (7 проверок, по данным пакета).

## Предложения системе

- Ревью-пакет этой задачи (генератор review-package) сообщил
  `tasks/01M2CYQR0357VAQFZ5VACJD9TD/SPEC.md` и `PLAN.md`
  отсутствующими и «в ветке» (fatal: path does not exist), и «в дереве
  — файл не найден» — хотя оба файла физически присутствуют в рабочем
  каталоге шага (материализованы из головы артефактной ветки, как
  описывает conventions-core). Ложное «не найдено» могло увести
  ревьювера в эскалацию по несуществующему основанию — стоит
  проверить, по какому пути/ссылке генератор пакета искал эти файлы
  для этой задачи.
