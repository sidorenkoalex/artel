---
task: 01M6EZXVFG405Y1BTFDSGBKS8E
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, docs/incident-external-project.md, tests/
merge_after: 01M6EZXVFGXC6WBDA9QJESAZRW, 01M6EZXVFGCHB1S4W45AWJ0QH6, 01M6EZXVFGH5Z2876XWMQG35FP
budget_usd: 25
---

# SPEC: GitLab Б2.3-4: открытие gitlab и target-human, тексты отказа, порядок при инциденте

## Контекст
Часть 4 из 4 деления задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3), идёт
последней (после частей 1–3: 01M6EZXVFGXC6WBDA9QJESAZRW,
01M6EZXVFGCHB1S4W45AWJ0QH6, 01M6EZXVFGH5Z2876XWMQG35FP). Основание —
ADR-0029 п. 14. Сегодня поддержку закрывают
`targets.SUPPORTED_FORGES = ("github",)` и
`SUPPORTED_MERGE_GATES = ("operator",)` (`orchestrator/targets.py:29-30`);
отказ формирует `targets.unsupported_reason` (`orchestrator/targets.py:283`)
текстом «хостинг gitlab не поддержан: адаптера нет (ADR-0029)»
(`:299`), хотя адаптер GitLab уже есть (`forge.IMPLEMENTATIONS`,
`orchestrator/forge.py:163`). Текст «адаптера нет» в `forge._hosting`
(`orchestrator/forge.py:184`) верен — он относится к хостингу вне
`forge.IMPLEMENTATIONS` — и не меняется (решение Оператора на гейте SPEC).
Сторож поддержки —
`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` (А0).

## Требования
1. Текст отказа `targets.unsupported_reason` не утверждает отсутствие
   адаптера: для неподдержанной пары ни один текст причины не содержит
   «адаптера нет». Причина называет действительное — неподдержанный гейт
   мержа для хостинга (п. 2). Меняется только `targets.unsupported_reason`;
   `orchestrator/forge.py` не меняется.
2. Открытие: `SUPPORTED_FORGES = ("github", "gitlab")`,
   `SUPPORTED_MERGE_GATES = ("operator", "target-human")`.
   `unsupported_reason` решает по явному множеству поддержанных пар
   (`forge`, `merge_gate`) — именованная константа модуля
   `orchestrator/targets.py` `SUPPORTED_PAIRS`, равная
   `{("github", "operator"), ("gitlab", "target-human")}`; пара вне
   множества — неподдержана.
   - Запись `github` + `target-human` читается как сейчас (загрузка
     записи не отказывает), а действия `new`/`run`/`auto`/`approve`
     отказывают с причиной «гейт мержа target-human не поддержан для
     хостинга github» (полный текст — п. 3).
   - Запись `gitlab` + `operator` остаётся неподдержанной с причиной
     «гейт мержа operator не поддержан для хостинга gitlab» (свой мерж и
     отправка `base` внешнего проекта на GitLab не проверены; полный
     текст — п. 3).
   - Запись `gitlab` + `target-human` поддержана: `unsupported_reason`
     возвращает None, действия не отказывают по поддержке.
3. Текст причины `unsupported_reason` для неподдержанной пары называет
   значение `forge`, значение `merge_gate` и перечень поддержанных пар и
   НЕ начинается с префикса «проект <имя>: » — проект называет
   вызывающий, который уже ставит этот префикс сам
   (`orchestrator/catalog.py:858`, `orchestrator/runner.py:188-189`,
   `orchestrator/doctor/cli.py:44`; решение Оператора на гейте SPEC).
   Текст ровно в виде
   `гейт мержа <merge_gate> не поддержан для хостинга <forge> (поддержаны: github + operator, gitlab + target-human)`,
   где `<merge_gate>` и `<forge>` — значения полей записи, а перечень —
   пары `SUPPORTED_PAIRS` в порядке `sorted(SUPPORTED_PAIRS)`, каждая как
   `<forge> + <merge_gate>`, через `, `. Для двух неподдержанных пар
   тексты:
   - `github` + `target-human`: `гейт мержа target-human не поддержан для хостинга github (поддержаны: github + operator, gitlab + target-human)`;
   - `gitlab` + `operator`: `гейт мержа operator не поддержан для хостинга gitlab (поддержаны: github + operator, gitlab + target-human)`.
   Вывод действий `new`/`run`/`auto`/`approve` и подробность строки
   `doctor` несут эту причину после префикса вызывающего
   `проект <имя>: ` ровно один раз (без удвоения «проект <имя>: проект
   <имя>: »).
