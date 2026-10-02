---
task: 01M3YXYAX5PW9BM67MB4GK85D1
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Предполёт шага сверяет CLI и вход провайдера шага, а не провайдера роли

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–6 → шаги 1–4. Шаг 5 (возврат
  из verifying) — правка заглушки после подтяжки main, обоснована.
- Шаги — проверяемые единицы (runner / preflight / тесты / docs). Подход
  не расходится с архитектурой: провайдер шага берётся из уже
  существующего `runner._step_provider`, а не считается заново. Для
  задачи без набора вызов прежний: `preflight_checks(role, target)`.
- ANSWER-1 (Б) учтён: `stack.REQUIRED_TOOLS` и `models.py` не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `runner.py` `_refuse_before_start`: `provider` и `task_set` передаются только при `_step_set_name(t, role) is not None`. `preflight_checks` берёт CLI, версию и вход у переданного провайдера, без набора — `providers.for_role`, как раньше. |
| 2 | OK | `_named_by_set` дописывает к каждому `fail` хвост `[провайдер шага, роль, набор задачи]`. Отказ происходит до запуска агента, без повтора: это подтверждают AC-2 и AC-4 долгоживущего файла. Провалы после раннего возврата (`git-identity`, версия CLI) бывают только `warn`, поэтому хвост не теряется. |
| 3 | OK | Шаг набора не спрашивает `check_token` и CLI боевого провайдера. Расхождение боевой цепочки отключено через `combat_chain=False`. Проверка ненайденного CLI в `check_model_provider_cli` сохранена. |
| 4 | OK | `provider_preflight_checks` дополнительно опрашивает `models.live_task_set_providers() - asked`. Закрытые задачи отсекает сам источник (`_CLOSED_STATES`). |
| 5 | OK | Долгоживущий файл задачи: AC-1…AC-5 зелёные. Метод AC-3 несёт заявку «Ловит мутацию: предполёт по провайдеру роли, а не шага». |
| 6 | OK | В `docs/stack.md` добавлен абзац «Предполёт шага задачи с набором». Он описывает провайдера шага, неизменный манифест и добавку `doctor`. |

Тесты: в `tests/test_preflight_step_provider.py` 5 методов. Каждый несёт
заявку «Ловит мутацию: …» с наблюдаемым расхождением: detail строки
`cli-found` / `combat_chain` / `asked`. Сверил заявки с утверждениями,
ловятся. Свойства долгоживущего файла (сквозные AC) этот файл не повторяет:
он покрывает углы на заглушках провайдеров. Две изменённые заглушки
`lambda role, target: []` → `lambda role, target, **step: []`
(`tests/test_01m3ychs4f08…:325`, `tests/test_01m3ychvvek14…:210`) только
расширяют сигнатуру. Ни одно утверждение не тронуто, сужения данных нет.

Влияние на систему соответствует диффу. Гейты, guard и инварианты не
тронуты, путей «только чтение» в диффе нет. Откат — revert.

## Замечания

Нет замечаний уровня blocker/major/minor. Наблюдение не в счёт
вердикта: `_set_step_model` вызывается дважды за шаг — через
`_step_provider` и через `_step_set_name`. Повторное разрешение модели
дешёвое и на исход не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py tests/test_preflight_step_provider.py tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py tests/test_doctor.py tests/test_runner_model_preflight.py tests/test_stack_optional_tools.py tests/test_task_model_set_units.py`
  — 211 passed, 7 subtests passed.
- Временная мутация `runner.py`: `preflight_checks(role, target, **step_kwargs)` →
  `preflight_checks(role, target)`, то есть предполёт по провайдеру роли.
  Долгоживущий файл: 4 failed (AC-1, AC-2, AC-4, AC-3 «шаг, а не роль»),
  2 passed. Код возвращён через `git checkout orchestrator/runner.py`,
  дерево чистое.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой
  только в заголовке diff, содержимое совпадает (карта свежая). Файл
  возвращён.
- CI коммита 19a275e8 зелёный (из пакета).

## Предложения системе
- Тот же класс, что в PLAN: позиционные заглушки
  `lambda role, target: []` для `doctor.preflight_checks` разбросаны по
  тестам. Расширение сигнатуры уже дважды ломало чужие долгоживущие файлы.
  Общая заглушка в `tests/sandbox.py` закрыла бы этот класс.
