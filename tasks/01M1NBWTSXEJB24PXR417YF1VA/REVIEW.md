---
task: 01M1NBWTSXEJB24PXR417YF1VA
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 3
---

# REVIEW: WIP-чекпоинт после таймаута: зона роли и артефактная ветка

## Фаза A: гейт плана

PLAN.md не менялся с коммита `bf1a1a12` (2026-09-04 12:45:11) — то есть
с состояния ДО вердикта итерации 1 (`changes_requested`, коммит `a4d5cc73`,
2026-09-04 13:17:54). Код (`orchestrator/checkpoint.py`) и оба
относящихся к задаче тестовых файла (`tests/test_timeout_checkpoint.py`,
`tests/test_checkpoint_external_step_artifacts.py`) идентичны байт-в-байт
состоянию на момент review итерации 1 — проверено `git diff --stat
c0ab85fb HEAD -- orchestrator/checkpoint.py tests/test_timeout_checkpoint.py
tests/test_checkpoint_external_step_artifacts.py`, вывод пуст. Автокоммит
шага `developer` после итерации 1 (`744e9afb`, артефактная ветка) —
пустой коммит (то же дерево, что у родителя `a4d5cc73`,
`git diff-tree -r 744e9afb` пуст): роль не написала в `tasks/<id>/`
вообще ничего, включая обновление реестра замечаний REVIEW.md
(`fixed`/`rejected`, как того требует `review-checklist`). Единственные
коммиты задачи после итерации 1 на кодовой ветке — два слияния `main`
(`c0ab85fb`, `0d9883b5`), не затрагивающие ни `checkpoint.py`, ни
профильные тесты.

Итог гейта плана: план сам по себе по-прежнему покрывает требования и
не конфликтует с конвенциями (см. итерацию 1) — но реализация НЕ
продвинулась ни на шаг относительно замечаний прошлой итерации. Оценка
`fixed`/`rejected` невозможна за отсутствием попытки: оба замечания
итерации 1 остаются в состоянии `open`.

## Фаза B: ревью MR

## Соответствие SPEC

| Требование/AC | Вердикт | Комментарий |
|---|---|---|
| Требование 1 / AC-1 | OK | Без изменений с итерации 1 — `developer` коммитит все пути кроме `tasks/<id>/`. |
| Требование 1 / AC-2 | реализовано не так (см. R1-F1) | Без изменений с итерации 1 — откат для git-статуса `R` (staged rename) по-прежнему не срабатывает. |
| Требование 1 / AC-3 | OK для нерасширенных случаев | То же ограничение, что у AC-2: журнал лжёт об откате для случая rename (см. R1-F1). |
| Требование 2 / AC-4 | OK | Без изменений. |
| Требование 2 / AC-5 | OK | Без изменений. |
| Требование 3 / AC-6 | OK | Без изменений. |
| Требование 4 / AC-7 | OK | Сквозной сценарий `test_author` зелёный, без изменений. |
| Требование 4 / AC-8 | OK | Сквозной сценарий `developer` зелёный, без изменений. |
| Требование 4 / AC-9 | OK | `python3 -m unittest discover -s tests` — 1418 тестов, зелёные (выросло с 1390 за счёт подтяжки main из соседних задач, не из этой). |

## Замечания