4. Новый документ `docs/incident-external-project.md` — порядок действий
   при инциденте внешнего проекта (ADR-0029 п. 14): отзыв токена, срез
   журнала задачи, ссылка на MR, остановка задач проекта. Без данных
   конкретных проектов (имён, адресов, токенов, слотов реальных
   проектов).
5. Сторож А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`
   обновляется по мандату Оператора на три теста (не на файл целиком;
   перечень — раздел «Существующие тесты сторожа А0») на условиях:
   - (а) закрепляет точное равенство кортежей `SUPPORTED_FORGES`,
     `SUPPORTED_MERGE_GATES` и множества поддержанных пар
     `SUPPORTED_PAIRS`, а не только членство;
   - (б) отказ ac2–ac7 проверяется на обеих неподдержанных парах
     (`gitlab` + `operator`, `github` + `target-human`) — до клона, git,
     агента и слияния, как сейчас;
   - (в) ac1 и ac7 — на обеих поддержанных парах (`github` + `operator`,
     `gitlab` + `target-human`); ac8 (`new` не отказывает) — в том числе
     на `gitlab` + `target-human`;
   - (г) тексты причин двух неподдержанных пар различимы и сверяются
     точным равенством с полным текстом п. 3 для каждой пары.
   Тест `test_ac9_no_support_literals_outside_targets` и его `EXEMPT` не
   меняются.
6. Сохраняемые утверждения сторожа А0. Правка сторожа меняет только:
   значения строковых констант модуля `GITLAB_REASON` (пара `gitlab` +
   `operator`) и `TARGET_HUMAN_REASON` (пара `github` + `target-human`) —
   на тексты п. 3 без префикса; а под мандатом — три теста раздела
   «Существующие тесты сторожа А0» (`test_ac1_…`, `test_ac7_…`,
   `test_ac8_…`): их параметризацию/набор записей поддержанных пар и
   утверждения о константах поддержки в ac1 (`:165-166`). Список
   `UNSUPPORTED` (пары `gitlab` + `operator`, `github` + `target-human`,
   их порядок и ссылки на эти две константы) и `UNSUPPORTED_IDS` не
   меняются; тесты ac2–ac6 (декораторы и тела) не меняются вовсе и
   остаются под рубежом неослабления. Следующие утверждения остаются в
   своём тесте в прежнем виде и прежней силе; их удаление, ослабление или
   смена вида запрещены и под мандатом:
   - `test_ac2_new_refuses_without_side_effects` (`:191-196`): код выхода
     ненулевой; причина в выводе; клон проекта не создан
     (`repo_context.clone_path(name).exists()` ложно); вызовов git нет
     (`git_calls(spy, start) == []`); таблицы `tasks` и `steps` не
     изменились;
   - `test_ac3_run_refuses_before_agent_and_git` (`:223-226`): причина в
     выводе; агент не запущен (`spawn.call_count == 0`); вызовов git нет;
     причина в журнале задачи (`journal_with(task_id, reason)`);
   - `test_ac4_auto_refuses_at_entry` (`:251-255`): причина в выводе;
     `advance` не вызван; агент не запущен; вызовов git нет; причина в
     журнале задачи;
   - `test_ac5_approve_on_merge_gate_refuses_before_merge` (`:283-286`):
     причина в выводе; слияний нет (`merges == []`); состояние задачи
     `merge_gate`; причина в журнале задачи;
   - `test_ac6_approve_on_spec_gate_refuses` (`:306-308`): причина в
     выводе; состояние задачи `spec_gate`; причина в журнале задачи;
   - `test_ac7_doctor_project_support_line` (`:374-379`): ровно одна
     строка поддержки проекта; `ok` для поддержанной пары, `fail` для
     неподдержанной; причина в подробности строки `fail`;
   - `test_ac8_supported_project_new_is_not_refused` (`:404-406`): код
     выхода 0; создана ровно одна задача с проектом `name`; в выводе нет
     «ADR-0029».

## Критерии приёмки

AC-1. Для записи `gitlab` + `target-human` загрузка записи (`targets.target`) проходит без отказа, `targets.unsupported_reason` возвращает None, а `new` такой задачи не отказывает по поддержке проекта.

AC-2. Для записи `github` + `target-human` загрузка записи проходит без отказа, `targets.unsupported_reason` возвращает ровно текст п. 3 требований для этой пары (`гейт мержа target-human не поддержан для хостинга github (поддержаны: github + operator, gitlab + target-human)`); действия `new`/`run`/`auto`/`approve` отказывают, и их вывод содержит `проект <имя>: гейт мержа target-human не поддержан для хостинга github (поддержаны: github + operator, gitlab + target-human)` с префиксом `проект <имя>: ` ровно один раз.

AC-3. Для записи `gitlab` + `operator` загрузка записи проходит без отказа, `targets.unsupported_reason` возвращает ровно текст п. 3 требований для этой пары (`гейт мержа operator не поддержан для хостинга gitlab (поддержаны: github + operator, gitlab + target-human)`); действия `new`/`run`/`auto`/`approve` отказывают, и их вывод содержит `проект <имя>: гейт мержа operator не поддержан для хостинга gitlab (поддержаны: github + operator, gitlab + target-human)` с префиксом `проект <имя>: ` ровно один раз.

AC-4. В `orchestrator/targets.py` `SUPPORTED_FORGES == ("github", "gitlab")`, `SUPPORTED_MERGE_GATES == ("operator", "target-human")`, `SUPPORTED_PAIRS == {("github", "operator"), ("gitlab", "target-human")}`; для каждой неподдержанной пары (`github` + `target-human`, `gitlab` + `operator`) текст `unsupported_reason` называет значение `forge`, значение `merge_gate` и перечень поддержанных пар, не начинается с `проект ` и точно равен тексту п. 3 требований для этой пары; ни один из этих текстов не содержит «адаптера нет».

AC-5. Сторож А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` выполняет условия (а)–(г) требования 5 и зелёный; относительно main изменены только значения констант `GITLAB_REASON`, `TARGET_HUMAN_REASON` и три теста раздела «Существующие тесты сторожа А0»; `UNSUPPORTED`, `UNSUPPORTED_IDS`, тесты ac2–ac6, `test_ac9_no_support_literals_outside_targets` и `EXEMPT` побайтно совпадают с main; утверждения требования 6 сохранены в своих тестах в прежнем виде.

