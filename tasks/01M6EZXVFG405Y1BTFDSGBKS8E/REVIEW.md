---
task: 01M6EZXVFG405Y1BTFDSGBKS8E
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab Б2.3-4: открытие gitlab и target-human, тексты отказа, порядок при инциденте

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–6 и AC-7 → шаги 1–3; шаг 4 — регенерация карты.
- Шаги размера MR (код, сторож, документ), не микрооперации.
- Подход (решение по явному множеству пар) не конфликтует с архитектурой: вызывающие
  `unsupported_reason` (`catalog.py`, `runner.py`, `doctor/cli.py`) не тронуты, префикс
  «проект <имя>: » ставят они (`git diff --stat c57c39382 -- orchestrator/forge.py
  orchestrator/catalog.py orchestrator/runner.py orchestrator/doctor/` — пусто).
- «Влияние на систему» = diff: три файла (`targets.py`, сторож А0, новый документ) плюс карта.
  Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/targets.py:296-302` — единый текст без «адаптера нет»; `forge.py` не изменён (diff пуст). |
| 2 | OK | `targets.py:31-33` — кортежи и `SUPPORTED_PAIRS` ровно по SPEC; `:298` решение по паре. github+target-human и gitlab+operator отказывают, gitlab+target-human → None (долгоживущий `test_ac1_*`, `test_ac2_*`, `test_ac3_*`). |
| 3 | OK | `targets.py:300-302` — `sorted(SUPPORTED_PAIRS)`, формат `<forge> + <gate>` через `, `, без префикса; тексты двух пар совпадают с SPEC побайтно (сверено в долгоживущем `test_ac4_reason_text_*` и в сторожe). Одинарный префикс в выводе `new/run/auto/approve` — `check_refusal` долгоживущего файла. |
| 4 | OK | `docs/incident-external-project.md` — четыре раздела (остановка, отзыв токена, срез журнала, ссылка на MR); имён/адресов/токенов реальных проектов нет. Команды `status`, `board`, `pause [--now]`, `kill`, `log`, `show`, `docs`, `doctor`, `resume` есть в диспетчере `orchestrator/artel.py` (2363, 2617-2701). |
| 5 | OK | (а) ac1 — точное равенство трёх констант; (б) ac2–ac7 на обеих неподдержанных парах (`UNSUPPORTED` прежний); (в) ac1/ac7 — обе поддержанные пары, ac8 параметризован по `github+operator`, `gitlab+target-human`; (г) `GITLAB_REASON`/`TARGET_HUMAN_REASON` различимы, сверка `==`. |
| 6 | OK | AST-сверка узлов верхнего уровня с базой `c57c39382`: изменены только `GITLAB_REASON`, `TARGET_HUMAN_REASON`, `test_ac1_*`, `test_ac7_*`, `test_ac8_*`; `UNSUPPORTED`, `UNSUPPORTED_IDS`, ac2–ac6, ac9, `EXEMPT` побайтно прежние; узлов не добавлено/не удалено. Удалённые `assert` — только два старых равенства кортежей ac1, заменены более строгими (три равенства). Утверждения ac7/ac8 сохранены. |
| AC-7 | OK | Долгоживущий `test_ac7_artel_and_github_operator_supported`; тесты вне сторожа А0 не изменены (diff трогает один файл `tests/`). Тесты, подменяющие кортежи, зелёные. |

Тесты: заявки «Ловит мутацию» в изменённых ac1/ac7/ac8 называют наблюдаемое расхождение (решение по кортежам вместо пар → неподдержанная пара вернёт None; выпадение пары из `SUPPORTED_PAIRS` → `new` откажет). Мандат ANSWER-1 покрывает все изменённые методы; гейт исходов — «покрыто мандатом ANSWER-1» по каждому. Долгоживущее свойство «решение по паре» держит `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py` (в `tests/`, не только в планке). Код не заточен под литералы планки — общее правило по множеству.

## Замечания
Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M6EZXVFG405Y1BTFDSGBKS8E` — 19 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider` по файлам: сторож А0, `test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py`, `test_awaiting_human_units.py`, `test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py`, `test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`, `test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`, `test_epic_draft_promote_unsupported_project.py` — 131 passed.
- AST-сравнение узлов верхнего уровня сторожа А0 с `git show c57c39382:<файл>`: изменены ровно 5 узлов из разрешённых; `git diff … | grep assert` — удалены только два старых равенства кортежей.
- `grep` диспетчера `orchestrator/artel.py` — все команды документа существуют; `grep SUPPORTED_*` по `orchestrator/` — решения по кортежам вне `targets.py` нет (единственное упоминание — докстринг `artel.py:2410`, остаётся верным).

## Предложения системе
- Поддерживаю наблюдение PLAN: документы с командами пульта (`docs/incident-external-project.md`) не сверяются с диспетчером `artel.py` — кандидат на общий сторож «команды в docs существуют».
