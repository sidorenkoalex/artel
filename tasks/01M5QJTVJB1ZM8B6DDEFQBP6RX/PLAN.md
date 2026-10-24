---
task: 01M5QJTVJB1ZM8B6DDEFQBP6RX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 3м-1 — тесты замка и очереди мержа в файлы модулей pytest

## Подход

Свод механический, ожидания переносятся дословно, доказательство — один
набор из 38 патчей `mutation-001.diff` … `mutation-038.diff`, прогнанный
«до» на трёх исходных файлах базы и «после» на двух файлах модулей.

- Патчи меняют только `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`,
  `orchestrator/store.py`; каждый собран правкой во временной копии
  репозитория в `$TMPDIR` и `git diff` (пути `a/orchestrator/…`), применимость
  к дереву ветки — `git apply --check` (все 38 — код 0). Каждый патч
  перед прогоном `mutation-run` проверен одиночным прогоном трёх исходных
  файлов в той же копии: убийца падает утверждением в теле теста.
- Патчи 1-15 — вне пути взятия окна (часть 15 патчей), 16-38 — патчи
  функций `acquire`, `_holder_is_dead`, `_is_own_process`, `run_window`,
  `wait_for_window`, `_head_task_id`, `_prune_dead_entries` (части 16-23,
  24-31, 32-38 — по 8, 8 и 7 патчей). Классификацию сверил функциями
  планки (`_plan.patch_old_lines` + `enclosing_functions`).
- Без зависаний: единственный тест с настоящей паузой —
  `WaitForWindowTest::test_free_mutex_registers_then_immediately_takes_the_window`
  (90 с на опрос). Ни один патч пути окна не мешает ему взять свободное
  окно: свой процесс не признаётся мёртвым (`_holder_is_dead` ломается
  только в сторону «живой» либо «чужой host мёртв»), свободная строка
  берётся, своя запись — голова. Таймаутов pytest-timeout в логах нет.
- Мутация `ConcurrentAcquireTest` (решение 4 ANSWER-1) — `acquire` без
  проверки занятости строки (`if True:`): все восемь потоков побеждают
  при любом порядке, детерминированно.
- pytest 9.1.1 сам разворачивает `subTest` исходных файлов: упавший
  подслучай — отдельная запись отчёта с тем же узлом
  `<файл>::<Класс>::<метод>`; в функции модуля набор — прежний цикл, тест
  останавливается на первом упавшем подслучае тем же утверждением.
- Стенды — фикстуры поверх `tmp_root` с телами `setUp` дословно и хвостом
  `return tmp_root`; помощники — функции модуля (перечень ниже); `self.` →
  параметр стенда, атрибуты классов → константы модуля.
- Дублей не удаляю: у каждого из 40 тестов своя заявка, 21 из них
  получил её в этой задаче (решение 3 ANSWER-1).

## Шаги

1. Патчи `mutation-001.diff` … `mutation-038.diff`, по одному на заявку
   (одинаковые по смыслу заявки — одна мутация со списком тестов).
2. Таблица «до»: `mutation-run --ref base` частями 1-15, 16-23, 24-31, 32-38
   (прогоны №1–№4), каждая часть перенесена в PLAN до старта следующей.
3. Свод: `tests/test_merge_lock_module.py` (новый), `tests/test_merge_queue.py`
   (переписан на месте), удаление `tests/test_merge_lock.py` и
   `tests/test_merge_lock_by_project.py`, `python3 scripts/codebase_map.py`;
   коммит 7c0bc906.
4. Таблица «после»: `mutation-run --ref worktree` теми же частями (прогоны
   №5–№8), перед каждой — пустой `git status --porcelain -- orchestrator/`.
5. Строки падения из логов патчей (`.artel/logs/suite-run/01M5QJTVJB1ZM8B6DDEFQBP6RX/01M5QJTVJB1ZM8B6DDEFQBP6RX-mutation-run-<n>-p<nnn>.log`,
   последняя ссылка `tests/<файл>.py:<строка>` раздела FAILURES узла).

## Мутации (сопоставление заявкам)

Заявка каждого из 40 исходных тестов — патч набора; 19 прежних заявок
воплощены дословно, 21 новая записана в докстринг функции модуля.

- mutation-001 — ProcessOwnershipTest::test_release_from_non_holder_process_keeps_the_mutex, ProcessOwnershipTest::test_store_release_merge_lock_requires_both_session_and_pid — `store.release_merge_lock` удаляет строку по одному `session_id` (pid выпал из `WHERE`)
- mutation-002 — AcquireReleaseTest::test_release_removes_only_the_matching_session, ProcessOwnershipTest::test_store_release_merge_lock_requires_both_session_and_pid — `store.release_merge_lock` удаляет строку по одному `pid` (`session_id` выпал из `WHERE`)
- mutation-003 — ProcessOwnershipTest::test_release_from_holder_process_removes_the_mutex — `merge_lock.release` передаёт `os.getppid()` вместо pid вызывающего процесса
- mutation-004 — CurrentHolderIdTest::test_no_holder_degrades_to_placeholder — `_current_holder_id` без держателя отдаёт пустую строку вместо «?»
- mutation-005 — CurrentHolderIdTest::test_names_the_holder_task — `_current_holder_id` отдаёт `session_id` строки вместо `task_id`
- mutation-006 — CurrentHolderLabelTest::test_no_holder_degrades_to_the_same_placeholder — `_current_holder_label` без держателя отдаёт «? (pid ?)» вместо «?»
- mutation-007 — QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder — `wait_suffix` называет держателя через `_current_holder_id` (без pid)
- mutation-008 — QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder — `queue_wait_minutes` считает начатые минуты (`// 60` + 1)
- mutation-009 — QueueWaitMinutesAndStatusSuffixTest::test_not_queued_returns_none_and_empty_suffix — `queue_wait_minutes` задачи вне очереди отдаёт `0` вместо `None`
- mutation-010 — CurrentHolderLabelTest::test_label_names_task_and_pid_of_the_holder — `_current_holder_label` собран по одному `task_id`, без pid
- mutation-011 — ProcessScopedQueueRowsTest::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order — `store.enqueue_merge_wait` — одна запись на сессию (перед вставкой удаляет записи того же `session_id`)
- mutation-012 — ProcessScopedQueueRowsTest::test_touch_heartbeat_updates_only_the_row_of_that_process — `store.touch_merge_queue_heartbeat` продлевает по одному `session_id` (pid выпал из `WHERE`)
- mutation-013 — ProcessScopedQueueRowsTest::test_dequeue_removes_only_the_row_of_that_process, ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window — `store.dequeue_merge_wait` снимает по одному `session_id` (pid выпал из `WHERE`)
- mutation-014 — LegacyTouchHeartbeatTest::test_no_args_with_several_projects_renews_only_current_session — `_own_rows` прежней формы отдаёт все строки (`len(rows) >= 1`)
- mutation-015 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order — `_holder_row` берёт первую строку таблицы, а не строку проекта
- mutation-016 — ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid — `_is_own_process` сверяет один `session_id`, без pid
- mutation-017 — ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text — `acquire` для живого держателя своей сессии отдаёт отдельный текст отказа
- mutation-018 — ProcessOwnershipTest::test_own_process_re_enters_and_refreshes_the_row — ветка «свой процесс» в `acquire` не переписывает строку
- mutation-019 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled — отказ «та же сессия» в `acquire` стоит перед проверкой живости держателя
- mutation-020 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled, AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled — перехват мёртвого держателя в `acquire` идёт без записи журнала
- mutation-021 — AcquireReleaseTest::test_fresh_acquire_on_empty_table_takes_the_lock — `acquire` пишет host `"localhost"` вместо `socket.gethostname()`
- mutation-022 — AcquireReleaseTest::test_own_session_re_enters_without_refusal — условие взятия в `acquire` — только `row is None`, без ветки «свой процесс»
- mutation-023 — AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task — текст отказа `acquire` без session_id держателя
- mutation-024 — ConcurrentAcquireTest::test_concurrent_acquire_on_free_lock_exactly_one_wins — `acquire` не проверяет занятость строки замка (условие взятия `if True:`)
- mutation-025 — AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled, PruneDeadEntriesTest::test_stale_heartbeat_on_foreign_host_is_pruned — `_holder_is_dead` не считает протухший heartbeat признаком смерти
- mutation-026 — AcquireReleaseTest::test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat, PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it — `_holder_is_dead` не проверяет живость pid своего host (`return False`)
- mutation-027 — AcquireReleaseTest::test_foreign_dead_pid_on_a_different_host_is_not_taken_over, PruneDeadEntriesTest::test_live_entry_survives_pruning — `_holder_is_dead` признаёт мёртвым любого участника чужого host (`!=`/`or` в сверке host)
- mutation-028 — RunWindowTest::test_success_runs_body_and_releases_the_mutex_afterwards — `run_window` не снимает мьютекс (`release` выпал вместе с `finally`)
- mutation-029 — RunWindowTest::test_mutex_is_released_even_when_the_body_raises — `run_window` снимает мьютекс после тела вне `finally`
- mutation-030 — RunWindowTest::test_refusal_exits_without_running_the_body — `run_window` исполняет тело перед `sys.exit` по отказу
- mutation-031 — PruneDeadEntriesTest::test_dead_pid_on_own_host_is_pruned — `_prune_dead_entries` удаляет запись по `pid` вместо `rowid`
- mutation-032 — HeadTaskIdTest::test_empty_queue_has_no_head — `_head_task_id` пустой очереди отдаёт `""` вместо `None`
- mutation-033 — HeadTaskIdTest::test_head_is_earliest_by_enqueued_ts — `_head_task_id` берёт последнюю запись (`rows[-1]`)
- mutation-034 — WaitForWindowTest::test_free_mutex_registers_then_immediately_takes_the_window — `wait_for_window` снимает свою запись только на выходе по потолку (`except SystemExit` вместо `finally`)
- mutation-035 — WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state — `wait_for_window` снимает свою запись только на успехе (`finally` при `sys.exc_info()[0] is None`)
- mutation-036 — CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid — журнал входа в очередь `wait_for_window` называет держателя через `_current_holder_id`
- mutation-037 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window — голова очереди в `wait_for_window` — первая запись проекта своей сессии (по `session_id`)
- mutation-038 — WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry — голова очереди в `wait_for_window` — голова всей очереди (`_head_task_id(conn)` без проекта)

