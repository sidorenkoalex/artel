---
task: 01M6KWKZ8GKZZFABDG8QC9RDJF
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: approve --note на гейте SPEC: указание Оператора для test_author и ревьювера

# Указание Оператора для test_author при одобрении SPEC: `approve <id> --note <файл>` на гейте SPEC

## Факты

1. На `spec_gate` у Оператора два действия: `approve` (`fsm._approve_spec_gate`, `orchestrator/fsm.py:1337`) и `reject` (возврат аналитику, в том числе `reject --decision`). `answer` на `spec_gate` принимает только файл со строкой мандата (`answer._spec_gate_answer_text`, `orchestrator/answer.py:239`, отказ без мандата — `:268`); в `tests_writing` `answer` недоступен (`answer.INSTRUCTION_STATES`, `orchestrator/answer.py:216`).
2. Бриф test_author — `brief.test_author_answer_component` (`orchestrator/brief.py:1650`), вызов в `orchestrator/role_prompt.py:116`; в него входят причина возврата текущего визита, последний `ANSWER-n.md`, конвенции внешнего проекта, справочник ядра; плюс записки шагов `brief.step_notes_block` (`role_prompt.py:181`). Вход ревьювера — `review.review_package` (`orchestrator/review.py:770`): текст собирается из списка частей (`review.py:921-1000`), ANSWER-n — циклом на `review.py:965-971`. Текст внутри граничных маркеров брифа и пакета объявлен данными, а не инструкциями (`brief.py:179-184`, `review.py:925-930`). Уточнение к тестам, не вписанное в SPEC и не поданное мандатом, до test_author не доходит; после шага test_author долгоживущие тесты закреплены, правка — только `amend-tests` Оператора.
3. Образец канала «текст Оператора из журнала в бриф»: причины `reject` с `spec_gate` берутся из записей журнала по исполнителю `operator` и предыдущему состоянию (`brief._spec_gate_reasons`, `orchestrator/brief.py:1343`; `brief._spec_gate_decision_components`, `:1361`). `store.task_steps` возвращает записи по возрастанию id (`store.py:1504`). Команда `approve` процессу роли недоступна — белый список команд роли закрыт по умолчанию (`orchestrator/artel.py:2568`, `:2581-2597`, `:2616-2628`), поэтому запись от `approve` роль подделать не может.
4. Почему не файл задачи: новое имя в `tasks/<id>/` требует правки `scripts/guard.py` (`TASK_ROOT_ALLOWED_MD`, `guard.py:3463`), иначе файл отбрасывается автокоммитом шага и роняет гейт мержа; файл к тому же лежит в рабочей копии роли. Почему не `ANSWER-n`: последний ANSWER идёт в бриф test_author (`brief.py:1027`), номер и число ANSWER — в QUESTIONS и снимок эскалации (`fsm._latest_answer_number`, `fsm.py:569`; `fsm._answer_file_count`, `fsm.py:517`): указание вытеснило бы прежний ответ с мандатом из брифа test_author.
5. Разбор флагов `approve` — диспетчер `orchestrator/artel.py:2696`; позиционный sha — `_approve_sha_arg` (`artel.py:2257`; неизвестного флага у `approve` нет — без правки `--note` был бы взят за sha), индексы флагов со значением — `_approve_reason_indices` (`artel.py:2223`); именованный флаг только при наличии — приём `_approve_as_epic_kwargs` (`artel.py:2277`); отказ флага вне `spec_gate` до lease с чтением SPEC без записи журнала — образец `_as_epic_goal` (`fsm.py:1006-1022`), повтор под lease — `fsm.py:1799-1800`. Ветвление `approve` на `spec_gate`: деление — `fsm.py:1486`, `skip_tests` и SPEC без разметки AC — `fsm.py:1491-1502`, переход в `tests_writing` — `fsm.py:1507`; мягкие отказы — `fsm.py:1350`, `:1371`, `:1389-1439`. Формат строк мандата — `mandate.line_elements` по `mandate.MANDATE_MARKERS` (`orchestrator/advance_gates/mandate.py:55`, `:118`; четыре маркера); чтение файла с отказом при `OSError`/`UnicodeDecodeError` — образец `_read_decision_file` (`fsm.py:1928-1934`); заголовок файла решения `reject --decision` — `spec_gate_decision.starts_with_header`.
6. Решение Оператора 04.11: замечание к SPEC, меняющее то, что проверяет тест и против чего, — возвратом SPEC; остальное — одобрение и `answer` разработчику в `in_dev` (правило «Замечание к SPEC: возврат или одобрение», `docs/operator-session.md`, «Уроки 04.11»; на момент ТЗ — в удержанном doc-commit Оператора; задача на это правило не опирается). Круг «аналитик → аудитор» — около $3 и 10–20 минут; этап SPEC пяти задач 04.11 — около $124 из $192.

