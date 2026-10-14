---
task: 01M4X4WFB01A18X6SRS0JF3G2Y
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Свежесть аудита по свидетельству штатного автокоммита

## Подход
В `orchestrator/advance_gates/spec_audit.py::freshness_refusal` проверять точное действие автокоммита артефактной ветки и полный формат свидетельства: задача, роль spec_auditor, SHA последнего коммита SPEC-AUDIT.md. Сохранить проверку автора orchestrator и порядка после последнего входа. Допустить оба штатных сообщения checkpoint: обычное и WIP после таймаута, а также суффикс удалённых файлов. Досыл в suite_lock не менять.

## Шаги
1. Уточнить свидетельство свежести; проверить зафиксированные AC-1–5. Добавить собственные юнит-тесты только для пробелов: суффикс удалённых файлов и неверный автор точного свидетельства; проверить заявленные мутации.
2. Прогнать существующие проверки аудита и досыла, записать матрицу неослабления и красный/зелёный результат AC-1. Прогнать планку через plank-run, регенерировать карту и проверить PLAN через guard.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 — подлинное свидетельство текущего визита | 1 |
| 2 — существующее событие автокоммита | 1 |
| 3 — точный SHA, запрет посторонних записей | 1 |
| 4 — штатный проход и прежние отказы | 1, 2 |
| 5 — сохранение доставки и лимитов | 2 |
| 6 — продуктовая регрессия через файл очереди | 1, 2 |
| 7 — матрица неослабления | 2 |

## Влияние на систему
Меняется только условие подтверждения свежести обязательного аудита. Автор, действие и точная форма события проверяются совместно; порядок записей, принадлежность коммита аудитору и привязка к содержимому SPEC сохраняются. suite_lock, авторы досыла, ограничения текста, общий лимит knowledge и однократность доставки остаются прежними. Существующие и зафиксированные тесты не меняются. Откат — revert изменения этой задачи; он возвращает известную уязвимость свежести. Бюджет SPEC достаточен.

## Риски
Формат свидетельства определён checkpoint.py:1354–1358,1416–1418. При будущей смене формата потребуется согласованное обновление распознавания; штатные варианты проверяются тестами.

## Матрица неослабления
F — `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`;
D — `tests/test_suite_run_deferred_journal.py`;
K — `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.py`;
C — `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`;
A — `tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py`;
P — `tests/test_01m4x4wfb01a18x6srs0jf3g2y_delivery_preserved.py`.

| Прежнее свойство | Существующая проверка | Покрытие после исправления / результат |
|---|---|---|
| Новый pass/concerns проходит, draft остаётся | F: AuditExitTest::test_ac13_pass_and_concerns_lead_to_gate_draft_stays | Та же проверка; A: test_ac4_current_autocommit_passes (обычный и WIP) |
| Старый аудит и файл аналитика не продвигают задачу | F: FreshnessTest::test_ac15_previous_visit_pass_does_not_advance, test_ac15_spec_audit_written_by_analyst_does_not_advance | Те же проверки; A: AC-1, AC-2, AC-5 |
| Привязка к SPEC, отказ после изменения и при неверном spec_sha | F: ShaBindingTest::test_ac16_entry_journal_carries_spec_content_sha_not_ref_head, test_ac16_spec_changed_in_audit_step_refuses_with_both_sha, test_ac16_spec_sha_mismatch_refuses_and_match_passes | Те же проверки; A: AC-5 |
| Нечитаемая история не подтверждает свежесть | spec_audit.py::freshness_refusal | A: test_ac5_previous_visit_wrong_role_binding_and_unreadable_history |
| Свидетельство точного коммита | На базе дефект поиска SHA подстрокой | A: test_ac2_ordinary_orchestrator_record_cannot_advance, test_ac3_similar_sha_and_foreign_text_cannot_advance; законный AC-4 |
| Доставка однократно и сохранение сессии; возврат файла при ошибке БД | D: DeferredJournalTest::test_delivered_once_with_role_session, test_db_refusal_keeps_record_for_next_delivery | P: AC-6 исполняет исходные проверки |
| Запрет постороннего действия/автора, ограничение текста | D: DeferredJournalTest::test_forged_actor_and_foreign_action_are_not_delivered | P: AC-6 и AC-7 исполняют исходную проверку |
| Общий лимит knowledge команды/досыла и одна запись об исчерпании | K: DeliveryLimitTest (три метода) | P: test_ac7_authors_text_bound_and_shared_knowledge_limit исполняет исходный класс |
| Сохранение записей и авторов knowledge/сигнала близости к пределу | C: DeferredJournalTest::test_ac10_unwritable_db_defers_and_delivery_writes_once | P: AC-7 исполняет исходную проверку |
| Автор свидетельства — orchestrator, суффикс удаления допустим | checkpoint.py:1354–1358; проверка actor в freshness_refusal | tests/test_spec_audit_witness.py: два новых юнит-теста |

