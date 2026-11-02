---
task: 01M6EZXVFGXC6WBDA9QJESAZRW
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: GitLab Б2.3-1: отказ при сбое вместо пропуска

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–13 сопоставлены шагам 1–4.
- Шаги размера MR: по модулю (github_adapter+fsm_merge_gate, gitcmd, ci/targets, тесты).
- Подход согласован с SPEC: шов `_people_entry_record`, отказ через `_people_refusal`,
  код `IN_FLIGHT_REFUSAL`, ленивый реестр в `targets`. «Влияние на систему» совпадает
  с diff: тронуты только файлы зон, `tests_writing.py`, `repo_context.py`, `forge.py`,
  `mr_sync.py` не менялись. Откат — revert merge-коммита.
- Пробел плана, тот же, что в R1-F1: шаг 4 заявляет «долгоживущие свойства, не
  покрытые файлом лока», но требования 1, 5, 6, 7 в `tests/` не доведены.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `github_adapter.py` `_people_entry_record` + `people_entry` (артель — `None` без чтения); `fsm_merge_gate.py:1519-1525` ловит `TargetsError` → `_people_refusal(PEOPLE_REFUSED_ACTION, "запись проекта не прочитана: …")`, `("stopped",)`. Планка AC-1/2/18 зелёная. Сторожа в `tests/` нет — R1-F1 |
| 2 | OK | `gitcmd._destination_project`: при `entries is None` сетевой адрес, не совпадающий с `remote.origin.url` корня, получает проект `url_key(dest)` → «гейт мержа неизвестен — targets.yaml не читается». Имя remote (`origin`) идёт как локальный путь (`_local_dest_path`) — артель как прежде; scp-адрес распознаётся `_is_url` |
| 3 | OK | `_awaiting_limit_refuses` — отказ `AWAITING_UNCHECKED_DETAIL: запись проекта не прочитана: …`, `True` → `("stopped",)` (`fsm_merge_gate.py:1640`) |
| 4 | OK | `in_flight_refusal`: `sqlite3.Error` в `task_target` — отказ для всех; `TargetsError`/`sqlite3.Error` дальше — отказ вне артели, `None` у артели. Тексты без `IN_FLIGHT_LIMIT_REASON` |
| 5 | OK | `_push_plan`: `sqlite3.Error` при счёте предела вне артели — `_refuse(...)`. Сторожа в `tests/` нет — R1-F1 |
| 6 | OK | `in_repo` больше не глотает `sqlite3.Error`; `_awaiting_human_refusal` ловит его в `_project_tasks` и отказывает вне артели (`_refuse` сам глотает сбой журнала). Сторожа в `tests/` нет — R1-F1 |
| 7 | OK | `IN_FLIGHT_REFUSAL = 75`, `plan.code` передаётся во все `_refused` (git, carpentry, read, read_env, read_stream); `ensure_draft_mr` сверяет `returncode`. Проводка кода в `tests/` не проверена — R1-F1 |
| 8 | OK | ветка `else` в `_mr_incident_stops` — отказ `MR_REFUSED_ACTION`, `True` |
| 9 | OK | `test_mr_sync_opened_mr_sha_in_base_is_not_sign_a`; код `mr_sync.py` не тронут |
| 10 | OK | строка в `ci.py` удалена, `targets._hosting_registry()` импортирует `forge` при вызове; остатков `hosting_registry` в orchestrator/tests нет (grep) |
| 11 | OK | новых сравнений `forge`/`merge_gate` с литералом нет; сравнения только с `config.DEFAULT_TARGET`; планка AC-16 зелёная |
| 12 | OK | планка подменяет шов в названных точках; сверка «состояние не изменилось» — в планке |
| 13 | OK | `ensure_forge_draft_mr` возвращает `"запись проекта не прочитана: …"`, `open_forge_mr` не зван (тест в `tests/`) |

Смена входа заглушки `tests/test_mr_delivery_units.py:156` (код `1` → `IN_FLIGHT_REFUSAL`) прямо названа в SPEC «Материалы»; утверждения `assert_not_called` не тронуты — не ослабление.

## Замечания

