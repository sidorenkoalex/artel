---
task: T038
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Стоп-кран auto по повторному отказу advance

## Гейт плана (Фаза A)

1. Покрытие — таблица PLAN полна: все 6 требований SPEC отображены на
   единственный шаг 1. Соответствует факту: весь код — в
   `orchestrator/auto.py` (константа `REFUSAL_ACTION_PREFIX`,
   `_advance_refusal`, watermark + `prev_refusal` в `cmd_auto`).
2. Шаг — проверяемая единица размера MR (не микрооперация, не «сделать
   всё»): один файл продакшн-кода + тесты на все AC.
3. Подход не конфликтует с конвенциями: `fsm.py` не тронут (SPEC, «Не
   входит»), `AUTO_MAX_STEPS` не тронут (требование 6), guard-ветка
   (T034, требование 2) физически недостижима одновременно с новой
   веткой — `cmd_advance() -> True` делает `return` раньше вычисления
   watermark'а (`orchestrator/auto.py:116-128`). Пересечения нет по
   построению, как заявлено в PLAN.

Гейт плана пройден, замечаний нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_advance_refusal` (`orchestrator/auto.py:13-25`) ищет запись `actor="fsm"`, `action` с префиксом `REFUSAL_ACTION_PREFIX = "переход отклонён"` среди строк журнала, добавленных ИМЕННО этим вызовом `cmd_advance` (watermark `journaled_before`, `auto.py:115`); сравнение `refusal == prev_refusal` (`auto.py:137`) — дословное совпадение текста `action`. |
| 2 | OK | `auto_stop(conn, task_id, state, f"{refusal} — {hint}", hint)` (`auto.py:142`) переиспользует журнальный текст `fsm` как есть; `hint` — точный текст SPEC («почини причину и повтори `artel.py advance <id>`», `auto.py:141`); `auto_stop` пишет в журнал (`actor="operator"`, `action="auto остановлен"`) и печатает Оператору (`auto.py:45-51`) — тот же механизм, что у существующих остановок. |
| 3 | OK | Ветка `if fsm.cmd_advance(task_id):` (guard, `True`) делает `return` до вычисления `journaled_before`/`refusal` (`auto.py:116-128`) — новая проверка физически не видит guard-случай. Проверено чтением `orchestrator/fsm.py`: все 4 места `guard_refuses(...)` внутри `cmd_advance` (строки 138, 149, 168, 289) сопровождаются `return True` сразу после — новое и старое правило не пересекаются по построению. |
| 4 | OK | Шаг, где `advance` не журналирует «переход отклонён…» (`PLAN.md`/`SPEC.md` не `ready`, `REVIEW.md` без вердикта — печать без `store.journal`), даёт `refusal = None`, что и обнуляет `prev_refusal` (`auto.py:147`) — не даёт серии сложиться. Проверено тестом `test_a_step_without_a_refusal_breaks_the_streak` и AC-2 в `tasks/T038/acceptance_tests/`. |
| 5 | OK | `refusal == prev_refusal` — строгое сравнение текста; разные тексты не совпадают, серия не засчитывается (`test_ac3_two_different_refusal_texts_do_not_stop_the_cycle`, `Ac3DifferentRefusalTextDoesNotStopTest`). |
| 6 | OK | `config.AUTO_MAX_STEPS` не тронут (не входит в diff); ветка потолка (`auto.py:88-93`) не изменена. |

Проверено запуском (см. «Замечания» ниже за деталями окружения):
- `python3 -m unittest tests.test_auto_cycle -v` — 28/28 OK.
- `python3 -m unittest tasks.T038.acceptance_tests.test_auto_stop_on_repeated_advance_refusal -v` — 8/8 OK.
- `python3 -m unittest discover -s tests -p "test_*.py"` — 605 тестов, 3 упавших (не по вине diff'а, см. ниже).
- `python3 scripts/guard.py tasks/T038/SPEC.md tasks/T038/PLAN.md` — ок.
- `python3 scripts/codebase_map.py` в рабочей копии vs закоммиченная версия — расхождение только в строке `built_at_sha` (карта сверяется по содержимому, не по sha — коммит `d2f9b62`); карта свежая.

Мысленный мутационный тест: убрать `refusal == prev_refusal` (оставить
`refusal is not None`) — красит `test_ac3_two_different_refusal_texts_do_not_stop_the_cycle`;
убрать сброс `prev_refusal = ... if state == before else None` — красит
`test_a_step_without_a_refusal_breaks_the_streak` и
`test_progress_between_refusals_does_not_carry_the_streak_across_states`.
Тесты пристёгнуты к реализации, не к структуре.

## Замечания

Замечаний нет.

Информационно (не замечание, не блокирует аппрув):

- `python3 -m unittest discover` даёт 3 неудачи в
  `tests/test_multitarget.py::RoleEnvTest`
  (`test_absent_identity_is_journalled_before_the_step`,
  `test_env_carries_the_git_identity`,
  `test_identity_already_in_the_environment_is_not_overridden`) —
  вызвано `GIT_COMMITTER_EMAIL`/`user.email`, заданными в окружении этой
  машины, а не diff'ом задачи: `tests/test_multitarget.py` в diff не
  входит, тест ожидает окружение без git-identity Оператора. К AC-4
  (регрессия `tests/test_auto_cycle.py`) не относится. Стоит убедиться,
  что CI-раннер не тянет такие переменные из профиля — если тянет, тест
  будет падать и на других задачах, вне зависимости от T038.
- Доля diff'а `docs/codebase-map.md`, документирующая `tests/sandbox.py`
  / `spawn_agent` / рефактор тестовых импортов на `tests/sandbox.py`, —
  не новая работа T038: `git cat-file -e <merge-base>:tests/sandbox.py`
  подтверждает, что файл существовал на `main` уже на момент ветвления
  задачи. Карта на `main` не была перегенерирована после того мержа;
  T038 обязана перегенерировать карту по конвенции (правка `.py` в
  `orchestrator/`) и заодно зафиксировала чужой дрейф. Раздел PLAN
  «Влияние на систему» не упоминает это отдельно, но по факту diff'а
  вне-зонных side-effects нет — это документационная фиксация
  существовавшего состояния, не код.

## Вердикт

approved

## Проверено исполнением
Ретроактивная пометка при миграции корпуса под evidence-контракт (T072, 2026-08-30): это ревью прошло до появления обязательной секции «Проверено исполнением» (SPEC T072, guard.py:review_evidence_errors). Факт исполнения проверок этим ревью, если они проводились, восстановить задним числом нельзя — что реально оценивалось, отражено выше, в разделах «Соответствие SPEC»/«Замечания» этого файла. Секция добавлена постфактум одним коммитом по всему корпусу только для соответствия новому структурному правилу guard.py, содержательно не переписывает исходное ревью.
