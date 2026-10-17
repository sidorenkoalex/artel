---
task: 01M52EEHSRD93WMPHWB5VJYRKD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: D0-3: один источник профиля у вызывающих прогон

## Подход
Механика приёма профиля уже вмёржена частью 2 (`orchestrator/acceptance.py`,
`orchestrator/advance_gates/two_sided.py` не правятся). Задача — на стороне
вызывающих передать профиль `pytest-own` проекта задачи тем же каналом, не
трогая путь `pult-pytest` и артели (AC-10, AC-11). Два приёма по тому, что
вызывающий имеет на руках:

- **Вызывающий уже берёт `decision.profile` и передаёт `list(command)`**
  (гейт мержа `fsm_merge_gate._full_suite_command`, рубеж `in_dev` в
  `advance_gates/acceptance.py`, сухой сбор `fsm_advance.tests_writing`):
  `acceptance._own(profile) or list(profile.command)` — у `pytest-own` идёт
  сам `Profile`, у `pult-pytest` прежний список байт в байт. Узел сухого
  сбора `tests_writing._tests_writing_dry_collect_gate` больше не
  сворачивает команду в `list(...)`, если пришёл профиль `pytest-own`.
- **Вызывающий не передавал ничего** (`plank-run`, `pull`, обе точки
  `amend-tests`): `acceptance._task_own_profile(conn, task_id)` — тот же
  источник, что у `acceptance_suite` (часть 2); профиль передаётся только
  при не-`None`, иначе вызов остаётся прежней формы. В
  `amend._amend_plank_only` у `pytest-own` дополнительно `cwd=wt_path`
  (требование 1: `workdir` отсчитан от рабочей копии); у `pult-pytest`
  `cwd` не передаётся — корень пульта, как на main.
- **Двусторонний прогон** (`test_integrity`): профиль у гейта уже есть
  (`decision.profile`); новый помощник `_own_profile` отдаёт его только у
  `runner: pytest-own`, и он пробрасывается в `_observe` →
  `_observe_methods` → `two_sided.run(..., profile=…)` и в вызов гейта.
  У `pult-pytest` `two_sided.run` зовётся прежней формой (без `profile`),
  иначе стороны пошли бы командой профиля вместо команды пульта.
- **`suite-run`**: `_profile_command` при `runner: pytest-own` отдаёт
  `Profile` (из тех же значений `repo_context.profile_of`), иначе прежний
  список. Этот же объект идёт в `run_full_suite` ветки и базы и в
  `acceptance.suite_result_key(…, base=True)` у `_base` — ключ итога базы
  считается по профилю (AC-4). `--failed` у `pytest-own`: id упавших
  напечатаны pytest из `workdir`, поэтому идут каналом `test_ids`
  `run_full_suite` (предусмотрен частью 2, ANSWER-1 той задачи), а не
  целями `targets`, которые переводятся к `workdir`. У списка — прежние
  `targets`, `test_ids` не передаётся.

Автогейт приёмки и `approve` на acceptance (требование 2) уже идут через
`acceptance.acceptance_suite` — правка не нужна, AC-1/AC-2 зелёны с рождения.
`notes.py` (прогон без задачи) не меняется (требование 4, AC-11).

Обращение к `acceptance._own`/`acceptance._task_own_profile` из других
модулей — закрытые имена: правка `orchestrator/acceptance.py` вне зоны
задачи («Не входит»), а заводить второй источник профиля противоречит
названию задачи. См. «Предложения системе».

## Шаги
1. Передача профиля у всех вызывающих требования 1 (9 файлов
   `orchestrator/`), юнит-тест `--failed` у `pytest-own`
   (`tests/test_suite_run.py::FailedIdsByProfileTest`), регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 — гейт мержа `fsm_merge_gate.py` (`:965`, `:967` через `_full_suite_command`) | 1 |
