---
task: 01M2B6JWGS9HMR9XZJBASXVNSY
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: lease: живой держатель своей сессии не переписывается

Источник: копилка docs/backlog.md, строка П2 от 12.09 «Команда своей
сессии переписывает pid живого lease цикла» (коммит 41c821ae); решение
Оператора 12.09 об отказе от хука клиента `.claude/hooks/guard-artel-bg.py`
в пользу отказа пульта.

Факты:
- `lease.acquire` (orchestrator/lease.py:95–167), ветка «своя сессия»
  (строки 115–117): при совпадении `session_id` строка lease
  перезаписывается pid ТЕКУЩЕГО процесса без проверки, жив ли прежний
  держатель. 12.09 13:00:56Z `budget 01M2ARQD7C` из той же сессии, что и
  работающий `auto` (pid 21120, под ним агент developer pgid 35482),
  записала pid самой команды budget (35909), который тут же завершился:
  `status` показал «[lease: ppid-15998 мёртв]» у живого цикла
  (`catalog._lease_holder_suffix`, orchestrator/catalog.py:343–362,
  проверяет только `liveness._pid_alive(row["pid"])`), а команда ДРУГОЙ
  сессии того же host перехватила бы lease немедленно как «pid держателя
  мёртв» (SPEC 01M290PS, без ожидания LEASE_STALE_AFTER_SEC=7200) и
  запустила бы вторую роль поверх работающей.
- Тот же путь у любой команды своей сессии под `run_locked`: `run`/`auto`
  повторно из той же сессии (двойной запуск роли — инцидент T043 27.08,
  сегодня закрыт только хуком клиента модели `.claude/hooks/
  guard-artel-bg.py`, который планируется снять: отвязка от конкретной
  LLM), `answer`, `amend-tests`, `zones-extend`, `budget`.
- Вызыватели `lease.run_locked`/`acquire`: runner.py:154 (run), auto.py:521
  и 129 (auto, продление в ожидании зоны — тот же процесс), fsm.py:478/
  655/862 (advance/approve/reject), budget.py:354 (`same_host_ok=True`),
  answer.py:97/170, amend.py:75/79, cleanup.py:236 (kill, `force=True`),
  workspace.py:134.
- Живость: `liveness._pid_alive(pid)`, `liveness._group_member_count(pgid)`
  (orchestrator/liveness.py:38, 53); в строке lease есть `pgid` группы
  агента (`store.update_lease_pgid`).

Требуется:
1. `lease.acquire`, ветка «своя сессия»: если pid держателя жив
   (`liveness._pid_alive`) и это НЕ текущий процесс — строка lease НЕ
   переписывается. Для вызывателя с `same_host_ok=True` (`budget`)
   возврат «не отказ, не свежий» без мутации (потолок меняется под живым
   шагом, как и задумано SPEC 01M1VBEDGM); для остальных — именованный
   отказ «[<id>] задачу прямо сейчас ведёт процесс <pid> этой же сессии
   (<действие держателя, если известно>) — дождись завершения шага либо
   artel.py stop <id>» (тот же класс отказа, что «задачу ведёт сессия …»
   для чужой сессии). `force=True` (kill) — прежний перехват.
   Продление своим же процессом (pid совпадает) — прежнее поведение.
2. Отказ п.1 закрывает двойной запуск `run`/`auto` из одной сессии на
   уровне пульта: второй `auto`/`run` при живом первом отказывает до
   запуска роли. Хук клиента `.claude/hooks/guard-artel-bg.py` после этого
   лишний — в «Предложения системе» PLAN: снять хук решением Оператора
   (файл вне зон задачи).
3. `catalog._lease_holder_suffix`: «жив/мёртв» по pid держателя И по
   pgid агента (`_group_member_count(pgid) > 0`): живой агент при
   мёртвом pid держателя — «жив (агент pgid N)», чтобы status не
   называл живой цикл мёртвым.
4. Тесты в tests/test_lease*.py и tests/test_catalog*.py (по образцу
   существующих, живость — через `mock.patch.object(liveness, …)`):
   (а) своя сессия, держатель жив, другой pid, `same_host_ok=False` —
   отказ с названным pid, строка lease не изменилась (мутация «pid
   переписан» — красный); (б) то же с `same_host_ok=True` — без отказа,
   строка не изменилась; (в) держатель мёртв — прежняя перезапись;
   (г) свой pid — прежнее продление; (д) status: pid мёртв, pgid жив —
   «жив»; (е) существующие тесты lease/budget/catalog — без ослабления.

Зоны: orchestrator/lease.py, orchestrator/catalog.py,
orchestrator/liveness.py, tests/.

Приложением: orchestrator/budget.py (`cmd_budget`, `mid_step`),
orchestrator/auto.py (`_wait_for_zone`, продление lease тем же
процессом), .claude/hooks/guard-artel-bg.py (хук клиента — снимается
Оператором), docs/backlog.md (строка П2 12.09), журнал 01M2ARQD7C
13:00:56Z.

Не входит: правка budget.py, auto.py, runner.py, cleanup.py; снятие хука;
изменение LEASE_STALE_AFTER_SEC и перехвата чужой сессии.

Рамка: $30.
