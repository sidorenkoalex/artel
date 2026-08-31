---
task: T075
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: ANSWER-артефакт: канал ответа Оператора на эскалацию

## Гейт плана (Фаза A)

PLAN.md итерации 2 добавляет только описание уже согласованных фиксов
(git add точечно, branch-aware юнит-тесты) — таблица покрытия
требований не изменилась и по-прежнему полна, подход не расходится с
конвенциями (точечный `git add --`, тот же приём `_read_branch_text_or_refuse`
для `_answer_baseline_or_refuse`). Гейт плана пройден повторно без
новых замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (шаблон ANSWER, guard) | OK | Не тронуто с итерации 1 — `guard.py --all` зелёный (265 файлов, выросло за счёт T076-T078, слитых в main). |
| 2 (команда `answer`) | OK | Замечание major итерации 1 закрыто: `orchestrator/answer.py:86-87` теперь стейджит точечно `git add -- tasks/<id>/ANSWER-{n}.md`, не `add -A tasks/<id>`. Регресс-тест `tests/test_answer.py::AnswerCommandStrayFilesTest` (реальный git) подтверждает, что посторонний незакоммиченный файл того же worktree остаётся нетронутым и не попадает в коммит. |
| 3 (гейт возврата) | OK | Не тронуто по существу; minor-замечание итерации 1 (тихий `or 0` на git-сбое) тоже закрыто — новый узел `_answer_baseline_or_refuse` (fsm.py:499-533) отказывает переход явно, тем же приёмом, что `_read_branch_text_or_refuse`, во всех 4 точках эскалации (fsm.py ветки `spec_writing`×2, `review`/`escalate`, `tests_writing`). |
| 4 (видимость в брифе) | OK | Замечание major итерации 1 закрыто: `tests/test_answer_branch_reads.py` (новый файл, реальный git по образцу `RealGitSandbox`/`tests/test_gitcmd_branch_reads.py`) покрывает `_answer_file_count`, `_answer_component`, `_questions_component`, `_latest_answer_rel` именно на чужой ветке (`on_foreign_branch=True`) — числовое сравнение номеров ANSWER (`ANSWER-10.md` против `ANSWER-2.md`), пустой снимок, `None` при неответившем git. |
| 5 (право пересмотра тестов не меняется) | OK | По-прежнему вне diff'а. |

AC-1..AC-6 — зелёные (17 приёмочных тестов T075). AC-7 — зелёный (полный набор `tests/`, 1028 тестов — рост числа против итерации 1 (981) объясняется слиянием main, принёсшим тесты T076/T077/T078, не регрессией этой задачи). Оба major-замечания и minor-замечание итерации 1 закрыты предметно: не текстом «исправлено», а конкретным кодом и тестом на каждое.

Прочее в diff'е (`orchestrator/fixation.py`, `gitcmd.commit_committer_dates`, `orchestrator/store.py::refusal_history`, `orchestrator/brief.py::advance_refusal_history`, правки `scripts/guard.py`, артефакты `tasks/T076`, `tasks/T077`, `tasks/T078`) — не работа этой ветки: коммит `T075: подтяжка main` подтянул уже слитые в `main` и одобренные отдельными REVIEW.md (все три — `status: approved`) задачи T076-T078. Это не расширение объёма T075 (PLAN «Влияние на систему» этого diff'а этих файлов не касается), а обычная подтяжка главной ветки — вне зоны повторного ревью здесь.

## Замечания

(нет)

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_answer tests.test_answer_branch_reads tests.test_answer_gate -v` — 16 тестов, все зелёные, включая новый регресс `AnswerCommandStrayFilesTest` (точечный `git add`) и новые branch-aware тесты `AnswerFileCountOnForeignBranchTest`/`BriefAnswerComponentsOnForeignBranchTest` на реальном git.
- `python3 -m unittest discover -s tests -q` — 1028 тестов, все зелёные (полный регресс проекта после подтяжки main).
- `python3 -m unittest discover -s tasks/T075/acceptance_tests -v` — 17 тестов (AC-1..AC-6), все зелёные.
- `python3 -m unittest tests.test_invariants.CountersNeverResetTest tests.test_analyst_role.QuestionsEscalationTest -v` — 6 тестов, все зелёные (два теста, которые PLAN шаг 5 итерации 1 называет починенными под новое поведение — подтверждено, что они зелёные и на текущем HEAD).
- `python3 scripts/guard.py --all` — «GUARD: ок (265 файлов)».
- `python3 scripts/codebase_map.py` + `git diff --stat -- docs/codebase-map.md` — расхождение только в строке `built_at_sha`, содержимое карты свежее; изменение отменено (`git checkout -- docs/codebase-map.md`), `git status --short` пуст.
- Чтение: `orchestrator/answer.py` целиком (подтверждён точечный `git add -- tasks/<id>/ANSWER-{n}.md`), `orchestrator/fsm.py::_answer_file_count`/`_answer_baseline_or_refuse` и все 4 точки её вызова, `orchestrator/brief.py` (`_answer_component`/`_questions_component`/`_latest_answer_rel`/`_branch_or_disk_text` — подтверждено существование и совпадение с тем, что покрывают новые тесты), `tests/test_answer_branch_reads.py` целиком (сценарий на чужой ветке без чекаута файлов на диск — `on_foreign_branch` истинно с рождения песочницы `RealGitSandbox`).
- `git log --oneline task/t075-answer-artefakt-kanal-otveta-o --not main` + `git merge-base main task/t075-answer-artefakt-kanal-otveta-o` — подтверждено, что артефакты T076/T077/T078 в diff'е пришли исключительно коммитом «T075: подтяжка main» (уже слиты и одобрены на main), не авторством этой ветки.

## Предложения системе

(нет)
