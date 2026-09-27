---
task: 01M3FQ3JVC3DGGM33XCX8TC7ME
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Автогейт приёмки называет упавшие тесты; approve в acceptance проверяет то, что обещает

# ТЗ: Автогейт приёмки называет упавшие тесты; approve в acceptance проверяет то, что обещает

Источник: строка копилки П2 от 26.09 «Гонка ручной приёмки с автогейтом…
запись автогейта не называет упавший тест» (docs/backlog.md). Задача вне
линии провайдеров.

Факты (origin/main a24d78fc):
- Автогейт приёмки (orchestrator/fsm_autogate.py, _autogate_conditions)
  читает пометки AC из артефактной ветки (тесты не запускает — планка
  уже прошла на гейте review -> verifying, advance_gates/acceptance.py),
  затем зовёт acceptance.run_full_suite(wt_root) и берёт только первый
  элемент ответа: `green, _ = acceptance.run_full_suite(wt_root)`
  (fsm_autogate.py:225). Хвост вывода (второй элемент, последние 2000
  символов stdout+stderr) отбрасывается. При провале в журнал уходит
  ровно «автогейт: полный набор tests/ красный» (:227) — без имён
  упавших тестов, без итоговой строки pytest, и одна и та же фраза для
  трёх разных причин run_full_suite: красный прогон, таймаут
  (FULL_SUITE_TIMEOUT_SEC=900, текст «прогон … превысил Nс»), отсутствие
  tests/ в worktree.
- acceptance.run_full_suite (orchestrator/acceptance.py:229-274) гоняет
  pytest tests/ с `-n auto -p xdist`, без `-q`/`-rf`, `capture_output`;
  вывод в файл не пишется. 26.09 автогейт задачи 01M3F7C66Y дал «полный
  набор tests/ красный» через 2 минуты после входа в acceptance;
  причину (гонка с ручной материализацией tasks/<id>/ в том же worktree)
  пришлось восстанавливать по времени событий.
- Ручной approve в acceptance (orchestrator/fsm.py::_approve_acceptance,
  :816-838) полный набор НЕ запускает: подтяжка main и переход в
  merge_gate с detail «приёмка пройдена». При этом запись журнала
  «приёмка: что проверит approve» (fsm_autogate.py:111) обещает
  «автоматически при approve: прогон планки приёмочных тестов …; полный
  набор tests/ в worktree ветки задачи». 26.09 после красного автогейта
  approve Оператора прошёл без повтора набора — зелёность доказал только
  ручной прогон сессии.
- Образец связки «файл лога + выжимка в журнале» в пульте есть: логи
  ролей .artel/logs/<id>-<role>-<n>.log и agent_log.log_tail
  (LOG_TAIL_LINES=15, LOG_TAIL_CHARS=1000, config.py:191-192); выжимка
  итоговой строки pytest — регулярка amend._RUN_SUMMARY
  (orchestrator/amend.py:53-56). Разбора строк «FAILED path::Class::test» в пульте нет.
  store.journal длину detail не ограничивает.

Требуется:
1. Провал полного набора у автогейта именуется: detail записи «автогейт
   acceptance не пройден» несёт причину (красный прогон / таймаут /
   tests/ нет), итоговую строку pytest («N failed, M passed …») и имена
   упавших тестов (строки `FAILED <nodeid>` вывода pytest; при их
   отсутствии — хвост вывода), с ограничением объёма как у выжимки логов
   ролей. Полный вывод прогона пишется в файл лога рядом с логами ролей
   (.artel/logs/<id>-fullsuite-<n>.log или иное имя по образцу
   agent_log), путь к файлу — в detail. Тот же разбор — у прогона
   полного набора на гейте мержа (fsm_merge_gate._full_suite_or_refuse),
   если укладывается в зоны.
2. Разбор вывода pytest (итоговая строка, имена FAILED/ERROR) — один узел,
   переиспользующий amend._RUN_SUMMARY или заменяющий его общей функцией
   в acceptance.py; amend продолжает писать ту же выжимку.
3. approve в acceptance делает то, что обещает запись «что проверит
   approve»: гоняет условия автогейта (полный набор tests/ в worktree с
   тем же разбором провала) и отказывает именованно при красном наборе,
   называя упавшие тесты; либо — если Оператор осознанно принимает
   красный набор — только с явным флагом (например `approve <id>
   --accept-red "<основание>"`) и записью основания в журнал. Текст
   записи «что проверит approve» приводится в соответствие с фактическим
   поведением (планка на этом шаге не гоняется — сказать, где гонялась).
4. Документация: docs/operator-session.md (раздел «Запуски и рабочие
   копии», пункт о планке и автогейте) — что именно проверяет автогейт,
   что гоняет approve, где лог полного набора.
5. Тесты (tests/): detail провала несёт имена упавших тестов и итоговую
   строку (подменённый run_full_suite с хвостом настоящего вида);
   таймаут и отсутствие tests/ различимы в detail; файл лога создаётся и
   назван в detail; approve в acceptance при красном наборе — отказ с
   именами (или проход только с флагом и основанием в журнале); текст
   «что проверит approve» совпадает с проверяемым; существующие
   tests/test_fsm_autogate.py, tests/test_acceptance.py,
   tests/test_amend.py, tests/test_plan_appendix.py зелёные, не ослаблены.

Зоны: orchestrator/fsm_autogate.py, orchestrator/acceptance.py,
orchestrator/fsm.py, orchestrator/amend.py, orchestrator/config.py,
orchestrator/agent_log.py, orchestrator/fsm_merge_gate.py (только
переиспользование разбора в _full_suite_or_refuse; состав и порядок
гейтов мержа не меняются), docs/operator-session.md, tests/.

Только чтение (не менять): orchestrator/advance_gates/acceptance.py
(планка на review -> verifying не трогается), orchestrator/store.py,
orchestrator/runner.py, docs/backlog.md, tests/test_invariants.py
(защищённый путь).

Не входит: изменение состава и порядка условий автогейта; правка
run_full_suite по составу флагов pytest (кроме нужного для разбора,
например `-rf`); повтор упавших тестов; гейт неослабления тестов
(отдельная задача 26.09).

Рамка: $25 (пол калибровки).
