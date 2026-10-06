---
task: 01M48FRD9RJDBBVT2SN0FY5G2A
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: детерминированный тест AC-6 части 2 и ловля тестов, зависимых от случайного зерна

## Фаза A — план

- Покрытие полно: требование 1 → шаг 2, требование 2 → шаг 1, требование 3 → шаг 1 (долгоживущий файл test_author + юнит-тесты углов).
- Шаги — единицы размера MR. Подход в рамках архитектуры: новая логика в `orchestrator/acceptance.py` (раннер) и узел `_seed_repeats_escalate` в `advance_gates/acceptance.py` (рубеж), константа в `config.py`.
- «Влияние на систему» совпадает с диффом: 5 файлов (`orchestrator/acceptance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/config.py`, метод AC-6, новый `tests/test_acceptance_seed_repeat.py`) + карта; путь отката описан (revert, функции новые).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Метод перебирает все записи `config.PROTECTED_PATHS` `subTest`-ом в обоих сценариях; отсутствие пути сверяется с перечнем, вырезанным `HIGHLIGHT_PATHS` из комментария, а не подстрокой всего текста. Правка ровно дифф ANSWER-1: блок ```diff PLAN.md побайтно совпадает с `git diff c8548dab -- tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py`; строка «Ловит мутацию» не тронута. Форма «один черновик на сценарий» принята мандатом (п. 3 ANSWER-1). |
| 2 | OK | `_seed_repeats_escalate` зовётся только после зелёного первого прогона (`advance_gates/acceptance.py:386`, после ветки `if not green`) и только при непустом `long_lived`; признак — `ast`-разбор `import random`/`from random import`; N читается `config.LONG_LIVED_SEED_REPEATS` в момент рубежа; повторы не обрываются на первом красном; каждый повтор — `timeout=config.ACCEPTANCE_TIMEOUT_SEC`, истёкший предел — красный с пометкой; эскалация `escalated_from="in_dev"` + `set_state(..., "escalated")`, деталь печатается `store.set_state` (`store.py:684`) и пишется в журнал; узел `файл::Класс::метод` и зёрна — из junit-отчёта, без зерна — «зерно не напечатано». |
| 3 | OK | Долгоживущий файл test_author (AC-4..AC-7) зелёный; юнит-тесты разработчика держат иные углы (формы импорта, функция без класса, тест без зерна, таймаут) — не повтор долгоживущего. Существующие тесты не ослаблены: единственная смена утверждений — метод AC-6 под мандатом ANSWER-1, и он строже (18 записей вместо одной случайной). |

## Замечания

Блокеров, major и minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_acceptance_seed_repeat.py tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py` — 11 passed, 45 subtests passed за 28 с.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M48FRD9RJDBBVT2SN0FY5G2A` — 4 passed (AC-1/AC-2, AC-3 под двумя мутациями), код выхода pytest 0.
- Сверка мандата: Python-скрипт сравнил блок ```diff раздела «Правка метода AC-6» PLAN.md с `git diff c8548dab -- tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py` — `IDENTICAL`.
- Временная мутация (код возвращён, `git status` чист): `carries_random_seed` заменён на подстроку `"random" in text` → `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py::NoSeedSingleRunTest::test_ac6_file_without_random_import_runs_once` красный (1 failed) — сторож заявки работает.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в строке `built_at_sha` (не дефект); изменение откачено `git checkout`.
- Чтение сверх пакета: `orchestrator/advance_gates/acceptance.py:290-400` и `orchestrator/fsm_advance.py:640-700` (место вызова и возврат `True` → `advance` выходит без перехода в `verifying`), `orchestrator/store.py:680-685` (печать детали `set_state` — чтобы проверить, что деталь эскалации попадает в вывод `advance`, AC-4).

## Предложения системе

- Пакет ревью: строка «Изменённые утверждения тестов» печатает старые утверждения, но не новые; для сверки мандата «ровно дифф PLAN» полезна была бы встроенная проверка побайтного совпадения диффа файла с блоком ```diff PLAN.md — сейчас ревьювер делает её скриптом вручную.