AC-6. `docs/incident-external-project.md` существует и описывает четыре действия: отзыв токена, срез журнала задачи, ссылку на MR, остановку задач проекта; в нём нет данных конкретных проектов.

AC-7. Для артели и проектов `github` + `operator` поведение прежнее: `unsupported_reason` возвращает None, существующие тесты `tests/` вне сторожа А0 не изменены.

## Существующие тесты сторожа А0
Решение Оператора на гейте SPEC: мандат на ослабление/смену будет дан на
тесты поимённо, не на файл целиком.

Меняются под мандатом (только они):
- `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac1_entry_loads_and_reason_names_unsupported_value`
  — параметризация дополняется поддержанной парой `gitlab` +
  `target-human` (ожидание None); утверждения `:165-166` о кортежах
  заменяются точным равенством `SUPPORTED_FORGES`,
  `SUPPORTED_MERGE_GATES` и `SUPPORTED_PAIRS` значениям требования 2
  (условие (а)).
- `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac7_doctor_project_support_line`
  — набор записей дополняется поддержанной парой `gitlab` +
  `target-human` (`ok`) (условие (в)).
- `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac8_supported_project_new_is_not_refused`
  — `new` не отказывает в том числе на `gitlab` + `target-human`
  (условие (в)).

Не меняются вовсе и остаются под механикой рубежа неослабления:
`test_ac2_new_refuses_without_side_effects`,
`test_ac3_run_refuses_before_agent_and_git`,
`test_ac4_auto_refuses_at_entry`,
`test_ac5_approve_on_merge_gate_refuses_before_merge`,
`test_ac6_approve_on_spec_gate_refuses` и их параметры `UNSUPPORTED`/
`UNSUPPORTED_IDS` (пары `gitlab` + `operator`, `github` + `target-human`
прежние). Меняются только значения строковых констант модуля
`GITLAB_REASON` и `TARGET_HUMAN_REASON`, на которые ссылается
`UNSUPPORTED`, — на тексты требования 3.