## Строки падения и соответствие «до» → «после»

Тест `<Класс>::<метод>` перенесён в функцию с тем же именем своего файла
модуля. Для каждой мутации и каждого её убийцы «до» — убийца «после»
(функция, в которую перенесён тест) и две строки падения: утверждение
исходного файла базы («до», прогоны №1–№4) и утверждение функции модуля
(«после», прогоны №5–№8). Нормальная форма у пары одна (решение 1
ANSWER-1); для мутации 38 строка падения — `raise AssertionError("задача P
ушла в паузу очереди")` подмены паузы. Убийство только исключением
(`KeyError` у `test_touch_heartbeat_updates_only_the_row_of_that_process`
на патче 11) доказательством не считается — патч 11 доказан
утверждениями двух других убийц.

- mutation-001 — ProcessOwnershipTest::test_release_from_non_holder_process_keeps_the_mutex → test_merge_lock_module.py::test_release_from_non_holder_process_keeps_the_mutex — «до» tests/test_merge_lock.py:240, «после» tests/test_merge_lock_module.py:375
- mutation-001 — ProcessOwnershipTest::test_store_release_merge_lock_requires_both_session_and_pid → test_merge_lock_module.py::test_store_release_merge_lock_requires_both_session_and_pid — «до» tests/test_merge_lock.py:269, «после» tests/test_merge_lock_module.py:407
- mutation-002 — AcquireReleaseTest::test_release_removes_only_the_matching_session → test_merge_lock_module.py::test_release_removes_only_the_matching_session — «до» tests/test_merge_lock.py:119, «после» tests/test_merge_lock_module.py:265
- mutation-002 — ProcessOwnershipTest::test_store_release_merge_lock_requires_both_session_and_pid → test_merge_lock_module.py::test_store_release_merge_lock_requires_both_session_and_pid — «до» tests/test_merge_lock.py:271, «после» tests/test_merge_lock_module.py:409
- mutation-003 — AcquireReleaseTest::test_release_removes_only_the_matching_session → test_merge_lock_module.py::test_release_removes_only_the_matching_session — «до» tests/test_merge_lock.py:122, «после» tests/test_merge_lock_module.py:268
- mutation-003 — RunWindowTest::test_success_runs_body_and_releases_the_mutex_afterwards → test_merge_lock_module.py::test_success_runs_body_and_releases_the_mutex_afterwards — «до» tests/test_merge_lock.py:304, «после» tests/test_merge_lock_module.py:433
- mutation-003 — RunWindowTest::test_mutex_is_released_even_when_the_body_raises → test_merge_lock_module.py::test_mutex_is_released_even_when_the_body_raises — «до» tests/test_merge_lock.py:331, «после» tests/test_merge_lock_module.py:474
- mutation-003 — ProcessOwnershipTest::test_release_from_holder_process_removes_the_mutex → test_merge_lock_module.py::test_release_from_holder_process_removes_the_mutex — «до» tests/test_merge_lock.py:255, «после» tests/test_merge_lock_module.py:391
- mutation-004 — CurrentHolderIdTest::test_no_holder_degrades_to_placeholder → test_merge_queue.py::test_no_holder_degrades_to_placeholder — «до» tests/test_merge_queue.py:95, «после» tests/test_merge_queue.py:196
- mutation-005 — CurrentHolderIdTest::test_names_the_holder_task → test_merge_queue.py::test_names_the_holder_task — «до» tests/test_merge_queue.py:101, «после» tests/test_merge_queue.py:208
- mutation-006 — CurrentHolderLabelTest::test_no_holder_degrades_to_the_same_placeholder → test_merge_queue.py::test_no_holder_degrades_to_the_same_placeholder — «до» tests/test_merge_queue.py:149, «после» tests/test_merge_queue.py:260
- mutation-006 — WaitForWindowTest::test_free_mutex_registers_then_immediately_takes_the_window → test_merge_queue.py::test_free_mutex_registers_then_immediately_takes_the_window — «до» tests/test_merge_queue.py:291, «после» tests/test_merge_queue.py:412
- mutation-007 — QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder → test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder — «до» tests/test_merge_queue.py:133, «после» tests/test_merge_queue.py:245
- mutation-007 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:157, «после» tests/test_merge_queue.py:522
- mutation-008 — QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder → test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder — «до» tests/test_merge_queue.py:130, «после» tests/test_merge_queue.py:242
- mutation-008 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:157, «после» tests/test_merge_queue.py:522
- mutation-009 — QueueWaitMinutesAndStatusSuffixTest::test_not_queued_returns_none_and_empty_suffix → test_merge_queue.py::test_not_queued_returns_none_and_empty_suffix — «до» tests/test_merge_queue.py:110, «после» tests/test_merge_queue.py:221
- mutation-010 — QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder → test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder — «до» tests/test_merge_queue.py:133, «после» tests/test_merge_queue.py:245
- mutation-010 — CurrentHolderLabelTest::test_label_names_task_and_pid_of_the_holder → test_merge_queue.py::test_label_names_task_and_pid_of_the_holder — «до» tests/test_merge_queue.py:160, «после» tests/test_merge_queue.py:272
- mutation-010 — CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid → test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid — «до» tests/test_merge_queue.py:184, «после» tests/test_merge_queue.py:297
- mutation-010 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:155, «после» tests/test_merge_queue.py:520
- mutation-011 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window → test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window — «до» tests/test_merge_queue.py:269, «после» tests/test_merge_queue.py:382
- mutation-011 — ProcessScopedQueueRowsTest::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order → test_merge_queue.py::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order — «до» tests/test_merge_queue.py:209, «после» tests/test_merge_queue.py:319
- mutation-011 — ProcessScopedQueueRowsTest::test_touch_heartbeat_updates_only_the_row_of_that_process → test_merge_queue.py::test_touch_heartbeat_updates_only_the_row_of_that_process — «до» tests/test_merge_queue.py:228, «после» tests/test_merge_queue.py:339 (до: KeyError) (после: KeyError)
- mutation-012 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window → test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window — «до» tests/test_merge_queue.py:275, «после» tests/test_merge_queue.py:388
- mutation-012 — ProcessScopedQueueRowsTest::test_touch_heartbeat_updates_only_the_row_of_that_process → test_merge_queue.py::test_touch_heartbeat_updates_only_the_row_of_that_process — «до» tests/test_merge_queue.py:229, «после» tests/test_merge_queue.py:340
- mutation-013 — ProcessScopedQueueRowsTest::test_dequeue_removes_only_the_row_of_that_process → test_merge_queue.py::test_dequeue_removes_only_the_row_of_that_process — «до» tests/test_merge_queue.py:243, «после» tests/test_merge_queue.py:355
- mutation-013 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window → test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window — «до» tests/test_merge_queue.py:274, «после» tests/test_merge_queue.py:387
- mutation-014 — LegacyTouchHeartbeatTest::test_no_args_with_several_projects_renews_only_current_session → test_merge_lock_module.py::test_no_args_with_several_projects_renews_only_current_session — «до» tests/test_merge_lock_by_project.py:79, «после» tests/test_merge_lock_module.py:545
- mutation-015 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:155, «после» tests/test_merge_queue.py:520
- mutation-016 — ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text → test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text — «до» tests/test_merge_lock.py:185, «после» tests/test_merge_lock_module.py:315
- mutation-016 — ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid → test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid — «до» tests/test_merge_lock.py:165, «после» tests/test_merge_lock_module.py:293
- mutation-016 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled → test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled — «до» tests/test_merge_lock.py:224, «после» tests/test_merge_lock_module.py:358
- mutation-017 — ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text → test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text — «до» tests/test_merge_lock.py:186, «после» tests/test_merge_lock_module.py:316
- mutation-017 — ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid → test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid — «до» tests/test_merge_lock.py:167, «после» tests/test_merge_lock_module.py:295
- mutation-018 — ProcessOwnershipTest::test_own_process_re_enters_and_refreshes_the_row → test_merge_lock_module.py::test_own_process_re_enters_and_refreshes_the_row — «до» tests/test_merge_lock.py:204, «после» tests/test_merge_lock_module.py:336
- mutation-019 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled → test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled — «до» tests/test_merge_lock.py:221, «после» tests/test_merge_lock_module.py:355
- mutation-020 — AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled → test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled — «до» tests/test_merge_lock.py:90, «после» tests/test_merge_lock_module.py:215
- mutation-020 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled → test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled — «до» tests/test_merge_lock.py:224, «после» tests/test_merge_lock_module.py:358
- mutation-021 — AcquireReleaseTest::test_fresh_acquire_on_empty_table_takes_the_lock → test_merge_lock_module.py::test_fresh_acquire_on_empty_table_takes_the_lock — «до» tests/test_merge_lock.py:53, «после» tests/test_merge_lock_module.py:155
- mutation-022 — AcquireReleaseTest::test_own_session_re_enters_without_refusal → test_merge_lock_module.py::test_own_session_re_enters_without_refusal — «до» tests/test_merge_lock.py:60, «после» tests/test_merge_lock_module.py:169
- mutation-022 — ProcessOwnershipTest::test_own_process_re_enters_and_refreshes_the_row → test_merge_lock_module.py::test_own_process_re_enters_and_refreshes_the_row — «до» tests/test_merge_lock.py:202, «после» tests/test_merge_lock_module.py:334
- mutation-023 — AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task → test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task — «до» tests/test_merge_lock.py:71, «после» tests/test_merge_lock_module.py:187
- mutation-023 — RunWindowTest::test_refusal_exits_without_running_the_body → test_merge_lock_module.py::test_refusal_exits_without_running_the_body — «до» tests/test_merge_lock.py:317, «после» tests/test_merge_lock_module.py:453
- mutation-024 — AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task → test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task — «до» tests/test_merge_lock.py:70, «после» tests/test_merge_lock_module.py:186
- mutation-024 — ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text → test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text — «до» tests/test_merge_lock.py:184, «после» tests/test_merge_lock_module.py:314
- mutation-024 — ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid → test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid — «до» tests/test_merge_lock.py:165, «после» tests/test_merge_lock_module.py:293
- mutation-024 — AcquireReleaseTest::test_foreign_dead_pid_on_a_different_host_is_not_taken_over → test_merge_lock_module.py::test_foreign_dead_pid_on_a_different_host_is_not_taken_over — «до» tests/test_merge_lock.py:113, «после» tests/test_merge_lock_module.py:252
- mutation-024 — RunWindowTest::test_refusal_exits_without_running_the_body → test_merge_lock_module.py::test_refusal_exits_without_running_the_body — «до» tests/test_merge_lock.py:313, «после» tests/test_merge_lock_module.py:449
- mutation-024 — ConcurrentAcquireTest::test_concurrent_acquire_on_free_lock_exactly_one_wins → test_merge_lock_module.py::test_concurrent_acquire_on_free_lock_exactly_one_wins — «до» tests/test_merge_lock.py:378, «после» tests/test_merge_lock_module.py:515
- mutation-024 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled → test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled — «до» tests/test_merge_lock.py:224, «после» tests/test_merge_lock_module.py:358
- mutation-024 — AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled → test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled — «до» tests/test_merge_lock.py:90, «после» tests/test_merge_lock_module.py:215
- mutation-024 — CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid → test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid — «до» tests/test_merge_queue.py:180, «после» tests/test_merge_queue.py:293
- mutation-024 — WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state → test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state — «до» tests/test_merge_queue.py:316, «после» tests/test_merge_queue.py:438
- mutation-024 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:142, «после» tests/test_merge_queue.py:506
- mutation-025 — PruneDeadEntriesTest::test_stale_heartbeat_on_foreign_host_is_pruned → test_merge_queue.py::test_stale_heartbeat_on_foreign_host_is_pruned — «до» tests/test_merge_queue.py:60, «после» tests/test_merge_queue.py:129
- mutation-025 — AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled → test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled — «до» tests/test_merge_lock.py:85, «после» tests/test_merge_lock_module.py:210
- mutation-026 — PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it → test_merge_queue.py::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it — «до» tests/test_merge_queue.py:77, «после» tests/test_merge_queue.py:161
- mutation-026 — AcquireReleaseTest::test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat → test_merge_lock_module.py::test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat — «до» tests/test_merge_lock.py:99, «после» tests/test_merge_lock_module.py:232
- mutation-026 — ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled → test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled — «до» tests/test_merge_lock.py:221, «после» tests/test_merge_lock_module.py:355
- mutation-026 — PruneDeadEntriesTest::test_dead_pid_on_own_host_is_pruned → test_merge_queue.py::test_dead_pid_on_own_host_is_pruned — «до» tests/test_merge_queue.py:52, «после» tests/test_merge_queue.py:114
- mutation-027 — PruneDeadEntriesTest::test_live_entry_survives_pruning → test_merge_queue.py::test_live_entry_survives_pruning — «до» tests/test_merge_queue.py:68, «после» tests/test_merge_queue.py:144
- mutation-027 — PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it → test_merge_queue.py::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it — «до» tests/test_merge_queue.py:77, «после» tests/test_merge_queue.py:161
- mutation-027 — AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task → test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task — «до» tests/test_merge_lock.py:70, «после» tests/test_merge_lock_module.py:186
- mutation-027 — AcquireReleaseTest::test_foreign_dead_pid_on_a_different_host_is_not_taken_over → test_merge_lock_module.py::test_foreign_dead_pid_on_a_different_host_is_not_taken_over — «до» tests/test_merge_lock.py:113, «после» tests/test_merge_lock_module.py:252
- mutation-027 — RunWindowTest::test_refusal_exits_without_running_the_body → test_merge_lock_module.py::test_refusal_exits_without_running_the_body — «до» tests/test_merge_lock.py:313, «после» tests/test_merge_lock_module.py:449
- mutation-027 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:142, «после» tests/test_merge_queue.py:506
- mutation-027 — WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state → test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state — «до» tests/test_merge_queue.py:316, «после» tests/test_merge_queue.py:438
- mutation-027 — WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry → test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry — «до» tests/test_merge_lock_by_project.py:111, «после» tests/test_merge_queue.py:477
- mutation-027 — CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid → test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid — «до» tests/test_merge_queue.py:180, «после» tests/test_merge_queue.py:293
- mutation-028 — RunWindowTest::test_mutex_is_released_even_when_the_body_raises → test_merge_lock_module.py::test_mutex_is_released_even_when_the_body_raises — «до» tests/test_merge_lock.py:331, «после» tests/test_merge_lock_module.py:474
- mutation-028 — RunWindowTest::test_success_runs_body_and_releases_the_mutex_afterwards → test_merge_lock_module.py::test_success_runs_body_and_releases_the_mutex_afterwards — «до» tests/test_merge_lock.py:304, «после» tests/test_merge_lock_module.py:433
- mutation-029 — RunWindowTest::test_mutex_is_released_even_when_the_body_raises → test_merge_lock_module.py::test_mutex_is_released_even_when_the_body_raises — «до» tests/test_merge_lock.py:331, «после» tests/test_merge_lock_module.py:474
- mutation-030 — RunWindowTest::test_refusal_exits_without_running_the_body → test_merge_lock_module.py::test_refusal_exits_without_running_the_body — «до» tests/test_merge_lock.py:318, «после» tests/test_merge_lock_module.py:454
- mutation-031 — PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it → test_merge_queue.py::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it — «до» tests/test_merge_queue.py:77, «после» tests/test_merge_queue.py:161
- mutation-031 — PruneDeadEntriesTest::test_dead_pid_on_own_host_is_pruned → test_merge_queue.py::test_dead_pid_on_own_host_is_pruned — «до» tests/test_merge_queue.py:52, «после» tests/test_merge_queue.py:114
- mutation-031 — PruneDeadEntriesTest::test_stale_heartbeat_on_foreign_host_is_pruned → test_merge_queue.py::test_stale_heartbeat_on_foreign_host_is_pruned — «до» tests/test_merge_queue.py:60, «после» tests/test_merge_queue.py:129
- mutation-032 — HeadTaskIdTest::test_empty_queue_has_no_head → test_merge_queue.py::test_empty_queue_has_no_head — «до» tests/test_merge_queue.py:83, «после» tests/test_merge_queue.py:172
- mutation-033 — HeadTaskIdTest::test_head_is_earliest_by_enqueued_ts → test_merge_queue.py::test_head_is_earliest_by_enqueued_ts — «до» tests/test_merge_queue.py:89, «после» tests/test_merge_queue.py:185
- mutation-033 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window → test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window — «до» tests/test_merge_queue.py:269, «после» tests/test_merge_queue.py:382
- mutation-033 — ProcessScopedQueueRowsTest::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order → test_merge_queue.py::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order — «до» tests/test_merge_queue.py:210, «после» tests/test_merge_queue.py:320
- mutation-034 — WaitForWindowTest::test_free_mutex_registers_then_immediately_takes_the_window → test_merge_queue.py::test_free_mutex_registers_then_immediately_takes_the_window — «до» tests/test_merge_queue.py:287, «после» tests/test_merge_queue.py:408
- mutation-034 — WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry → test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry — «до» tests/test_merge_lock_by_project.py:111, «после» tests/test_merge_queue.py:477
- mutation-035 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window → test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window — «до» tests/test_merge_queue.py:274, «после» tests/test_merge_queue.py:387
- mutation-035 — WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state → test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state — «до» tests/test_merge_queue.py:323, «после» tests/test_merge_queue.py:444
- mutation-036 — CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid → test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid — «до» tests/test_merge_queue.py:184, «после» tests/test_merge_queue.py:297
- mutation-036 — WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order → test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order — «до» tests/test_merge_lock_by_project.py:155, «после» tests/test_merge_queue.py:520
- mutation-037 — ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window → test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window — «до» tests/test_merge_queue.py:269, «после» tests/test_merge_queue.py:382
- mutation-038 — WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry → test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry — «до» tests/test_merge_lock_by_project.py:105, «после» tests/test_merge_queue.py:470

