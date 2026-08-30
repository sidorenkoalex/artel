---
task: T073
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Retention-политика и команда prune

## Фаза A: проверка плана

Покрытие требований в PLAN.md полное (таблица «Покрытие требований»
называет шаг для каждого из 4 требований SPEC). Шаги — проверяемые
единицы (константы конфига / таблица+функции store / новая функция
cleanup / вызов в fsm / модуль prune / строка CLI / документ / тесты /
регенерация карты), не микрооперации и не «сделать всё разом». Подход
не конфликтует с конвенциями: SQL остаётся только в `store.py`
(ADR-0003 3ж), новая функция `cleanup.drop_merged_task_branch`
осмысленно отделена от `drop_task_branch` (разная семантика: killed
namespace оставляет смерженную ветку, done — удаляет), `prune`
получает тот же стиль `execute: bool = False`, что и `doctor`/`canary`.
Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (docs/retention.md по видам данных) | OK | Все виды данных из требования покрыты (логи, ветки, alerts, worktree, report-страница, журнал БД/гейты, premod); AC-8/AC-9 зелёные. |
| 2 (уборка ветки/worktree на done) | OK | `fsm._cmd_approve_merge_gate` — worktree первым, затем `cleanup.drop_merged_task_branch` (`git branch -d`, безопасное удаление); AC-1/AC-2/AC-3 зелёные. |
| 3 (команда prune) | OK | dry-run по умолчанию, `--execute` исполняет; логи — AND обоих лимитов; alerts — архивация, не удаление; отчёт в обоих режимах. AC-4..AC-7 зелёные. |
| 4 (текст уточнения инварианта 16) | OK | Текст подготовлен в PLAN.md («Подход», п.5) и продублирован в docs/retention.md; ADR не создан (AC-10 зелёный, дифф-тест это подтверждает). |

## Проверка

- `python3 -m unittest discover -s tests -v` — 940 тестов, все зелёные
  (включая новые `tests/test_prune.py`, `tests/test_done_branch_
  cleanup.py` и неизменённый `tests/test_invariants.py`).
- `python3 -m unittest discover -s tasks/T073/acceptance_tests -p
  "test_ac*.py" -v` — 25 тестов, все зелёные (AC-1..AC-11).
- `python3 scripts/codebase_map.py` — без диффа в содержимом
  (менялся только `built_at_sha`, который я откатил обратно): карта
  свежая, регенерация в коммите `92e6d75` корректна.
- `git diff main...HEAD --name-only` — только заявленные файлы
  (`docs/`, `orchestrator/{artel,cleanup,config,fsm,prune,store}.py`,
  `tasks/T073/`, `tests/test_prune.py`,
  `tests/test_done_branch_cleanup.py`); `docs/adr/`, `docs/
  invariants.md`, `tests/test_invariants.py`, `gates.yaml`,
  `roles.yaml`, `.github/`, `templates/`, `skills/` не затронуты.

## Замечания

<нет>

## Вердикт

approved.

Обоснование: все 11 AC покрыты приёмочными тестами и проходят вместе
со всем существующим набором (940+25 тестов зелёные), инварианты и
защищённые файлы не тронуты (подтверждено дифф-тестами AC-10/AC-11 и
независимо командой `git diff --name-only`), retention-документ
покрывает все виды данных из требования 1, класс дефектов «AND вместо
OR» / «-D вместо -d» / «удаление без архивации» проверен полной
таблицей истинности (test_ac5) и мутационно-чувствительным тестом на
неслитую ветку (test_done_branch_cleanup). Влияние на систему в PLAN
соответствует фактическому диффу — side effects вне заявленной зоны
не обнаружено.

## Предложения системе

<нет>