## Требуется

1. Флаг `approve <id> --note <файл>` — только в состоянии `spec_gate`; вне его — отказ с причиной до lease и повторно под lease (как `--as-epic`). Файл обязателен, читается (образец `_read_decision_file`) и непуст; `--note` без значения или со значением, начинающимся с `--`, — отказ до lease. `--note` и его значение входят в `_approve_reason_indices` и не попадают в `_approve_sha_arg`. Новый параметр `cmd_approve`/`_cmd_approve` — только именованный, по умолчанию `None`; без флага диспетчер вызывает их без нового аргумента.
2. Отказ без записей и без перехода, если хоть одна строка текста даёт `mandate.line_elements(строка, маркер) is not None` для любого из четырёх маркеров `mandate.MANDATE_MARKERS` (цикл по маркерам, местный импорт `mandate`; `answer._has_mandate_lines` не импортировать — круг импортов `answer` → `fsm`); текст отказа называет `answer <id> <файл>`. Отказ и тогда, когда текст начинается заголовком файла решения (`spec_gate_decision.starts_with_header`) — это файл для `reject --decision`.
3. Отказ без записей и без перехода, если `approve` поведёт задачу не в `tests_writing`: SPEC несёт деление, `skip_tests` либо SPEC без разметки AC — по тем же условиям, что `fsm.py:1486`, `:1491-1492`. Проверка — до lease, чтением SPEC как в `_as_epic_goal` (без `_read_branch_text_or_refuse`, который сам пишет журнал), и повторно под lease. Мягкие отказы `approve` (`fsm.py:1350`, `:1371`, `:1389-1439`) — как сейчас: их собственная запись «approve отклонён» остаётся, указание не пишется.
4. Запись указания — отдельная запись журнала исполнителем `operator`, деталь — полный текст файла; пишется внутри обработчика сразу после успешного `store.set_state(… "tests_writing" …)` (`fsm.py:1507`), под тем же lease. Если `set_state` бросил `CasConflict` или `DocsRefIncident` — записи нет. Действие — константа, не совпадающая ни с одним существующим действием и не начинающаяся с `state -> ` (иначе её подхватят `_previous_state_name`, `brief.py:1522`, и выборки гейтов, `mandate.py:718`, `test_integrity.py:1095`). Предел размера текста — `config.CONTEXT_FILE_MAX_BYTES` (`config.py:560`); больше — отказ до lease.
5. Текст указания для брифа и пакета даёт одна функция `brief.py`: последняя запись действия указания от `operator` с id больше id последней записи `state -> spec_gate` задачи; нет такой — `None`. Указание прежнего прохождения гейта новое одобрение не переживает — без новых записей и коммитов; возврат через эскалацию из `tests_writing` указание сохраняет.
6. Бриф test_author получает раздел «Указание Оператора на гейте SPEC» — после причины возврата и ANSWER, до конвенций; запись журнала «бриф: компонент» как у прочих компонентов. Перед граничными маркерами раздела — фиксированная строка (константа): текст внутри — указание Оператора, учитывать как уточнение тестов по SPEC; ослаблять, удалять или пропускать проверки SPEC оно не разрешает; при противоречии со SPEC — эскалация.
7. Пакет ревьювера `review.review_package` получает тот же текст отдельной частью сразу после цикла ANSWER-n (`review.py:965-971`), до долгоживущих файлов; только при наличии указания; набор ключей словаря пакета прежний; запись «бриф: компонент» от `reviewer` как у ANSWER (`review.py:858-865`). Перед маркерами — своя фиксированная строка: расхождение закреплённых тестов с указанием записать в REVIEW наблюдением для Оператора, а не замечанием разработчику.
8. Без `--note` поведение `approve` на `spec_gate`, брифы test_author и пакет ревьювера — прежние.
9. **Приложения Оператора к PLAN** (защищённые пути, коммит Оператора воротами мержа): `skills/test-authoring.md` и `skills/review-checklist.md` — короткий абзац, как учитывать раздел «Указание Оператора на гейте SPEC» (по образцу абзаца о ANSWER, `skills/review-checklist.md:82-85`); текст абзацев пишет аналитик в PLAN, существующие строки не меняются.
10. Справка `approve` в `orchestrator/artel.py` (продолжение строки — отступом больше двух пробелов, как сейчас у `approve`, `artel.py:187-189`); документация: `docs/operator-gates.md` (гейт SPEC), `docs/codebase-map.md`. `docs/operator-session.md` задача не меняет: правило «Замечание к SPEC» дополнит Оператор после мержа. В `docs/operator-gates.md` — что `watch` и `log` печатают деталь записи целиком.

