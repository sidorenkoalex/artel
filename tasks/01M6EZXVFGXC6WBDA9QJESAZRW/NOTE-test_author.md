# Записка test_author — 01M6EZXVFGXC6WBDA9QJESAZRW

## Выяснено
- Планка готова, preflight пройден по всем пунктам. Все AC-1…AC-20 покрыты тестами, без пометок.
- Файлы планки (Группа: разовый): test_merge_gate_fail_closed.py (AC-1,2,3,6,13,17,18,19,20),
  test_push_point_fail_closed.py (AC-4,5,7,8,9,10,11,12,17), test_mr_sync_sign_a.py (AC-14),
  test_gate_literals_unchanged.py (AC-16). Долгоживущий: tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py (AC-15).
- Почему почти всё разовое: guard долгоживущих (scripts/guard.py:4111-4367) запрещает импорт
  orchestrator.gitcmd и закрытые имена, а швы SPEC (читатель people_entry, возврат
  _cmd_approve_merge_gate, чтение в _awaiting_limit_refuses, _push_plan) — закрытые.
- Читатель people_entry ищется по people_entry.__code__.co_names: функция модуля github_adapter,
  которую больше никто в модуле не зовёт. Имя разработчик выбирает сам; две такие функции — тест упадёт.
- Шов AC-6: обёртка targets.target бросает, только если в стеке есть _awaiting_limit_refuses.
- Сбой БД: первый вызов store.project_tasks (in_repo), store.last_task_step_of (max_in_flight),
  store.db (in_flight_refusal). Код предела AC-12 — любая ПРОПИСНАЯ int-константа gitcmd, ≠ коду «гейт неизвестен».
- Тело гейта зовётся дважды: ("wait", ветка) и повтор; BodySpy смотрит последний заход.
- На main: 27 красных / 15 зелёных (сторожа AC-4, 5 артель, 8, 10 непрочит., 11, 12 код предела, 14, 16, 17).
  Со стабом (откачен, git status чист кроме долгоживущего файла) — 42/42 и 3/3 зелёные.
  Мутация AC-14 (if True в mr_sync.py:356) краснит; AC-16 ловит новое сравнение, если оно в закоммиченном диффе.

## Не сработало
- grep с `$` в регэкспе и составные команды требуют подтверждения — по одной команде.
- changed_paths() не видит незакоммиченные правки отслеживаемых файлов — мутацию AC-16 проверял отдельным вызовом.

## Где остановился
- Шаг завершён: планка и долгоживущий файл написаны, preflight пройден.

## Чего не хватило
- Имени функции-читателя записи people_entry в SPEC (требование 1) — шов пришлось искать по коду.
