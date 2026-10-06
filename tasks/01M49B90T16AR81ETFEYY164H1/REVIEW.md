---
task: 01M49B90T16AR81ETFEYY164H1
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: CI ветки задачи — полный набор tests/ один раз на sha

## Фаза A: план

- Таблица покрытия PLAN полна (требования 1–8), шаги — проверяемые единицы.
- Подход не изменился с итерации 1: вывод `open_pr` job `changes` и правило
  исполненного близнеца в `orchestrator/ci.py`. ADR-0016 и инвариант 36 не задеты:
  `paths`/`paths-ignore` не вводятся.
- PLAN дополнен абзацем о закрытии R1-F1. «Влияние на систему» соответствует
  фактическому diff: дублирующий тест удалён, карта пересобрана.
- Замер требования 7 (2 → 1 на коммит по задаче 01M484RNV3) честно оговаривает,
  что `gh run list` недоступен. Это принято ещё в итерации 1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Приложение к `ci.yml` не менялось с итерации 1; планка AC-1 зелёная. |
| 2 | OK | Без изменений с итерации 1: push без PR и ошибка API оставляют набор на push, `main` не затронут. |
| 3 | OK | `orchestrator/ci.py` в инкременте не менялся. Правило держит долгоживущий файл задачи: в итерации 1 мутация `_unexecuted_full_suite → []` дала 28 failed. |
| 4 | OK | `find_run_id`/`trigger_rerun` не менялись; AC-10 долгоживущего файла зелёный. |
| 5 | OK | Планка `test_workflow_appendix.py` — 1 passed. |
| 6 | OK | Все свойства AC-4…AC-14 держит `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py`. Дубль удалён (R1-F1). Изменение `test_ac8_parsers_keep_outcomes_on_the_new_text` остаётся в рамках ANSWER-1, вариант А. |
| 7 | OK | См. Фазу A. |
| 8 | OK | `ci.FULL_SUITE_CHECKS` — единственное объявление. Удалённый файл держал второй, литеральный список имён; теперь его нет. |

## Замечания

Новых замечаний нет. Инкремент `2c72ad93..27ccce74` содержит только удаление
`tests/test_ci_full_suite_once.py` и пересборку `docs/codebase-map.md`. Удаление
набор не ослабляет: этого файла нет в базе ветки (`main`), это новый файл задачи.
Все его свойства перечислены в R1-F1 и сторожатся долгоживущим файлом.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_ci_full_suite_once.py:53-164 | Файл повторял AC-4…AC-14 долгоживущего `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py` (ADR-0020 п. 4); докстринги — только однострочная заявка | Двойная правка при смене механики; литералы имён расходились с `ci.yml` | Файл удалён целиком (коммит 27ccce74). Ссылок на него в дереве нет (`git grep` пуст). Карта пересобрана и свежа. Принято. |

## Вердикт

approved. R1-F1 закрыт, код пульта и приложение к `ci.yml` по-прежнему
соответствуют SPEC, блокирующих и major-замечаний нет.

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M49B90T16AR81ETFEYY164H1` — `test_workflow_appendix.py`: 1 passed, код выхода pytest 0.
- `python3 -m pytest -q tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py tests/test_ci_status.py tests/test_ci_rerun_command.py tests/test_ci_push_class.py` — 126 passed, 126 subtests passed. Это 134 из итерации 1 минус 8 методов удалённого дубля.
- `git show --stat 27ccce74`: только `docs/codebase-map.md` и удаление `tests/test_ci_full_suite_once.py`. `orchestrator/ci.py` в инкременте не менялся.
- `git grep -n test_ci_full_suite_once` — пусто: висячих ссылок нет.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежая. Регенерация откачена, `git status` чистый.
- `git diff --stat main -- .github/workflows/ci.yml` — пусто: `ci.yml` ветки не тронут, правка едет только приложением PLAN.
- CI коммита 27ccce74 зелёный (16 проверок) — по статусу из пакета.

## Предложения системе

- Пакет итерации 2 не включает diff `docs/codebase-map.md` в инкремент, хотя коммит
  27ccce74 его меняет. Свежесть карты ревьюверу приходится перепроверять вручную
  при каждом удалении или добавлении теста. Можно печатать в пакете однострочный итог
  «карта свежа / расходится» вместо исключения карты целиком.
