---
task: 01M1NBWTSXEJB24PXR417YF1VA
type: review
author_role: reviewer
status: changes_requested
iteration: 3
schema_version: 3
---

# REVIEW: WIP-чекпоинт после таймаута: зона роли и артефактная ветка

## Фаза A: гейт плана

PLAN.md не менялся с коммита `bf1a1a12` (12:45:11) — с состояния ДО
итерации 1. Код (`orchestrator/checkpoint.py`) и оба профильных
тестовых файла (`tests/test_timeout_checkpoint.py`,
`tests/test_checkpoint_external_step_artifacts.py`) по-прежнему
идентичны байт-в-байт ревизии итерации 1 — `git diff --stat c0ab85fb
HEAD -- orchestrator/checkpoint.py tests/test_timeout_checkpoint.py
tests/test_checkpoint_external_step_artifacts.py` пуст, и тот же вывод
пуст относительно ревизии итерации 2 (`58992242`). Автокоммит шага
`developer` после итерации 2 (`8f11ddd1`, артефактная ветка) — снова
пустой коммит (`git diff-tree -r 8f11ddd1` пуст, `git diff --stat
58992242 8f11ddd1` пуст): второй раз подряд роль не внесла ни строчки
правки в ответ на вердикт `changes_requested`. Единственные коммиты
задачи на кодовой ветке после итерации 2 — два технических: подтяжка
`main` (`0d9883b5`) и регенерация карты кодовой базы (`fc33ecbc`), оба
не затрагивают `checkpoint.py`/профильные тесты.

Сам план по-прежнему покрывает требования SPEC и не конфликтует с
конвенциями (см. итерации 1–2, повторной ревизии не требуется —
текст не менялся). Оценка `fixed`/`rejected` по замечаниям итерации 1
снова невозможна за отсутствием попытки: оба замечания остаются
`open`.

## Фаза B: ревью MR

## Соответствие SPEC

| Требование/AC | Вердикт | Комментарий |
|---|---|---|
| Требование 1 / AC-1 | OK | Без изменений — `developer` коммитит все пути, кроме `tasks/<id>/`. |
| Требование 1 / AC-2 | реализовано не так (см. R1-F1) | Без изменений — откат для git-статуса `R` (staged rename) по-прежнему не срабатывает; независимо воспроизведено в этой итерации (см. «Проверено исполнением»). |
| Требование 1 / AC-3 | реализовано не так (см. R1-F1) | То же ограничение: журнал лжёт об откате для случая rename. |
| Требование 2 / AC-4 | OK | Без изменений. |
| Требование 2 / AC-5 | OK | Без изменений. |
| Требование 3 / AC-6 | OK | Без изменений. |
| Требование 4 / AC-7 | OK | Сквозной сценарий `test_author` зелёный. |
| Требование 4 / AC-8 | OK | Сквозной сценарий `developer` зелёный. |
| Требование 4 / AC-9 | OK | `python3 -m unittest discover -s tests` — 1418 тестов, зелёные (без изменений численности со времён итерации 2). |

## Замечания

