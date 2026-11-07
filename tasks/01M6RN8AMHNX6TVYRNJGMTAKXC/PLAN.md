---
task: 01M6RN8AMHNX6TVYRNJGMTAKXC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Служебная строка коммитов пульта по записи проекта: policy.commit_trailer

## Подход
Поле `commit_trailer` добавляется в `targets.LOCAL_FIELDS["policy"]` (необязательное)
и в `DELIVERY_POLICY_FIELDS` — тогда `_flatten` переносит его в сведённую запись,
включая пустую строку. Проверка формы — в `targets._check_delivery` рядом с
`co_author`: допустимо ровно `""` либо одна строка, полностью совпадающая с
`[A-Za-z0-9-]+: .*\S.*` без `\n`/`\r`; всё прочее — `refuse("commit_trailer", …)`,
текст которого содержит `policy.commit_trailer`.
`gitcmd.pult_message` берёт `entry.get("commit_trailer", PULT_ACTOR_TRAILER)`:
отсутствие поля даёт прежний побайтно текст; пустое значение — строки нет, а
если нет и `co_author`, абзац не добавляется (сообщение — `message.rstrip("\n") + "\n"`).
`target-set` правит любое поле `LOCAL_FIELDS` — отдельной правки `projects.py` не нужно.

## Шаги
1. `orchestrator/targets.py`: поле в `LOCAL_FIELDS`/`DELIVERY_POLICY_FIELDS`, проверка в `_check_delivery`.
2. `orchestrator/gitcmd.py`: `pult_message` читает поле записи.
3. Регенерация `docs/codebase-map.md`; прогон долгоживущего теста, планки, тестов `targets`/`gitcmd`/rewrite_flow.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 1 (штатный `target-set` по `LOCAL_FIELDS`) |
| 7 | 3 |

## Влияние на систему
Без поля поведение `pult_message` побайтно прежнее (умолчание `PULT_ACTOR_TRAILER`
не тронуто); слой репозитория и `snapshot.py` не меняются. Ни один гейт, тест
или лимит не ослабляется — добавляется новая проверка. Откат — revert одного
merge-коммита.

## Риски
`gitcmd._project_entry` глотает `TargetsError`: запись с негодным полем даст
прежнюю строку `Artel-Actor`, но такой отказ виден на загрузке (`doctor`, `target-set`).

## Предложения системе
