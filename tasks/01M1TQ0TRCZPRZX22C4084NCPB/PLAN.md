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

### Итерация 3 — закрытие REVIEW.md, iteration 2, замечание R2-F1 (major)

Ревьювер поймал: коммит `d9893cd3` («подтяжка main», текущий HEAD
кодовой ветки на момент открытия итерации 2) внёс через `git merge
main` правки `orchestrator/config.py` и двух тестовых файлов
(`tests/test_capacity_gate.py`, `tests/test_fsm_advance_gate_smoke.py`
— чужая задача 01M1TT9BPB, гейт ёмкости), но не перегенерировал
`docs/codebase-map.md` — ровно класс аномалии, названный в
conventions-core («подтяжка main меняет `*.py`, но не через `Edit`, и
не регенерирует карту», подтверждён дважды на T079/T087, теперь и на
этой задаче третий раз). Исправлено:

- `python3 scripts/codebase_map.py` — перегенерирована карта;
  фактическая правка (сверх строки `built_at_sha`) ровно там, где
  указал ревьювер: список «Импортируется» `orchestrator/config.py`
  пополнился `tests/test_capacity_gate.py`, список «Импортирует»
  `orchestrator/fsm_advance.py` пополнился `orchestrator/config.py`
  (оба — прямое следствие `d9893cd3`);
- `git diff` после регенерации сверен построчно — расхождений с
  ожиданием (только два перечисленных места + `built_at_sha`) нет.

### Итерация 4 — закрытие причины возврата приёмки (AC-20, AC-22)

Приёмка отклонила предыдущую сдачу: AC-20 требовал перечисления КАЖДОЙ
правки ассерта старого порядка с обоснованием (семь файлов были
названы одной строкой без разбора — «сделано предыдущей итерацией» не
обоснование), AC-22 требовал списка (файл/строки) планок живых задач,
фиксирующих старый порядок, вместо их правки. Код этой итерацией НЕ
менялся (причина возврата явно требует «кода не менять») — исправлены
только разделы «AC-20»/«AC-22» выше: по каждому из семи файлов —
конкретный ассерт и почему он фиксировал старый порядок (см. AC-20,
пп.5-11); для AC-22 — точный список из трёх живых задач (`git grep -n
"in_dev -> review"` по дереву `acceptance_tests/` их артефактных
веток), 6+5+2 места, ни один файл не тронут.

### Итерация 5 — закрытие причины возврата: конфликт подтяжки main

Причина возврата этого шага — конфликт подтяжки main в кодовую ветку
(конфликтный файл `docs/roadmap.md`), возникший после Итерации 4.
Конфликт содержательный (оба берега правили §2 роадмапа: main — статус
A7 «выполнена», ветка — пункт про ADR-0015) и лежит в защищённом пути
вне зон этой роли — сведение сделал Оператор коммитом `a29e0782`
(«подтяжка main (сведение Оператором: docs/roadmap.md §2 — A7
«выполнена» из main, пункт ADR-0015 из ветки)»); код этой итерацией не
менялся. Эта итерация — тот самый «шаг developer после возврата»,
которого не хватало по истории отказов advance:

- `git status`/`git log -1` — рабочее дерево чистое, конфликт-маркеров
  нет, HEAD — `a29e0782`, слияние с main завершено полностью
  (`git merge-base --is-ancestor main HEAD` истинно).
- `git show --stat a29e0782` — сведение тронуло только
  `docs/adr/0010-stop-loss-as-milestone.md` и `docs/roadmap.md`, `*.py`
  не затронуты — регенерация `docs/codebase-map.md` не требуется
  (проверено: `python3 scripts/codebase_map.py` + `git diff` дают
  расхождение только в строке `built_at_sha`, откачено `git checkout
  --`).
- Чтением: `docs/roadmap.md:75-82` и `docs/invariants.md:54,61,63`
  по-прежнему называют порядок `in_dev -> verifying -> review ->
  acceptance -> merge_gate` (AC-17/AC-18) — сведение конфликта не
  потеряло формулировку ADR-0015.
