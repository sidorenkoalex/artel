---
task: 01M28NX0M2WTVC38XVN75N01XD
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: kill при живом цикле — отказ с подсказкой stop, ликвидация только с --yes

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (kill без `--yes` при живом lease отказывает, ничего не меняет) | OK | `cleanup._live_cycle_holder`/`_live_cycle_role`/`_refuse_live_cycle` (orchestrator/cleanup.py:141-207); отказ вызывается ДО `lease.run_locked`, подтверждено тестами AC-1 |
| 2 (kill `--yes` при живом lease — прежнее полное поведение + журнал) | OK | orchestrator/cleanup.py:225-231; AC-2 тесты зелёные |
| 3 (kill без флага при отсутствии живого lease — как раньше) | OK | `live_role is None` пропускает guard целиком; AC-3 тесты зелёные |
| 4 (подсказка «дальше:» называет обе команды на гейте/ожидании зоны) | OK | `config._BOTH_COMMANDS` дописан в `AUTO_STOP["spec_gate"/"acceptance"/"merge_gate"/"escalated"]` и `AUTO_STOP_ZONE_WAIT`; AC-4/AC-5 тесты зелёные |
| 5 (`docs/operator-session.md` несёт абзац «stop против kill») | OK | docs/operator-session.md:169-178; AC-6 тест зелёный |
| 6 (`tests/test_kill_cleanup.py`/`tests/test_detached_cycle.py` зелёные без правки) | OK | `git diff` этих файлов пуст (не тронуты вовсе); оба набора зелёные при прогоне |

## Замечания

- major — tests/test_kill_live_cycle_refusal.py:39,42,46,50,54,72,79,105,111 —
  ни один из 9 новых тестовых методов не несёт собственного докстринга
  с заявкой «Ловит мутацию: …» (skills/test-authoring.md, пункт 3
  review-checklist). У `LiveCycleHolderTest` (5 методов: 39, 42, 46, 50,
  54) есть только докстринг класса с формулировкой «ловит мутацию, что
  любой из них перестал влиять на результат» — общий на все 5 разных
  сценариев (чужой host / мёртвый pid / протухший heartbeat / все три
  живы / None), без привязки заявки к конкретному сценарию каждого
  теста. У `LiveCycleRoleTest` (72, 79) и `KillDispatchYesFlagTest`
  (105, 111) фразы «Ловит мутацию» нет вовсе — докстринги классов
  описывают назначение проверяемой функции/пути, но не называют, какую
  порчу кода тест обязан поймать. Для сравнения — приёмочные тесты
  этой же задачи (`tasks/01M28NX0M2WTVC38XVN75N01XD/acceptance_tests/
  test_ac1_ac2_ac3_kill_confirmation.py` и др.) конвенцию соблюдают
  полностью: у каждого метода свой докстринг с явной «Ловит мутацию:
  …». Последствие: при будущей правке `cleanup.py`/`artel.py`
  ревьювер не может свериться с явной заявкой, какую порчу каждый
  юнит-тест обязан поймать (требование review-checklist п.3 — «сверяй
  тест С НЕЙ, а не мысленным мутационным тестом по наитию»), и не
  отличит случайно ослабленный тест от намеренного. Предложение:
  добавить каждому из 9 методов собственный докстринг вида «Ловит
  мутацию: …», описывающий конкретный сценарий и наблюдаемое свойство
  (по аналогии с уже принятым стилем приёмочных тестов этой же
  задачи), а не полагаться на общий докстринг класса.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_kill_live_cycle_refusal.py:39,42,46,50,54,72,79,105,111 | новые тестовые методы (9 из 9) не несут собственного докстринга с заявкой «Ловит мутацию: …» — у части классов заявки нет вовсе, у остальных она общая на класс, не на сценарий | ревьювер будущих правок не может сверить тест с явной заявкой о том, какую порчу кода он обязан поймать | добавить каждому методу собственный докстринг «Ловит мутацию: …» по образцу приёмочных тестов этой же задачи |

## Вердикт

changes_requested — единственное замечание R1-F1: дописать докстринги
9 новым тестовым методам в `tests/test_kill_live_cycle_refusal.py` по
конвенции `skills/test-authoring.md`. Функционально код корректен:
все требования и AC SPEC покрыты и подтверждены зелёными тестами,
защищённые тесты не тронуты, побочных изменений вне заявленного
diff нет.

## Проверено исполнением

- `python3 -m unittest tests.test_kill_live_cycle_refusal
  tests.test_kill_cleanup tests.test_detached_cycle -v` — 54 теста,
  все зелёные (в т.ч. `tests/test_kill_cleanup.py` и
  `tests/test_detached_cycle.py` — защищённые требованием 6/AC-7,
  подтверждено, что diff их не касается: `git diff --stat
  6d65b9f0feaeaaae20f1e5af5e6ab71a777d39f2...HEAD -- tests/test_kill_cleanup.py
  tests/test_detached_cycle.py` пуст).
- `python3 -m unittest
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_ac1_ac2_ac3_kill_confirmation
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_ac4_ac5_auto_stop_hint_names_stop_and_kill
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_ac6_operator_session_doc_has_stop_vs_kill_paragraph
  -v` — 9 тестов (AC-1..AC-6), все зелёные.
- `python3 scripts/codebase_map.py` на рабочей копии — diff с
  зафиксированной `docs/codebase-map.md` только в строке
  `built_at_sha` (законное отставание, см. `review-checklist`); карта
  регенерирована той же задачей, содержимое совпадает.
- Прочитаны SPEC.md/PLAN.md/все 4 файла acceptance_tests/ и весь diff
  построчно; сверены признаки «живого» lease (`_live_cycle_holder`) с
  `lease.py`/`liveness.py` (`_pid_alive`, `_age_seconds`,
  `config.LEASE_STALE_AFTER_SEC`) — переиспользуют те же примитивы,
  что и остальной код, констант/порогов не задваивают.
- Проверено, что `orchestrator/config.py` — законная общая зона
  (`config.COMMON_ZONES`), поэтому её отсутствие в `zones:` SPEC не
  является нарушением (зона `docs/codebase-map.md` — тоже общая).

## Предложения системе

- Приёмочные тесты этой задачи (`tasks/01M28NX0M2WTVC38XVN75N01XD/
  acceptance_tests/`) конвенцию «докстринг = заявка "Ловит мутацию"»
  соблюдают образцово, а новый юнит-тестовый файл той же задачи — нет
  вовсе (см. R1-F1). Стоит явно продублировать конвенцию из
  `skills/test-authoring.md` в `conventions-core` или напрямую в
  шаблоне юнит-теста — разрыв между приёмочными и юнит-тестами внутри
  ОДНОЙ задачи говорит, что конвенция для юнит-тестов не так заметна
  разработчику, как для приёмочных.