## Мутации до

Часть 1 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref base --tests tests/test_merge_lock.py,tests/test_merge_queue.py,tests/test_merge_lock_by_project.py --copy-table --wait-lock 4 --patches 1-15` (прогон №1):

```
# mutation-run №1 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: base ec948ea430e262436fbedcd59c35c6f472764af9
# тесты: tests/test_merge_lock.py, tests/test_merge_queue.py, tests/test_merge_lock_by_project.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 7ff574f0aa97476645b548cf1faf5e25c9f0c1ea772ff3d095c9c01254423473
# патч 2 mutation-002.diff sha256 24d168e6b09f6fdd4e1adf4451edf35836de156e870dbac61712262249d21d76
# патч 3 mutation-003.diff sha256 5cc6e103246f296ee0ecb07160132e0309643484fba7ce17dc62c461d169031e
# патч 4 mutation-004.diff sha256 a8b83110b8dc531e9c9f464f12ba7dcdbceb725bed04c7f2f0ea3502599deb4a
# патч 5 mutation-005.diff sha256 c109eae165d3cf0e40ac13629e24646793f2c2b4f9c8f94f21a1ef0139e38bbb
# патч 6 mutation-006.diff sha256 328b2935a16d03395a202854e291695062e03488a9d5b406d393b1eeb79b3569
# патч 7 mutation-007.diff sha256 b09990d77c15beb89e62d202594fd569d5533ab74fa437e1dc0a0fed77ab7ef4
# патч 8 mutation-008.diff sha256 691fc46fed09baa8e5a57d933077f3b356c79b305eec0e5362300f14dcf3aa16
# патч 9 mutation-009.diff sha256 1a077c2cff4deb27c9587e1e553e395f651d49a59c11604b98c1ba13de8b1a4f
# патч 10 mutation-010.diff sha256 8e1b3acdda571e83d720c624dc1b338316e3898788f1b9ad3b2e1f314bfad52b
# патч 11 mutation-011.diff sha256 67f40be58f7666bd77c0a1dc04e48d71b4a1ce230c0d80522f2b1af828d97584
# патч 12 mutation-012.diff sha256 8ba062f336071ea2421295f1ebc5e65affd55c312e8dac01b4c07e6551322df0
# патч 13 mutation-013.diff sha256 0e964ec5ca07ec2a1244892851d8f6d07bae2919cc280b51732381f5d7d319ae
# патч 14 mutation-014.diff sha256 299d8b214c004e4a8067cdbc5c7e87b8056e734e13ad193133c644c4951fb525
# патч 15 mutation-015.diff sha256 2f864bb5546777d64e554cead533581ea4e13f9639b16871fca5a9e763e7060b
номер	исход	узлы
1	убита	tests/test_merge_lock.py::ProcessOwnershipTest::test_release_from_non_holder_process_keeps_the_mutex,tests/test_merge_lock.py::ProcessOwnershipTest::test_store_release_merge_lock_requires_both_session_and_pid
2	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_release_removes_only_the_matching_session,tests/test_merge_lock.py::ProcessOwnershipTest::test_store_release_merge_lock_requires_both_session_and_pid
3	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_release_removes_only_the_matching_session,tests/test_merge_lock.py::RunWindowTest::test_success_runs_body_and_releases_the_mutex_afterwards,tests/test_merge_lock.py::RunWindowTest::test_mutex_is_released_even_when_the_body_raises,tests/test_merge_lock.py::ProcessOwnershipTest::test_release_from_holder_process_removes_the_mutex
4	убита	tests/test_merge_queue.py::CurrentHolderIdTest::test_no_holder_degrades_to_placeholder
5	убита	tests/test_merge_queue.py::CurrentHolderIdTest::test_names_the_holder_task
6	убита	tests/test_merge_queue.py::CurrentHolderLabelTest::test_no_holder_degrades_to_the_same_placeholder,tests/test_merge_queue.py::WaitForWindowTest::test_free_mutex_registers_then_immediately_takes_the_window
7	убита	tests/test_merge_queue.py::QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder,tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order
8	убита	tests/test_merge_queue.py::QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder,tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order
9	убита	tests/test_merge_queue.py::QueueWaitMinutesAndStatusSuffixTest::test_not_queued_returns_none_and_empty_suffix
10	убита	tests/test_merge_queue.py::QueueWaitMinutesAndStatusSuffixTest::test_queued_reports_minutes_waited_and_the_current_holder,tests/test_merge_queue.py::CurrentHolderLabelTest::test_label_names_task_and_pid_of_the_holder,tests/test_merge_queue.py::CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order
11	убита	tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order,tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_touch_heartbeat_updates_only_the_row_of_that_process
12	убита	tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_touch_heartbeat_updates_only_the_row_of_that_process
13	убита	tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_dequeue_removes_only_the_row_of_that_process,tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window
14	убита	tests/test_merge_lock_by_project.py::LegacyTouchHeartbeatTest::test_no_args_with_several_projects_renews_only_current_session
15	убита	tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order
```

Часть 2 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref base --tests tests/test_merge_lock.py,tests/test_merge_queue.py,tests/test_merge_lock_by_project.py --copy-table --wait-lock 4 --patches 16-23` (прогон №2):