- `python3 scripts/guard.py tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md
  tasks/01M1TQ0TRCZPRZX22C4084NCPB/PLAN.md` — «GUARD: ок (2 файлов)».
- `python3 -m unittest tests.test_fsm_advance_gate_smoke
  tests.test_advance_guard tests.test_auto_cycle
  tests.test_review_freshness tests.test_invariants
  tests.test_codebase_map` — 134 теста, все зелёные (~131с).

Кода в кодовую ветку эта итерация не коммитит — коммитить нечего:
диф ветки от main (сведённый Оператором) идентичен тому, что уже
проверило и одобрило REVIEW.md итерации 3 (`approved`); задача этого
шага — подтвердить сведение и дать оркестратору журнальную запись шага
developer, снимающую отказ «возврат не отработан».

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
7. Итерация 3: закрыть REVIEW.md R2-F1 (см. «Итерация 3» выше) —
   перегенерировать `docs/codebase-map.md` после подтяжки main
   (`d9893cd3`), разметить реестр замечаний `fixed`, закоммитить.
8. Итерация 4: закрыть причину возврата приёмки (см. «Итерация 4»
   выше) — расписать AC-20 по каждому из семи файлов с обоснованием,
   найти и перечислить (файл/строки) планки трёх живых задач для
   AC-22; кода не менять, коммита в кодовую ветку не требуется (правка
   только `tasks/<id>/PLAN.md`).

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

### AC-20 — правки ассертов старого порядка (с обоснованием, по каждому файлу)

Причина возврата (приёмка) указала, что семь файлов ниже (п.5-11) были
упомянуты в предыдущей редакции PLAN.md одной строкой («сделаны
предыдущей итерацией... без дополнительных правок») без обоснования —
«сделано предыдущей итерацией» не обоснование, почему именно этот
ассерт фиксировал старый порядок. Ниже — по каждому файлу отдельно, с
конкретным ассертом/фикстурой и причиной правки. Все правки сделаны
одним и тем же диффом (WIP-чекпоинт `0f19be5c`, до первого выхода этого
шага на ревью) — эта итерация только документирует их, кода не меняет.

1. `tests/test_verifying_ceiling.py::test_green_ci_moves_on_regardless_of_elapsed_time`
   — целевое состояние на зелёном CI сменено с `"acceptance"` на
   `"review"` (AC-9): по старому порядку `verifying` вело в
   `acceptance`, по новому — в `review`.
2. `tests/test_branch_freshness_gate.py` — три теста
   (`test_advance_skips_pull_when_branch_not_behind`,
   `test_advance_treats_origin_fetch_failure_as_fresh`,
   `test_advance_pulls_main_and_advances_when_acceptance_green`):
   целевое состояние `in_dev -> {review->verifying}`; плюс
   `acceptance.run` теперь звонится безусловно как часть `in_dev`
   (`assert_not_called()` → сконфигурированный `return_value=(True,
   "ok")` + `assert_called_once()`/`call_count == 2`, где пул реально
   сработал — см. «Подход», известная двойная планка): рубеж «прогон
   приёмки» переехал из approved-ветки `review()` в `in_dev`, где
   звонится безусловно на каждом входе, а не только при approved.
3. `tests/test_acceptance_tests_flow.py::LockTest` — три теста
   (`test_untouched_tests_pass_the_transition`,
   `test_new_unrelated_file_does_not_trip_the_lock`,
   `test_pyc_only_diff_after_lock_does_not_block_the_transition`):
   реальный git без origin — добавлен `mock.patch.object(github_adapter,
   "ensure_head_in_origin", return_value=(True, ""))` вокруг
   `cmd_advance`: рубеж «сверка головы на origin» переехал в `in_dev`,
   где звонится безусловно, а песочница этих тестов не заводит
   настоящий origin — без мока рубеж отказал бы транзиту, которого
   раньше на этом пути не было.
4. `tests/test_amend.py::AmendThenReviewGateTest::test_amend_then_advance_passes_lock_gate`
   — тот же приём (мок `ensure_head_in_origin`, тот же довод, что в
   п.3) + целевое состояние `"review"` → `"verifying"` (AC-1: `in_dev`
   теперь ведёт в `verifying`, не в `review`).
