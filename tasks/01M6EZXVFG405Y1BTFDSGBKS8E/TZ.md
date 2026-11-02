---
task: 01M6EZXVFG405Y1BTFDSGBKS8E
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab Б2.3-4: открытие gitlab и target-human, тексты отказа, порядок при инциденте

Родительская задача: 01M6EXF3TMNRKCZH8CS9BXXG1Z — GitLab Б2.3: хук pre-push в клоне, сверки отправки, строки doctor, отказ при сбое, открытие gitlab и target-human
Зоны: orchestrator/targets.py, orchestrator/forge.py, docs/incident-external-project.md, tests/
Порядок: после части 1, части 2, части 3
Рамка: $25

Часть 4 из 4 деления задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3), идёт последней. Основание — ADR-0029 п. 14. Поддержку закрывают списки `targets.SUPPORTED_FORGES = ("github",)` и `SUPPORTED_MERGE_GATES = ("operator",)` (`orchestrator/targets.py:29-30`). Отказ формирует `targets.unsupported_reason` (`:283`) с текстом «адаптера нет (ADR-0029)» (`:299`, а также `forge._hosting`, `orchestrator/forge.py:184`), хотя адаптер GitLab уже есть. Сторож — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`.

Требуется:
1. Тексты отказа: для хостинга с адаптером в тексте нет «адаптера нет». Причина называет действительное: неподдержанный гейт мержа или хостинг вне списка (`orchestrator/forge.py` — только текст `_hosting`).
2. Открытие: `SUPPORTED_FORGES = ("github", "gitlab")`, `SUPPORTED_MERGE_GATES = ("operator", "target-human")`. `unsupported_reason` проверяет сочетание по явному множеству поддержанных пар `{("github", "operator"), ("gitlab", "target-human")}`.
   - Запись `github` + `target-human` читается как сейчас, а действия `new`/`run`/`auto`/`approve` отказывают с причиной «гейт мержа target-human не поддержан для хостинга github».
   - Запись `gitlab` + `operator` остаётся неподдержанной с причиной «гейт мержа operator не поддержан для хостинга gitlab»: свой мерж и отправка `base` внешнего проекта на GitLab не проверены.
3. Порядок действий при инциденте (ADR-0029 п. 14): новый `docs/incident-external-project.md` — отзыв токена, срез журнала задачи, ссылка на MR, остановка задач проекта. Без данных конкретных проектов.
4. Сторож А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` обновляется по мандату Оператора 26.10 на тесты, которые меняет ADR-0029 (ответ ANSWER-1 п. 3 задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z, с матрицей неослабления и независимой проверкой), на условиях:
   - (а) сторож закрепляет точное равенство кортежей `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` и множества поддержанных пар, а не только членство;
   - (б) отказ ac2–ac7 по-прежнему проверяется на обеих неподдержанных парах (`gitlab` + `operator`, `github` + `target-human`), до клона, git, агента и слияния;
   - (в) ac1 и ac7 — на обеих поддержанных парах, ac8 (`new` не отказывает) — в том числе на `gitlab` + `target-human`;
   - (г) тексты причин двух неподдержанных пар различимы и сверяются точно.
   Тест ac9 и его `EXEMPT` не меняются.
   Мандат дан в ANSWER-1 родителя строкой `Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`. Рубеж неослабления читает мандат из ANSWER этой задачи, поэтому Оператору нужно повторить строку мандата, матрицу и строку независимой проверки в ANSWER этой задачи.

Критерии приёмки:
- загрузка `gitlab` + `target-human` проходит без отказа; `github` + `target-human` и `gitlab` + `operator` получают отказ действий с причиной; в тексте отказа нет «адаптера нет»;
- сторож А0 выполняет условия (а)–(г); тест ac9 и `EXEMPT` не изменены и зелёные;
- `docs/incident-external-project.md` описывает четыре действия и не содержит данных конкретных проектов;
- артель и проекты `github` + `operator`: поведение и существующие тесты прежние.

Только чтение: `orchestrator/gitlab_adapter.py`, `docs/adr/0029-external-delivery-via-mr.md`.

Не входит: сверка MR по веб-хуку хостинга (бэклог); исполнение `agent:*`/`script:*` в `verify` (C4).