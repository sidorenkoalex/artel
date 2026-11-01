---
task: 01M6AB4VE2R0Q2V5D4MMJGNGH7
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Б2.2 — команда `mr-sync`: сверка MR и нахождения правки в `base`, закрытие `done` по подтверждению Оператора

## Фаза A: план

- Таблица покрытия по-прежнему полна: требования 1–8 → шаги 1–6.
- PLAN дополнен абзацем «После ревью итерации 1». Каждое исправление R1-F1…F4 в нём описано, и описание совпадает с инкрементальным diff: `fsm_merge_gate.py`, `mr_sync.py`, `tests/test_mr_sync_units.py`.
- В «Рисках» добавлен риск: `read_env` декодирует строкой. Он честный — сбой декодирования stderr `git apply` даёт итог «неизвестно», закрытия при этом нет, то есть ошибка уходит в безопасную сторону.
- Защищённые пути не тронуты. Приложение к `tests/test_invariants.py` после итерации 1 не менялось.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1 |
| 2 | OK | точка считает `mr_sync.fork_point` до вызовов MR (`fsm_merge_gate.py:1822`). Записывает её `record_fork_point` при переходе в `awaiting_human` (`:1846`). Сверка берёт записанное значение |
| 3 | OK | строка 1 таблицы теперь держится. Вывод git читается байтами (`mr_sync.py:101-117`), строки декодируются `surrogateescape` (`:120-124`), патчи в `patch-id` и `git apply` идут байтами. Истёкший срок, `OSError` и сбой декодирования сводятся к `GitFailure`, итог — «неизвестно» |
| 4 | OK | без изменений с итерации 1 |
| 5 | OK | без изменений; к этому добавлен отказ `approve` без точки ответвления, MR при этом не тронут |
| 6 | OK | без изменений с итерации 1 |
| 7 | OK | без изменений с итерации 1 |
| 8 | OK | приложение не менялось; планка зелёная |

Неослабление тестов:
- В итерации 2 существующие тесты не менялись. Изменённые утверждения прежние: `test_ac15_…` правлен по мандату ANSWER-2, подделка `FakeForge.mr_status` добавлена по ANSWER-3.
- Из `tests/test_mr_sync_units.py` удалён `test_foreign_commit_escalation_accepts_server_head`. Это ответ на R1-F4: файл новый в ветке, в base его нет, и свойство держит долгоживущий AC-14.

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/mr_sync.py:101-124 | строгий UTF-8 вывода git | — | Проверено: `_git` → `gitcmd.read` без `text` (байты), `_out` → `surrogateescape`, `_shown` в выводе и журнале. `diff -z --name-only`, патчи передаются файлом в `wb`. Тест `NonUtf8DiffTest::test_signs_on_cp1251_file` проверен временной мутацией: строгий `decode("utf-8")` в `_out_bytes` даёт красный тест с `UnicodeDecodeError`. Код возвращён, `git status` чист |
| R1-F2 | accepted | orchestrator/mr_sync.py:132-154 | `_apply_passes` мимо `read_env`, без срока | — | `read-tree` и `apply` идут через `gitcmd.read_env` со сроком `GIT_TIMEOUT_SEC` = 60 с, с планом точки. `Timeout`, `OSError` и `UnicodeDecodeError` сводятся к `GitFailure`. `import subprocess` убран |
| R1-F3 | accepted | orchestrator/fsm_merge_gate.py:1813-1827 | точка не вычислена — уход в `awaiting_human` | — | Точку теперь считают до любых вызовов MR. Если её нет, `_people_refusal` даёт отказ `approve`, задача остаётся на гейте, предлагается повтор `approve`. Тест `test_gate_refuses_without_fork_point`: состояние `merge_gate`, `fork_point` пуст, `undraft_mr` и `assign_mr` не вызывались |
| R1-F4 | accepted | tests/test_mr_sync_units.py:37 | повтор AC-14 | — | Положительная половина удалена, осталась отрицательная `test_other_escalation_does_not_accept_head` (ANSWER-1 п. 6) |

## Вердикт

`approved`. Все четыре замечания итерации 1 закрыты по существу. В инкрементальном diff новых дефектов нет. Соответствие SPEC и ANSWER-1..3 сохранено.

## Проверено исполнением

- `timeout 590 python3 -m pytest tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_awaiting_hint.py tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_fields.py tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py tests/test_mr_sync_units.py tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_commands.py -q -p no:cacheprovider` — 103 passed за 126 с.
- `artel.py plank-run 01M6AB4VE2R0Q2V5D4MMJGNGH7` — 1 passed, код выхода pytest 0.
- Временная мутация R1-F1: `_out_bytes` возвращал `res.stdout.decode("utf-8").encode("utf-8")`. Прогон `pytest tests/test_mr_sync_units.py -k cp1251` дал 1 failed, `UnicodeDecodeError` на `mr_sync.py:117`. Код возвращён, `git status --porcelain` пуст.
- `grep` по `docs/codebase-map.md`: карта несёт `fork_point`, `record_fork_point` и `test_gate_refuses_without_fork_point`, то есть регенерирована после правки.

## Предложения системе

- В пакете ревью нет отметки, менялось ли приложение PLAN между итерациями. Без неё `git apply --check` приходится повторять вслепую или полагаться на текст PLAN.
