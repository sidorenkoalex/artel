---
task: 01M28NX0M2WTVC38XVN75N01XD
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: kill при живом цикле — отказ с подсказкой stop, ликвидация только с --yes

## Подход

`kill` уже снимает снимок держателя lease ДО `run_locked(force=True)`
(`cleanup.cmd_kill`, комментарий про SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P,
AC-10) — этот снимок (`holder_before`) и есть точка, где нужно решить
«живой цикл или нет» ДО того, как `force=True` перезапишет строку lease
своим pid. Признаки «живой» — те, что называет SPEC: держатель на этом
host (иначе pid не проверяем), pid адресуем (`liveness._pid_alive`),
heartbeat не протух (`liveness._age_seconds` <= `config.
LEASE_STALE_AFTER_SEC`) — три отдельные проверки, уже существующие по
одной в `doctor.check_leases` (host+pid) и `lease.is_live`/`acquire`
(heartbeat); здесь они впервые собираются в одну функцию
`cleanup._live_cycle_holder(row)`, а не переиспользуют `lease.
foreign_live_lease` — та лишняя (исключает lease СВОЕЙ сессии, что тут
не нужно: kill проверяет живость держателя независимо от того, чья это
сессия) и её семантика «foreign» пришлось бы обходить лишним
аргументом.

Без `--yes` и живом держателе — `sys.exit` текстом AC-1 ДО вызова
`lease.run_locked`: так гарантированно ничего не меняется (ни lease, ни
state, ни branch/worktree) — `run_locked(force=True)` внутри `acquire()`
уже переписал бы строку lease на свой pid, если бы дошёл до вызова.
Роль/шаг в тексте отказа — `runner.step_role(t)` (уже читает
`config.STATE_ROLE` без обращения к git для агентских состояний,
которых касается сценарий), время — `heartbeat_ts` снимка (единственная
метка времени, которую несёт строка `leases`).

С `--yes` при живом держателе — отдельная запись журнала ДО
`run_locked`, дальше `_cmd_kill` идёт прежним путём без изменений (AC-2
требует байт-в-байт прежнее полное поведение). Без `--yes` и без живого
держателя (нет lease или он не живой по одному из трёх признаков) —
путь не меняется вовсе (AC-3): `_live_cycle_holder` возвращает `False`,
guard не срабатывает.

Обнаружен конфликт при первом прогоне: `tests/test_detached_cycle.py::
KillSignalsDetachedHolderTest` (файл защищён требованием 6/AC-7, править
нельзя) сеет ЖИВОЙ lease (свежий heartbeat, свой pid, этот host) на
голом `spec_writing`-состоянии (`TmpRepoTest`, `TZ.md` не заведён) и
зовёт `cmd_kill` БЕЗ `--yes`, ожидая прежний полный kill — ровно
сценарий, который AC-1 требует отказывать. Развязка — вторая часть
признака «живой цикл», `cleanup._live_cycle_role(conn, task_id, row)`:
lease живой (`_live_cycle_holder`) ЕЩЁ не значит «цикл жив» в смысле
SPEC — SPEC называет сценарий «живой ОТВЯЗАННЫЙ ЦИКЛ (`auto`/`run`)», а
`auto`/`run` берут lease только вокруг реального шага роли
(`runner.step_role(t) is not None`); синтетический lease на состоянии
без роли (как в защищённом тесте) циклом не является — `_live_cycle_
role` возвращает `None`, guard не срабатывает, старый путь сохраняется
байт-в-байт. Сама приёмка AC-1/AC-2 не задевается: её сценарий форсирует
`in_dev` (роль `developer`) — `_live_cycle_role` там возвращает роль, не
`None`. Отдельный плюс: без роли тексту отказа («шаг <роль> с <время>»)
и нечего было бы называть.

`--yes` разбирается в `orchestrator/artel.py` (диспетчер `"kill"`) —
`rest[1:]` после task_id, без отдельного парсера аргументов (нет других
флагов у `kill` сегодня); прокидывается `cleanup.cmd_kill` новым
keyword-only параметром `confirmed: bool = False`, чтобы не менять
позиционную сигнатуру для трёх вызывателей `canary.py` и теста
`test_invariants.py`, которые продолжают звать без него.