5. `tests/test_advance_guard.py:92-94,285` — таблица `TRANSITIONS`
   (строки 92-94, генерик-сценарная фикстура переходов для ВСЕХ
   состояний) держала `"in_dev": (..., "review")` и `"review": (...,
   "verifying")` — переписана в `"in_dev": (..., "verifying")` и
   `"review": (..., "acceptance")`, ровно новый маршрут (AC-1); итоговый
   ассерт `self.assertEqual(self.state(), "acceptance")` (строка 285)
   после advance из `review` — было `"verifying"`, approved из `review`
   теперь идёт прямиком в `acceptance` (verifying уже пройден раньше,
   AC-9/AC-10).
6. `tests/test_auto_cycle.py` — шесть точек:
   - `FSM_STATES` (строка 59): порядок кортежа `in_dev, review,
     verifying` → `in_dev, verifying, review` — этим кортежем идут
     свипы по ВСЕМ состояниям, порядок обязан отражать реальный маршрут
     (иначе свипы проверяли бы несуществующий с этой задачи порядок);
   - `test_cycle_runs_the_task_from_dev_to_verifying` (строка 383):
     `len(self.agent.calls)` `2 → 0` — PLAN.md готов с самого начала;
     по старому порядку до `verifying` задача проходила ЧЕРЕЗ `review`
     и звала агента-ревьювера дважды (нулевой шаг без перехода +
     approve), по новому — все семь рубежей `in_dev -> verifying`
     свободны, `review` эта задача вообще не посещает (CI дефолтно
     красный, цикл стопорится на входе в `verifying`), агент не
     звонится ни разу;
   - `test_review_iterations_are_passed_without_the_operator` (строки
     398-407): добавлен явный мок `ci.verifying_status` (зелёный) и
     итоговое состояние `"verifying"` → `"acceptance"` — раньше
     `verifying` стоял ПОСЛЕ `review`, опрос CI не мешал сценарию
     повтора итераций ревью; теперь `verifying` стоит ДО `review` —
     без зелёного мока цикл встал бы на самом входе, ни разу не дойдя
     до ревьювера, а после отработки итераций ревью с зелёным CI
     задача идёт в `acceptance`, не остаётся в `verifying`;
   - `test_first_real_step_uses_a_free_transition_first` (строки
     425-434, 446-461) — тот же приём и тот же довод, что в предыдущем
     пункте: явный зелёный мок `ci.verifying_status` + целевое
     состояние `"acceptance"`;
   - `test_escalation_by_the_ceiling_names_budget` /
     `test_escalation_with_the_ceiling_intact_names_approve` — убран
     вызов `self.write_plan("ready")` в начале теста: с ADR-0015
     `ready` с самого начала увёл бы задачу свободным переходом сразу в
     `verifying`, минуя сам шаг developer, чей отказ по бюджету/паузе и
     есть предмет теста;
   - `AutoReportsTheCycleTest` (строка 987): строка ожидаемого текста
     сводки `"...переход выполнен по готовым артефактам (in_dev ->
     review)"` → `"...(in_dev -> verifying)"` — сводка называет
     реальное имя свободного перехода, которым он теперь и является.
7. `tests/test_fsm_map_conflict_autoresolve.py:275,291-292` — целевое
   состояние конфликта карты `"review"` → `"verifying"` (строка 275:
   конфликт только по карте не имеет права эскалировать, переход
   обязан состояться — теперь этот переход ведёт в `verifying`, не в
   `review`); `acc_run.call_count` `1 → 2` и `plank_root =
   acc_run.call_args[0][0]` → `acc_run.call_args_list[0][0][0]` (строки
   291-292) — с ADR-0015 `in_dev` зовёт `acceptance.run` дважды за один
   вызов (рубеж `pull.evaluate` + отдельный рубеж
   `_acceptance_run_refuses`, переехавший из `review()`, см.
   «Подход»), тест изначально проверял именно первый (от
   `pull.evaluate`) вызов — понадобилась индексация по списку вызовов
   вместо единственного `call_args`.