```
# mutation-run №2 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: base ec948ea430e262436fbedcd59c35c6f472764af9
# тесты: tests/test_merge_lock.py, tests/test_merge_queue.py, tests/test_merge_lock_by_project.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 90bec572bf5be50462370a2b29fe56507fb2c0620ef99f17e721a2aad6afd50a
# патч 17 mutation-017.diff sha256 f8a325305e2b5a5871501843e5bdde9ad96bd27258b3436af0ff54510db88aa0
# патч 18 mutation-018.diff sha256 84a1043d815cde02b26b0bcc630179a2943d6f1173c5ef47530e2c22fdaa220c
# патч 19 mutation-019.diff sha256 6a31ec1633f3e01b66a7cea061f672a7b73c88aad39cd64f0fd32f2a368036e7
# патч 20 mutation-020.diff sha256 3e0e2c06df2a47efe68dc15fc3e72307f02f57900e53a96bc2a810bf4b5e3a90
# патч 21 mutation-021.diff sha256 0ce10c2fcb54c44662fce3267226cd25a4c4ad8283023799940f7e3e94d7ed55
# патч 22 mutation-022.diff sha256 2e878a79b2f450d5a7b1c8db2094536831f8fc6370c5c74600cc1822011b6574
# патч 23 mutation-023.diff sha256 80df3f76882c0d0244f6690b9fc4ea49d04c30a18691c3f2a147c02d5b35ae97
номер	исход	узлы
16	убита	tests/test_merge_lock.py::ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock.py::ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid,tests/test_merge_lock.py::ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled
17	убита	tests/test_merge_lock.py::ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock.py::ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid
18	убита	tests/test_merge_lock.py::ProcessOwnershipTest::test_own_process_re_enters_and_refreshes_the_row
19	убита	tests/test_merge_lock.py::ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled
20	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled,tests/test_merge_lock.py::ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled
21	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_fresh_acquire_on_empty_table_takes_the_lock
22	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_own_session_re_enters_without_refusal,tests/test_merge_lock.py::ProcessOwnershipTest::test_own_process_re_enters_and_refreshes_the_row
23	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_lock.py::RunWindowTest::test_refusal_exits_without_running_the_body
```

