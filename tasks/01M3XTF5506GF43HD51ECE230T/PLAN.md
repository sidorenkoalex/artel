---
task: 01M3XTF5506GF43HD51ECE230T
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Признак «процесс — шаг роли» не снимается ролью, и команды Оператора отказывают вызову из-под роли

## Подход
Один признак — `runner.in_role_environment`: непустой `ARTEL_ROLE` либо
`HOME`, равный `config.ROLE_HOME` после `os.path.abspath` (снимает
завершающую черту; пустой `HOME` — не роль, иначе `abspath("")` дал бы
текущий каталог). Пара `HOME`+`CLAUDE_CONFIG_DIR` остаётся достаточной:
её `HOME` совпадает с домом роли.

Диспетчер `artel.py` переведён с перечня запрещённых команд на белый
список, закрытый по умолчанию (`_role_allowed_command`): читающие команды
целиком (`_ROLE_ALLOWED_COMMANDS`), команды с флагом, меняющим состояние
(`_ROLE_REFUSED_FLAGS`: `doctor --fix/--restore`, `prune --execute`,
`watch --observation`), составные с единственной читающей подкомандой
(`observe show`, `hook-migrate inspect`), `run`/`auto` — только с
`--attach`. Всё прочее, включая будущие записи таблицы и неизвестные
имена, под ролью отказывает до разбора таблицы. `_refuse_if_role_restricted`
спрашивает `runner.in_role_environment()`; текст отказа называет роль либо
«(окружение роли)». Реализации `fsm`/`auto`/`catalog` не тронуты — прямые
вызовы пультом не останавливаются.

## Шаги
1. `orchestrator/runner.py` — `in_role_environment` + `_is_role_home`.
2. `orchestrator/artel.py` — белый список и отказ через единый признак.
3. Тесты, зовущие `artel.main()` с командами списка отказа
   (`tests/test_analyst_role.py` — `new`, `tests/test_approve_acceptance_full_suite.py`
   — `approve`, `tests/test_kill_live_cycle_refusal.py` — `kill`), снимают
   `ARTEL_ROLE` и `HOME` из окружения вызова (`mock.patch.dict(..., clear=True)`).
   Ассерты не тронуты, методы не удалены. Прочие вызыватели
   (`test_doc_commit.py`, `test_artel_role_restricted_commands.py`,
   `test_observation_edges.py`, файлы 01M3SX69) зелёные под ролью без правки:
   песочница подменяет `config.ROLE_HOME`, а `ARTEL_ROLE` они выставляют/снимают сами.
4. `docs/stack.md`, «Паритет безопасности роли»: проза и строка «Отказ
   команд пульта из-под роли» — признак отсекает ошибочный вызов, обходится
   сменой `HOME` и `ARTEL_ROLE`, граница — песочница клиента и гейты после
   шага; перечень того, что реально запрещает `permissions.deny`.
5. Карта кодовой базы регенерирована тем же коммитом (28e4d254).
6. По ANSWER-2 (вариант А, зона расширена на `orchestrator/doctor/isolation.py`):
   `isolation_smoke` (Claude) и `_codex_environment_leaks` (Codex) проверяют
   непустой `config.ARTEL_ROLE_ENV` в собранном окружении напрямую, отдельно
   от признака роли; при пустом — красная строка «окружение шага роли не
   распознаётся как окружение роли: нет маркера роли ARTEL_ROLE». Тест
   `tests/test_providers_codex.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_codex_env_is_red`
   не тронут и снова зелёный. Симметричный сторож Claude —
   `tests/test_doctor.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_env_is_red`.
   Коммит 3ff0f528 (карта регенерирована).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 (ветка маркера — `bool(...)`, без изменений) |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 (отказ только в диспетчере), 6 (`isolation-smoke`/`codex-isolation-smoke` зелёные и по-прежнему ловят пропажу маркера) |
| 8 | 4 |
| 9 | долгоживущий `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py` (test_author) |
| 10 | 3 |

Прогоны (в шаге, сам шаг идёт под `ARTEL_ROLE=developer`):
- `tests/test_analyst_role.py tests/test_approve_acceptance_full_suite.py tests/test_kill_live_cycle_refusal.py tests/test_stack_parity_table.py tests/test_stack_codex_section.py tests/test_stack_zones_pull_section.py tests/test_stack.py tasks/01M3XTF5506GF43HD51ECE230T/acceptance_tests` — 102 passed, 29 subtests (планка AC-3/AC-8/AC-9 зелёная).
- `tests/test_answer.py tests/test_canary.py tests/test_doc_commit.py tests/test_notes.py tests/test_notes_apply.py tests/test_doctor.py tests/test_providers_codex.py tests/test_artel_role_restricted_commands.py tests/test_observation_edges.py tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_detached_cycle.py tests/test_new_argv_parsing.py tests/test_conftest_role_guard.py tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py tests/test_runner_role_environment.py` — 480 passed, 1 failed (`test_providers_codex.py::...::test_missing_role_marker_in_assembled_codex_env_is_red`) до шага 6.
- После шага 6: `tests/test_doctor.py tests/test_providers_codex.py tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py tasks/01M3XTF5506GF43HD51ECE230T/acceptance_tests` — 219 passed, 215 subtests, красных нет.
- Мутация нового сторожа `test_doctor.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_env_is_red`: прямая проверка маркера в `isolation_smoke` выключена — тест красный; код возвращён.
- `tests/test_invariants.py tests/test_multitarget.py tests/test_providers.py tests/test_provider_scoped_step_env.py` — 155 passed.
- Мутация заявки изменённого метода `test_analyst_role.py::ArtelCliTzFlagTest::test_cli_new_with_dangling_tz_flag_exits_cleanly`: снята проверка длины в `artel._tz_arg` — тест красный; код возвращён.

## Влияние на систему
- Признак стал шире (HOME без `CLAUDE_CONFIG_DIR`): внутренние отказы
  `answer.py`/`notes.py`/`pool_seal.py` и смоки `doctor`, зовущие тот же
  признак, срабатывают и в окружении с HOME дома роли без маркера. Их тесты
  зелёные; смоки `doctor` проверяют маркер напрямую (шаг 6), поэтому
  расширение признака не гасит их сторожевую функцию.
- Отказ диспетчера стал закрытым по умолчанию: новая команда таблицы под
  ролью отказывает, пока её не внесут в белый список (`note`, `doc-commit`
  теперь отказывают уже в диспетчере — по требованию 5).
- `conftest.py` не тронут (по-прежнему читает только `ARTEL_ROLE`).
- Откат — revert коммитов 3ff0f528 и 28e4d254.

## Риски
- Шаг роли, у которого `HOME` = дом роли, а `ARTEL_ROLE` снят, теперь
  получает отказ на `note`/`doc-commit` и прочие команды — это цель задачи,
  но если какая-то роль звала их штатно, она начнёт отказывать (по скилам
  такого вызова нет).

## Расширение зон
Мандат Оператора — ANSWER-2.md («Расширение зон разрешено:
orchestrator/doctor/isolation.py»): прямая проверка маркера `ARTEL_ROLE`
в смоках изоляции Claude и Codex (шаг 6).

Пути: orchestrator/doctor/isolation.py

## Предложения системе
- Смок `codex-isolation-smoke` (`orchestrator/doctor/isolation.py:298`)
  проверяет наличие маркера через признак роли, а не напрямую — любое
  расширение признака молча гасит его сторожевую функцию (пойман этой
  задачей); проверку «маркер поставлен» стоит держать отдельной строкой.