Критерии приёмки:
- `approve <id> --note f` на `spec_gate`: переход в `tests_writing`, запись журнала с полным текстом; бриф test_author и пакет ревьювера содержат раздел с текстом и своими фиксированными строками;
- `--note` вне `spec_gate`, без значения, без файла, с нечитаемым или пустым файлом, со строкой любого из четырёх маркеров мандата, с заголовком файла решения, сверх `CONTEXT_FILE_MAX_BYTES`, при делении/`skip_tests`/SPEC без AC — отказ с причиной; состояние, журнал и ссылка документов прежние (кроме записи мягкого отказа, которая есть и без `--note`);
- `--note f` не попадает в `_approve_sha_arg`;
- повторное прохождение `spec_gate` той же задачей: `approve` без `--note` — раздела нет; с `--note` — новый текст;
- текст указания берётся только из записи `approve` (команда недоступна роли);
- последний `ANSWER-n`, счёт ANSWER, проверки мандатов, `_spec_gate_reasons` и прежние решения `reject --decision` не меняются от наличия указания;
- без `--note` — зелёные без правки: `tests/test_cmd_approve_dispatch.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_main_ci_line.py`, тесты брифа test_author (`tests/test_brief.py`, `tests/test_long_lived_manifest.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`), пакета ревьювера (`tests/test_task_component_places.py`, `tests/test_review_package_map.py`), реестра справки, тесты `reject --decision`.

Безопасность тестов: временная песочница пульта (`config` подменён), временная БД; никогда настоящая БД и репозиторий пульта.

Зоны: `orchestrator/fsm.py`, `orchestrator/artel.py` (флаг, разбор, справка), `orchestrator/brief.py` (функция указания и раздел брифа test_author), `orchestrator/review.py` (часть пакета ревьювера), `orchestrator/role_prompt.py` (если раздел подключается там), `docs/operator-gates.md`, `docs/codebase-map.md`, `tests/` (долгоживущие файлы задачи).

Приложением: `skills/test-authoring.md`, `skills/review-checklist.md`.

Только чтение: `orchestrator/answer.py`, `orchestrator/advance_gates/mandate.py`, `orchestrator/spec_gate_decision.py`, `orchestrator/store.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/fsm_advance.py`, `orchestrator/config.py`, `scripts/guard.py`.

Не входит:
- указание другим ролям (у разработчика есть `answer` в `in_dev`) и на других гейтах;
- изменение `answer` на `spec_gate` и `reject --decision`;
- проверка содержания указания аудитором SPEC (его проверяет независимый проверяющий Оператора до `approve`);
- файл указания в `tasks/<id>/` и правка `scripts/guard.py`.
- правка `docs/operator-session.md` (правило «Замечание к SPEC» дополнит Оператор после мержа).

Порядок: задача 01M6KB0SJHDA4D4GNEM7PGZ40P (возврат с гейта SPEC файлом решения) смержена (`b0c4f8b2`); факты сверены с `origin/main` 32ec975d.

Приоритет 2. Рамка: $45. Набор моделей — по умолчанию.
