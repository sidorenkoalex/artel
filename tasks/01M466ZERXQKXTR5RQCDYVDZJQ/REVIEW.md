---
task: 01M466ZERXQKXTR5RQCDYVDZJQ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: приложения PLAN накладываются и на прогонах CI по pull_request веток задач

## Фаза A — план

- Таблица покрытия полна: требования 1–6 → шаги 1–2; шаг 3 добавлен по
  ANSWER-1 (вариант А). Шаги размером в MR, проверяемые.
- Подход не спорит с архитектурой: сигнатура `task_branch` сохранена,
  отбор ветки вынесен в `tested_ref`, `run` по сути не изменился.
  Защищённый `.github/workflows/ci.yml` правится только Приложением 1
  (требование 4, SPEC «Не входит»).
- «Влияние на систему» совпадает с diff: изменены только
  `scripts/plan_appendix_ci.py`, `tests/test_plan_appendix_ci.py` и
  перегенерированная карта. Новый git в job `guard` на ветках `task/**`
  заявлен. Путь отката — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tested_ref` (scripts/plan_appendix_ci.py:119-140): на pull_request ветка берётся из `refs/heads/<GITHUB_HEAD_REF>`, `task_branch` пропускает событие `pull_request`. Приложения ложатся на дерево чекаута, `run` тот же. Неприменимое приложение даёт код 1 с номером и путями («на дерево чекаута»). AC-1/AC-2 долгоживущего файла зелёные. |
| 2 | OK | Голова не `task/**` → `""` без чтения файла события и без git. Форк (сверка `pull_request.head.repo.full_name` с `GITHUB_REPOSITORY`) → `""`. Нечитаемый файл события при голове `task/**` → `CiError`, код 1 (fail-closed, не угадываем). AC-3/AC-4 зелёные. |
| 3 | OK | На push `tested_ref` отдаёт `GITHUB_REF` как раньше. AC-5 зелёный. |
| 4 | OK | Приложение 1: `git apply --check` на дереве ветки — код 0. В обоих jobs условие пропускает pull_request `task/**` того же репозитория. |
| 5 | OK | `_step_condition` + `condition_push_only`, нарушение с именем job. На текущем ci.yml сторож даёт код 1 (оба jobs), на ci.yml с Приложением 1 — код 0. Шаг без `if:` и условие без сравнения события нарушением не считаются. AC-6 зелёный. |
| 6 | OK | У каждого нового и изменённого метода есть заявка «Ловит мутацию»; две заявки я проверил временной мутацией (ниже). Ожидание изменено только в `test_only_task_push_is_processed`, это раздел SPEC «Меняемое поведение» с мандатом ANSWER-2: было `None`, стало сравнение с `"01abc-x"` — строже, остальные три утверждения на месте. Других изменённых или удалённых утверждений, сужения данных и переноса под условие в diff `tests/` нет. |
| ANSWER-1 | OK | `check_workflow_on_run` (:352-376): на прогоне ветки задачи сначала вызывается `run`, затем `check_workflow`. Вне CI и на прочих прогонах файл проверяется как есть. Отказ `run` или `CiError` дают код 1 без проверки файла. Шаг сторожа — последний в job `guard` (ci.yml:48-49), поэтому изменённое дерево не задевает другие шаги job. |

## Замечания

Блокирующих и major-замечаний нет.

Наблюдение без записи в реестр (не дефект):
`TestedRefTest::test_fork_head_is_not_task_branch` и
`test_push_ref_and_same_repo_pr_head` частично пересекаются со
сквозными AC-4/AC-1 долгоживущего файла. При этом они проверяют функцию
`tested_ref` напрямую, на уровне юнита, и это законная граница с
end-to-end, а не повтор того же свойства тем же способом. Свойство
fail-closed на нечитаемом файле события держит только юнит.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_plan_appendix_ci.py tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py` — 23 passed.
- `artel.py plank-run 01M466ZERXQKXTR5RQCDYVDZJQ` — «планки нет»: в `refs/artifacts/<id>` нет `test_*.py`. У задачи только долгоживущий файл в `tests/`, он прогнан выше.
- Приложение 1 извлечено из PLAN.md. `git apply --check` на дереве ветки — код 0. `--check-workflow .github/workflows/ci.yml` без `GITHUB_*`: на текущем файле — код 1 с нарушением в `python` и `python-min`; на копии с наложенным приложением — код 0.
- Временная мутация 1: снята сверка репозитория головы (`if False and _head_repo(...)`). `tests/test_plan_appendix_ci.py` красный: `test_fork_head_is_not_task_branch`, `test_unreadable_event_file_fails_closed_only_for_task_head`. Код возвращён (`git status` чистый).
- Временная мутация 2: продолжение условия `if:` не склеивается. Красный `test_push_only_condition_in_dash_and_multiline_forms`. Код возвращён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — 0 строк расхождения, карта свежая; файл возвращён.
- CI коммита 94a74c5c зелёный (16 проверок, из пакета): job `guard` на ветке с наложением приложений проходит.

## Предложения системе

- Сторож защищённого файла, который сам меняется приложением PLAN
  (класс задачи: `--check-workflow` + приложение к ci.yml), закрыт здесь
  наложением приложений в job `guard`. Стоит закрепить это в
  skills/spec-authoring.md, чтобы SPEC сразу называл, на каком дереве
  сторож видит приложение, без отдельной эскалации (здесь ушла на это
  ANSWER-1).
