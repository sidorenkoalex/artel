# Записка developer — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- Возврат из verifying (CI 40365146908) закрыт: литерал ("killed","done") в gitcmd заменён `_dead_states()` -> `fsm.TERMINAL_STATES` (отложенный импорт, цикл fsm<->gitcmd); SQL из `catalog.branch_refusal` -> новая `store.project_branch_tasks` (мандат ANSWER-2); SQL в gitcmd `_project_tasks`/`_last_sent_sha` -> `store.project_tasks`/`store.last_task_step_of` (сторож SqlOnlyInStore находил и их).
- Планка AC-6..AC-9 — 75 passed; долгоживущие AC-1..AC-5 + сторожа + push_point + А0 — 115 passed; соседние модули — 160 passed.
- Устройство: ветка — `catalog.branch_template/branch_name/_branch_ref_key/branch_refusal/division_branches`; точка отправки — `gitcmd._push_plan` во всех пяти точках; белый список — `_whitelist_refusal`; предикат `targets.push_whitelisted`.

## Не сработало
- `pytest -n 4` в рабочей копии роняет воркеры — гонял последовательно.

## Где остановился
- Шаг завершён: PLAN.md status: ready, карта регенерирована.

## Чего не хватило
- Сторожа `test_multitarget.py::SqlOnlyInStoreTest` и литерала окончательных состояний не входят в «тесты затронутых модулей» по имени — стоит гонять их при любой правке orchestrator/.
