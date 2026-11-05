---
task: 01M6PFGA0GR4ZMGT3H7PKS7SN5
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Канарейка: синтетический ответ на батч вопросов аналитика ставит признак «батч отвечен»

## Фаза A — план
- Покрытие: требования 1–3 → шаг 1; таблица полна.
- Шаг один, размера MR — для правки в 11 строк адекватно.
- Подход (вызов того же узла `fsm._mark_questions_answered` при дословном
  условии `fsm._cmd_approve`, `orchestrator/fsm.py:1870`) не конфликтует с
  архитектурой; дублирования логики хэша/номера нет.
- Дефект плана: раздел «Риски» утверждает, что переименование/выпадение
  вызова «ловит планка/тесты признака», а «Покрытие» — что отдельный тест в
  `tests/` не нужен, т.к. «шов — закрытое имя, которое долгоживущему файлу
  запрещено». Оба утверждения неверны — см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/canary.py:1489-1493`: после `answer.cmd_answer` и `store.get_task`, до `store.update_task`/`store.set_state`; условие `escalated_from == "spec_writing" and answer_baseline is not None` — как у approve. |
| 2 | OK | Иные `escalated_from` и `answer_baseline = None` вызова не получают (AC-3 зелёный, мутация «только escalated_from» планкой краснеет). |
| 3 | OK | Остальное тело функции не тронуто (diff — только вставка); докстринг дополнен абзацем `canary.py:1463-1467`. |

## Замечания

- major — `orchestrator/canary.py:1491-1493` (тест отсутствует в `tests/`) —
  свойство «синтетический ответ канарейки ставит признак батча» закрыто
  только планкой, а планка помечена `Группа: разовый` и после мержа не
  гоняется ни CI, ни гейтами (ADR-0018 п. 3). Проверено временной мутацией:
  вызов `fsm._mark_questions_answered` заменён на `pass` —
  `tests/test_canary_synthetic_answer.py`, `tests/test_canary.py`,
  `tests/test_canary_budget_ceiling.py`,
  `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py` — 140 passed,
  ни один не покраснел; `grep` по `tests/` на `_mark_questions_answered`/
  `QUESTIONS_ANSWERED_ACTION` в связке с canary — пусто. Сценарий: следующая
  правка `_pass_escalated_with_synthetic_answer` (PLAN сам называет её
  вероятной — «вынести общий узел») молча теряет вызов, CI зелёный, прогон
  канарейки снова red четырьмя эскалациями, как 03.11. Обоснование PLAN
  («закрытое имя запрещено долгоживущему файлу») относится к долгоживущим
  файлам планки `tests/test_<id>_*.py`, а не к тестам разработчика в
  `tests/`: `tests/test_canary_synthetic_answer.py` уже зовёт
  `canary._pass_escalated_with_synthetic_answer` напрямую. Предложение:
  новый файл разработчика в `tests/` (зона SPEC `tests/`;
  `tests/test_canary_synthetic_answer.py` по SPEC не трогать), например
  `tests/test_canary_synthetic_answer_batch_mark.py`, с минимум двумя
  методами: (а) `spec_writing` + `answer_baseline = 0` → ровно одна строка
  `fsm.QUESTIONS_ANSWERED_ACTION` до записи смены состояния (ловит
  «вызов удалён» и «по истинности»); (б) `in_dev`/`answer_baseline = None` →
  строки нет (ловит «безусловный вызов»). Каждому — «Ловит мутацию: …» с
  наблюдаемым расхождением. Поправить и раздел PLAN «Риски».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/canary.py:1491-1493; tests/ (нет файла) | Признак батча в канарейке закрыт только разовой планкой; ни один тест `tests/` не краснеет при удалении вызова (проверено мутацией, 140 passed) | После мержа регрессия возвращается незамеченной CI — канарейка снова red на повторных эскалациях `QUESTIONS.md` | Добавить тест разработчика в новый файл `tests/` (положительный случай `answer_baseline = 0` с порядком «признак раньше смены состояния» + отрицательный), с заявками «Ловит мутацию»; исправить «Риски» PLAN |

## Вердикт
changes_requested — закрыть R1-F1 (сторож свойства в `tests/`). Код
функции по существу корректен, правка не требуется.

Наблюдение для Оператора (не замечание разработчику): планка помечена
`Группа: разовый` при том, что проверяет свойство кода; по
skills/test-authoring (ADR-0020) свойство кода — долгоживущее. Автор
планки обосновал выбор запретом закрытых имён в долгоживущем файле; планка
залочена, правка — `amend-tests` Оператора. R1-F1 закрывает пробел со
стороны разработчика независимо от этого.

## Проверено исполнением
- `artel.py plank-run 01M6PFGA0GR4ZMGT3H7PKS7SN5` — 7 passed, код выхода 0.
- Временная мутация «`answer_baseline` по истинности» (`canary.py:1492`) —
  планка 2 failed / 5 passed; мутация «только `escalated_from`» — 1 failed /
  6 passed. Код возвращён `git checkout`, `git status` чистый.
- Временная мутация «вызов удалён» (`pass` вместо
  `fsm._mark_questions_answered`): `python3 -m pytest
  tests/test_canary_synthetic_answer.py tests/test_canary.py
  tests/test_canary_budget_ceiling.py
  tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py -p no:cacheprovider`
  — 140 passed (основание R1-F1). Код возвращён.
- Без мутаций: `tests/test_canary_synthetic_answer.py
  tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py` — 26 passed.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой
  только в `built_at_sha` (не дефект); файл возвращён.
- Сверено с `orchestrator/fsm.py:613-626` и `:1866-1871`: тот же узел, то
  же условие, тот же актор журнала (`operator`, внутри узла).

## Предложения системе
- Класс «свойство закрыто только разовой планкой, PLAN считает планку
  сторожем после мержа»: формулировку «закрытое имя запрещено
  долгоживущему файлу» роли читают как запрет на тест разработчика в
  `tests/`; стоит явно развести это в skills/test-authoring.md.
