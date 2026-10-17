---
task: 01M52EEHSRD93WMPHWB5VJYRKD
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/; в) пути-признаки (гейты): orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm_advance.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py; д) ТЗ ссылается на ADR: ADR-0023."
spec_sha: c1f992105c7662a09da6e0fdc872753f614444b2
schema_version: 5
---

# SPEC-AUDIT: D0-3: один источник профиля у вызывающих прогон

## ТЗ и SPEC
ANSWER-n.md у задачи нет. В брифе есть решение Оператора на гейте SPEC №1
(17.10.2026), шесть пунктов. Сверил, как каждый внесён в SPEC:
1. Прогон планки `in_dev -> verifying` и повторы seed вошли в требование 1
   (SPEC.md:~44-48) и в новый AC-12 (SPEC.md:121-125). Внесено.
2. `amend.py:715-718`: `cwd=wt_path` и отсчёт `workdir` от рабочей копии
   только у `pytest-own`, у `pult-pytest` поведение прежнее — требование 1
   (SPEC.md:~52-58) и AC-6 (SPEC.md:95-99). Внесено.
3. Каждая из двух точек в AC-3, AC-6, AC-7, AC-8, у AC-3 вместе с условием
   «после применённого приложения» (SPEC.md:82-108). Внесено.
4. Ключ итога `suite-run` в AC-4 (SPEC.md:87-90). Внесено.
5. Канал `profile` у `run_plank` и `two_sided.run`, а в точках, где сегодня
   ничего не передаётся, — профиль. Это есть в «Контексте» и в требовании 1.
   Внесено.
6. `pult-pytest` у внешних проектов — «поведение прежнее (команда пульта)»:
   требование 4 (SPEC.md:69-71), AC-10 (SPEC.md:113-115), «Не входит»
   (SPEC.md:157-159). Внесено дословно, но скобка «команда пульта»
   расходится с кодом — см. «Факты против кода» и отклонение 1.

ТЗ → SPEC: перечень вызывающих, `acceptance_suite`, «только передача
профиля», прогоны без задачи, `preflight`/`acceptance-dry-run`, «Не входит»
(`acceptance.py`, `two_sided.py`, sled), рамка $40 и `merge_after` по строке
«Порядок: после части 2» — всё перенесено. Сверх ТЗ добавлены только
пункты из решения Оператора (AC-12, `cwd=wt_path`, `pult-pytest`). Других
лишних требований нет.

## Факты против кода
Рабочий каталог — ветка задачи на `d2806c69` (main с вмёржённой частью 2).
Подтвердилось:
- `fsm_merge_gate.py:962-967`: `full_suite` в двух ветвях `fresh_suite`.
  `_full_suite_command` возвращает `None` для артели и
  `list(decision.profile.command)` для внешнего проекта
  (`fsm_merge_gate.py:816-820`).
- `advance_gates/acceptance.py:169`: `run_repeat(..., command=command)`.
  `:387-405`: `command = list(decision.profile.command)` (`:393`), затем
  `acceptance.run` в двух ветвях (`:399-402`); `command` уходит в
  `_seed_repeats_escalate` (`:425-426`).
- `suite_run.py:511`: ключ `suite_result_key(tree, command, base=True)`;
  `:533`: `save_suite_result`. Команда — список из `_profile_command`
  (`:268-283`) с проверкой `_is_pytest`. Тот же `command` уходит в прогон
  базы (`:524-526`) и в основной прогон (`:565-566`).
- `plank_run.py:187`: `run_plank([target_arg], code_dir)` без профиля.
- `amend.py:545`, `:549`: `collect`/`run` с `cwd` без `command`. `:715`,
  `:718`: `collect(tdir)`/`run(tdir)` без `cwd`, то есть с `config.ROOT`, где
  `tdir = wt_path/tasks/<id>` (`amend.py:695`).
- `pull.py:664`, `:666`: `run(tdir, cwd=wt_path[, extra])` без `command`.
- `fsm_advance.py:594-596`: `list(profile.command)` → `_tests_writing_dry_collect_gate`.
  `advance_gates/tests_writing.py:557`: `{"command": list(command)}`.
  `list(Profile)` упадёт, так что эту строку придётся менять (она в зонах).
- `test_integrity.py:1429` (наблюдение) и `:1527` (гейт): `two_sided.run`
  без `profile`. Сигнатура — `two_sided.py:319-320` (`profile=None`),
  `run_plank` — `acceptance.py:1096-1097`.
