---
task: 01M1TQ0TRCZPRZX22C4084NCPB
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: CI кодовой ветки до ревью: порядок in_dev -> verifying -> review (ADR-0015)

## Подход

Эскалация снята Оператором (ANSWER-1.md, вариант б): R2
(01M1TKNXX5YN5KT4WHG4T44JWV) и R3 (01M1TKP08PKB87K8772H69GCXJ) смержены
в main 06.09 (коммит `c4f893710d843eaf45ec99529556e342c4131247`,
«роадмап §3 — R2 и R3 смержены 06.09») — реализация выполнена поверх
уже рефакторенного `fsm_advance.py` (каркас `GateRefusal`/`_run_gates`
R2, модуль `pull.py` R3).

Реализованный дизайн:

1. **`fsm_advance.in_dev`**: семь рубежей перехода `in_dev -> review`
   (лок `acceptance_tests/`, подтяжка main, гейт ёмкости, гейт зон, гейт
   «замечания ревью не отработаны», сверка головы на origin, прогон
   приёмочной планки) стоят здесь целиком; финальный `store.set_state`
   ведёт в `"verifying"` вместо `"review"`, `verifying_attempts`
   обнуляется тут же.
2. **`fsm_advance.review`**: ветка `status == "approved"` лишена
   push-проверки и прогона `acceptance.run` (переехали в `in_dev`,
   см. п.1; правка сверки на origin — итерация 2, см. ниже, REVIEW.md
   R1-F1: в итерации 1 push-проверка была ДОБАВЛЕНА в `in_dev`, но по
   ошибке не убрана со старого места здесь — дубль); реестр замечаний
   (`guard.requires_registry`) — без изменений (не один из семи
   рубежей). После реестра — прямой переход
   в `"acceptance"` с материализацией `acc_tdir` и вызовом автогейта
   acceptance (`fsm_autogate._maybe_autogate_acceptance`), той же
   логикой, что раньше стояла на входе `verifying -> acceptance`.
3. **`fsm_advance.verifying`**: на зелёном CI — переход в `"review"`
   вместо `"acceptance"`; материализация планки/автогейт из этой
   функции убраны (переехали в `review()`, см. п.2). Опрос CI, счётчик
   попыток, потолок ожидания — без изменений.
4. **`orchestrator/review.py::review_package`**: несёт часть «Статус CI
   (verifying)» — последняя по времени запись журнала `fsm.
   VERIFYING_STATUS_ACTION` этой задачи; ревьювер получает строку
   статуса CI (sha, число проверок) без нового опроса `ci.py`.
5. **`orchestrator/auto.py`**: без изменений — цикл дизъюнкции и
   `_advance_verifying_poll` не зависят от того, что стоит ДО/ПОСЛЕ
   `verifying`; подсказка `AUTO_STOP_VERIFYING_RED` уже называет
   `reject`, а `_cmd_reject` уже ведёт `verifying -> in_dev`.
6. **Документация**: `docs/invariants.md` (строка реестра 36 + правка
   строк 27/34, называющих рубеж, переехавший на `in_dev -> verifying`);
   `docs/roadmap.md` (пункт живого хвоста §2 с новой цепочкой состояний,
   историческая строка «Фиксация К3» не тронута — протокол прошлого
   прогона); `orchestrator/artel.py` (докстринг схемы состояний и
   описание лока `acceptance_tests/` — правка вне заявленных `zones`
   SPEC, см. «Расширение зон» ниже).
7. **Housekeeping**: удалён `baseline_fsm_advance_tmp.py` — рабочий
   снимок дореформенного `fsm_advance.py`, оставленный в рабочем дереве
   предыдущей (прерванной таймаутом) итерацией этого же шага; в диффе
   не участвовал, найден и убран как случайный мусор.