- major — `orchestrator/checkpoint.py:151-197` (`_discard_out_of_mandate_changes`)
  — REVIEW.md итерации 1/2, замечание R1-F1, по-прежнему НЕ исправлено:
  третья итерация подряд без единой правки кода. Строки 161-162 (`if "
  -> " in rel: rel = rel.split(" -> ", 1)[1]`) корректно выбирают путь
  НАЗНАЧЕНИЯ rename для фильтра по префиксу `tasks/<id>/`, но строка 176
  (`new_path = code[:1] in ("A", "?")`) не относит git-статус `R` к
  «новым» путям, поэтому функция уходит в ветку «трекенный путь»
  (строка 184) и на строке 196 вызывает `git checkout -- <путь
  назначения>` — путь назначения физически отсутствует в HEAD (он
  появился в этом же индексе как часть staged rename). Независимо
  воспроизведено в этой итерации (не переиспользуя репро прошлых
  итераций): `git mv tasks/T1/foo.py orchestrator_new.py` →
  `git status --porcelain=v1` даёт `R  tasks/T1/foo.py ->
  orchestrator_new.py`; симуляция логики функции (`git reset -q --
  orchestrator_new.py`, затем `git checkout -- orchestrator_new.py`) →
  код возврата 1, `error: pathspec 'orchestrator_new.py' did not match
  any file(s) known to git`; итоговый `git status --porcelain=v1`
  показывает `D  tasks/T1/foo.py` и `?? orchestrator_new.py` — то есть
  результат ХУЖЕ, чем «не откачено»: физически исчезает и исходный файл
  ВНУТРИ `tasks/<id>/` (`git mv` переместил его на диске, `reset`/
  `checkout` его не возвращают), а вне-мандатный файл всё равно остаётся
  на диске. Код возврата `checkout` по-прежнему не проверяется, и `rel`
  (строка 197) всё равно добавляется в `paths` для журнала — AC-2 не
  выполняется, запись журнала AC-3 лжёт о результате, и как побочный
  эффект возможна порча самого `tasks/<id>/`. Тестов на этот сценарий
  по-прежнему нет ни в `tests/test_timeout_checkpoint.py`, ни в
  `tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/` (`grep -rn
  "rename\|git mv\|code\[:1\] in" tests/*.py
  tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/*.py` — по существу
  ноль совпадений). Предложение — то же, что в итерациях 1–2: отдельная
  ветка для `code[:1] == "R"` (взять ОБА пути rename через
  `rel.split(" -> ", 1)`, путь назначения обрабатывать как «новый» —
  без `checkout`, прямым удалением с диска), либо не отчитываться об
  откате в `paths`/журнале при ненулевом коде возврата `checkout`.

- minor — `tests/test_timeout_checkpoint.py:108,177,198,238,264`,
  `tests/test_checkpoint_external_step_artifacts.py:224` — REVIEW.md
  итерации 1/2, замечание R1-F2, по-прежнему НЕ исправлено ни для
  одного из шести мест (проверено заново: `grep -n "Ловит мутацию"
  tests/test_timeout_checkpoint.py
  tests/test_checkpoint_external_step_artifacts.py` — ноль совпадений в
  первом файле, во втором совпадения только на строках 163, 310, 329,
  344, 368, 392 — ни одно не строка 224, где по-прежнему сидит
  `test_timeout_marker_carried_and_deletion_still_matches_across_flavors`
  без заявки). Предложение — то же: дописать «Ловит мутацию: …» во все
  шесть перечисленных мест.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/checkpoint.py:151-197 | `_discard_out_of_mandate_changes` не обрабатывает git-статус `R` (staged rename) — путь назначения не в HEAD, `checkout --` падает без проверки кода возврата | вне-мандатный файл остаётся на диске незакоммиченным, журнал AC-3 ложно сообщает об откате; независимой репро этой итерации дополнительно показано, что исходный файл внутри `tasks/<id>/` при этом тоже теряется физически | обработать `code[:1] == "R"` отдельной веткой (путь назначения — как новый/untracked) или не отчитываться об откате при неудачном checkout; без изменений с итерации 1, третья итерация без попытки |
| R1-F2 | open | tests/test_timeout_checkpoint.py:108,177,198,238,264; tests/test_checkpoint_external_step_artifacts.py:224 | 6 тестов без явной заявки «Ловит мутацию: …» в докстринге | ревьювер не может сверить тест с заявленной мутацией по правилу review-checklist п.3 | добавить явную строку «Ловит мутацию: …» в докстринги перечисленных тестов; без изменений с итерации 1, третья итерация без попытки |

## Вердикт

changes_requested — с момента итерации 1 в `orchestrator/checkpoint.py`
и профильные тесты не внесено ни одной правки: `git diff --stat
c0ab85fb HEAD -- orchestrator/checkpoint.py
tests/test_timeout_checkpoint.py
tests/test_checkpoint_external_step_artifacts.py` пуст. Второй раз
подряд автокоммит шага `developer` в ответ на вердикт `changes_requested`
пуст (`744e9afb` после итерации 1, `8f11ddd1` после итерации 2) — роль
не сделала попытки ни исправить, ни отклонить замечания. Оба замечания
(R1-F1 — major, R1-F2 — minor) остаются в силе, независимо
переподтверждены в этой итерации. До исправления R1-F1 (обязательно) и
R1-F2 (желательно в том же заходе) задача не может получить `approved`.
Остальная функциональность (AC-1, AC-4..AC-9) по-прежнему корректна и
зелена.