Часть 3 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref base --tests tests/test_merge_lock.py,tests/test_merge_queue.py,tests/test_merge_lock_by_project.py --copy-table --wait-lock 4 --patches 24-31` (прогон №3):

```
# mutation-run №3 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: base ec948ea430e262436fbedcd59c35c6f472764af9
# тесты: tests/test_merge_lock.py, tests/test_merge_queue.py, tests/test_merge_lock_by_project.py
# рабочих процессов: auto
# патч 24 mutation-024.diff sha256 852afc25556b99477086fecfaec260ede47cae0b5186fb9ade5ec3e9c9ec3144
# патч 25 mutation-025.diff sha256 c4c2e1f379a366514d301c4c2885164d6a5011f339d43111ba286248a75703e8
# патч 26 mutation-026.diff sha256 8c9a27af6a4300d3cdd2ce269dc2551f3bb0b2670cdf4c5e581b07b15498f7e5
# патч 27 mutation-027.diff sha256 8b2662d2d55213c561ea17cb4771b449425fcf5e4511cb0c4dcfdded20fddf03
# патч 28 mutation-028.diff sha256 53e132477bcfc2259a60b4a6ac980af51efdcb14c968858951112a60c891721e
# патч 29 mutation-029.diff sha256 a62cdea1407829f1fd540c283f3743159052152827852148c7f815e04720cd58
# патч 30 mutation-030.diff sha256 1df9369c86617ccde24bc03d6ebb3c5184a145d7d7e6107dcddbeda1a0893ec6
# патч 31 mutation-031.diff sha256 cf0cab33f355ac5bd9595d5da7f7cfbd981c0029c954e409a7b16e039976bea8
номер	исход	узлы
24	убита	tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_lock.py::ProcessOwnershipTest::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock.py::ProcessOwnershipTest::test_live_other_process_of_same_session_is_refused_with_holder_pid,tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_dead_pid_on_a_different_host_is_not_taken_over,tests/test_merge_lock.py::RunWindowTest::test_refusal_exits_without_running_the_body,tests/test_merge_lock.py::ConcurrentAcquireTest::test_concurrent_acquire_on_free_lock_exactly_one_wins,tests/test_merge_lock.py::ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled,tests/test_merge_queue.py::CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state,tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order
25	убита	tests/test_merge_queue.py::PruneDeadEntriesTest::test_stale_heartbeat_on_foreign_host_is_pruned,tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled
26	убита	tests/test_merge_queue.py::PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it,tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat,tests/test_merge_lock.py::ProcessOwnershipTest::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_queue.py::PruneDeadEntriesTest::test_dead_pid_on_own_host_is_pruned
27	убита	tests/test_merge_queue.py::PruneDeadEntriesTest::test_live_entry_survives_pruning,tests/test_merge_queue.py::PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it,tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_lock.py::AcquireReleaseTest::test_foreign_dead_pid_on_a_different_host_is_not_taken_over,tests/test_merge_lock.py::RunWindowTest::test_refusal_exits_without_running_the_body,tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state,tests/test_merge_lock_by_project.py::WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry,tests/test_merge_queue.py::CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid
28	убита	tests/test_merge_lock.py::RunWindowTest::test_mutex_is_released_even_when_the_body_raises,tests/test_merge_lock.py::RunWindowTest::test_success_runs_body_and_releases_the_mutex_afterwards
29	убита	tests/test_merge_lock.py::RunWindowTest::test_mutex_is_released_even_when_the_body_raises
30	убита	tests/test_merge_lock.py::RunWindowTest::test_refusal_exits_without_running_the_body
31	убита	tests/test_merge_queue.py::PruneDeadEntriesTest::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it,tests/test_merge_queue.py::PruneDeadEntriesTest::test_dead_pid_on_own_host_is_pruned,tests/test_merge_queue.py::PruneDeadEntriesTest::test_stale_heartbeat_on_foreign_host_is_pruned
```

Часть 4 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref base --tests tests/test_merge_lock.py,tests/test_merge_queue.py,tests/test_merge_lock_by_project.py --copy-table --wait-lock 4 --patches 32-38` (прогон №4):

