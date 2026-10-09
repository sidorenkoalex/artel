---
task: 01M4FZ6QYPPKYQZFEX14QH8XT6
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Запуск без привязки к чату

## Фаза A — план
- Таблица покрытия полна: требования 1–7 разложены по шагам 1–5, у каждого
  требования есть шаг с кодом и тестом.
- Шаги размера MR (store → artel → cycle_hint/doctor → тесты → docs), без
  микроопераций.
- Подход не трогает пути «только чтение» (schema.py, watch.py, runner.py,
  auto.py, lease.py и др.) — по diff --stat подтверждено. Имя
  `store.matching_observation` сохранено (его подменяет
  `test_ac6_detached_launch_spawns_attach_child`). Откат описан (revert).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_cycle_args` разбирает `--observation`; `_launch_observation` (artel.py): названное — только оно, без отката; без флага — `matching_observation` с `ORDER BY last_seen_at DESC, created_at DESC, rowid DESC`. Гейт свежести (`OBSERVATION_STALE_SECONDS`) общий для выбранного и названного. |
| 2 | OK | Пара не участвует в SQL выбора; `_refuse_malformed_pair` сохраняет отказ на неполную/кривую пару у `run`/`auto` и `observe register`; пара пишется в журнал шагов записью «отвязанный запуск» (`client=…, chat=…`). |
| 3 | OK | `observe register` без пары пишет `""`; schema.py не тронута; наблюдения с парой выбираются (AC-8 долгоживущего теста). |
| 4 | OK | `launch_hint` строит строку через `cycle_command(cmd, id, observation_id)`; `_observation_args` возвращает `(ID,)`/`()`, `stale_cycle_lines` разворачивает `*observation_args` в `cycle_command` (doctor/stale_cycles.py:166). Шаги `observe add`/`observe register` + `watch` сохранены. grep по orchestrator/ — `--client` в подсказках не печатается. |
| 5 | OK | Отказы: не найдено / чужая сессия или проект / не активно (с состоянием) / задачи нет в наборе / связи с watch ещё нет / связь устарела на N с (порог) — каждый с ID и `watch --observation <ID>` либо `observe register`/`observe add`; пару ни один не предлагает. |
| 6 | OK | Все проверки наблюдения до `lease.is_live` и `Popen`; lease и `tasks.state` до отвязки не трогаются (AC-10 долгоживущего теста). |
| 7 | OK | operator-session.md: порядок без пары, новый шаг 5 про `observe events`/`acknowledge` из любого чата, таблица отказов под требование 5, ссылки «шаг 3 подраздела «Порядок»» вместо номеров строк; stack.md — фраза о контракте. |

## Замечания
Блокирующих и major нет. Наблюдения без требования правки (вкус):
- `tests/test_observation_edges.py::test_two_chats_cannot_be_chosen_implicitly_for_one_task`
  — имя метода больше не соответствует проверяемому свойству (теперь
  запуск идёт в свежее наблюдение), но смена ожиданий объявлена в SPEC
  «Меняемое поведение» и покрыта ANSWER-1; переименование увело бы метод
  из-под мандата — оставить как есть.
- `--observation` при `--attach` молча игнорируется (`_cycle_args`); SPEC
  этого не регулирует, вреда нет.

Сверка изменённых утверждений `tests/` с base: 12 методов из ANSWER-1 и 3
объявленных в SPEC (без смены нормальной формы утверждений) — каждое
«было → стало» совпадает со строкой SPEC; проверка пары заменена
проверкой ID наблюдения той же строгости (в
`test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not` —
`assertNotIn(stale_observation_id)` вместо клиента/чата прежнего запуска).
Сужения данных под неизменными утверждениями не найдено: в
`test_ac8_launch_requires_matching_client_and_chat` все семь контекстов
сохранены, разнесены на `launched`/`refused` ровно по SPEC.
Новый `tests/test_launch_observation_refusals.py` не повторяет долгоживущие
файлы задачи: проверяет тексты отказов названного наблюдения (не
перебираемые долгоживущими) и отсутствие `client=`/`chat=` в записи аудита
без пары; заявки «Ловит мутацию» у всех трёх методов называют наблюдаемое
расхождение.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4FZ6QYPPKYQZFEX14QH8XT6`
  — `test_ac11_documentation.py`: 1 passed, код выхода 0.
- `python3 -m pytest -q tests/test_01m4fz6qyppkyqzfex14qh8xt6_hint.py tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py tests/test_launch_observation_refusals.py tests/test_observation_edges.py tests/test_cycle_hint.py tests/test_pin_update_stale_cycles.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py tests/test_detached_cycle.py`
  — 97 passed, 215 subtests passed (35.6 с).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расхождение только в строке `built_at_sha`, карта по содержимому свежая
  (изменение отменено `git checkout`).
- `grep -rn -- "--client\|--chat" orchestrator/ docs/operator-session.md docs/stack.md`
  — пара осталась только в usage (как необязательная), в разборе флагов,
  в `hook-migrate` и `observe acknowledge` (вне задачи); в подсказках и
  строке перезапуска её нет.
- Временную мутацию сторожей (`artel.py` — снять проверку «не активно»;
  `store.py` — тай-брейк `rowid ASC`) выполнить не удалось: правка файла
  через `sed -i` в шаге отклонена правами. Чувствительность оценена по
  тексту тестов: `test_named_observation_states_are_named_with_next_step`
  ждёт `SystemExit` с «не активно» для остановленного наблюдения,
  `test_ac4_freshest_then_latest_created_observation_is_chosen` в случае
  «равно» ждёт запуск только в позднее созданное.

## Предложения системе
- `review-checklist` требует проверять сторожей временной мутацией, но
  в шаге ревью правка рабочего каталога через Bash (`sed -i`) требует
  подтверждения, которого никто не даст — приём фактически недоступен;
  стоит дать пульту команду вида `artel.py mutate-run <id> <файл> <патч>`
  по образцу `plank-run`.
