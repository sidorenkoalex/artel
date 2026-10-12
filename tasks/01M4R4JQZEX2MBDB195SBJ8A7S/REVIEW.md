---
task: 01M4R4JQZEX2MBDB195SBJ8A7S
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Мандат Оператора на правку существующего теста — на гейте SPEC

## Фаза A — план
- Таблица покрытия полна: требования 1–4 → шаг 1, требование 5 → долгоживущие
  `tests/test_01m4r4jqzex2mbdb195sbj8a7s_*.py` (SPEC прямо разрешает не дублировать).
- Один шаг размера MR (~80 строк кода + справка) — адекватно монолиту из SPEC.
- Подход повторно использует `_read_checked_answer_file`/`_matrix_problems`/
  `_commit_answer` и вход `cmd_answer` под `lease.run_locked` — с архитектурой
  не конфликтует. «Влияние на систему» совпадает с diff (3 файла + карта).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/answer.py:216-244` `_spec_gate_answer_text`: зоны/зависимости распознаются `mandate.elements` с маркерами `_ZONES_MANDATE_MARKER`/`MERGE_AFTER_MANDATE_MARKER` (те же, что в `mandate.MANDATE_MARKERS`), отказ раньше `_read_checked_answer_file`; файл без строки мандата тестов — отказ со словом reject. Голый маркер без элементов идёт дальше и отказывается `mandate.refusals` — разумно, комментарий это объясняет. |
| 2 | OK | Рубеж `runner.in_role_environment()` до чтения файла тем же `_ROLE_ENV_REFUSAL` (`answer.py:402-403`); `_instruction_text` возвращает `None` вне `in_dev`/`review`, поэтому `spec_gate` идёт под `lease.run_locked` (`answer.py:288-289`); состояние не меняется; журнал «ANSWER создан (мандат на ослабление тестов: …)» без «ждёт approve». |
| 3 | OK | ANSWER коммитится общим `_commit_answer` в ссылку документов + `record_fixation`; рубежи читают все ANSWER ссылки — подтверждено AC-6 (включая reject + автокоммит аналитика). |
| 4 | OK | `orchestrator/artel.py` (справка `answer`) и `docs/operator-session.md:209-220`: аудит → мандат → approve, sha после мандата или голый approve, перечитать после reject. Планка AC-8 зелёная. |
| 5 | OK | Покрыто долгоживущими тестами задачи; свои тесты разработчик не дублировал. |

## Замечания

Нет blocker/major/minor.

Наблюдение без замечания: `merge_deps` в ветке `spec_gate` остаётся `None`
(строка зависимостей отказывается раньше), поэтому `merge_after` на гейте SPEC
не трогается — как требует AC-3.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4r4jqzex2mbdb195sbj8a7s_answer_spec_gate.py tests/test_01m4r4jqzex2mbdb195sbj8a7s_spec_gate_mandate_flow.py` — 10 passed, 47 subtests passed (39 с).
- `artel.py plank-run 01M4R4JQZEX2MBDB195SBJ8A7S` — 2 passed, код выхода pytest 0.
- Временная мутация: детектор строк зон/зависимостей в `_spec_gate_answer_text` заменён на `line.startswith(marker)` без учёта отступа → `-k ac3` красный (24 подтеста упали на вариантах с отступом); код возвращён `git checkout`, дерево чистое.
- `python3 scripts/codebase_map.py` → расхождение только в `built_at_sha` — карта свежа по содержимому; изменение откачено.
- CI коммита 9b662107 зелёный (16 проверок, из пакета).
- `git diff 8543e24e...HEAD --stat`: `tests/` в diff кода не тронут (кроме залоченных долгоживущих файлов задачи) — существующие тесты не ослаблены.

## Предложения системе
- Долгоживущие файлы задачи на CI идут ~90 с при пороге 60 с (локально оба — 39 с суммарно); предупреждение порога стоит сопоставлять с локальным временем перед выводами о тяжести песочницы.