## Проверки
База AC-1: `daec84553c0951b8ddb9c46573c0e308d7319057`. Сохранённый test_author отчёт `acceptance_tests/baseline_ac1.txt`: оба подслучая красные, `2 failed, 1 passed`, код выхода 1; причина — ложный проход в spec_gate вместо spec_audit после штатного deliver_journal. SHA256 неизменённого файла регрессии проверен разработчиком: `3eec53364c8eac7cffbd77ffd693bf7f65c1790754b84732c5ccb533c8c562c9`.


AC-1 на исправлении — успех: `test_ac1_deferred_old_sha_cannot_advance` прошёл вместе с обоими подслучаями; итог общего прогона `32 passed, 36 subtests passed in 260.88s`, код выхода 0. Команда:
```text
python3 -m pytest tests/test_spec_audit_witness.py tests/test_01m4x4wfb01a18x6srs0jf3g2y_audit_freshness.py tests/test_01m4x4wfb01a18x6srs0jf3g2y_delivery_preserved.py tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py -p no:cacheprovider -p timeout -o timeout=120 -q --tb=short
```

Все строки матрицы выше проверены успешно этим прогоном. P исполняет исходные тесты D/K/C через unittest; ожидания не копировались и не менялись. Дополнительно `python3 -m pytest tests/test_spec_audit_gate.py -p no:cacheprovider -p timeout -o timeout=120 -q --tb=short` — `4 passed in 0.61s`.

Проверка собственных сторожей временными мутациями spec_audit.py (каждый раз запускался только соответствующий метод tests/test_spec_audit_witness.py): удаление разрешённого суффикса дало два упавших подслучая обычного/WIP сообщения; снятие условия actor == orchestrator дало один упавший тест. Оба прогона завершились кодом 1 по заявленной причине. Код восстановлен в finally, повтор собственного файла — `2 passed, 2 subtests passed`.

Карта регенерирована командой `python3 scripts/codebase_map.py`. `git diff --check` успешен. Полный набор tests/ не запускался: для шага разработчика выполнены проверки затронутого модуля и матрицы.

## Предложения системе
- `plank-run` / `_pult.artifact_text`: локальный прогон AC-8 отказал «нет PLAN.md», хотя разработчик записал PLAN в назначенный каталог документов; автокоммит артефактов выполняется только после шага. Нужна штатная проверка планки с текущими документами роли либо явное разделение локальной проверки и проверки после автокоммита. Обход и правка зафиксированной планки не выполнялись.


## Результат локальной планки
`python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4X4WFB01A18X6SRS0JF3G2Y` — `1 failed in 0.09s`, код выхода 1. AC-8 остановлен на первом assert: `_pult.artifact_text("PLAN.md")` вернул None. Причина подтверждена `orchestrator/plank_helper.py::artifact_text`: помощник читает DOCS_REVISION ссылки документов на момент выкладки; `plank-run` в in_dev выбирает зафиксированную ссылку, а не текущий каталог документов. PLAN этой первой сдачи попадёт в ссылку штатным автокоммитом после окончания шага. Поэтому успех AC-8 локально не заявляется; его следует проверить после штатного сохранения PLAN. Обход фиксации, изменение планки и самостоятельная запись в ссылку документов не выполнялись. Реализация готова к ревью; ограничения локального прогона отражены явно.

Финальная проверка артефакта: `python3 scripts/guard.py /Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/01M4X4WFB01A18X6SRS0JF3G2Y/PLAN.md` — `GUARD: ок (1 файлов)`, код выхода 0.
