---
task: 01M6EZXVFG405Y1BTFDSGBKS8E
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab Б2.3-4: открытие gitlab и target-human, тексты отказа, порядок при инциденте

## Подход
Поддержка решается парой (`forge`, `merge_gate`), а не двумя независимыми
кортежами: в `orchestrator/targets.py` добавлена константа
`SUPPORTED_PAIRS = {("github", "operator"), ("gitlab", "target-human")}`,
кортежи `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` расширены до значений
требования 2 (остаются как перечень исполняемых значений, решения по ним
код больше не принимает). `unsupported_reason` для пары вне множества
отдаёт единый текст
`гейт мержа <gate> не поддержан для хостинга <forge> (поддержаны: <пары sorted через ", ">)`
— без «адаптера нет» и без префикса «проект <имя>: » (его ставят
вызывающие `catalog.py`/`runner.py`/`doctor/cli.py`, они не меняются).
`orchestrator/forge.py` не тронут.

Сторож А0 правится строго в рамках мандата ANSWER-1 и требования 6:
значения `GITLAB_REASON`/`TARGET_HUMAN_REASON`; в ac1 — параметр
`gitlab` + `target-human` → None и точное равенство трёх констант; в ac7 —
четвёртая запись `gitlab` + `target-human` (`ok`); ac8 параметризован по
двум поддержанным парам. Новых узлов верхнего уровня нет, `UNSUPPORTED`,
`UNSUPPORTED_IDS`, ac2–ac6, ac9, `EXEMPT` побайтно прежние, все `assert`
ac7/ac8 сохранены дословно.

Новый документ `docs/incident-external-project.md`: остановка задач
проекта, отзыв токена, срез журнала задачи, ссылка на MR — команды пульта
(`pause --now`, `pause`, `kill`, `log`, `show`, `docs`, `doctor`) сверены
с диспетчером `orchestrator/artel.py`; данных проектов нет.

## Шаги
1. `orchestrator/targets.py`: `SUPPORTED_PAIRS`, новые значения кортежей,
   решение `unsupported_reason` по паре и новый текст причины.
2. Сторож А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`:
   две константы и три теста мандата (ac1, ac7, ac8); заявки «Ловит
   мутацию» обновлены.
3. `docs/incident-external-project.md`.
4. Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (текст без «адаптера нет», forge.py не меняется) | 1 |
| 2 (константы, SUPPORTED_PAIRS, три пары) | 1 |
| 3 (точный текст, без префикса, один префикс у вызывающих) | 1 |
| 4 (документ порядка при инциденте) | 3 |
| 5 (сторож А0, условия (а)–(г)) | 2 |
| 6 (сохраняемые утверждения сторожа) | 2 |
| AC-7 (github + operator прежнее, прочие tests/ не тронуты) | 1, 2 |

Проверка в шаге:
- `python3 -m pytest` сторожа А0, долгоживущего
  `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py`, и тестов,
  подменяющих кортежи поддержки (`test_awaiting_human_units.py`,
  `test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py`,
  `test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`,
  `test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`) — 129 passed. Это
  подтверждает чтение аналитика: последние два заводят задачи прямой
  вставкой в БД и до `unsupported_reason` не доходят.
- `test_epic_draft_promote_unsupported_project.py` (берёт причину из
  `unsupported_reason` динамически), `test_multitarget.py`,
  `test_01m4s24963r9h18an2xdp6r15b_targets_field.py`,
  `test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py` — зелёные.
- `plank-run 01M6EZXVFG405Y1BTFDSGBKS8E` — 19 passed, включая
  мутационные прогоны сторожа А0 по условиям (а)–(г): каждый тест
  мандата краснеет на своей мутации.

## Влияние на систему
- Открываются две пары: задачи `gitlab` + `target-human` теперь проходят
  `new`/`run`/`auto`/`approve`. Пара `gitlab` + `operator` и `github` +
  `target-human` остаются закрытыми — переход на явное множество пар
  строже прежней проверки по кортежам (иначе расширение кортежей открыло
  бы все четыре сочетания).
- Сторож А0 не ослаблен: мандат ANSWER-1 и матрица неослабления;
  константы проверяются точным равенством (было — тоже равенство, но
  старых значений), добавлены поддержанная пара в ac1/ac7/ac8; отказ
  ac2–ac6 по-прежнему проверяется на обеих неподдержанных парах. Сторож
  ac9 (литералы вне `targets.py`) не тронут и зелёный.
- Вызывающие `unsupported_reason` не меняются; их префикс «проект <имя>: »
  встречается в выводе один раз (долгоживущий тест задачи).
- Откат — revert одного merge-коммита задачи.

## Риски
- Тексты причин зашиты в двух тестовых файлах (сторож А0 и долгоживущий
  файл задачи): смена `SUPPORTED_PAIRS` в будущем потребует правки обоих
  под мандатом — это намеренно (точное равенство, условие (г)).

## Предложения системе
- `docs/incident-external-project.md` ссылается на команды пульта текстом;
  сторожа соответствия команд документа диспетчеру `artel.py` нет —
  переименование команды молча устареет документ (класс «документ команд
  без сверки с диспетчером»).
