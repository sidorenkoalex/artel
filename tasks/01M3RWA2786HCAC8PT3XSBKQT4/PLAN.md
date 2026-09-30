---
task: 01M3RWA2786HCAC8PT3XSBKQT4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Автогейт приёмки видит долгоживущие файлы планки

## Подход

В `orchestrator/fsm_autogate.py` соберу один источник текстов планки для автогейта и записи приёмки: разовые `*.py` из артефактной ветки, затем пути перечня из лока через `advance_gates.acceptance.long_lived_manifest` и тексты этих путей из головы кодовой ветки. Ошибку чтения названного долгоживущего файла верну отдельной причиной отказа с путём. Для задачи без перечня сохраню действующий сбор разовых файлов и текст отказа пустому каталогу.

## Шаги

1. Объединить источники в `orchestrator/fsm_autogate.py`, применять их к сканированию AC-пометок в обоих местах и различать пустой набор с ошибкой чтения файла перечня.
2. Проверить четыре сценария зафиксированным `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, добавить адресные юнит-тесты для непокрытых углов; прогнать существующий `tests/test_fsm_autogate.py` без правок, проверить заявленную мутацию своего теста и обновить карту кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1, AC-1 | 1, 2 |
| 2, AC-2 | 1, 2 |
| 3, AC-3 | 1, 2 |
| 4, AC-4 | 2 |

## Влияние на систему

Меняется только выбор входных текстов условия «а» автогейта и перечня пометок записи приёмки. Лок перечня, сверка SHA, сам прогон планки, порядок остальных условий автогейта, гейты и лимиты остаются прежними. Ошибка чтения долгоживущего файла даёт отказ, поэтому проверка не ослабляется. Откат — revert одного кодового коммита задачи; артефакт PLAN пульт переносит отдельно.

## Риски

Старые юнит-тесты автогейта используют строки задачи без поля `tests_locked_sha`; отсутствие поля нужно трактовать как отсутствие перечня, сохраняя прежний результат. Разовый файл, который не удаётся прочесть, пока обрабатывается прежним способом; новый именованный отказ касается записей перечня.

## Проверка

- `python3 -m pytest tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py tests/test_fsm_autogate.py tests/test_fsm_autogate_long_lived.py tests/test_long_lived_manifest.py tests/test_long_lived_transitions.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 52 passed, 20 subtests passed.
- Оба новых теста `tests/test_fsm_autogate_long_lived.py` покраснели каждый на своей временной мутации в `orchestrator/fsm_autogate.py`; код восстановлен.
- `python3 scripts/codebase_map.py` — карта обновлена; `git diff --check` — без ошибок; `python3 scripts/guard.py tasks/01M3RWA2786HCAC8PT3XSBKQT4/PLAN.md` — ок.

## Предложения системе

- Рабочий каталог роли допускает запись только внутри worktree, но индекс этого worktree лежит в `/Users/al.sidorenko/projects/artel/.git/worktrees/01M3RWA2786HCAC8PT3XSBKQT4/`: `git add orchestrator/fsm_autogate.py tests/test_fsm_autogate_long_lived.py docs/codebase-map.md` отказал с `index.lock: Operation not permitted`. Контракт `coding-standards` требует коммит разработчика; для такой раскладки нужна доступная ролью операция коммита или writable git metadata. Кодовый diff оставлен для штатного автокоммита пульта, который сам контракт называет аварийным исходом шага.