| 1 — рубеж `in_dev` `advance_gates/acceptance.py` (прогон и `_seed_repeats_escalate`) | 1 |
| 1 — `suite_run.py` (прогон ветки, базы, ключ итога `:511`/`:533`) | 1 |
| 1 — `plank_run.py:187` | 1 |
| 1 — `amend.py` `_collect_and_run` и `_amend_plank_only` (с `cwd=wt_path` у `pytest-own`) | 1 |
| 1 — `pull.py:664-666` | 1 |
| 1 — `fsm_advance.py:594` + `tests_writing._tests_writing_dry_collect_gate` | 1 |
| 1 — `test_integrity.py` наблюдение и гейт (`two_sided.run`) | 1 |
| 2 — автогейт и `approve` через `acceptance_suite` | без правки (часть 2) |
| 3 — логика гейтов и `suite_run` не меняется | 1 (только передача профиля) |
| 4 — без задачи / артель / `pult-pytest` — прежнее | 1 (ветви `None`/список) |
| 5 — `preflight`, `acceptance-dry-run` не правятся | не трогаются |

Проверка: `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py` — 26
passed (AC-1 — AC-12); тесты затронутых модулей последовательно
(`test_suite_run`, `test_01m462q…_suite_run`, `…suite_run_appendix`,
`…base_reuse`, `…plank_run`, `test_plank_run_edges`, `…pytest_own_places`,
`test_pytest_own_result_ids`, `test_amend*`, `…amend_pult`, `…pull_main`,
`test_pull_main_unavailable`, `…seed_repeats`,
`test_fsm_advance_tests_writing_dry_collect`, `…merge_gate`,
`…two_sided_observation`, `test_test_integrity_gate`, `…declared_change`,
`test_long_lived_transitions`, `test_project_profile_gates`) — 320 passed.
Полный набор — `artel.py suite-run` №1: зелёный, прошло 5580, упало 0,
пропущено 2. Новый тест покраснел на мутации «у `pytest-own` id идут целями» и
позеленел после возврата кода.

## Влияние на систему
- Затронуты только аргументы вызовов мест запуска; логика гейтов (порядок,
  отказы, журнал), `suite_run` (замок, отчёт, сравнение с базой) и места
  запуска части 2 не меняются.
- Путь артели и `pult-pytest`: везде либо прежний список
  `list(profile.command)`, либо вызов прежней формы без нового
  аргумента — argv, `cwd` и окружение совпадают с main (AC-10 —
  оба метода зелёные, и долгоживущие тесты прошлых задач с ассертами
  на argv/kwargs вызовов не правились). Тесты, ассерты, гейты не
  ослаблялись; существующие тестовые методы не менялись, добавлен один.
- `_profile_command` у `pytest-own` теперь может отказать текстом «профиль
  не прочитан», если значения профиля не собираются в `Profile` — на
  практике недостижимо (`repo_context.profile_of` отдаёт `PRESENT` только
  проверенному профилю), у `pult-pytest` `Profile` не строится вовсе.
- Откат — revert одного merge-коммита задачи.

## Риски
- Закрытые имена `acceptance._own`/`_task_own_profile` в чужих модулях:
  переименование их в `acceptance.py` сломает вызывающих (поймают тесты
  этой задачи, AC-1 — AC-12).

## Предложения системе
- `orchestrator/acceptance.py`: `_own` и `_task_own_profile` стали общим
  источником профиля для 7 модулей — стоит сделать их публичными
  (`own_profile`, `task_own_profile`) отдельной задачей; эта задача правку
  `acceptance.py` исключала.
- `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`: помощник
  песочницы `tests_dir` начинается с `test` — pytest собирает его как тест
  в каждом классе (DeprecationWarning «return a value that is not None»);
  класс «помощник песочницы с именем `test*`» стоит ловить guard'ом/скилом
  test-authoring.
- Сторож роли (`conftest.py`) отказывает `-n … -p xdist` даже на явном
  перечне файлов — адресный прогон ~20 файлов затронутых модулей шёл
  последовательно ~12 минут тремя вызовами.
