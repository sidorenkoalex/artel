---
task: 01M5MHVFQ9SC6EDRH34F8THNQ3
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Одна функция открытия БД пульта только на чтение вместо пяти копий

## Подход
В `orchestrator/store.py` рядом с `db_usable` — функция `db_readonly(path=None, *, rows=True)`:
`path = config.DB if path is None else path` (читается в момент вызова), затем
`sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)` и при `rows` —
`row_factory = sqlite3.Row`. Ни проверки существования, ни перехвата исключений, ни `db()`.

Пять мест заменяют только строку(и) открытия соединения на вызов `store.db_readonly`
через атрибут модуля (`store.db_readonly(...)`, не `from … import db_readonly` — иначе
подмена шпионом в AC-6 не увидит вызов). Проверки `is_file()`, тексты отказов и `try/except`
остаются у вызывающих на прежнем месте: в `db_usable` и `scripts/test_rule_stats.journal`
вызов остаётся внутри `try … except sqlite3.Error`. Импорт `sqlite3` в вызывающих
остаётся там, где он ещё нужен (аннотации, `sqlite3.Error`, `sqlite3.Row`); в
`scripts/test_rule_stats.py` добавляется `from orchestrator import store`.
Промежуточная переменная `uri` в скрипте удаляется (SPEC «Не входит» это разрешает).

Свойства AC-1…AC-7 уже держат долгоживущие файлы test_author
(`tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py`, `…_db_readonly_callers.py`,
требование 4) — своих тестов не добавляю: непокрытых свойств не остаётся.

## Шаги
1. `store.db_readonly` + перевод `store.db_usable` (`rows=False`).
2. Перевод `knowledge_cards._open_db_readonly`, `suite_run._readonly_db`,
   `preflight._open_db_readonly`, `scripts/test_rule_stats.journal` (`path=db_path, rows=False`).
3. Регенерация `docs/codebase-map.md`; прогон долгоживущих файлов задачи и тестов
   затронутых модулей из списка SPEC «Не входит».

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 1, 2 |
| 4 | 3 (файлы test_author) |
| 5 | 2, 3 |

## Влияние на систему
Поведение не меняется: та же строка URI, те же флаги, те же места проверок и перехватов.
Новых ленивых импортов не появляется: `suite_run`, `preflight` уже импортируют `store`,
`knowledge_cards` — локально внутри функции (цикл импортов `store → … → knowledge_cards`
сохранён как был). Скрипт `test_rule_stats.py` начинает импортировать `orchestrator.store`
— тот тянет `config`, `session`, `schema`, побочных эффектов при импорте у них нет (БД не
открывается). Существующий тест `test_ac11_sqlite_connect_only_from_store` (connect только
из store) не ослабляется — напротив, вызовов `sqlite3.connect` вне store становится меньше.
Гейты/лимиты не трогаются. Откат — revert одного merge-коммита.

## Риски
- Вызов через `from orchestrator.store import db_readonly` обошёл бы шпиона AC-6 — везде
  вызов через атрибут модуля.

## Предложения системе