8. `tests/test_git_fixation.py:298-302` — обёрнут
   `mock.patch.object(github_adapter, "ensure_head_in_origin",
   return_value=(True, ""))` вокруг `fsm.cmd_advance`, целевое
   состояние `"review"` → `"verifying"` — рубеж «сверка головы на
   origin» переехал на `in_dev -> verifying`, а песочница этого теста
   не заводит настоящую кодовую ветку с origin (только артефактную
   PLAN-заглушку); предмет теста — сверка чистоты дерева для внешнего
   target, не origin-push (у него свой тест, `test_github_adapter.py`).
9. `tests/test_invariants.py::FreshVerdictGuardsAcceptanceTest` (строки
   774-859) и три соседних теста
   (`ExhaustedBudgetIsNotBypassableTest.test_advance_does_not_unblock_the_run`
   строка 900, `ParallelTaskLimitIsNotBypassableTest...` строка 1064,
   `CountersNeverResetTest.test_no_transition_of_the_full_cycle_resets_a_counter`
   /`test_exhausted_review_limit_is_not_reopened_by_escalation` строки
   1167-1223) — везде один и тот же класс правки: целевое состояние
   после `in_dev -> advance` сменено с `"review"` на `"verifying"`
   (AC-1), а после approved-`review` — с `"verifying"` на `"acceptance"`
   (AC-9/AC-10); там, где сценарий должен дойти до `review`, добавлен
   явный `self.set_ci(GREEN_CI)` перед advance — иначе `verifying`
   держит задачу по дефолтно красному CI фикстуры и до `review` она не
   доходит.
10. `tests/test_review_freshness.py` — хелпер-метод переименован
    `back_to_review_after_verifying_reject` →
    `back_to_review_after_acceptance_reject` (строка 214) и переписан:
    сценарий `review(approved) → verifying → reject` заменён на
    `review(approved) → acceptance → reject → in_dev → verifying →
    review` (последний шаг — прямая установка `self.set_state
    ("review")`, CI в этом модуле не мокается, а предмет тестов —
    свежесть вердикта в `review()`, не опрос CI); пять тестов,
    использующих хелпер и целевые состояния
    (`test_stale_approved_does_not_pass_after_acceptance_reject`,
    `test_stale_verdict_is_journaled`,
    `test_fresh_verdict_passes_to_acceptance` строка 264,
    `test_changes_requested_counted_once` строка 273,
    `test_first_verdict_passes_to_acceptance` строка 291) —
    переименованы и/или целевое состояние `"verifying"` →
    `"acceptance"`, тем же доводом: approved теперь ведёт прямиком в
    `acceptance`, не в `verifying`.
11. `tests/test_review_registry_gate.py:84,108` —
    `self.assertNotEqual(self.state(), "verifying")` → `"acceptance"`
    (строка 84: гейт реестра держит задачу НЕ в `acceptance`, а не НЕ в
    `verifying` — `verifying` уже пройден раньше по маршруту) и
    `self.assertEqual(self.state(), "verifying")` → `"acceptance"`
    (строка 108: пустой реестр не держит переход, конечная точка теперь
    `acceptance`).

### AC-22 — эскалация: планки живых задач со старым порядком (не правятся)

Требование 7/AC-22: приёмочная планка живой (не закрытой) задачи,
фиксирующая старый порядок состояний, не правится этой задачей —
эскалируется списком (файл, строка). Поиск — по точной подстроке
`in_dev -> review` (буквальное имя перехода СТАРОГО маршрута,
замененного этой задачей на `in_dev -> verifying`, AC-1) в дереве
`acceptance_tests/` артефактной ветки каждой задачи:
`git grep -n "in_dev -> review" artifact/<id> -- tasks/<ID>/acceptance_tests`.
Совпадение означает, что планка либо прогоняет сценарий через этот
несуществующий с этой задачи переход, либо докстрингом/сообщением
ассерта утверждает факт о том, где стоит гейт/рубеж, для которого
теперь верно другое имя перехода.

