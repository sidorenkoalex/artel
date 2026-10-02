---
task: 01M3XTF5506GF43HD51ECE230T
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Признак «процесс — шаг роли» не снимается ролью, и команды Оператора отказывают вызову из-под роли

## Фаза A — план
- Таблица покрытия PLAN.md полна: требования 1–10 привязаны к шагам. Требование 9 закрыто долгоживущим файлом test_author. Требование 7 закрыто шагами 2 и 6.
- Шаги имеют размер MR. Отказ стоит только в диспетчере, реализации `fsm`/`auto`/`catalog` не тронуты — это совпадает с архитектурой из SPEC.
- Расширение зоны на `orchestrator/doctor/isolation.py` санкционировано ANSWER-1/ANSWER-2 (тексты совпадают), и правка не выходит за п.3 ответа: других изменений в `orchestrator/doctor/` в diff нет.
- «Влияние на систему» совпадает с diff (8 файлов + карта). Путь отката — revert 28e4d254 и 3ff0f528.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel.py::_refuse_if_role_restricted` зовёт `runner.in_role_environment()`. Без маркера текст отказа — «роли (окружение роли)», с маркером в тексте имя роли. |
| 2 | OK | `runner._is_role_home`: `os.path.abspath` с обеих сторон снимает завершающую черту, пустой HOME — не роль. `CLAUDE_CONFIG_DIR` не участвует. Пара HOME+CCD остаётся достаточной, потому что её HOME — дом роли. |
| 3 | OK | Ветка маркера осталась `bool(env.get(...))`. Случай `{"HOME": "/tmp/operator", "ARTEL_ROLE": ""}` даёт ложь. Файл 01M3SE87 не тронут и зелёный. |
| 4 | OK | Белый список закрыт по умолчанию: всё, чего в нём нет, отказывает до разбора таблицы (`artel.py:1338`, до `table`). Флаги `doctor --fix/--restore`, `prune --execute`, `watch --observation` сверены с разбором (`artel.py:1364,1373`, `watch._flag_value`): все проверяют точное вхождение токена, обхода формой `--flag=value` нет. |
| 5 | OK | `_ROLE_ALLOWED_COMMANDS` + `_ROLE_REFUSED_FLAGS` + `_ROLE_ALLOWED_SUBCOMMANDS`. `note` и `doc-commit` теперь отказывают в диспетчере. Неизвестное имя под ролью получает отказ роли. |
| 6 | OK | `run`/`auto` с `--attach` разрешены. В `_launch_detached` отказа нет. |
| 7 | OK | Отказ стоит только в диспетчере. Смоки `isolation-smoke`/`codex-isolation-smoke` по ANSWER-2 напрямую проверяют маркер. Ветка `elif not in_role_environment(...)` после проверки маркера фактически недостижима: при непустом маркере признак истинен. Вреда нет, это не замечание. |
| 8 | OK | Проза и строка таблицы не подают признак как границу. Перечень `permissions.deny` сверен с `docs/reference/role-home/claude/settings.json` и точен (init, doctor --restore, git clone, gh repo clone, git remote add, openssl enc -d, security find-generic-password, Read ~/.artel-canary/**). Ни одна ячейка не равна голому «да». `test_stack_parity_table.py` зелёный. Мелочь без последствий: фраза «Оба офлайн-смока изоляции проверяют признак» не упоминает, что маркер теперь проверяется отдельно. |
| 9 | OK | `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py` покрывает AC-1, 2, 4, 5, 6, 7 (+AC-3). |
| 10 | OK | В трёх файлах снят `ARTEL_ROLE` и `HOME` через `mock.patch.dict(..., clear=True)`, ассерты не изменены. Остальных вызывателей `artel.main()` я перебрал grep'ом: `test_doc_commit`, `test_artel_role_restricted_commands`, `test_observation_edges`, 01M3SX69, `test_01m3xtfjcc…_launch_hint` (пришёл подтяжкой main, сам ставит `ARTEL_ROLE=""`, а песочница подменяет `ROLE_HOME`), `test_models`, `test_detached_cycle`, `test_answer_mandate`, `test_artel_bootstrap`. Все они зелёные под окружением роли (см. ниже). |

Тесты: в diff `tests/` удалённых и ослабленных ассертов нет, только обёртка окружения и докстринги. Новый `test_doctor.py::test_missing_role_marker_in_assembled_env_is_red` несёт заявку «Ловит мутацию»; его мутацию автор проверил (PLAN). Изменённый метод `test_analyst_role.py` получил заявку. Сторожа Codex я проверил временной мутацией сам (ниже). Защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) в diff нет.

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- Pytest под окружением роли главной копии (`ARTEL_ROLE=developer`, `HOME=/Users/al.sidorenko/projects/artel/.artel/home`, выставлены в `os.environ` перед `pytest.main`) на файлах: `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`, `test_analyst_role.py`, `test_approve_acceptance_full_suite.py`, `test_kill_live_cycle_refusal.py`, `test_artel_role_restricted_commands.py`, `test_doc_commit.py`, `test_observation_edges.py`, `test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `test_01m3sx69e8p64d77j1xthmhe40_migration.py`, `test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, `test_models.py`, `test_detached_cycle.py`, `test_answer_mandate.py`, `test_artel_bootstrap.py`, `test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `test_runner_role_environment.py`, `test_doctor.py`, `test_providers_codex.py`, `test_stack_parity_table.py`, `test_invariants.py` и на планке `tasks/01M3XTF5506GF43HD51ECE230T/acceptance_tests`. Итог: **498 passed, 537 subtests passed**, 195 с.
- Временная мутация: в `orchestrator/doctor/isolation.py::_codex_environment_leaks` прямую проверку маркера заменил на `if False:`. После этого `tests/test_providers_codex.py::IsolationSmokeTest::test_missing_role_marker_in_assembled_codex_env_is_red` **FAILED**. Код возвращён `git checkout`, дерево чистое.
- `python3 scripts/codebase_map.py`: diff `docs/codebase-map.md` без строки `built_at_sha` пуст, карта свежая. Файл возвращён.
- Сверка `docs/reference/role-home/claude/settings.json` с перечнем deny в `docs/stack.md` совпала.
- CI коммита 05fc5f45 зелёный (14 проверок, по пакету).

## Предложения системе
- `conftest.py::pytest_configure` читает `sys.argv`. Поэтому запуск `python3 -c "...pytest.main([...])"` под ролью сторож считает полным прогоном, если не подменить `sys.argv`. Ревьюверу, которому нужно прогнать тесты с явным `ARTEL_ROLE`/`HOME`, префикс `VAR=… pytest` недоступен (требует подтверждения), и он упирается в это. Стоит описать в review-checklist штатный приём прогона «под окружением роли» для критериев вида AC-9.
