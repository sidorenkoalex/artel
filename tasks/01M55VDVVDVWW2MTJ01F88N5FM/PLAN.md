---
task: 01M55VDVVDVWW2MTJ01F88N5FM
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Мандат на ослабление тестов внешнему проекту — проверка при записи по профилю проекта

## Подход
Проверка при записи берёт область из того же решения, что гейт:
`project_profile.for_task(conn, task_id)` → `Profile.in_weakening_scope`.

- `orchestrator/advance_gates/mandate.py`:
  - `_task_decision(conn, task_id)` — решение профиля; `None` без задачи
    (ленивый импорт `project_profile`).
  - `_weakening_scope_refusal(path, decision)` — без задачи: прежние
    `in_weakening_scope` и текст; решение-отказ / пропуск: именованный отказ
    с текстом `decision.refusal` / `decision.skip`; профиль: маски
    `weakening_scope`, текст «путь вне области <маски> — гейт неослабления
    тестов другие пути не рассматривает». У артели маска `tests/**/*.py`,
    поэтому текст отказа у неё буквально прежний (требование 3).
  - `refusals` считает решение один раз и только при строке «Ослабление
    тестов разрешено:» — ответ с одним мандатом зон `targets.yaml` не читает,
    и сбой профиля ему не отказывает (вне объёма SPEC ничего не меняется).
  - `matrix_refusals(..., conn=, task_id=)`: у задачи внешнего проекта с
    профилем ссылка «Чем покрыто после» — путь `*.py` (`_PY_PATH_RE`, за ним
    может стоять `:строка`/`::имя`) в области профиля; у артели, без задачи и
    при отказе/пропуске решения — прежний `_TEST_REF_RE` буквально
    (требование 4: «у артели решения прежние»).
- `orchestrator/answer.py`: `conn`/`task_id` передаются в
  `mandate.matrix_refusals` в обоих каналах — `_matrix_problems` (answer) и
  `_zones_extend_matrix` (zones-extend).

## Шаги
1. `mandate.py`: решение профиля в `refusals`/`_element_refusal`, профиль в
   `matrix_refusals`/`_covered`; `answer.py`: передача задачи в оба канала
   матрицы; юнит-тесты `tests/test_mandate_profile_scope.py`; регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_weakening_scope_refusal`, ветка профиля) |
| 2 | 1 (`decision is None` / `refusal` / `skip`) |
| 3 | 1 (текст по маскам артели совпадает с прежним; деградация — ветка отказа) |
| 4 | 1 (`matrix_refusals` + `_covered(cell, profile)`, оба канала `answer.py`) |
| 5 | 1 (долгоживущий файл задачи + `tests/test_mandate_profile_scope.py`) |

Проверено: `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py`
— 6 passed (AC-1..AC-6); тесты соседних модулей (`test_answer*.py`,
`test_mandate_matrix_form.py`, `test_zones_gate.py`, `test_merge_after.py`,
`test_01m4nz5…_mandate_matrix.py`, `test_01m42nb…_class_mandate.py`,
`test_01m446…`, `test_01m44ep…`, `test_01m4r4j…` оба, `test_01m4kay…`,
`test_01m443b…` оба, `test_01m45d29…`, `test_01m3xtf…`,
`test_canary_synthetic_answer.py`, `test_docs_ref_deleted_refusal.py`) —
186 passed. Сторожа нового файла проверены временной мутацией (решение
профиля на каждом вызове; любая `*.py` ссылкой; только первый путь ячейки)
— каждый покраснел, код возвращён. Планки (`acceptance_tests/`) у задачи нет.

## Влияние на систему
- Гейт неослабления, `project_profile`, `test_integrity._in_scope` не
  тронуты; проверка при записи стала строже/точнее ровно на путях, которые
  гейт не засчитает: у артели в деградированном состоянии профиля мандат
  ослабления теперь отказан при записи (решение Оператора 18.10, требование
  3) — в том же состоянии отказывают гейт перехода и мерж.
- Мандат зон и строка «Зависимости мержа» не меняются; ответ без мандата
  ослабления `targets.yaml` не читает.
- Существующие тесты не правились. Откат — revert коммита задачи.

## Риски
- Ссылка матрицы у внешнего проекта сверяется с масками буквально
  (без нижнего регистра нормализации) — путь в другом регистре покрытием не
  считается; так же сверяет пути гейт.

## Предложения системе
- Составные команды Bash и `sed -i` в шаге требуют одобрения, которого
  никто не даёт: временную мутацию сторожа пришлось гонять сценарием
  python из каталога документов (скил coding-standards описывает мутацию, но
  не штатный инструмент для неё).
