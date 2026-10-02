---
task: 01M3XTF5506GF43HD51ECE230T
type: plan
author_role: developer
status: escalate
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

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 (ветка маркера — `bool(...)`, без изменений) |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 (отказ только в диспетчере); `isolation-smoke`/`codex-isolation-smoke` зелёные, см. «Эскалация» |
| 8 | 4 |
| 9 | долгоживущий `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py` (test_author) |
| 10 | 3 |

Прогоны (в шаге, сам шаг идёт под `ARTEL_ROLE=developer`):
- `tests/test_analyst_role.py tests/test_approve_acceptance_full_suite.py tests/test_kill_live_cycle_refusal.py tests/test_stack_parity_table.py tests/test_stack_codex_section.py tests/test_stack_zones_pull_section.py tests/test_stack.py tasks/01M3XTF5506GF43HD51ECE230T/acceptance_tests` — 102 passed, 29 subtests (планка AC-3/AC-8/AC-9 зелёная).
- `tests/test_answer.py tests/test_canary.py tests/test_doc_commit.py tests/test_notes.py tests/test_notes_apply.py tests/test_doctor.py tests/test_providers_codex.py tests/test_artel_role_restricted_commands.py tests/test_observation_edges.py tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_detached_cycle.py tests/test_new_argv_parsing.py tests/test_conftest_role_guard.py tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py tests/test_runner_role_environment.py` — 480 passed, **1 failed** (`tests/test_providers_codex.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_codex_env_is_red`, см. «Эскалация»).
- `tests/test_invariants.py tests/test_multitarget.py tests/test_providers.py tests/test_provider_scoped_step_env.py` — 155 passed.
- Мутация заявки изменённого метода `test_analyst_role.py::ArtelCliTzFlagTest::test_cli_new_with_dangling_tz_flag_exits_cleanly`: снята проверка длины в `artel._tz_arg` — тест красный; код возвращён.

## Влияние на систему
- Признак стал шире (HOME без `CLAUDE_CONFIG_DIR`): внутренние отказы
  `answer.py`/`notes.py`/`pool_seal.py` и смоки `doctor`, зовущие тот же
  признак, срабатывают и в окружении с HOME дома роли без маркера. Их тесты
  зелёные; единственное следствие, ломающее существующий тест, — в «Эскалации».
- Отказ диспетчера стал закрытым по умолчанию: новая команда таблицы под
  ролью отказывает, пока её не внесут в белый список (`note`, `doc-commit`
  теперь отказывают уже в диспетчере — по требованию 5).
- `conftest.py` не тронут (по-прежнему читает только `ARTEL_ROLE`).
- Откат — revert коммита 28e4d254.

## Риски
- Шаг роли, у которого `HOME` = дом роли, а `ARTEL_ROLE` снят, теперь
  получает отказ на `note`/`doc-commit` и прочие команды — это цель задачи,
  но если какая-то роль звала их штатно, она начнёт отказывать (по скилам
  такого вызова нет).

## Предложения системе
- Смок `codex-isolation-smoke` (`orchestrator/doctor/isolation.py:298`)
  проверяет наличие маркера через признак роли, а не напрямую — любое
  расширение признака молча гасит его сторожевую функцию (пойман этой
  задачей); проверку «маркер поставлен» стоит держать отдельной строкой.

## Эскалация

**Вопросы**

1. (блокирует сдачу) `tests/test_providers_codex.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_codex_env_is_red`
   требует, чтобы `doctor.codex_isolation_smoke` краснел, когда `runner.role_env`
   перестал ставить `ARTEL_ROLE` шагу Codex. Смок проверяет это вызовом
   `runner.in_role_environment(step_env)` (`orchestrator/doctor/isolation.py:298`),
   а по требованию 2 / AC-2 SPEC окружение Codex со снятым маркером теперь
   распознаётся ролью по `HOME` — смок зелёный, тест красный. Это прямое
   противоречие SPEC и существующего теста; `orchestrator/doctor/` по SPEC
   только для чтения, ослаблять тест мне нельзя. Варианты:
   - **А (дефолт)** — `zones-extend` на `orchestrator/doctor/isolation.py`:
     смок Codex дополнительно проверяет напрямую, что
     `config.ARTEL_ROLE_ENV` в собранном окружении непуст (строка
     «окружение шага роли не распознаётся как окружение роли» при
     отсутствии маркера). Тест остаётся без правки и снова зелёный, его
     свойство («`role_env` ставит маркер шагу Codex») сохранено. Правка —
     2-3 строки; то же стоит сделать и в `isolation_smoke` Claude
     (`isolation.py:94`) ради симметрии.
   - **Б** — `amend`/мандат на правку теста: метод сохраняет имя и
     проверяет то же свойство напрямую (`runner.role_env` для Codex несёт
     непустой `ARTEL_ROLE`), без участия смока. Минус — смок `doctor`
     перестаёт ловить пропажу маркера.
   - **В** — принять, что маркер у Codex больше не обязателен (признак по
     HOME его покрывает), и удалить метод. Не рекомендую: маркер остаётся
     единственным основанием для `conftest.py` и для текста отказа с именем роли.

**Контекст**
Весь остальной объём SPEC реализован и закоммичен (28e4d254): признак,
белый список диспетчера, правка трёх тестов-вызывателей, `docs/stack.md`,
карта. Планка задачи (долгоживущий файл + `acceptance_tests/`) зелёная.
Красный только один названный метод.

**Блокирует**
Сдачу `ready`: с красным методом CI ветки и гейт `in_dev -> review` не
пройдут. При ответе А — правка `isolation.py` в этой же ветке и `ready`.