`test_ac9_no_support_literals_outside_targets` (с `WATCHED_VALUES`,
`EXEMPT`) не меняется: его список литералов `WATCHED_VALUES` уже
содержит все четыре значения (`github`, `gitlab`, `operator`,
`target-human`), а новая проверка пар живёт в `targets.py`, который
сторож исключает (`SUPPORT_MODULE`) — правка ac9 не требуется.

## Оценка объёма и деление
Сигналов нет: три зоны, семь критериев, `budget_usd` 25 (рамка ТЗ
$25).

## Не входит
- Сверка MR по веб-хуку хостинга (бэклог).
- Исполнение `agent:*`/`script:*` в `verify` (C4).
- Любая правка `orchestrator/forge.py`, в том числе текста `_hosting`:
  «адаптера нет» там верно для хостинга вне `forge.IMPLEMENTATIONS`
  (решение Оператора на гейте SPEC).
- Правка `orchestrator/gitlab_adapter.py` и
  `docs/adr/0029-external-delivery-via-mr.md` — только чтение.
- Изменение `test_ac9_no_support_literals_outside_targets` и `EXEMPT`.
- Правка вызывающих `unsupported_reason` (`orchestrator/catalog.py`,
  `orchestrator/runner.py`, `orchestrator/doctor/cli.py`): их префикс
  «проект <имя>: » остаётся как есть — убирается только префикс из
  самой причины.
- Закрытие строки `docs/backlog.md:54` (п. 3, текст
  `unsupported_reason` для gitlab) — его делает Оператор после мержа, не
  задача.
- Полный зелёный набор `tests/` и CI ветки — их держит пульт.

## Материалы
- ТЗ: `tasks/01M6EZXVFG405Y1BTFDSGBKS8E/TZ.md`.
- Мандат на правку сторожа А0 дан в ANSWER-1 п. 3 родителя
  01M6EXF3TMNRKCZH8CS9BXXG1Z строкой
  `Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`.
  Рубеж неослабления читает мандат из ANSWER этой задачи: Оператор даст
  ANSWER этой задачи на `in_dev` — строку мандата на три теста раздела
  «Существующие тесты сторожа А0» (не на файл), матрицу неослабления
  и строку независимой проверки (решение на гейте SPEC). Мандат не
  распространяется на утверждения требования 6 и на тесты ac2–ac6, ac9. Смена ожиданий сторожа —
  кортежи и строковые константы модуля (`GITLAB_REASON`,
  `TARGET_HUMAN_REASON`), поэтому в раздел «Меняемое поведение» она не
  оформляется.
- Тесты, подменяющие `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES`
  (`tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`,
  `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`,
  `tests/test_awaiting_human_units.py`,
  `tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py`): последние
  два открывают `github` + `target-human` подменой одного
  `SUPPORTED_MERGE_GATES` — после перехода на `SUPPORTED_PAIRS` эта пара
  неподдержана при любой подмене кортежей. По чтению аналитика и аудитора
  они заводят задачи прямой вставкой в БД и до `unsupported_reason`
  (`orchestrator/catalog.py:856`, `orchestrator/runner.py:184`) не
  доходят — разработчику стоит это подтвердить прогоном (AC-7).