Известная особенность (не дефект): при реальной подтяжке main
`in_dev` прогоняет `acceptance.run` дважды за один вызов —
один раз внутри `pull.evaluate` (рубеж «прогон планки после подтяжки»,
SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS/`pull.py`, вне зон этой задачи) и
второй раз собственным рубежом `_acceptance_run_refuses` (переехавшим
из `review()`, SPEC T023 требование 6). Оба рубежа легитимны и стояли
в системе ДО этой задачи — просто на двух разных вызовах `advance`
(`in_dev -> review`, затем `review -> verifying`), а не в одном; эта
задача не меняет и не убирает ни один из них (её зона не включает
`pull.py`, «Не входит» SPEC), только консолидирует момент, когда оба
срабатывают. Задокументировано явными ассертами `acc_run.call_count ==
2` в `tests/test_fsm_map_conflict_autoresolve.py` (уже было в WIP) и
`tests/test_branch_freshness_gate.py::test_advance_pulls_main_and_advances_when_acceptance_green`
(правка этого шага). См. «Предложения системе».

### Итерация 2 — закрытие REVIEW.md, iteration 1, замечание R1-F1 (blocker)

Ревьювер поймал ровно то, что описано выше в п.2 скобкой: рубеж
«сверка головы на origin» (`_origin_push_gate`) был добавлен в
`in_dev()` (строки 1123-1125), но старая точка вызова в `review()`
(строки 301-303, ветка `status == "approved" and not t["is_canary"]`)
не была удалена — дублирование, прямо запрещённое требованием 1.
Исправлено:

- блок строк 301-303 убран из `review()` целиком (сама сверка
  свежести вердикта, `_freshness_refuses`/`fresh_verdict_iteration`, не
  трогалась — она не входит в семь переехавших рубежей);
- докстринг `_origin_push_gate` (`fsm_advance.py:171-184`) и докстринг
  `github_adapter.ensure_head_in_origin` (`github_adapter.py:114-116`)
  переписаны — оба называют `in_dev()` единственным местом вызова, а не
  `review()`;
- расширение локального `test_ac02_ac08_gates_moved_to_verifying.py`
  (просьба ревьювера) НЕ сделано: этот файл — часть
  `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/`, залоченной
  приёмочной планки (SPEC T023: «код чинится под них, их правка —
  эскалация, не правка», conventions-core) — правка залоченного файла
  силами developer не входит в допустимые действия этой роли. Вместо
  этого тот же класс регрессии («рубеж оставлен на старом месте после
  переноса») закрыт НОВЫМ тестом в незалоченной зоне `tests/`:
  `tests/test_auto_cycle.py::AutoStopsWhereTheOperatorIsNeededTest::
  test_origin_push_check_runs_once_not_twice_on_the_way_to_acceptance`
  — шпион (`mock.MagicMock(wraps=...)`) на
  `github_adapter.ensure_head_in_origin`, цикл `auto` от `in_dev` через
  `verifying` (зелёный CI) и `review` (approved) до `acceptance`,
  `assertEqual(spy.call_count, 1)`. Проверено разрезом на
  дореформенном коде (`git stash` только по `fsm_advance.py`): тест
  падает `2 != 1`; на исправленном — зелёный.

## Шаги

1. Дождаться мержа R2/R3 (сделано Оператором, 06.09) — снято.
2. Реализовать п.1-4 «Подхода» одним диффом (было сделано в
   предыдущей, прерванной таймаутом итерации этого шага — код уже в
   рабочем дереве при старте этой итерации).
3. Прогнать `tests/test_fsm*.py`, `tests/test_auto*.py`, `tests/
   test_review*.py` и смежные модули, поправить ассерты старого
   порядка (список — «Покрытие требований»/AC-20 ниже).
4. Реализовать п.6 «Подхода» (документация) — было сделано в
   предыдущей итерации, сверено в этой.
5. Убрать housekeeping-мусор (п.7 «Подхода»), прогнать `scripts/
   guard.py` на артефактах, закоммитить код.
6. Итерация 2: закрыть REVIEW.md R1-F1 (см. «Итерация 2» выше) —
   убрать дубль `_origin_push_gate` из `review()`, поправить два
   докстринга, добавить регрессионный тест в `tests/test_auto_cycle.py`,
   пересчитать `docs/codebase-map.md`, разметить реестр замечаний
   `fixed`, закоммитить код.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 (без правки auto.py) |
| 6 | 4 |
| 7 | 1 (эскалация вместо правки чужой планки — снята Оператором) |

### AC-20 — правки ассертов старого порядка (с обоснованием)

Все перечисленные тесты фиксировали поведение ДО ADR-0015
(`in_dev -> review`, `verifying -> acceptance`) либо не учитывали, что
рубежи «прогон приёмки»/«сверка головы на origin» переехали в `in_dev`
и теперь звонятся на КАЖДОМ входе в этот переход, а не только на
approved-ветке `review()`:

- `tests/test_verifying_ceiling.py::test_green_ci_moves_on_regardless_of_elapsed_time`
  — целевое состояние на зелёном CI сменено с `"acceptance"` на
  `"review"` (AC-9).
- `tests/test_branch_freshness_gate.py` — три теста
  (`test_advance_skips_pull_when_branch_not_behind`,
  `test_advance_treats_origin_fetch_failure_as_fresh`,
  `test_advance_pulls_main_and_advances_when_acceptance_green`):
  целевое состояние `in_dev -> {review->verifying}`; плюс
  `acceptance.run` теперь звонится безусловно как часть `in_dev`
  (`assert_not_called()` → сконфигурированный `return_value=(True,
  "ok")` + `assert_called_once()`/`call_count == 2`, где пул реально
  сработал — см. «Подход», известная двойная планка).
- `tests/test_acceptance_tests_flow.py::LockTest` — три теста
  (`test_untouched_tests_pass_the_transition`,
  `test_new_unrelated_file_does_not_trip_the_lock`,
  `test_pyc_only_diff_after_lock_does_not_block_the_transition`):
  реальный git без origin — добавлен `mock.patch.object(github_adapter,
  "ensure_head_in_origin", return_value=(True, ""))` вокруг
  `cmd_advance`, тем же приёмом, что уже применён в
  `tests/test_git_fixation.py` (предыдущей итерацией).
- `tests/test_amend.py::AmendThenReviewGateTest::test_amend_then_advance_passes_lock_gate`
  — тот же приём (мок `ensure_head_in_origin`) + целевое состояние
  `"review"` → `"verifying"`.

Остальные правки (`test_advance_guard.py`, `test_auto_cycle.py`,
`test_fsm_map_conflict_autoresolve.py`, `test_git_fixation.py`, `test_invariants.py`,
`test_review_freshness.py`, `test_review_registry_gate.py`) сделаны
предыдущей итерацией этого же шага (до таймаута) — сверены в этой
итерации прогоном, без дополнительных правок.

## Расширение зон

Пути: orchestrator/artel.py

Обоснование: AC-19 требует, чтобы текст схемы состояний в выводе
`artel.py --help` отражал новый порядок — `cmd_help` печатает
`__doc__` этого же модуля (`orchestrator/artel.py:443`), других мест
вывода `--help` нет. SPEC `zones:` называет `orchestrator/fsm.py,
fsm_advance.py, auto.py, review.py, config.py, docs/invariants.md,
docs/roadmap.md, tests/` — `orchestrator/artel.py` в списке не
назван, хотя единственный способ выполнить AC-19 буквально — править
именно его. Правка — модульный докстринг (схема состояний, абзац про
`verifying`, название рубежа лока `acceptance_tests/`), без изменений
кода.

## Влияние на систему

Не ослабляет ни один гейт/инвариант: семь рубежей `in_dev -> review`
переехали на `in_dev -> verifying` тем же кодом, без потери проверки
ни на одном пути (SPEC требование 1 буквально это и требует); реестр
замечаний, лимит итераций ревью, автогейт acceptance, потолок ожидания
CI — все остались на месте, только на новых именах переходов. Счётчики
`review_iters`/`verifying_attempts` не тронуты (AC-12). Единственная
известная небезупречность — двойной прогон `acceptance.run` при
реальной подтяжке main (см. «Подход»): не ослабление (оба прогона были
легитимны и раньше), а избыточная работа — задокументирована тестами,
не скрыта.

`docs/invariants.md`/`docs/roadmap.md`/`orchestrator/artel.py`
переписаны под новый порядок (AC-17..19), проверено чтением; полный
`tests/` не прогонялся в этом шаге (идёт 3-4 минуты, гоняется CI на
каждый пуш ветки, решение Оператора 05.09) — прогнаны точечно ~470
тестов из модулей, пересекающихся с зоной (`test_fsm*`, `test_auto*`,
`test_review*`, `test_invariants`, `test_advance_guard`,
`test_zones_gate`, `test_capacity_gate`, `test_verifying_ceiling`,
`test_acceptance_tests_flow`, `test_branch_freshness_gate`,
`test_amend`, `test_git_fixation`, `test_ci_status*`, `test_gates`,
`test_brief`, `test_agent_prompt`, `test_agent_failure`,
`test_cas_set_state`, `test_cmd_approve_dispatch`,
`test_doctor_fix_ignored_artifacts`, `test_guard_schema`,
`test_guard_artifact_branch_mode`, `test_guard_zones`,
`test_stall_alerts`, `test_report`, `test_split_assessment_merge_gate`,
`test_step_cost`, `test_zone_lock`), все зелёные; 20 приёмочных тестов
этой задачи — зелёные.

