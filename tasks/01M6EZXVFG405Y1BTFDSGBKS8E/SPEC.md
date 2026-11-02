---
task: 01M6EZXVFG405Y1BTFDSGBKS8E
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/forge.py, docs/incident-external-project.md, tests/
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
(`:299`), а `forge._hosting` (`orchestrator/forge.py:184`) — текстом
«…: адаптера нет», хотя адаптер GitLab уже есть
(`forge.IMPLEMENTATIONS`, `orchestrator/forge.py:163`). Сторож поддержки —
`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` (А0).

## Требования
1. Тексты отказа не утверждают отсутствие адаптера для хостинга, у
   которого адаптер есть: ни `targets.unsupported_reason`, ни
   `forge._hosting` не выдают текста с «адаптера нет». Причина называет
   действительное: неподдержанный гейт мержа для хостинга (п. 2) либо
   хостинг вне списка реализованных (`forge._hosting`; в
   `orchestrator/forge.py` меняется только этот текст).
2. Открытие: `SUPPORTED_FORGES = ("github", "gitlab")`,
   `SUPPORTED_MERGE_GATES = ("operator", "target-human")`.
   `unsupported_reason` решает по явному множеству поддержанных пар
   (`forge`, `merge_gate`) — именованная константа модуля
   `orchestrator/targets.py` `SUPPORTED_PAIRS`, равная
   `{("github", "operator"), ("gitlab", "target-human")}`; пара вне
   множества — неподдержана.
   - Запись `github` + `target-human` читается как сейчас (загрузка
     записи не отказывает), а действия `new`/`run`/`auto`/`approve`
     отказывают с причиной ровно
     «гейт мержа target-human не поддержан для хостинга github».
   - Запись `gitlab` + `operator` остаётся неподдержанной с причиной ровно
     «гейт мержа operator не поддержан для хостинга gitlab» (свой мерж и
     отправка `base` внешнего проекта на GitLab не проверены).
   - Запись `gitlab` + `target-human` поддержана: `unsupported_reason`
     возвращает None, действия не отказывают по поддержке.
3. Новый документ `docs/incident-external-project.md` — порядок действий
   при инциденте внешнего проекта (ADR-0029 п. 14): отзыв токена, срез
   журнала задачи, ссылка на MR, остановка задач проекта. Без данных
   конкретных проектов (имён, адресов, токенов, слотов реальных
   проектов).
4. Сторож А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`
   обновляется по мандату Оператора на условиях:
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
     точным равенством.
   Тест `test_ac9_no_support_literals_outside_targets` и его `EXEMPT` не
   меняются.

## Критерии приёмки

AC-1. Для записи `gitlab` + `target-human` загрузка записи (`targets.target`) проходит без отказа, `targets.unsupported_reason` возвращает None, а `new` такой задачи не отказывает по поддержке проекта.

AC-2. Для записи `github` + `target-human` загрузка записи проходит без отказа, а `targets.unsupported_reason` возвращает ровно «гейт мержа target-human не поддержан для хостинга github»; действия `new`/`run`/`auto`/`approve` отказывают с этой причиной.

AC-3. Для записи `gitlab` + `operator` загрузка записи проходит без отказа, а `targets.unsupported_reason` возвращает ровно «гейт мержа operator не поддержан для хостинга gitlab»; действия `new`/`run`/`auto`/`approve` отказывают с этой причиной.

AC-4. В `orchestrator/targets.py` `SUPPORTED_FORGES == ("github", "gitlab")`, `SUPPORTED_MERGE_GATES == ("operator", "target-human")`, `SUPPORTED_PAIRS == {("github", "operator"), ("gitlab", "target-human")}`; ни один текст причины `unsupported_reason` ни для одной пары из `FORGES` × `MERGE_GATES` и текст причины `forge._hosting` для значения `forge` вне `forge.IMPLEMENTATIONS` не содержат «адаптера нет».

AC-5. Сторож А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` выполняет условия (а)–(г) требования 4 и зелёный; `test_ac9_no_support_literals_outside_targets` и `EXEMPT` побайтно совпадают с main и зелёные.

AC-6. `docs/incident-external-project.md` существует и описывает четыре действия: отзыв токена, срез журнала задачи, ссылку на MR, остановку задач проекта; в нём нет данных конкретных проектов.

AC-7. Для артели и проектов `github` + `operator` поведение прежнее: `unsupported_reason` возвращает None, существующие тесты `tests/` вне сторожа А0 не изменены.

## Оценка объёма и деление
Сигналов нет: четыре зоны, семь критериев, `budget_usd` 25 (рамка ТЗ
$25).

## Не входит
- Сверка MR по веб-хуку хостинга (бэклог).
- Исполнение `agent:*`/`script:*` в `verify` (C4).
- Правка `orchestrator/gitlab_adapter.py` и
  `docs/adr/0029-external-delivery-via-mr.md` — только чтение.
- Изменение в `orchestrator/forge.py` сверх текста `_hosting`.
- Изменение `test_ac9_no_support_literals_outside_targets` и `EXEMPT`.
- Полный зелёный набор `tests/` и CI ветки — их держит пульт.

## Материалы
- ТЗ: `tasks/01M6EZXVFG405Y1BTFDSGBKS8E/TZ.md`.
- Мандат на правку сторожа А0 дан в ANSWER-1 п. 3 родителя
  01M6EXF3TMNRKCZH8CS9BXXG1Z строкой
  `Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`.
  Рубеж неослабления читает мандат из ANSWER этой задачи: по ТЗ (п. 4)
  Оператор повторяет строку мандата, матрицу неослабления и строку
  независимой проверки в ANSWER этой задачи. Смена ожиданий сторожа —
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
  неподдержана при любой подмене кортежей. По чтению аналитика они
  заводят задачи прямой вставкой в БД и до `unsupported_reason`
  (`orchestrator/catalog.py:856`, `orchestrator/runner.py:184`) не
  доходят — разработчику стоит это подтвердить прогоном (AC-7).