```
# mutation-run №4 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: base ec948ea430e262436fbedcd59c35c6f472764af9
# тесты: tests/test_merge_lock.py, tests/test_merge_queue.py, tests/test_merge_lock_by_project.py
# рабочих процессов: auto
# патч 32 mutation-032.diff sha256 6c433e6274df9a904e5782c1b8e0186e4ea86c23dc906fb592be25373ee514b3
# патч 33 mutation-033.diff sha256 daa30f94b4dbf38e691079dcd3cafbc811140c2ae7ffdcb516f1d0ba930404f9
# патч 34 mutation-034.diff sha256 85cfd972375e547857ce958d5b0778d2d9555906d2c923b5bcac00c3ad24c17b
# патч 35 mutation-035.diff sha256 d5fef11c7ef7ea0db7820b436176ef4b43a5ebfd4a7cbb3fe45f5db0302cbee1
# патч 36 mutation-036.diff sha256 fe760e67a3e59283e119aa4e42a455a27375b68ccb38dc40668037f11b861622
# патч 37 mutation-037.diff sha256 a934d3065c05678ff7c280deeeb24faa8c19bddb164239724ce9b809d8e6a739
# патч 38 mutation-038.diff sha256 270f7a87ecdd4b3e51382366b7ea2c7152eac4b3f05cb07dae37889bd89bd6cd
номер	исход	узлы
32	убита	tests/test_merge_queue.py::HeadTaskIdTest::test_empty_queue_has_no_head
33	убита	tests/test_merge_queue.py::HeadTaskIdTest::test_head_is_earliest_by_enqueued_ts,tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order
34	убита	tests/test_merge_queue.py::WaitForWindowTest::test_free_mutex_registers_then_immediately_takes_the_window,tests/test_merge_lock_by_project.py::WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry
35	убита	tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state
36	убита	tests/test_merge_queue.py::CurrentHolderLabelTest::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_lock_by_project.py::WaitTextsAnyOrderTest::test_texts_name_own_project_holder_in_every_insertion_order
37	убита	tests/test_merge_queue.py::ProcessScopedQueueRowsTest::test_non_head_process_of_the_same_session_does_not_take_the_window
38	убита	tests/test_merge_lock_by_project.py::WaitForWindowOtherProjectQueueTest::test_earlier_entry_of_other_project_does_not_delay_entry
```

## Мутации после

Перед частью 1 — `git status --porcelain -- orchestrator/` (код 0, вывод пуст):

```
$ git status --porcelain -- orchestrator/
```

Часть 1 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref worktree --tests tests/test_merge_lock_module.py,tests/test_merge_queue.py --copy-table --wait-lock 4 --patches 1-15` (прогон №5):

```
# mutation-run №5 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: worktree 7c0bc906b70814114a1de34c1415033e1fd62d26
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 7ff574f0aa97476645b548cf1faf5e25c9f0c1ea772ff3d095c9c01254423473
# патч 2 mutation-002.diff sha256 24d168e6b09f6fdd4e1adf4451edf35836de156e870dbac61712262249d21d76
# патч 3 mutation-003.diff sha256 5cc6e103246f296ee0ecb07160132e0309643484fba7ce17dc62c461d169031e
# патч 4 mutation-004.diff sha256 a8b83110b8dc531e9c9f464f12ba7dcdbceb725bed04c7f2f0ea3502599deb4a
# патч 5 mutation-005.diff sha256 c109eae165d3cf0e40ac13629e24646793f2c2b4f9c8f94f21a1ef0139e38bbb
# патч 6 mutation-006.diff sha256 328b2935a16d03395a202854e291695062e03488a9d5b406d393b1eeb79b3569
# патч 7 mutation-007.diff sha256 b09990d77c15beb89e62d202594fd569d5533ab74fa437e1dc0a0fed77ab7ef4
# патч 8 mutation-008.diff sha256 691fc46fed09baa8e5a57d933077f3b356c79b305eec0e5362300f14dcf3aa16
# патч 9 mutation-009.diff sha256 1a077c2cff4deb27c9587e1e553e395f651d49a59c11604b98c1ba13de8b1a4f
# патч 10 mutation-010.diff sha256 8e1b3acdda571e83d720c624dc1b338316e3898788f1b9ad3b2e1f314bfad52b
# патч 11 mutation-011.diff sha256 67f40be58f7666bd77c0a1dc04e48d71b4a1ce230c0d80522f2b1af828d97584
# патч 12 mutation-012.diff sha256 8ba062f336071ea2421295f1ebc5e65affd55c312e8dac01b4c07e6551322df0
# патч 13 mutation-013.diff sha256 0e964ec5ca07ec2a1244892851d8f6d07bae2919cc280b51732381f5d7d319ae
# патч 14 mutation-014.diff sha256 299d8b214c004e4a8067cdbc5c7e87b8056e734e13ad193133c644c4951fb525
# патч 15 mutation-015.diff sha256 2f864bb5546777d64e554cead533581ea4e13f9639b16871fca5a9e763e7060b
номер	исход	узлы
1	убита	tests/test_merge_lock_module.py::test_store_release_merge_lock_requires_both_session_and_pid,tests/test_merge_lock_module.py::test_release_from_non_holder_process_keeps_the_mutex
2	убита	tests/test_merge_lock_module.py::test_release_removes_only_the_matching_session,tests/test_merge_lock_module.py::test_store_release_merge_lock_requires_both_session_and_pid
3	убита	tests/test_merge_lock_module.py::test_release_from_holder_process_removes_the_mutex,tests/test_merge_lock_module.py::test_success_runs_body_and_releases_the_mutex_afterwards,tests/test_merge_lock_module.py::test_mutex_is_released_even_when_the_body_raises,tests/test_merge_lock_module.py::test_release_removes_only_the_matching_session
4	убита	tests/test_merge_queue.py::test_no_holder_degrades_to_placeholder
5	убита	tests/test_merge_queue.py::test_names_the_holder_task
6	убита	tests/test_merge_queue.py::test_no_holder_degrades_to_the_same_placeholder,tests/test_merge_queue.py::test_free_mutex_registers_then_immediately_takes_the_window
7	убита	tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder
8	убита	tests/test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order
9	убита	tests/test_merge_queue.py::test_not_queued_returns_none_and_empty_suffix
10	убита	tests/test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::test_label_names_task_and_pid_of_the_holder
11	убита	tests/test_merge_queue.py::test_touch_heartbeat_updates_only_the_row_of_that_process,tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order
12	убита	tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::test_touch_heartbeat_updates_only_the_row_of_that_process
13	убита	tests/test_merge_queue.py::test_dequeue_removes_only_the_row_of_that_process,tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window
14	убита	tests/test_merge_lock_module.py::test_no_args_with_several_projects_renews_only_current_session
15	убита	tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order
```

Перед частью 2 — `git status --porcelain -- orchestrator/` (код 0, вывод пуст):

```
$ git status --porcelain -- orchestrator/
```

Часть 2 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref worktree --tests tests/test_merge_lock_module.py,tests/test_merge_queue.py --copy-table --wait-lock 4 --patches 16-23` (прогон №6):

