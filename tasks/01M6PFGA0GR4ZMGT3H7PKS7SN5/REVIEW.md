---
task: 01M6PFGA0GR4ZMGT3H7PKS7SN5
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Канарейка: синтетический ответ на батч вопросов аналитика ставит признак «батч отвечен»

## Фаза A — план
- Покрытие: требования 1–3 → шаги 1–2; таблица полна.
- Шаги размера MR: правка функции + сторож в `tests/`.
- «Риски» исправлены: сторожем после мержа названа
  `tests/test_canary_synthetic_answer_batch_mark.py`, а не разовая планка.
- «Влияние на систему» = diff: итерация 2 добавила только новый файл
  `tests/`; `fsm.py`, `fsm_advance.py`, `answer.py`,
  `tests/test_canary_synthetic_answer.py` не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/canary.py:1488-1493`: вызов `fsm._mark_questions_answered` после `answer.cmd_answer`/`store.get_task`, до `update_task`/`set_state`; условие как у approve (`fsm.py:1870`). |
| 2 | OK | Иные `escalated_from` и `answer_baseline = None` вызова не получают — планка AC-3 и подтесты сторожа зелёные. |
| 3 | OK | Остальное тело функции не изменено; докстринг дополнен. |

## Замечания

Нет. Сторож `tests/test_canary_synthetic_answer_batch_mark.py`:
заявки «Ловит мутацию» называют наблюдаемое расхождение (нет строки /
строка позже `state -> spec_writing` / строка в подтесте) и подтверждены
временными мутациями (см. ниже). Свойство в `tests/` не повторяет
долгоживущий файл задачи — такого файла нет (планка разовая).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/canary.py:1491-1493; tests/test_canary_synthetic_answer_batch_mark.py | Признак батча в канарейке закрыт только разовой планкой | Регрессия после мержа не ловилась бы CI | Закрыто: новый сторож в `tests/`; мутации «вызов удалён», «по истинности», «безусловный вызов» краснят его (проверено ревьювером); «Риски» PLAN исправлены |

## Вердикт
approved.

Наблюдение для Оператора (повтор итерации 1, не замечание разработчику):
планка помечена `Группа: разовый`, хотя проверяет свойство кода; пробел
со стороны сторожа закрыт тестом разработчика в `tests/`.

## Проверено исполнением
- `python3 -m pytest tests/test_canary_synthetic_answer_batch_mark.py
  tests/test_canary_synthetic_answer.py
  tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py -p no:cacheprovider`
  — 28 passed, 34 subtests passed.
- `artel.py plank-run 01M6PFGA0GR4ZMGT3H7PKS7SN5` — 7 passed, код выхода 0.
- Временные мутации `orchestrator/canary.py` (Edit), прогон только
  `tests/test_canary_synthetic_answer_batch_mark.py`:
  - `answer_baseline` по истинности — 1 failed
    (`test_first_escalation_…`);
  - условие `if True:` (безусловный вызов) — оба подтеста SUBFAILED
    (`in_dev/0`, `spec_writing/None`);
  - вызов заменён на `pass` — 1 failed (`test_first_escalation_…`).
  Код возвращён `git checkout -- orchestrator/canary.py`, `git status` чистый.
- `python3 scripts/codebase_map.py` — расхождений с закоммиченной картой
  нет (кроме, возможно, `built_at_sha`); файл возвращён.
- CI коммита 827a2478 — зелёный (16 проверок, по пакету).

## Предложения системе
- Повтор итерации 1: развести в skills/test-authoring.md запрет закрытых
  имён в долгоживущем файле планки и тесты разработчика в `tests/`.