- major — `orchestrator/checkpoint.py:151-197` (`_discard_out_of_mandate_changes`)
  — REVIEW.md итерации 1, замечание R1-F1, НЕ исправлено: код идентичен
  ревизии, на которой замечание было заведено (`git blame` — строки
  161-197 датированы `a49ab080`, самым первым коммитом реализации, до
  какого-либо ревью). Логика на строках 161-162 (`if " -> " in rel: rel
  = rel.split(" -> ", 1)[1]`) корректно выбирает путь НАЗНАЧЕНИЯ rename
  для фильтрации по префиксу `tasks/<id>/`, но это не устраняет суть
  замечания: для git-статуса `R` (`code[:1]` не входит в `("A", "?")`)
  функция всё равно уходит в ветку «трекенный путь» (строка 184) и
  вызывает `git checkout -- <путь_назначения>` (строка 196) — путь
  назначения НЕ существует в HEAD (он появился в этом же индексе как
  часть staged rename), поэтому `checkout` завершается кодом возврата 1
  и ничего не делает; код возврата по-прежнему не проверяется. Файл
  остаётся на диске незакоммиченным вне мандата роли, а `paths.append`
  (строка 197) всё равно добавляет его в список «отброшенных» для
  журнала — AC-2 не выполняется, запись журнала AC-3 лжёт о результате.
  Повторно воспроизведено в этой итерации вручную (см. «Проверено
  исполнением») — тот же результат, что и в итерации 1. Тестов на этот
  сценарий по-прежнему нет ни в `tests/test_timeout_checkpoint.py`, ни
  в `tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/` (проверено
  `grep -rn "rename\|git mv"` — совпадений по существу нет). Предложение
  — то же, что в итерации 1: отдельная ветка для `code[:1] == "R"`,
  достающая оба пути rename (`rel.split(" -> ", 1)`) и учитывающая, что
  путь назначения не в HEAD (не пытаться `checkout` его, а обрабатывать
  как «новый», то есть удалять с диска), либо не отчитываться об откате
  в `paths`/журнале при неудачном `checkout` (код возврата ≠ 0).

- minor — `tests/test_timeout_checkpoint.py:108,177,198,238,264`,
  `tests/test_checkpoint_external_step_artifacts.py:224` — REVIEW.md
  итерации 1, замечание R1-F2, НЕ исправлено ни для одного из пяти
  тестов в `test_timeout_checkpoint.py` (`test_dirty_tree_commits_with_
  message_sha_and_journal_entry`, `test_git_diff_failure_commits_
  nothing_and_journals_nothing`, `test_git_commit_failure_commits_
  nothing_and_journals_nothing`, `test_developer_mandate_excludes_task_
  dir_from_code_commit`, `test_non_developer_role_discards_change_
  outside_task_dir` — докстрины прочитаны заново, явной заявки «Ловит
  мутацию: …» по-прежнему нет ни у одного). Для `tests/test_checkpoint_
  external_step_artifacts.py` пять ДРУГИХ тестов того же файла (строки
  163, 310, 329, 344, 368, 392) заявку несут — но именно исходно
  отмеченный тест `test_timeout_marker_carried_and_deletion_still_
  matches_across_flavors` (строка 224) заявки по-прежнему не имеет.
  Похоже, что часть докстринов файла `test_checkpoint_external_step_
  artifacts.py` была дописана в рамках подтяжки main (задача
  01M1KVG3KSCY47HWXWF5HM0E76/смежная), а не в ответ на это замечание —
  ровно тот тест, который называло R1-F2, остался нетронутым.
  Предложение — то же, что в итерации 1: дописать «Ловит мутацию: …» во
  все шесть перечисленных мест.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/checkpoint.py:151-197 | `_discard_out_of_mandate_changes` не обрабатывает git-статус `R` (staged rename) — путь назначения не в HEAD, `checkout --` падает без проверки кода возврата | вне-мандатный файл остаётся на диске незакоммиченным, журнал AC-3 ложно сообщает об откате | обработать `code[:1] == "R"` отдельной веткой (путь назначения — как новый/untracked) или не отчитываться об откате при неудачном checkout; без изменений со времён итерации 1 |
| R1-F2 | open | tests/test_timeout_checkpoint.py:108,177,198,238,264; tests/test_checkpoint_external_step_artifacts.py:224 | 6 тестов без явной заявки «Ловит мутацию: …» в докстринге | ревьювер не может сверить тест с заявленной мутацией по правилу review-checklist п.3 | добавить явную строку «Ловит мутацию: …» в докстринги перечисленных тестов; без изменений со времён итерации 1 |

## Вердикт