```
# mutation-run №6 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: worktree 7c0bc906b70814114a1de34c1415033e1fd62d26
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 90bec572bf5be50462370a2b29fe56507fb2c0620ef99f17e721a2aad6afd50a
# патч 17 mutation-017.diff sha256 f8a325305e2b5a5871501843e5bdde9ad96bd27258b3436af0ff54510db88aa0
# патч 18 mutation-018.diff sha256 84a1043d815cde02b26b0bcc630179a2943d6f1173c5ef47530e2c22fdaa220c
# патч 19 mutation-019.diff sha256 6a31ec1633f3e01b66a7cea061f672a7b73c88aad39cd64f0fd32f2a368036e7
# патч 20 mutation-020.diff sha256 3e0e2c06df2a47efe68dc15fc3e72307f02f57900e53a96bc2a810bf4b5e3a90
# патч 21 mutation-021.diff sha256 0ce10c2fcb54c44662fce3267226cd25a4c4ad8283023799940f7e3e94d7ed55
# патч 22 mutation-022.diff sha256 2e878a79b2f450d5a7b1c8db2094536831f8fc6370c5c74600cc1822011b6574
# патч 23 mutation-023.diff sha256 80df3f76882c0d0244f6690b9fc4ea49d04c30a18691c3f2a147c02d5b35ae97
номер	исход	узлы
16	убита	tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid
17	убита	tests/test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid
18	убита	tests/test_merge_lock_module.py::test_own_process_re_enters_and_refreshes_the_row
19	убита	tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled
20	убита	tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled
21	убита	tests/test_merge_lock_module.py::test_fresh_acquire_on_empty_table_takes_the_lock
22	убита	tests/test_merge_lock_module.py::test_own_session_re_enters_without_refusal,tests/test_merge_lock_module.py::test_own_process_re_enters_and_refreshes_the_row
23	убита	tests/test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_lock_module.py::test_refusal_exits_without_running_the_body
```

Перед частью 3 — `git status --porcelain -- orchestrator/` (код 0, вывод пуст):

```
$ git status --porcelain -- orchestrator/
```

