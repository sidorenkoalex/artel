---
task: 01M5QR7KGYZNVWDP5H86S9PY04
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Скорость пульта, git 1 — одна проверка origin при отправке документов и отправка в сверке с origin только при расхождении

## Подход
Две точечные правки `orchestrator/artifact_branch.py`, вызывающие не меняются.

- `_attempt_push(branch, repo, *, origin_checked=False)`. Если признак истинен,
  `gitcmd.has_no_remote` не вызывается: истинный `_origin_configured` уже
  означает, что `git remote` не пуст. По умолчанию признак ложен, поэтому
  `push(task_id)` и прочие вызывающие проверяют remote как раньше (AC-3).
  Признак передаёт только `_send`, и только после истинного
  `_origin_configured`. Исходы, повторы ответа сервера и записи журнала не
  менялись.
- `origin_sync_refusal`: сначала `gitcmd.remote_ref_state`. Только если
  первая сверка ответила, `local` не пуст и `local != remote`, выполняются
  `_send` и повторная сверка. Сравнение и тексты отказов остались прежними.
  Если origin не ответил на первую сверку, отказ уходит без `push`
  (следствие, принятое Оператором на гейте SPEC). Пустой `local` не
  досылается — это прежнее условие (AC-10).

Бюджет SPEC ($30) не пересматривается.

## Шаги
1. Правка `_attempt_push`/`_send` (признак `origin_checked`) и
   `origin_sync_refusal` (сверка → досылка при расхождении → пересверка);
   регенерация `docs/codebase-map.md`.
2. Новый файл `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`
   (pytest, фикстура `origin_real_git`, шпион на `subprocess.run`). В нём
   10 функций на AC-1–AC-10, у каждой есть «Ловит мутацию:».
3. Замер AC-11 (раздел ниже).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 (AC-1–AC-3) |
| 2 | 1, 2 (AC-4–AC-10) |
| 3 | 2 |
| 4 | 3 |
| 5 | 1 (существующие файлы tests/ не правились; прогоны ниже) |

## Счёт вызовов git на Ac5ProofMismatchTest (AC-11)
Замер сделан на `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest`.
Файл волной не сведён, адрес тот же. Шпион процессов — плагин, который
подменяет `subprocess.run` и считает подкоманду git после пар `-C`/`-c`. Код
«до» взят из временной копии дерева базы (`git archive HEAD`, распаковка в
игнорируемый каталог рабочей копии, затем копия удалена), код «после» —
дерево ветки. Файл теста не менялся.

| Команда | до | после |
|---|---|---|
| git remote | 88 | 43 |
| git push | 49 | 43 |
| git ls-remote | 9 | 9 |
| все вызовы git | 1323 | 1272 |

`git remote` сократился вдвое: каждая отправка `_send` теряет второй
вызов `git remote` (из `has_no_remote`). Минус 6 `git push` — досылки из
`origin_sync_refusal` при уже совпадающих ссылках. Число `ls-remote` не
изменилось: в этом тесте все сверки застают совпадение, повторной сверки нет.

## Проверки
- `python3 -m pytest` по новому файлу и `tests/test_artifact_ref_sync.py`,
  `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`,
  `tests/test_artifact_branch_server_retry.py`,
  `tests/test_artifact_branch_push.py`,
  `tests/test_doctor_artifact_branch_sync.py` — 67 passed.
- Тесты вызывающих: `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`,
  `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`,
  `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`,
  `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py`,
  `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py` — 89 passed,
  82 subtests passed.
- `plank-run … test_origin_push_checks.py` — 10 passed.
- Временные мутации, после каждой код возвращён:
  - признак по умолчанию `True` — красные AC-3;
  - `if local != remote` без `local` — красные AC-10;
  - `_send` без признака плюс досылка до сверки без пересверки — красные
    AC-1, AC-4, AC-5, AC-6, AC-9;
  - `_send` без `_origin_configured`, потеря ветки «нет в origin» и
    перестановка sha — красные AC-2, AC-7, AC-8.

## Влияние на систему
- Гейт мержа (`fsm_merge_gate.py:1349`) и закрытие (`cleanup.py:681`) получают
  те же тексты отказов и `None`. Разница одна, принятая на гейте SPEC: при
  недоступном origin в журнале больше нет записи «push артефактной ветки
  FAILED» от сверки. Отказ при этом остаётся, и он называет origin.
- Ссылка, отставшая от origin, раньше досылалась `_send` до сверки. Теперь
  первая сверка застаёт расхождение, и досылка идёт сразу за ней — исход тот
  же.
- Гейты, лимиты и инварианты не тронуты; `push(task_id)` проверяет
  `has_no_remote` по-прежнему.
- Откат — revert коммита ветки.

## Риски
- Между первой сверкой и `_send` чужой процесс может сдвинуть origin. Тогда
  пересверка покажет фактическое состояние, и действует прежнее сравнение —
  поведение не хуже прежнего, где сверка шла один раз после досылки.

## Предложения системе
- Сторож роли в `conftest.py` читает `sys.argv`. Замер шпионом через
  обёртку `pytest.main` поэтому требует подменять `sys.argv`, а переменные
  окружения в Bash шага (`PYTHONPATH=…`) отклоняются правами. Для AC-11
  пришлось писать сценарий-обёртку. Не хватает команды пульта «счёт вызовов
  git на тесте до/после» (класс: замер скорости git 1–5 повторится в каждой
  задаче серии).