## Проверено исполнением

- `git checkout -- tasks/01M1NBWTSXEJB24PXR417YF1VA/` — восстановлен
  каталог задачи, пропавший из рабочего дерева (файлы присутствуют в
  истории кодовой ветки).
- `python3 scripts/guard.py tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md
  tasks/01M1NBWTSXEJB24PXR417YF1VA/PLAN.md` — `GUARD: ок (2 файлов)`.
- `git diff --stat c0ab85fb HEAD -- orchestrator/checkpoint.py
  tests/test_timeout_checkpoint.py
  tests/test_checkpoint_external_step_artifacts.py` — пусто (код и
  тесты не менялись с ревизии итерации 1); то же самое относительно
  `58992242` (ревизия итерации 2).
- `git diff-tree -r 8f11ddd1` и `git diff --stat 58992242 8f11ddd1` —
  оба пусты (автокоммит шага `developer` после итерации 2 не содержит
  правок).
- `python3 -m unittest tests.test_timeout_checkpoint
  tests.test_checkpoint_external_step_artifacts -v` — 33 теста, все
  зелёные (сценарий rename ими не покрыт — R1-F1 этим набором не
  ловится).
- `python3 -m unittest discover -s tasks/01M1NBWTSXEJB24PXR417YF1VA/
  acceptance_tests -p "test_ac*.py" -v` — 11 тестов (AC-1..AC-8), все
  зелёные (сценарий rename не покрыт).
- `python3 -m unittest discover -s tests` — 1418 тестов, `OK` (AC-9,
  без изменений численности со времён итерации 2).
- Независимое ручное воспроизведение R1-F1 в
  `$SCRATCHPAD/r1f1check` (отдельный репозиторий, не переиспользован
  из прошлых итераций): `git init`, коммит `tasks/T1/foo.py`, `git mv
  tasks/T1/foo.py orchestrator_new.py` → `git status --porcelain=v1`
  даёт `R  tasks/T1/foo.py -> orchestrator_new.py`; симуляция функции
  (`git reset -q -- orchestrator_new.py`, затем `git checkout --
  orchestrator_new.py`) → код возврата 1, `error: pathspec
  'orchestrator_new.py' did not match any file(s) known to git`;
  итоговый статус — `D  tasks/T1/foo.py`, `?? orchestrator_new.py`:
  вне-мандатный файл не откачен И исходный файл в `tasks/<id>/`
  потерян физически. Подтверждает R1-F1 и вскрывает дополнительное
  следствие (порча `tasks/<id>/`), не описанное явно в прошлых
  итерациях.
- `grep -n "Ловит мутацию" tests/test_timeout_checkpoint.py
  tests/test_checkpoint_external_step_artifacts.py` — ноль совпадений
  в первом файле; во втором — только строки 163, 310, 329, 344, 368,
  392 (строка 224 по-прежнему без заявки).
- `grep -rn "rename\|git mv\|code\[:1\] in" tests/*.py
  tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/*.py` — совпадений
  по существу задачи нет (единственное совпадение — `tests/
  test_amend.py:106`, к этой задаче не относится).

## Предложения системе

- Класс «шаг роли не даёт вообще никакого прогресса между итерациями
  ревью» (отмечен в итерации 2 как наблюдение) подтвердился ВТОРОЙ раз
  подряд на этой же задаче: `744e9afb` (после итерации 1) и `8f11ddd1`
  (после итерации 2) — оба пустые автокоммиты. Реестр замечаний
  рассчитан на `fixed`/`rejected` от роли, но не описывает, что делать
  ревьюверу или пульту, если роль на протяжении нескольких итераций
  вообще не отвечает — стоит завести отдельный сигнал (например,
  счётчик пустых ответов подряд) и эскалировать его пульту/Оператору,
  а не оставлять задачу крутиться в review без изменений.
