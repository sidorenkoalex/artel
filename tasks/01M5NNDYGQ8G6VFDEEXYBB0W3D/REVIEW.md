---
task: 01M5NNDYGQ8G6VFDEEXYBB0W3D
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Сведение тестов, волна 1а — тесты копилки, бэклога и окна тишины в `tests/test_notes_module.py`

## Фаза A — план

- Таблица покрытия PLAN закрывает требования 1–10; требование 11 отнесено к сессии при Операторе.
- Раздел PLAN «Возврат из merge_gate (24.10)» описывает причину возврата и правку. Правка совпадает с фактическим diff `7ea8ae48..6dee632d`: новый помощник `silence_origin_backlog` и 4 вызова, больше ничего в `tests/`.
- «Влияние на систему» соответствует diff ветки: D×4, A `tests/test_notes_module.py`, M `docs/codebase-map.md`. Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: 72 патча подряд, по одному хунку в `orchestrator/`, сопоставление всех 80 тестов есть. |
| 2 | OK | Таблицы «до» (части 1-24, 25-48, 45-72) не менялись. Находка по первой редакции 045 записана. |
| 3 | OK | Стиль pytest сохранён. Новый помощник `silence_origin_backlog` — функция модуля с `assert`, а не фикстура (ADR-0027 п. 3). |
| 4 | OK | Это и есть предмет итерации. Исходный `NoteSilenceSandbox.origin_backlog` читал литерал `f"{config.MAIN_BRANCH}:docs/backlog.md"`; теперь так же читает `silence_origin_backlog` (`tests/test_notes_module.py:269-272`). Все 4 вызова со стендом `silence_box` переведены на него (`:970`, `:989`, `:1007`, `:1047`). `origin_backlog` с `notes.BACKLOG_REL` остался только у `apply_box`, как в исходном `ApplySandbox.origin_backlog`. Ассерты не менялись, литералы тоже. Источник пути в фикстурах совпадает с исходниками: `silence_box` и `window_box` пишут литерал, `apply_box` — `BACKLOG_REL`. |
| 5 | OK | Дублей не удалено. |
| 6 | OK | Строка «Ловит мутацию:» есть у всех 80 функций; новый помощник — не тест. |
| 7 | OK | Таблицы «после» сняты на 7ea8ae48. На HEAD 6dee632d изменились только тела четырёх тестов: путь чтения origin. `orchestrator/` в 549e997e и HEAD одинаков. Ни один из 72 патчей не переопределяет `BACKLOG_REL`: `grep '^[-+].*BACKLOG_REL *='` по патчам пуст, имя встречается только в строках контекста. Поэтому для этих 4 тестов исходы мутаций при смене `BACKLOG_REL` → литерал не меняются. Перепроверку на новой голове ведёт сессия при Операторе (требование 11), это честно записано в PLAN. |
| 8 | OK | Без изменений. |
| 9 | OK | Четыре файла удалены по мандату ANSWER-1. |
| 10 | OK | `tests/fixtures.py`, `tests/sandbox.py`, `orchestrator/` не изменены (см. «Проверено исполнением»). |
| 11 | вне роли | Повтор `mutation-run` сессией при Операторе до approve на merge_gate. |

## Замечания

Замечаний уровня blocker, major и minor нет. Причина возврата из merge_gate устранена целиком: ни одного вызова `origin_backlog` со стендом `silence_box` не осталось.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved. Мерж по-прежнему ждёт независимой проверки мутаций при Операторе (требование 11) на голове 6dee632d.

## Проверено исполнением

- `git diff 7ea8ae48 6dee632d -- tests/` — добавлен `silence_origin_backlog`, 4 замены вызова в `test_window_ac5/ac6/ac7/ac8_closed`, других изменений нет.
- `grep -n "origin_backlog(" tests/test_notes_module.py` — со `silence_box` зовётся только `silence_origin_backlog`, `origin_backlog` — только с `apply_box`.
- `git diff --quiet 549e997e HEAD -- orchestrator/ tests/fixtures.py tests/sandbox.py` — код 0.
- `git diff --name-status 549e997e...HEAD` — M `docs/codebase-map.md`, D×4, A `tests/test_notes_module.py`.
- `grep '^[-+].*BACKLOG_REL *=' mutation-*.diff` — пусто: ни один патч не меняет определение `BACKLOG_REL`.
- `grep -c "^def test_"` — 80; `wc -l` — 1798 (как в PLAN).
- `python3 -m pytest tests/test_notes_module.py -q -p no:cacheprovider -p timeout -o timeout=120` — 99 passed in 17.96s.
- `artel.py plank-run 01M5NNDYGQ8G6VFDEEXYBB0W3D` — 26 passed in 3.83s, код выхода pytest 0.

## Предложения системе

- Сверку «путь/литерал помощника = как в исходнике» ревью итерации 1 пропустило: эквивалентность значений (`BACKLOG_REL == "docs/backlog.md"`) — не то же, что дословный перенос, ведь мутация константы тогда перестаёт ловиться. Стоит добавить в `skills/review-checklist.md` для задач свода: литералы помощников и фикстур сверяются с исходником текстуально, а не по значению.