- **01M1R5B33CC7E6BZK085XV3ZCX** (6 мест) —
  `tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests/test_ac15_ac16_ac17_end_to_end.py`,
  строки 6, 12, 43, 93, 118, 202 (докстринг модуля и метода, ассерт
  `test_ac15_full_flow_merges_into_the_target_origin_only` — код
  дословно ожидает `store.get_task(...)["state"] == "review"` сразу
  после `fsm.cmd_advance` из `in_dev`, плюс `store.set_state(...,
  expected_state="verifying")` строкой ниже — оба сломались бы под
  ADR-0015, т.к. `in_dev` теперь ведёт в `verifying`, не в `review`;
  гейт ёмкости AC-16, `CapacityGateThroughAdvanceTest`, тоже описан
  через этот переход).
- **01M1THKWFXFYNW28HDJGYHQWH6** (5 мест) —
  `tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/_sandbox.py:171`;
  `tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/test_ac1_ac2_ac3_first_submission.py:8,62`;
  `tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/test_ac6_over_cap_blocks_transition.py:14,36`
  (эта планка держит `self.assertEqual(self.state(), "review")` сразу
  после advance из `in_dev` в нескольких файлах — та же ловушка).
- **01M1TNMBY8G3AH3MYCB07RW14N** (2 места) —
  `tasks/01M1TNMBY8G3AH3MYCB07RW14N/acceptance_tests/_sandbox.py:30,39`
  (только докстринг-обоснование дизайна песочницы — сценарий этой
  планки нарочно НИКОГДА не доходит до `in_dev`/`review`, код не
  исполняет этот переход, но факт «гейт ёмкости живёт на `in_dev ->
  review`» текстом устарел).

Ни один из перечисленных файлов не тронут этой задачей: все три задачи
живы (`git merge-base --is-ancestor artifact/<id> main` → not an
ancestor для всех трёх на момент этого шага, т.е. не смержены и не
`done`) — правку их планок делает только их собственный developer в
рамках их СВОИХ задач, не эта (AC-21, «Не входит» SPEC).

## Расширение зон

Пути: orchestrator/artel.py, orchestrator/github_adapter.py

Обоснование (orchestrator/artel.py): AC-19 требует, чтобы текст схемы
состояний в выводе `artel.py --help` отражал новый порядок —
`cmd_help` печатает `__doc__` этого же модуля
(`orchestrator/artel.py:443`), других мест вывода `--help` нет. SPEC
`zones:` называет `orchestrator/fsm.py, fsm_advance.py, auto.py,
review.py, config.py, docs/invariants.md, docs/roadmap.md, tests/` —
`orchestrator/artel.py` в списке не назван, хотя единственный способ
выполнить AC-19 буквально — править именно его. Правка — модульный
докстринг (схема состояний, абзац про `verifying`, название рубежа
лока `acceptance_tests/`), без изменений кода. Подтверждено
Оператором (ANSWER-2.md).

Обоснование (orchestrator/github_adapter.py): закрытие REVIEW.md R1-F1
(итерация 2, см. «Итерация 2» выше) — докстринг
`ensure_head_in_origin` (`github_adapter.py:114-116`) называл
`review()` местом вызова рубежа «сверка головы на origin», хотя после
переноса рубежа единственное место вызова — `in_dev()`; докстринг
переписан двумя строками под фактическое место вызова, без изменений
кода. `github_adapter.py` не входит в `zones:` SPEC. Подтверждено
Оператором (ANSWER-3.md).

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

- Диф трогает `orchestrator/artel.py` и `orchestrator/github_adapter.py`
  вне заявленных `zones` — гейт зон (`fsm_advance._zones_gate`) откажет
  `in_dev -> verifying` до тех пор, пока Оператор не подтвердит
  расширение (раздел «## Расширение зон» выше называет оба пути и
  обоснование) — это ожидаемый штатный отказ гейта, не авария. Снято:
  ANSWER-2.md подтверждает `orchestrator/artel.py`, ANSWER-3.md
  подтверждает `orchestrator/github_adapter.py`.
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