changes_requested — с момента итерации 1 (вердикт `changes_requested`,
`a4d5cc73`) в код и тесты задачи не внесено ни одной правки: `git diff`
между ревизией, на которой было проведено ревью итерации 1 (`c0ab85fb`),
и текущим HEAD пуст для `orchestrator/checkpoint.py`,
`tests/test_timeout_checkpoint.py` и
`tests/test_checkpoint_external_step_artifacts.py`; шаг `developer`
после итерации 1 дал пустой коммит артефактов (`744e9afb`); PLAN.md не
редактировался. Оба замечания итерации 1 (R1-F1 — major, R1-F2 — minor)
остаются в силе без изменений; заново подтверждены в этой итерации
самостоятельным воспроизведением (см. «Проверено исполнением»). До
исправления R1-F1 (обязательно) и R1-F2 (желательно в том же заходе)
задача не может получить `approved`. Остальная функциональность (AC-1,
AC-4..AC-9) по-прежнему корректна и зелена.

## Проверено исполнением

- `git checkout -- tasks/01M1NBWTSXEJB24PXR417YF1VA/` — восстановлен
  каталог задачи, пропавший из рабочего дерева (файлы присутствуют в
  истории ветки).
- `python3 scripts/guard.py tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md
  tasks/01M1NBWTSXEJB24PXR417YF1VA/PLAN.md` — `GUARD: ок (2 файлов)`.
- `git diff --stat c0ab85fb HEAD -- orchestrator/checkpoint.py
  tests/test_timeout_checkpoint.py
  tests/test_checkpoint_external_step_artifacts.py` — пусто (код и
  тесты не менялись с ревизии, рецензированной в итерации 1).
- `git diff-tree -r 744e9afb` — пусто (автокоммит шага developer после
  итерации 1 не содержит правок).
- `git blame -L 158,165 c0ab85fb -- orchestrator/checkpoint.py` —
  строки уже были в первом коммите реализации (`a49ab080`), до ревью.
- `python3 -m unittest tests.test_timeout_checkpoint
  tests.test_checkpoint_external_step_artifacts -v` — 33 теста, все
  зелёные (не покрывают сценарий rename — R1-F1 не поймать этим
  набором).
- `python3 -m unittest discover -s tasks/01M1NBWTSXEJB24PXR417YF1VA/
  acceptance_tests -p "test_ac*.py" -v` — 11 тестов (AC-1..AC-8), все
  зелёные (не покрывают сценарий rename).
- `python3 -m unittest discover -s tests` — 1418 тестов, `OK` (AC-9;
  выросло с 1390 на итерации 1 за счёт подтяжки main, задача
  01M1NBWTSXEJB24PXR417YF1VA своих новых тестов не добавляла).
- `python3 scripts/codebase_map.py` (пробный прогон, изменение
  отменено `git checkout -- docs/codebase-map.md`) — карта расходится
  с деревом только строкой `built_at_sha`, содержимое свежее.
- Ручное воспроизведение R1-F1 (повтор итерации 1, в
  `$SCRATCHPAD/r1f1test`): `git init`, коммит `tasks/T1/foo.py`, `git mv
  tasks/T1/foo.py orchestrator/foo.py` → `git status --porcelain=v1`
  даёт `R  tasks/T1/foo.py -> orchestrator/foo.py`; симуляция функции
  (`git reset -q -- orchestrator/foo.py` затем `git checkout --
  orchestrator/foo.py`) → код возврата 1, `error: pathspec
  'orchestrator/foo.py' did not match any file(s) known to git`, файл
  остался в `orchestrator/foo.py` (не откачен в `tasks/T1/`,
  подтверждает R1-F1).
- `grep -rn "rename\|git mv" tests/*.py
  tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/*.py` — совпадений
  по существу нет (тест на сценарий rename так и не добавлен).

## Предложения системе

- Класс «шаг роли не даёт вообще никакого прогресса между итерациями
  ревью (пустой автокоммит артефактов, PLAN.md не тронут, код не
  тронут)» — стоит подумать, различает ли пульт такой исход от
  обычного `changes_requested` с попыткой правки: реестр замечаний
  REVIEW.md рассчитан на `fixed`/`rejected` от роли, но не описывает,
  что делать ревьюверу, если роль вообще не отвечает на итерацию (эта
  задача — пример).