Часть 3 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref worktree --tests tests/test_merge_lock_module.py,tests/test_merge_queue.py --copy-table --wait-lock 4 --patches 24-31` (прогон №7):

```
# mutation-run №7 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: worktree 7c0bc906b70814114a1de34c1415033e1fd62d26
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py
# рабочих процессов: auto
# патч 24 mutation-024.diff sha256 852afc25556b99477086fecfaec260ede47cae0b5186fb9ade5ec3e9c9ec3144
# патч 25 mutation-025.diff sha256 c4c2e1f379a366514d301c4c2885164d6a5011f339d43111ba286248a75703e8
# патч 26 mutation-026.diff sha256 8c9a27af6a4300d3cdd2ce269dc2551f3bb0b2670cdf4c5e581b07b15498f7e5
# патч 27 mutation-027.diff sha256 8b2662d2d55213c561ea17cb4771b449425fcf5e4511cb0c4dcfdded20fddf03
# патч 28 mutation-028.diff sha256 53e132477bcfc2259a60b4a6ac980af51efdcb14c968858951112a60c891721e
# патч 29 mutation-029.diff sha256 a62cdea1407829f1fd540c283f3743159052152827852148c7f815e04720cd58
# патч 30 mutation-030.diff sha256 1df9369c86617ccde24bc03d6ebb3c5184a145d7d7e6107dcddbeda1a0893ec6
# патч 31 mutation-031.diff sha256 cf0cab33f355ac5bd9595d5da7f7cfbd981c0029c954e409a7b16e039976bea8
номер	исход	узлы
24	убита	tests/test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_lock_module.py::test_refusal_exits_without_running_the_body,tests/test_merge_lock_module.py::test_concurrent_acquire_on_free_lock_exactly_one_wins,tests/test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid,tests/test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled,tests/test_merge_lock_module.py::test_foreign_dead_pid_on_a_different_host_is_not_taken_over,tests/test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state
25	убита	tests/test_merge_queue.py::test_stale_heartbeat_on_foreign_host_is_pruned,tests/test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled
26	убита	tests/test_merge_queue.py::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it,tests/test_merge_lock_module.py::test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat,tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_queue.py::test_dead_pid_on_own_host_is_pruned
27	убита	tests/test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_queue.py::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it,tests/test_merge_queue.py::test_live_entry_survives_pruning,tests/test_merge_lock_module.py::test_refusal_exits_without_running_the_body,tests/test_merge_lock_module.py::test_foreign_dead_pid_on_a_different_host_is_not_taken_over,tests/test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry,tests/test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state
28	убита	tests/test_merge_lock_module.py::test_mutex_is_released_even_when_the_body_raises,tests/test_merge_lock_module.py::test_success_runs_body_and_releases_the_mutex_afterwards
29	убита	tests/test_merge_lock_module.py::test_mutex_is_released_even_when_the_body_raises
30	убита	tests/test_merge_lock_module.py::test_refusal_exits_without_running_the_body
31	убита	tests/test_merge_queue.py::test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it,tests/test_merge_queue.py::test_stale_heartbeat_on_foreign_host_is_pruned,tests/test_merge_queue.py::test_dead_pid_on_own_host_is_pruned
```

Перед частью 4 — `git status --porcelain -- orchestrator/` (код 0, вывод пуст):

```
$ git status --porcelain -- orchestrator/
```

Часть 4 — `mutation-run 01M5QJTVJB1ZM8B6DDEFQBP6RX --ref worktree --tests tests/test_merge_lock_module.py,tests/test_merge_queue.py --copy-table --wait-lock 4 --patches 32-38` (прогон №8):

```
# mutation-run №8 задачи 01M5QJTVJB1ZM8B6DDEFQBP6RX
# источник патчей: каталог на диске
# ревизия прогона: worktree 7c0bc906b70814114a1de34c1415033e1fd62d26
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py
# рабочих процессов: auto
# патч 32 mutation-032.diff sha256 6c433e6274df9a904e5782c1b8e0186e4ea86c23dc906fb592be25373ee514b3
# патч 33 mutation-033.diff sha256 daa30f94b4dbf38e691079dcd3cafbc811140c2ae7ffdcb516f1d0ba930404f9
# патч 34 mutation-034.diff sha256 85cfd972375e547857ce958d5b0778d2d9555906d2c923b5bcac00c3ad24c17b
# патч 35 mutation-035.diff sha256 d5fef11c7ef7ea0db7820b436176ef4b43a5ebfd4a7cbb3fe45f5db0302cbee1
# патч 36 mutation-036.diff sha256 fe760e67a3e59283e119aa4e42a455a27375b68ccb38dc40668037f11b861622
# патч 37 mutation-037.diff sha256 a934d3065c05678ff7c280deeeb24faa8c19bddb164239724ce9b809d8e6a739
# патч 38 mutation-038.diff sha256 270f7a87ecdd4b3e51382366b7ea2c7152eac4b3f05cb07dae37889bd89bd6cd
номер	исход	узлы
32	убита	tests/test_merge_queue.py::test_empty_queue_has_no_head
33	убита	tests/test_merge_queue.py::test_head_is_earliest_by_enqueued_ts,tests/test_merge_queue.py::test_two_processes_of_one_session_live_as_two_rows_in_fifo_order,tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window
34	убита	tests/test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry,tests/test_merge_queue.py::test_free_mutex_registers_then_immediately_takes_the_window
35	убита	tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state
36	убита	tests/test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order
37	убита	tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window
38	убита	tests/test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry
```

## Удалённые дубли

Нет: каждый из 40 исходных тестов перенесён в функцию с тем же именем.

## Находки

Находок нет: каждый патч набора убит «до» и «после» утверждением теста;
исходов «не убита», «итог неизвестен», «патч не применяется», «патч
трогает тесты», «не прогнана» и обрывов по пределу нет.

## Помощники, фикстуры, константы

- `tests/test_merge_lock_module.py`: фикстуры `lock_stand` (тела `setUp`
  `AcquireReleaseTest` и `RunWindowTest` равны по AST — одна фикстура),
  `ownership_stand`, `race_stand`, `project_stand` (бывший `_Base`);
  помощники `lock_row` (бывший `row` трёх классов; префикс — тесты держат
  локальную `row = self.row()`), `acquire_release_seed`,
  `process_ownership_seed`, `new_task`, `seed_lock`, `locks`, `clear`;
  константы `TASK`, `HOLDER_TASK`, `THREADS`, `OTHER_HOST`.
- `tests/test_merge_queue.py`: фикстуры `queue_stand` (бывший
  `_QueueTestBase`), `project_stand` (тело то же, что в файле замка);
  помощники `enqueue`, `rows_by_pid`, `new_task`, `seed_lock`, `locks`,
  `clear`; константы `TASK_A`, `TASK_B`, `TASK_C`, `OTHER_HOST`. Импорта
  между файлами модулей нет.
- Вложенные `fake_sleep`, `fake_monotonic`, `worker` остались вложенными.

## Числа и время

- До: 40 тестов — 18 в `tests/test_merge_lock.py`, 19 в
  `tests/test_merge_queue.py`, 3 в `tests/test_merge_lock_by_project.py`;
  строк 384 + 329 + 159 = 872.
- После: 40 функций-тестов — 19 в `tests/test_merge_lock_module.py`, 21 в
  `tests/test_merge_queue.py`; строк 546 + 523 = 1069 (рост — докстринги
  новых заявок и фикстур).
- Время контрольных прогонов `mutation-run`: «до» — 2,73 с, 2,60 с, 2,60 с,
  2,62 с (прогоны №1–№4, 40 passed, 22 subtests passed); «после» — 2,12 с,
  2,30 с, 2,21 с, 2,07 с (прогоны №5–№8, 40 passed).
- Адресный прогон под ролью: `python3 -m pytest tests/test_merge_lock_module.py
  tests/test_merge_queue.py` — 40 passed за 2,36 с.

## Сверка шапок

Ревизия «до» — base ec948ea430e262436fbedcd59c35c6f472764af9 (прогоны
№1–№4), «после» — worktree 7c0bc906b70814114a1de34c1415033e1fd62d26
(прогоны №5–№8); `git diff --quiet ec948ea430e262436fbedcd59c35c6f472764af9
7c0bc906b70814114a1de34c1415033e1fd62d26 -- orchestrator/` — код 0. sha256
каждого из 38 патчей в шапках «до» и «после» совпадает (сверка строк
`# патч …` таблиц №1/№5, №2/№6, №3/№7, №4/№8). Рабочих процессов — `auto`
во всех восьми прогонах (`--workers` не задавался: контроль зелёный с
первого раза).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 5 |
| 4 | 1, 5 |
| 5 | 2, 4 |
| 6 | 2, 4 (контроль зелёный во всех прогонах) |
| 7 | 1–4 (временные файлы — только в `$TMPDIR` и копии `mutation-run-<n>.tsv`) |
| 8 | 3 |
| 9 | 3 |
| 10 | 3 |
| 11 | 3 |
| 12 | 3 (дублей не удаляю) |
| 13 | 4 |
| 14 | 4, 5 |
| 15 | 3, 4 |
| 16 | 3 (мандат — ANSWER-1) |
| 17 | 3 |
| 18 | вне роли — сессия при Операторе |

## Влияние на систему

Код пульта не меняется: дифф ветки — два файла модулей, два удалённых
исходных файла и карта кода (вывод генератора). Множество убиваемых
мутаций до и после свода одно (38 из 38, те же убийцы), поэтому покрытие
не ослаблено; `skip`/`xfail` нет, пределы (`timeout=5`, `timeout=10`)
перенесены без подъёма. Долгоживущий сторож
`tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` по-прежнему видит
`tests/test_merge_queue.py` (файл переписан на месте; пауза подменяется
`patch_sleep`, как прежде). Откат — revert merge-коммита задачи.

## Риски

- Тест гонки зависит от планировщика потоков; заявка выбрана так, что
  исход не зависит от порядка (решение 4 ANSWER-1).
- Строки падения сняты с логов прогонов №1–№8; правка файлов модулей после
  коммита 7c0bc906 сдвинула бы номера строк «после» — правок после него нет.

## Предложения системе

- `plank-run` в шаге разработчика читает PLAN и патчи только из ссылки
  документов: до автокоммита шага PLAN-зависимые проверки планки
  недоступны (`LookupError: PLAN.md в ссылке документов задачи нет`);
  пришлось собирать стенд планки с `_pult.py` по каталогу документов в
  `$TMPDIR` (`orchestrator/plank_run.py`, класс «команда пульта не видит
  артефакт текущего шага»).
- Песочница Bash роли отказывает в `$VAR`/`${…}`: любое обращение к
  `$TMPDIR` — только через `python3` (`os.environ`), что удлиняет каждый
  шаг с временной копией.
