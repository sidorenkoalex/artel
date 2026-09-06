---
operator: Alexander Sidorenko
model: unknown
artel_sha: fe92473147b880d9541de788db3182c8c7285212
---

# RETRO: 01M1TKNXX5YN5KT4WHG4T44JWV — R2 — fsm_advance.py: гейты in_dev и review как предикаты с единым исходом

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: R2 — fsm_advance.py: гейты in_dev и review как предикаты с единым исходом

Стоимость итого: $33.43
  analyst: $1.01, 870165 токенов
  test_author: $10.66, 23802941 токенов
  developer: $19.67, 45389240 токенов
  reviewer: $2.08, 3445076 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): эскалация от разработчика: ### Вопросы

1. Блокирующий. Залоченная планка этой же задачи
   (`tasks/01M1TKNXX5YN5KT4WHG4T44JWV/acceptance_tests/
   test_ac9_smoke_fixture_byte_identical.py`, AC-9) фиксирует байт-в-байт
   вывод гейтов ёмкости/зон БЕЗ фразы «база сравнения ... от ...» и без
   предварительного вызова `gitcmd.diff_base`/`diff_base_source` — тот
   формат, что действовал ДО того, как в main влилась
   `01M1SG9T962WJJ31S282GWM0EN` (снимок test_author'а старше этого
   мержа: SPEC этой задачи не отделяла «зафиксировано ДО правки этой
   задачи» от «зафиксировано ДО ЛЮБОЙ последующей подтяжки main»).
   ANSWER-1 этой же задачи явно требует сохранить поведение
   `01M1SG9T962WJJ31S282GWM0EN` байт-в-байt (база сравнения через
   `diff_base`, текст «база сравнения … от …» в отказах) — это
   требование и локальная планка AC-9 взаимно исключают друг друга:
   код, проходящий планку, обязан НЕ содержать текст «база сравнения»,
   а код, сохраняющий поведение main (и не откатывающий чужую задачу),
   обязан его содержать. Правка `tasks/<id>/acceptance_tests/` — не в
   праве разработчика (лок T023: «код чинится под них, их правка —
   эскалация»), а откат поведения `01M1SG9T962WJJ31S282GWM0EN` нарушил
   бы принцип целостности (ADR-0002: не ослаблять чужую, уже смерженную
   в main механику) и прямое указание ANSWER-1. Варианты:
   - (по умолчанию) обновить фикстуру AC-9 через штатный канал
     `artel.py amend-tests` — новые ожидаемые строки те же, что уже
     несёт `tests/test_fsm_advance_gate_smoke.py` (эта задача, не
     залочен) после этого же возврата: «база сравнения deadbeef от
     origin/main» для гейта ёмкости/зон с тем же мокнутым
     `gitcmd.diff_base`/`diff_base_source`;
   - откатить требование ANSWER-1 сохранить поведение
     `01M1SG9T962WJJ31S282GWM0EN` для ЭТИХ двух гейтов конкретно —
     оценка автора: не рекомендуется, это откат уже смерженной в main
     механики ради одной задачи, регрессия для задачи
     01M1SG9T962WJJ31S282GWM0EN.

### Контекст

- Конфликт подтяжки main (причина возврата) разрешён: `git merge
  origin/main` в этом worktree, конфликт в `orchestrator/fsm_advance.py`
  (4 участка: хвост `review()`, дважды `_capacity_gate`, `_zones_gate`) и
  `docs/codebase-map.md` (взята версия main, карта перегенерирована
  `python3 scripts/codebase_map.py`) — по инструкции ANSWER-1. Структура
  каркаса `GateRefusal`/`_run_gates` этой задачи сохранена; база
  сравнения diff обоих гейтов переведена на `gitcmd.diff_base`/
  `diff_base_source` (`01M1SG9T962WJJ31S282GWM0EN`); `acceptance.summary`
  зовётся с `branch=t["branch"]` (`01M1SHJTT0V516BWHYXWS50F3G`). Также
  нашлась и вне маркеров конфликта утечка старого стиля (`store.journal`+
  `print`+`return True` внутри функции, возвращающей `GateRefusal`) —
  git 3-way merge вставил хунк origin/main по совпадающему контексту без
  объявления конфликта; переведена на `GateRefusal` тем же приёмом, что
  и остальной гейт. Коммит `1b828cf1`.
- Юнит-тесты каркаса (`tests/test_fsm_advance_gate_framework.py`),
  собственный смоук этой задачи (`tests/test_fsm_advance_gate_smoke.py`
  — фикстура обновлена под объединённое поведение, мок `diff_base`/
  `diff_base_source` явный, коммит `c24a2929`) и весь список планок
  ANSWER-1 (`tests/test_zones_gate.py`, `tests/test_capacity_gate*.py`,
  `tests/test_fsm_review_rework_gate.py`, `tests/test_review_registry_gate.py`,
  `tests/test_review_freshness.py`, `tests/test_review_package.py`,
  `tests/test_advance_guard.py`, `tests/test_github_adapter.py`,
  `tests/test_fsm_draft_mr_reentry.py`, `tests/test_invariants.py`,
  `tests/test_multitarget*.py`, `tests/test_zone_lock.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_fsm_merge_conflict_note.py`, `tests/test_step_refixation.py`,
  `tests/test_advance_refusal_history.py`, `tests/test_split_assessment_merge_gate.py`,
  `tests/test_canary.py`, `tests/test_acceptance_tests_flow.py`,
  `tests/test_acceptance.py`, `tests/test_branch_freshness_gate.py`) —
  все зелёные (334 теста одним прогоном). Планки
  `tasks/01M1SG9T962WJJ31S282GWM0EN/acceptance_tests/` (21 тест) и
  `tasks/01M1SHJTT0V516BWHYXWS50F3G/acceptance_tests/` (8 тестов) —
  зелёные.
- Планка ЭТОЙ задачи (`tasks/01M1TKNXX5YN5KT4WHG4T44JWV/acceptance_tests/`):
  14 из 16 зелёные. По ходу разбора найден и исправлен реальный дефект —
  `GateRefusal` был объявлен как `namedtuple("GateRefusal", [...])`
  (вызов фабрики, не `class`), AC-1/AC-2 ищут тип СТРУКТУРНО через AST
  (`class ... (NamedTuple)` либо `@dataclass(frozen=True)`) и не находили
  его вовсе — переведено на `class GateRefusal(NamedTuple): ...`, все
  четыре теста AC-1/AC-2 позеленели, семантика (`GateRefusal(a, d, h)`,
  `.action`/`.detail`/`.hint`) не изменилась. Оставшиеся 2 красных —
  `test_ac9_smoke_fixture_byte_identical.py`, предмет вопроса 1 выше.

### Блокирует

Не могу поставить `status: ready` не нарушив либо лок `acceptance_tests/`
(T023: правка — эскалация, не разработчика), либо явное указание
ANSWER-1 сохранить поведение `01M1SG9T962WJJ31S282GWM0EN` байт-в-байт,
либо принцип целостности (откат чужой смерженной механики). Нужно
решение Оператора, какую сторону конфликта снимать.

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
