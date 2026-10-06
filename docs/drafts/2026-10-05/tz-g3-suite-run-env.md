# ТЗ: suite-run роли выполняется в окружении пульта, а не роли

Порядок: после группы 3 (этап 3 ADR-0021, части 2 и 3) и после
01M46D5T8SZ9D6S34TZFX8S46V (один полный прогон на машину).

Источник: 05.10, задача 01M46D5ZZQY7GBEW5TBVQ0P3ZV, первый suite-run роли
после мержа 01M462QACEH29RPRD2RZHGHQFM. Тест
`tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
красный в suite-run (ветка и база — по 1 failed) и зелёный на гейтах
пульта и в CI. Причина: PATH роли (`orchestrator/runner.py::
_role_path_dirs`) — только каталоги объявленных инструментов
(`.artel/venv/bin`, pyenv, `/usr/bin`, `/opt/homebrew/bin`), без `/bin`;
на macOS `ps` лежит в `/bin`, `liveness._group_member_count` получает
`OSError` и по замыслу возвращает 0. Воспроизведено: `env PATH=<PATH роли>
python3 -m pytest <тест>` — 1 failed. Отчёт suite-run верно отнёс падение к
«падают и на базе», но роль потратила ещё два прогона на перепроверку.
Решение Оператора 05.10: сделать после группы 3, приоритет 3.

Факты (пин dff5a425, сверка кода 05.10):
- `orchestrator/suite_run.py::cmd_suite_run` (~602-) запускает фоновый
  прогон `subprocess.Popen(..., start_new_session=True)` с окружением
  вызывающего процесса без признака роли (`config.ARTEL_ROLE_ENV`), то есть
  с PATH и переменными роли (`runner.role_env`, белый список манифеста).
- Гейты пульта (автогейт приёмки `orchestrator/fsm_autogate.py`, approve в
  acceptance `orchestrator/fsm.py::_acceptance_full_suite_ok`, гейт мержа
  `orchestrator/fsm_merge_gate.py`) гоняют полный набор
  `acceptance.run_full_suite` из процесса пульта — в его окружении.
- Цикл `auto` (процесс пульта) на время шага роли ждёт процесс агента
  (`runner.spawn_agent`, ~74) и живёт всё время шага.
- Docstring модуля suite_run обещает прогон «без признака роли в
  окружении»; по PATH и переменным это обещание не выполняется.

Требуется:
1. Полный прогон `suite-run` (ветка, база, `--failed`) выполняется
   процессом пульта в окружении пульта — тем же, в котором гоняют полный
   набор гейты пульта; команда роли только ставит запрос и, как сегодня,
   сразу возвращается, а отчёт роль забирает `--wait`. Способ передачи
   запроса и кто его исполняет (цикл `auto` задачи, отдельный исполнитель
   пульта) — решение SPEC. Окружение роли в прогон не попадает ни
   переменными, ни PATH.
2. Нет живого процесса пульта, способного исполнить запрос (цикл задачи не
   идёт), — команда отказывает именованно, а не запускает прогон в
   окружении роли (fail-closed).
3. Поведение suite-run для роли не меняется: те же форма отчёта, группы
   «новые на ветке» / «падают и на базе», `--wait`, `--failed`, замок
   одного полного прогона на машину (01M46D5T8SZ9D6S34TZFX8S46V).
4. В инструкции ролей (skills/coding-standards.md, раздел о полном
   прогоне) — строка: падения группы «падают и на базе» не разбирать и не
   чинить, только упомянуть в отчёте. skills/ — защищённый путь: правка
   идёт приложением PLAN (применяет Оператор на гейте мержа).
5. Итог прогона ветки suite-run (в окружении пульта) записывается тем же
   ключом, что итоги гейтов (строка бэклога «Повторное использование итога
   полного прогона на гейтах», черновик docs/drafts/2026-10-05/
   tz-k6-suite-reuse.md), и гейты могут использовать его повторно, если
   дерево не менялось (ревьювер код не правил).
6. Тесты в `tests/` с заявками «Ловит мутацию»: прогон suite-run видит
   PATH и переменные окружения пульта, а не роли (например, каталог, есть
   в PATH пульта и нет в PATH роли, виден прогону); без живого процесса
   пульта — именованный отказ без прогона; отчёт и группы не изменились.
   Существующие тесты не ослабляются.

Зоны: orchestrator/ (orchestrator/suite_run.py, orchestrator/auto.py или
модуль исполнителя, orchestrator/runner.py — только при необходимости),
tests/, docs/codebase-map.md; skills/coding-standards.md — только
приложением PLAN.

Только чтение (не менять): conftest.py, tests/test_invariants.py,
tests/test_liveness.py, orchestrator/liveness.py, docs/invariants.md,
docs/adr/, docs/roadmap.md, docs/backlog.md, docs/operator-session.md,
templates/, CLAUDE.md, models.yaml, roles.yaml, targets.yaml,
.github/workflows/ci.yml.

Не входит: изменение PATH роли (`_role_path_dirs`) и белого списка
окружения роли; правка теста liveness; прогоны роли напрямую pytest (вне
suite-run).

Рамка: $40.
