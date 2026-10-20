---
task: 01M5CJVB5B5V55PQQVR2QRHWZN
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G3а-1а: гейт неослабления по исходам на выходе из `in_dev` — `PASS_TO_PASS`, нестабильность, сравнение отчётов

## Фаза A: план
- Таблица покрытия полна: требования 1–8 → шаг 1. Шаг один на весь MR —
  допустимо: SPEC обосновывает монолит (гейт без отказа/классов или без
  мандата не имеет смысла), а MR — 3 файла кода и 2 файла `tests/`.
- Подход не конфликтует с архитектурой: обёртка `_outcome_integrity_gate_refuses`
  той же формы, что соседи (`_run_gates`, `GateRefusal`), выписки — по образцу
  `two_sided.run`, мандат — переиспользованный `test_integrity._answer_mandate`
  (только чтение, как требует «Не входит»).
- «Влияние на систему» совпадает с diff: новый модуль, одна строка вызова +
  импорт в `fsm_advance.py`, три записи в `REFUSAL_CLASSES`, новый
  `tests/test_outcome_integrity.py`, добавленный метод в
  `tests/test_refusal_classes.py`, карта кодовой базы. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `outcome_integrity.py:315-322`: канарейка, `decide` refusal/skip, `in_outcome_bounds` — `None` до git/прогона/журнала. Запись из нескольких компонентов `decide` отдаёт отказом (`project_profile.py:195`, PROFILE_UNREAD+multi) — гейт не создаётся. Вызов в `fsm_advance.py:810` между гейтом по тексту и гейтом переделки ревью. |
| 2 | OK | `_checkouts`: `diff_base`/`branch_head_sha` пусто → `_Prepare`; `worktree add --detach` по sha в отдельные каталоги. `_full_runs`: `components_full_suite(..., fresh=True)`; NOT_STARTED (включая «неизвестно» — `acceptance._full_suite_outcome:2435`) и TIMEOUT → отказ подготовки с названной стороной; NO_TESTS → пустой список. Прочих исходов у `full_suite` нет (GREEN/RED/TIMEOUT/NO_TESTS/NOT_STARTED) — fail-open нет. |
| 3 | OK | `in_pass_to_pass` (`retries == 0`), `red_on_branch` (`skipped` не красный). `_rerun`: 2 раунда × (ветка, база) по файлам красных тестов, предел `component_limit(profile)[0]` = `full_suite_timeout_sec`; refusal (в т.ч. vitest без `select`), таймаут, state не GREEN/RED → `_Prepare`; итог по записи теста; база `skipped`/нет записи → `_Prepare`. `_redness` — правила итога верны. |
| 4 | OK | `compare`: исчез / появилось todo / стал пропуском (любой исход базы кроме skipped) / появилось fails; новые id — todo/пропуск/fails; одна находка на id (цепочка `elif`); неизменные todo/fails не находка; `skip_growth` — итоговая строка. Старшинство красноты над сравнением — `taken` в `_judge`. |
| 5 | OK | `covering`: равенство пути файла либо префикс с `::`/`[`/`#`/концом за ним; `test_id` формы `комп:путь::имя[#n]` (`project_profile.py:440`) — разбор `rest = cid.partition(":")[2]` корректен. Отбраковка автокоммита роли — внутри `_answer_mandate`. |
| 6 | OK | Порядок `ordered` (исчез → сломан → нестабилен → прочие, внутри — по id), строка на находку с исходами; «только сломан» → действие «… — сломан правкой», иначе общее; подготовка — своё действие; все три в `REFUSAL_CLASSES` с классами SPEC; запись пройденного гейта с числами (база, ветка, тестов перепрогона, прогонов файлов, покрытых находок) и строками «нестабилен и на базе». |
| 7 | OK | Долгоживущий сквозной файл задачи (junit-xml по метке выписки, vitest) + юнит-тесты записей `CaseResult` в `tests/test_outcome_integrity.py` (требование 7: функция сравнения и ветви `retries` на уровне записей). Без сети/Node. |
| 8 | OK | Долгоживущие тесты прежних задач не тронуты (в diff их нет), CI коммита e4582e56 зелёный; `tests/test_fsm_advance_gate_smoke.py` не изменён. |

## Замечания
Нет замечаний уровня blocker/major/minor.

Рассмотрено и не заведено:
- `tests/test_outcome_integrity.py` частично перекрывает долгоживущий
  `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` (AC-9, AC-11).
  Не повтор в смысле ADR-0020 п. 4: SPEC требование 7 прямо требует
  проверки функции сравнения и ветвей `retries` на уровне записей
  `CaseResult`; юнит-тесты наблюдают возврат чистых функций, а
  долгоживущий файл — журнал перехода; к тому же юнит-тест мандата
  покрывает повтор `#n`, которого сквозной сценарий не проверяет.
- Обрыв процесса между `worktree add` и `finally` оставляет запись
  worktree — заявлено в рисках PLAN, тот же приём, что у `two_sided`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — все требования SPEC 1–8 реализованы, тесты заявки свои ловят
(проверено временными мутациями), существующие тесты/гейты не ослаблены
(в `tests/test_refusal_classes.py` только переформатирован импорт и добавлен
метод).

## Проверено исполнением
- `python3 -m pytest -q tests/test_outcome_integrity.py tests/test_refusal_classes.py tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py` — 12 passed, 27 subtests passed.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` — 23 passed, 37 subtests passed за 205 с.
- `artel.py plank-run 01M5CJVB5B5V55PQQVR2QRHWZN` — 3 passed, код выхода 0.
- Временная мутация 1: в `compare` ветка «стал пропуском» из `elif` в
  `if` (две находки у `to_todo`) — `test_compare_vitest_findings_and_non_findings`
  красный; код возвращён (`git checkout`).
- Временная мутация 2: в `covering` проверка символа за префиксом заменена
  на `True` — `test_mandate_prefix_needs_separator` красный; код возвращён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без строки `built_at_sha` — расхождений нет (карта свежая); файл
  возвращён, `git status` чистый.
- Чтение `acceptance.full_suite`/`_full_suite_outcome`/`components_full_suite`,
  `project_profile.decide`/`test_id`, `test_integrity._answer_mandate` —
  проверка fail-closed по исходам стороны, границы нескольких компонентов
  и формы идентификатора для `covering`.

## Предложения системе
- Долгоживущий сквозной файл гейта исходов идёт 205–232 с (порог 60 с);
  каждый сценарий заводит задачу через настоящий `tests_writing` и два
  полных прогона — для гейтов на полном наборе стоит общий облегчённый
  стенд «задача сразу в `in_dev`» (`tests/sandbox.py`), иначе время CI
  растёт линейно с числом таких гейтов.
