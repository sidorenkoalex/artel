---
task: 01M5QR7KGYZNVWDP5H86S9PY04
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Скорость пульта, git 1 — одна проверка origin при отправке документов и отправка в сверке с origin только при расхождении

## Фаза A: план
- Таблица покрытия полна: требования 1–5 сведены к шагам 1–4; шаг 4 —
  возврат из verifying по мандату ANSWER-1.
- Шаги по размеру — единицы MR: правка кода, новый файл тестов, замер.
- Подход (keyword-признак `origin_checked=False` по умолчанию) не трогает
  вызывающих и сохраняет `has_no_remote` у `push(task_id)`. С архитектурой
  не конфликтует.
- AC-11: таблица до/после снята на `Ac5ProofMismatchTest`
  (`git remote` 88→43, `git push` 49→43, `ls-remote` 9→9). Методика
  описана (временная копия дерева базы, шпион `subprocess.run`), файл
  теста не менялся. Сокращение `remote` вдвое и неизменный `ls-remote`
  согласуются с кодом: в тесте все сверки застают совпадение.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/artifact_branch.py:367-385`: при `origin_checked` проверка `has_no_remote` пропускается. Признак передаёт только `_send` (:468-469), и только после истинного `_origin_configured` (:465). `push(task_id)` идёт с признаком по умолчанию. Ветки исхода и журнала (:470-471) не изменились. |
| 2 | OK | `:503-518`: сначала `remote_ref_state`. Досылка и пересверка идут только при `not reason and local and local != remote`. Тексты отказов и сравнение — прежние строки. Пустой `local` не досылается (AC-10). Вызывающие не тронуты: в диффе только 3 файла. |
| 3 | OK | `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`: pytest, 10 функций на AC-1–AC-10, у каждой есть «Ловит мутацию:» с наблюдаемым расхождением. Песочница — `origin_real_git` с настоящим bare-origin. Шпион стоит на `subprocess.run` и видит `has_no_remote`, как требует AC-1. |
| 4 | OK | Раздел PLAN «Счёт вызовов git на Ac5ProofMismatchTest». |
| 5 | OK | Существующие тесты не правились, кроме одной строки `tests/test_review_package.py:1284` (удалён `["-C", clone, "remote"]`). Это ровно то, что разрешает мандат ANSWER-1: строгий `assertEqual` и порядок остальных элементов сохранены. Удалённая строка соответствует требованию 1. |

Проверка заявок «Ловит мутацию»: заявки AC-4/AC-6 описывают поведение
кода до правки (досылка до сверки) — такая мутация правдоподобна, и
`git push` в шпионе её наблюдает. Заявка AC-5 («без пересверки» → отказ
«расходится»): наблюдаемо, первая сверка вернёт `head0`, а `local` —
новую голову. Заявка AC-2: без `_origin_configured` `has_no_remote` при
remote `upstream` ложен, уходит `push origin` и пишет FAILED — тест
ловит это и по spy, и по журналу.

Группы планки и повтор: долгоживущие свойства лежат в `tests/` (файл с
id задачи), повтора в других файлах `tests/` нет.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py tests/test_artifact_ref_sync.py tests/test_artifact_branch_push.py tests/test_artifact_branch_server_retry.py` — 47 passed.
- `artel.py plank-run 01M5QR7KGYZNVWDP5H86S9PY04` — 11 passed, код выхода pytest 0.
- `python3 -m pytest tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package` — 1 passed.
- `git diff f30696cc… --stat -- tests/` — новый файл задачи и ровно 1 удалённая строка в `tests/test_review_package.py`, в пределах мандата ANSWER-1.
- Временные мутации (каждый раз код возвращался `git checkout -- orchestrator/artifact_branch.py`, после этого `git status` чист):
  - в `_send` убран `origin_checked=True` → красный `test_send_checks_remote_once_then_pushes` (AC-1), остальные 9 зелёные;
  - `if not reason and local != remote` (без `local`) → красный `test_sync_refusal_no_local_ref_without_push` (AC-10), остальные 9 зелёные.

## Предложения системе
- `orchestrator/artifact_branch.py:496` — строка докстринга длиннее
  соседних (~100 символов). Линтера длины строк на ветке, видимо, нет;
  если конвенция есть, стоит её автоматизировать, а не ловить глазами.