- `notes.py:1040`: `run_full_suite(work_dir, **_suite_limit_kwargs())`.
- `acceptance_suite` берёт профиль сам (`acceptance.py:2098-2126`). AC-1 и
  AC-2 на main уже выполнены частью 2, их тесты будут зелёными с рождения
  и стерегут регресс.

Не подтвердилось:
- Требование 4 (SPEC.md:69-71), AC-10 (SPEC.md:115) и «Не входит»
  (SPEC.md:158-159) называют сегодняшнее поведение внешнего проекта с
  `runner: pult-pytest` «командой пульта». В половине мест это не так:
  гейт мержа (`fsm_merge_gate.py:819-820`), `suite-run`
  (`suite_run.py:277-283`), прогон планки в `in_dev`
  (`advance_gates/acceptance.py:393`) и сухой сбор `tests_writing`
  (`fsm_advance.py:594`) сегодня запускают внешний проект **командой
  профиля** (`_head`, `acceptance.py:126-131` → `_pytest_command`
  `:60-63`). Командой пульта они идут только в `pull`, `amend`,
  `plank-run` и двустороннем прогоне. Это поведение закрепляет тест
  `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:456`
  (`test_ac9_external_profile_runs_profile_command_red_refuses_merge`): в нём
  мутация «прогон идёт командой пульта, а не командой профиля» названа
  ловимой. Отклонение 1.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да (зелёный с рождения) | `acceptance_suite` не передаёт `_task_own_profile` → argv с `-p timeout`, `cwd` = корень, окружение пульта. Тест должен уводить приёмку в локальный прогон: при принятом итоге CI (`acceptance.py:2087-2094`) pytest не запускается |
| AC-2 | да (зелёный с рождения) | то же для `fsm.py:1294` |
| AC-3 | да | профиль передан только в одной ветви `fresh_suite` (`fsm_merge_gate.py:965`/`:967`); `_full_suite_command` оставлен со списком → нет `workdir`, окружение пульта |
| AC-4 | да | прогон с профилем, а ключ базы `:511` считается по списку → ключ `suite-run` расходится с ключом гейта (`acceptance.py:2041`); `_profile_command` по-прежнему отдаёт список |
| AC-5 | да | `run_plank` без `profile` → `cwd` = `code_dir`, окружение пульта |
| AC-6 | да | профиль только в одной из точек `:545-549`/`:715-718`; в `:715-718` профиль передан, но без `cwd=wt_path` → `workdir` отсчитан от `config.ROOT` |
| AC-7 | да | профиль только в одной ветви `pull.py:664`/`:666` |
| AC-8 | да | профиль только у одного вызывающего `test_integrity.py:1429`/`:1527` |
| AC-9 | да | `fsm_advance.py:594` по-прежнему `list(profile.command)` → `collect` без `workdir` |
| AC-10 | да, с оговоркой | `cwd=wt_path` в `amend.py:715-718` добавлен безусловно → у артели сменился `cwd`. Безусловная передача `Profile` в `pull`/`amend`/`plank-run`/`two_sided` у внешнего `pult-pytest` меняет argv с команды пульта на команду профиля. Тест увидит это, только если команда профиля в нём **отличается** от `python3 -m pytest`: у артели команда `[python3, -m, pytest]` (`targets.yaml:46`), а `_pytest_command` подменяет `python3` интерпретатором venv (`acceptance.py:62-63`), поэтому на артели такая мутация невидима. Отклонение 2 |
| AC-11 | да | в `notes.py:1040` добавлен профиль → argv/`cwd` расходятся с main |
| AC-12 | да | `advance_gates/acceptance.py:393` оставлен списком, или профиль передан в `run`, но не в `_seed_repeats_escalate` (`:169`, `:425-426`) |