Итерация 2 (закрытие R1-F1): `python3 -m unittest tests.test_acceptance_tests_flow
tests.test_advance_guard tests.test_amend tests.test_auto_cycle
tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve
tests.test_git_fixation tests.test_invariants tests.test_review_freshness
tests.test_review_registry_gate tests.test_verifying_ceiling
tests.test_github_adapter tests.test_merge_gate_ci_wait` — 296 тестов,
все зелёные (~178с); 20 приёмочных тестов задачи — зелёные (без
изменений); `python3 scripts/codebase_map.py` — пересчитан (новая
запись «Импортируется» у `github_adapter.py`/`ci.py` за счёт нового
импорта в `tests/test_auto_cycle.py`).

## Риски

- Диф трогает `orchestrator/artel.py` вне заявленных `zones` — гейт
  зон (`fsm_advance._zones_gate`) откажет `in_dev -> verifying` до
  тех пор, пока Оператор не подтвердит расширение строкой «Расширение
  зон разрешено: orchestrator/artel.py» в новом `ANSWER-n.md` (раздел
  «## Расширение зон» выше уже называет путь и обоснование) — это
  ожидаемый штатный отказ гейта, не авария.
- Двойной прогон `acceptance.run` внутри `in_dev` на реальной подтяжке
  main (см. «Подход») — не корректностный баг, но лишняя работа; вне
  зоны этой задачи (`pull.py` не в `zones`, «Не входит» SPEC не
  называет его предметом задачи) — кандидат для будущей задачи над
  `pull.py`/`fsm_advance.py` совместно.

## Предложения системе

- `orchestrator/report.py::STATE_ORDER` (строки 32-34, «Порядок
  колонок борда») всё ещё перечисляет состояния в СТАРОМ порядке
  (`in_dev, review, verifying, acceptance, ...`) — косметика борда
  Оператора, не предмет ни одного AC этой задачи и вне заявленных
  `zones` (`report.py` не назван); строки не поправлены этой задачей.
  Стоит завести отдельную мелкую задачу на актуализацию порядка колонок
  под ADR-0015, если борд действительно читается по порядку столбцов.
- SPEC этой задачи (`zones:`) не включил `orchestrator/artel.py`, хотя
  AC-19 явно требует правки его докстринга (`--help` печатает именно
  его `__doc__`) — тот же класс пробела, что уже отмечен в
  `tasks/01M1TQ0X14Y5B3C87WC0Q31PK2/PLAN.md` («Предложения системе»)
  для `orchestrator/answer.py`: аналитику стоит сверять `zones:` не
  только с текстом требований, но и с фактическим местом их реализации
  в коде, раз этот класс пробела повторился второй раз.
- REVIEW.md итерации 1 (R1-F1) попросил расширить сценарий ИМЕННО в
  залоченном `tasks/<id>/acceptance_tests/test_ac02_ac08_gates_moved_
  to_verifying.py` — но conventions-core прямо запрещает developer
  править файлы под `acceptance_tests/` (SPEC T023, «код чинится под
  них, их правка — эскалация, не правка»). Реестр замечаний
  (schema_version >= 3) сегодня не различает «замечание с решением,
  требующим правки залоченного файла» от обычного — ревьюверу нечем
  пометить такое решение иначе, чем как обычный текст «предложения»,
  и developer при выполнении молча упирается в запрет своей же роли.
  Разошлось предложением-заменой в незалоченной зоне `tests/` в этой
  задаче (см. «Итерация 2» выше) — но в общем случае стоит явно
  оговорить в coding-standards.md, что «решение» реестра, адресующее
  залоченный акцептанс-файл, для developer не императив, а сигнал
  подобрать эквивалентную незалоченную проверку или эскалировать.
