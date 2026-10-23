---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

## Фаза A: план
- Таблица покрытия полна: требования 1–6 → шаги 1–3; шаг 3 (итерация 2)
  закрывает долгоживущие тесты требований 1–4 — прежнее замечание к плану
  (совпадало с R1-F1) снято.
- «Влияние на систему» совпадает с инкрементальным diff: пробел в
  `orchestrator/artifact_branch.py:472` и новые тесты в
  `tests/test_artifact_branch_server_retry.py`. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Классификация без изменений с итерации 1. Сторожа в `tests/`: `ClassifyServerSignsTest` — HTTP 502 / `returned error: 503`, `fatal error in commit_refs`, старшинство (а) над (б) |
| 2 | OK | Цикл повтора без изменений; `test_pause_uses_module_constant` держит аргумент паузы — константу модуля в момент вызова |
| 3 | OK | `SendJournalTest::test_server_failure_detail_names_attempts_without_merge_advice` — деталь `сервер (попыток 3): `, без совета и sha |
| 4 | OK | `SendJournalTest`: успех после повтора с `попыток 2`, успех после записанного FAILED, два успеха без отказа — без записи |
| 5 | OK | Без изменений с итерации 1 (`send_pending` в `orchestrator/` — 0 вхождений) |
| 6 | OK | Новые тесты без сети: `_git`, `gitcmd.*`, `artifact_branch.time` (`TimeWithSleep`) подменены на модуле; песочница БД `SchemaSeededTmpRootTest`; существующие методы теста не тронуты (diff `tests/` — только добавления, плюс импорт `store`/`SchemaSeededTmpRootTest`) |

## Замечания

Новых замечаний нет. Заявки «Ловит мутацию» новых тестов называют
наблюдаемое расхождение (значение классификации, аргумент `sleep`,
содержимое/число записей журнала) и проверены временной мутацией (ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_artifact_branch_server_retry.py; orchestrator/artifact_branch.py:74,393,396–419,462 | Требования 3, 4 и признаки 5xx/commit_refs/старшинство (а)>(б), аргумент паузы треб. 2 не держал ни один тест `tests/` | Регрессия прошла бы CI после мержа молча | Закрыто: добавлены `ClassifyServerSignsTest`, `test_pause_uses_module_constant`, `SendJournalTest`; семь временных мутаций по одной — каждая красит тест |
| R1-F2 | accepted | orchestrator/artifact_branch.py:472 | `last =store.…` — пропущен пробел | Вкус/читаемость | Закрыто: `last = store.last_task_step_of(…)`, выравнивание продолжения верное |

## Вердикт
approved. R1-F1 и R1-F2 закрыты, новых blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_artifact_branch_server_retry.py
  tests/test_artifact_branch_push.py tests/test_artifact_ref_sync.py
  tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` — 41 passed,
  45 subtests passed.
- Временные мутации `orchestrator/artifact_branch.py`, по одной, прогон
  `tests/test_artifact_branch_server_retry.py` (14 тестов) после каждой:
  (1) убран `or _last_send_failed(task_id)` из условия `_send`;
  (2) `time.sleep(5)` вместо `PUSH_SERVER_RETRY_PAUSE_SEC`;
  (3) убран шаблон `http 5\d\d`; (4) убран `returned error: 5\d\d`;
  (5) `fatal error in commit_refs` заменён на мусор; (6) деталь отказа без
  `(попыток N)`; (7) убрано `attempts > 1 or` из условия `_send` — каждая
  дала `1 failed, 13 passed`. Исходный файл восстановлен скриптом,
  `git status --short` чистый.
- `python3 …/artel.py plank-run 01M5K11D3284ZZGRHN39FGQVF2` — 15 passed,
  код выхода pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без строк `built_at_sha` — расхождений нет, карта свежая; регенерация
  отменена `git checkout`.
- CI коммита 28415fa1 — зелёный (16 проверок, по пакету).

## Предложения системе
- Итерация 1 этой задачи не прошла advance: разработчик дописал пояснение
  прямо в ячейку статуса реестра (`fixed — …`), guard принимает только
  голое слово статуса. Шаблону `templates/REVIEW.md` или брифу developer
  пригодилась бы строка «пояснение — в колонку «решение», в «статус» —
  одно слово».