## Зоны
Все места, которые меняют требования, в зонах есть: `advance_gates/acceptance.py`
(AC-12), `advance_gates/tests_writing.py:557` (`list(command)` придётся
менять), `fsm_merge_gate.py`, `suite_run.py`, `plank_run.py`, `amend.py`,
`pull.py`, `fsm_advance.py`, `test_integrity.py`, `tests/`. Защищённые пути
(`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не
затронуты, песочница ролей не расширяется. `fsm.py`, `fsm_autogate.py` и
`notes.py` правки не требуют (требования 2 и 4). Эти зоны задал Оператор в
ТЗ, отклонением не считаю.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Раннер мест запуска у `pytest-own` (все точки требования 1) | Таймаут отдельного теста `-p timeout -o timeout=…` — `orchestrator/acceptance.py:64-66` | у артели и `pult-pytest` да; у `pytest-own` его заменяет снятие группы процессов | общий предел прогона (`ACCEPTANCE_TIMEOUT_SEC`, предел полного набора профиля); ADR-0023, вторая поправка | решено ADR, не ослабление |
| Полный набор гейта мержа и `suite-run` у `pytest-own` | Параллель `-n … -p xdist` — `acceptance.py:1320-1327` | у артели да; у `pytest-own` по профилю (часть 2) | ADR-0023; AC-3, AC-4 | решено ADR |
| Красный полный прогон после приложений → отказ мержа | `fsm_merge_gate.py:968-1000`; `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:456` | да (требование 3) | тот же тест; AC-3 | сохранить |
| Внешний `pult-pytest` в гейте мержа идёт командой профиля | `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:456` | да при чтении «как на main» (AC-10); нет при буквальном «команда пульта» (требование 4, SPEC.md:71) | тот же тест | отклонение 1 |
| Ключ итога полного набора | `acceptance.suite_result_key` / ключ `pytest-own` (часть 2) | да | AC-4 | сохранить |
| Прогон планки `in_dev -> verifying` и повторы seed | `advance_gates/acceptance.py:387-405`, `:169` | да, у `pytest-own` строже (по профилю) | AC-12 | сохранить |
| argv, `cwd` и окружение артели во всех местах | `_pytest_command`/`_pytest_env` — `acceptance.py:36-91` | да | AC-10, AC-11 | сохранить |

Раздела «Меняемое поведение» в SPEC нет, и он не нужен. Тестов, которые
закрепляли бы канал списком через `assert_called_with`/`call_args`, в
`tests/` нет (grep по `command=`, `profile=`, `call_args`). Моки
`suite_run._profile_command` (`tests/test_suite_run.py:243`, `:380`) и
`fsm_merge_gate._full_suite_command` (`tests/test_worktree_db_files.py:94`)
подменяют возврат функции. Они остаются валидными, если сигнатуры этих
помощников сохранятся.

## Пути обхода гейтов
- Буквальное исполнение требования 4 и AC-10 «(команда пульта)» для внешнего
  `pult-pytest` позволяет перевести гейт мержа, `suite-run`, планку `in_dev`
  и сухой сбор на команду пульта. Тогда внешний проект в гейте мержа
  проверяется не своей командой, а это ослабление гейта, закреплённое
  тестом `test_merge_gate.py:456`. Сам тест такую правку отклонит, и
  исполнитель окажется между SPEC и тестом. Отклонение 1.
- Безусловная передача профиля в `pull.py:664-666`, `amend.py`,
  `plank_run.py:187` и `test_integrity.py:1429/:1527` меняет argv внешнего
  `pult-pytest` с команды пульта на команду профиля. Это нарушение AC-10,
  а тест на AC-10 поймает его, только если команда профиля в тесте
  отличается от `python3 -m pytest`. Отклонение 2.
- Других путей не нашёл: каждая точка требования 1 названа в своём AC, у
  двухточечных критериев — обе точки.

## Вердикт
`concerns`: все шесть пунктов решения Оператора внесены, адреса требования 1
сверены с кодом. Осталось два отклонения, оба решаются на гейте без
возврата аналитику.

1. Требование 4 (SPEC.md:69-71), AC-10 (SPEC.md:113-115) и «Не входит»
   (SPEC.md:157-159) называют сегодняшнее поведение внешнего проекта с
   `runner: pult-pytest` «командой пульта». В гейте мержа
   (`orchestrator/fsm_merge_gate.py:819-820`), `suite-run`
   (`orchestrator/suite_run.py:277-283`), планке `in_dev`
   (`orchestrator/advance_gates/acceptance.py:393`) и сухом сборе
   `tests_writing` (`orchestrator/fsm_advance.py:594`) это сегодня команда
   **профиля**, и тест закрепляет её:
   `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:456`. Предлагаю
   считать главным «не изменились относительно main» (AC-10), а скобку
   «команда пульта» — верной только для `pull`, `amend`, `plank-run` и
   двустороннего прогона.
2. AC-10 (SPEC.md:113-115): мутацию «`Profile` передаётся безусловно» в
   `pull`, `amend`, `plank-run` и двустороннем прогоне ловит только тест,
   где у внешнего `pult-pytest` команда профиля отличается от
   `python3 -m pytest`. На артели такая мутация невидима: её профиль —
   `[python3, -m, pytest]` (`targets.yaml:46`), а `python3` подменяется
   (`orchestrator/acceptance.py:62-63`). Это указание автору тестов, не
   правка SPEC.