Подсказки «дальше:» (AC-4/AC-5) — правка констант `config.AUTO_STOP`
(четыре ключа: `spec_gate`, `acceptance`, `merge_gate`, `escalated`) и
`config.AUTO_STOP_ZONE_WAIT` — дописывают ту же литеральную фразу SPEC
рядом с существующей командой, через уже подставляемый `{id}` (авто
уже форматирует хинт `.format(id=task_id, sha=sha_hint)` в
`auto.auto_stop_advice`/на месте для zone-wait) — саму механику
форматирования не трогаем. `AUTO_STOP_BUDGET` не входит: requirement 5
называет ровно четыре состояния, эскалация по бюджету —
самостоятельная подсказка (`config.AUTO_STOP_BUDGET`), приёмочный
AC-5 явно её не тестирует.

`docs/operator-session.md` — абзац «stop против kill» рядом с уже
существующим описанием `stop <id>` в разделе «Запуски и рабочие
копии» (там же лежит инцидент zones-extend по духу — рядом с описанием
поведения `stop`, не отдельным новым разделом).

## Шаги

1. `orchestrator/cleanup.py` + `orchestrator/artel.py`: `_live_cycle_
   holder`, `_live_cycle_role`, `_refuse_live_cycle`,
   `KILL_REFUSAL_JOURNAL_ACTION`/`KILL_CONFIRM_JOURNAL_ACTION`,
   `cmd_kill(..., confirmed=False)`, диспетчер `"kill"` читает `--yes`
   из `rest[1:]`. Закрывает требования 1-3, AC-1..AC-3.
2. `orchestrator/config.py`: дописать литеральную фразу в
   `AUTO_STOP["spec_gate"/"acceptance"/"merge_gate"/"escalated"][1]` и
   `AUTO_STOP_ZONE_WAIT[1]`. Закрывает требование 4, AC-4/AC-5.
3. `docs/operator-session.md`: абзац «stop против kill» — назначение
   команд, последствия, флаг `--yes`, ссылка на инцидент 11.09. Закрывает
   требование 5, AC-6.
4. Юнит-тесты: новый файл `tests/test_kill_live_cycle_refusal.py` —
   `cleanup._live_cycle_holder` по трём признакам отдельно (чужой host,
   мёртвый pid, протухший heartbeat, все три живы), `_live_cycle_role`
   отдельно (роль есть/нет на текущем состоянии) и то, что `artel.py
   main` доносит `--yes` до `cleanup.cmd_kill` как `confirmed=True`
   (не трогает `tests/test_kill_cleanup.py`/`tests/
   test_detached_cycle.py` — требование 6/AC-7, только добавление
   нового файла).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 3 |
| 6 | 1, 2 (не правит существующие утверждения) |

## Влияние на систему

- `cleanup.cmd_kill` получает новый keyword-only параметр
  `confirmed: bool = False` — три существующих вызова из
  `orchestrator/canary.py` и один из `tests/test_invariants.py` не
  передают его и продолжают звать без изменений (AC-3 — то же
  поведение, что раньше, если лиза не живая; канарейка обычно убивает
  задачу без живого держателя, а если держатель живой — новый отказ
  тоже уместен для неё, отдельного исключения SPEC для канарейки не
  просит).
- Guard-проверка «живой цикл» встаёт МЕЖДУ снимком `holder_before` и
  `lease.run_locked(force=True)` — сам `run_locked`/`force=True`
  не трогается, поведение AC-2/AC-3 (полный kill) остаётся тем же
  вызовом с тем же `force=True`, что и раньше.
- Правка `config.AUTO_STOP`/`AUTO_STOP_ZONE_WAIT` — только дописывает
  строки хинтов; ключи, `{id}`/`{sha}`-подстановка и код,
  форматирующий их (`auto.auto_stop_advice`, `auto._run_zone_wait_
  refusal` и её окружение) не трогаются — существующие тесты, сверяющие
  хинты по подстроке (`test_auto_cycle.py`), не ломаются, потому что
  проверяют вхождение старой подстроки, не равенство целой строке
  (перепроверено чтением этих тестов перед правкой).
- `docs/operator-session.md` — добавление абзаца, без правки соседних.
- Тесты `tests/test_kill_cleanup.py`/`tests/test_detached_cycle.py` не
  редактируются вовсе (требование 6/AC-7) — новый файл юнит-тестов
  отдельно.
- Откат: все три файла кода (`cleanup.py`, `artel.py`, `config.py`) и
  документ возвращаются к текущему состоянию `git revert` этого
  коммита; новый тестовый файл удаляется тем же коммитом.

## Риски

- Текст отказа AC-1 — точная регулярная сверка (`assertRegex` в
  приёмочном тесте): любое отклонение в пунктуации/порядке слов красит
  тест. Собран буквально из SPEC AC-1 построчно, сверено с
  `test_ac1_refuses_with_named_text_naming_stop_and_kill_yes` перед
  реализацией.

## Предложения системе