- major — `tests/test_fail_closed_on_read_failure.py` (нет тестов для мест ниже) — четыре
  свойства, которые должны держаться и после мержа, сторожит только планка. Проверено
  временными мутациями; при каждой `tests/` зелёные (103 passed), а планка краснеет:
  1. `orchestrator/fsm_merge_gate.py:1521` — `except targets.TargetsError` подменён на
     `except ZeroDivisionError` (место вызова `people_entry` не ловит сбой, требование 1);
  2. `orchestrator/gitcmd.py:1023` — убрано `plan.code = IN_FLIGHT_REFUSAL` (отказ
     пределом из `git()`/`in_repo` снова с кодом 1, требование 7; тест
     `test_in_flight_refusal_code_is_distinct` проверяет только константы и умолчания);
  3. `orchestrator/gitcmd.py:1016` — `if project != config.DEFAULT_TARGET` → `if False`
     (`sqlite3.Error` в счёте `max_in_flight` снова пропускает, требование 5);
  4. `orchestrator/gitcmd.py:905` — `if project == config.DEFAULT_TARGET` → `if True`
     (`sqlite3.Error` в `in_repo` снова пропускает внешний проект, требование 6).

  Чем грозит: после мержа планку не гоняет ни CI, ни автогейт (ADR-0018 п. 3). Регрессия
  любого из четырёх мест снова откроет обход — путь слияния в `base` или отправку мимо
  предела при сбое, — и CI останется зелёным. Что сделать: добавить в `tests/` по тесту
  на каждое место, с заявкой «Ловит мутацию: …» под мутацию из списка: (1) `approve`/
  `_cmd_approve_merge_gate` задачи внешнего проекта при подменённом
  `_people_entry_record` даёт `("stopped",)` и запись `PEOPLE_REFUSED_ACTION`; (2) отказ
  пределом через `gitcmd.git(...push...)` или `in_repo` возвращает
  `returncode == IN_FLIGHT_REFUSAL`; (3) `sqlite3.Error` из `_in_flight_refusal` внутри
  `_push_plan` для внешнего проекта — отказ, `git push` не зван; (4) `sqlite3.Error` из
  `_project_tasks` в `in_repo` для внешнего проекта — отказ, у артели — нет. Свойства
  AC-1/AC-9/AC-10/AC-12 в `tests/` сейчас не повторены, так что дубля долгоживущего
  файла лока не будет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_fail_closed_on_read_failure.py; места: orchestrator/fsm_merge_gate.py:1521, orchestrator/gitcmd.py:1023, :1016, :905 | долгоживущие свойства требований 1, 5, 6, 7 сторожит только планка: четыре временные мутации — `tests/` зелёные | после мержа регрессия снова откроет слияние/отправку при сбое чтения, CI не заметит (ADR-0018 п. 3) | по тесту в `tests/` на каждое место, с «Ловит мутацию: …» под мутацию из «Замечаний» |

## Вердикт
changes_requested: закрыть R1-F1 — добавить четыре сторожа в `tests/`. Код по SPEC
корректен, правок кода не требуется.

## Проверено исполнением
- `artel.py plank-run 01M6EZXVFGXC6WBDA9QJESAZRW`: 42 passed, код выхода 0.
- `python3 -m pytest tests/test_fail_closed_on_read_failure.py tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py tests/test_mr_delivery_units.py -p no:cacheprovider -q`: 29 passed, 8 subtests.
- Временные мутации A–D (см. R1-F1), каждая по отдельности, на файлах `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py`,
  `test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`, `test_01m5xz9z68v75vxf5z66c708t4_delivery_policy.py`,
  `test_awaiting_human_units.py`, `test_fail_closed_on_read_failure.py`, `test_mr_delivery_units.py`: A — 103 passed;
  B — 74 passed (без двух файлов); C+D вместе — 103 passed. Все четыре вместе на планке: 8 failed
  (AC-1, AC-2, AC-9×2, AC-10×2, AC-12×2). Код возвращён `git checkout -- orchestrator/`, `git status` чистый.
- Чтение кода (вне пакета, ради п. 2, 6, 8): `gitcmd._is_url`/`_local_dest_path`/`url_key` (scp-адрес и имя
  remote при непрочитанной записи), `_refuse` (глотает `sqlite3.Error` журнала — у артели в `in_repo` нового
  исключения нет), `fsm_merge_gate._mr_incident_stops` целиком (`else` относится к цепочке состояний).

## Предложения системе
- Шаг 4 PLAN («долгоживущие свойства, не покрытые файлом лока») ревьюер проверяет только временными
  мутациями. Помогла бы опись разработчика в PLAN «AC → тест в `tests/` или файл лока»: пробел был бы виден
  на гейте плана.
