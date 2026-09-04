---
task: 01M1NBWTSXEJB24PXR417YF1VA
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: WIP-чекпоинт после таймаута: зона роли и артефактная ветка

## Фаза A: гейт плана

1. Покрытие требований в PLAN.md — таблица «Покрытие требований» закрывает
   все 4 требования SPEC шагами 1–5; сами шаги (1–6) — проверяемые единицы
   размера MR (по одной функции/группе тестов на шаг), не микрооперации.
2. Подход не конфликтует с конвенциями: подтяжка `main` (зависимость по
   зонам с 01M1KVG3KSCY47HWXWF5HM0E76) описана отдельным шагом 6 с явным
   разрешением конфликта в `_commit_external_step_artifacts` и
   регенерацией карты — конвенция `conventions-core` про «подтяжка меняет
   *.py — регенерируй карту» соблюдена (проверено: `docs/codebase-map.md`
   после `python3 scripts/codebase_map.py` расходится с деревом только
   строкой `built_at_sha`, содержимое карты свежее).
3. План не ослабляет существующие инварианты (`commit_abnormal_checkpoint`/
   `commit_pause_now_checkpoint` не тронуты, `exclude` — опциональный
   параметр с дефолтом `None`) — подтверждено чтением полного файла
   `orchestrator/checkpoint.py`, не только диффа.

Гейт плана пройден, замечаний к PLAN.md по существу нет.

## Фаза B: ревью MR

## Соответствие SPEC

| Требование/AC | Вердикт | Комментарий |
|---|---|---|
| Требование 1 / AC-1 | OK | `developer` коммитит все пути worktree кроме `tasks/<id>/` (`exclude` у `_commit_worktree_change`, `checkpoint.py:113-114`) — подтверждено юнит- и приёмочным тестом. |
| Требование 1 / AC-2 | реализовано не так (см. R1-F1) | `analyst`/`test_author`/`reviewer` не коммитят в кодовую ветку — верно; но «откатываются» выполняется некорректно для одного класса git-статусов (staged rename), см. замечание. |
| Требование 1 / AC-3 | OK | Журнал называет отброшенные пути и суммарное число строк (`_discard_out_of_mandate_changes`, `checkpoint.py:199`) — подтверждено тестами `test_ac3_*`, `test_non_developer_role_discards_change_outside_task_dir`. |
| Требование 2 / AC-4 | OK | `_commit_external_step_artifacts(..., timeout=True)` вызывается безусловно для любой роли (`checkpoint.py:129-130`), `tasks/<id>/` не попадает в кодовую ветку — подтверждено `test_ac4_*` для `developer` и `test_author`. |
| Требование 2 / AC-5 | OK | Пометка «WIP после таймаута» в сообщении артефактного коммита (`checkpoint.py:402-404`) — подтверждено `test_ac5_*`. |
| Требование 3 / AC-6 | OK | Сообщение и журнал код-коммита называют роль и «таймаут» (текст не менялся, только область применения) — подтверждено `test_ac6_*`. |
| Требование 4 / AC-7 | OK | Сквозной сценарий `test_author` через реальный `runner.cmd_run` — зелёный. |
| Требование 4 / AC-8 | OK | Сквозной сценарий `developer` через реальный `runner.cmd_run` — зелёный. |
| Требование 4 / AC-9 | OK | Полный `tests/` — 1390 тестов, зелёные (см. «Проверено исполнением»); ни один существующий тест не ослаблен, только дополнен предусловием (`write_code_file`) там, где это требуется новым мандатом. |

## Замечания

- major — `orchestrator/checkpoint.py:134-199` (`_discard_out_of_mandate_changes`) —
  функция классифицирует путь как «новый, без истории в HEAD» по
  `code[:1] in ("A", "?")` (строка 176) и иначе безусловно вызывает
  `git checkout -- <rel>` (строка 196). Для git-статуса `R` (застейженный
  rename, ОБА конца которого — независимо от того, пересекает ли rename
  границу `tasks/<id>/` или нет — оказываются вне `tasks/<id>/`) путь
  классифицируется как «трекенный», и `git checkout -- <новый_путь>`
  завершается ошибкой (`pathspec ... did not match any file(s) known to
  git`, код возврата не проверяется, строка 196), потому что новый путь
  не существует в HEAD. Итог — файл остаётся на диске незакоммиченным
  вне мандата роли, а `paths.append(rel)` (строка 197) всё равно
  добавляет его в список «отброшенных» для журнала: AC-2 («откатываются
  командой git checkout --») нарушено по факту, а запись журнала AC-3
  лжёт о результате. Воспроизведено вручную (не через тесты пакета,
  которых на этот случай нет): `git mv` внутри рабочего дерева, staged
  rename `tasks/T1/foo.py -> orchestrator/foo.py`, `git status
  --porcelain=v1` даёт `R  tasks/T1/foo.py -> orchestrator/foo.py`;
  `git checkout -- orchestrator/foo.py` после `reset` возвращает код 1 и
  ничего не делает — файл остаётся в `orchestrator/`. Предпосылка не
  экзотична: конвенция `conventions-core` предполагает, что роль сама
  коммитит свою работу (`git add`/`git commit`) в рамках обычного шага —
  если процесс роли обрывается таймаутом ПОСЛЕ `git add` рендера, но ДО
  завершения коммита, застейдженный rename переживает обрыв ровно в этом
  виде. Класс дефекта — один (обработка git-статуса `R` в этой функции),
  проявляется в обеих формах: rename ЦЕЛИКОМ вне `tasks/<id>/` (файл,
  который должен быть отброшен, остаётся) и rename, пересекающий границу
  `tasks/<id>/` в любую сторону. Предложение: отдельная ветка для
  `code[:1] == "R"` — доставать оба пути (`rel.split(" -> ", 1)`, до и
  после), откатывать/удалять каждый по своей природе (старый путь —
  трекенный, восстановить через `checkout`; новый — учитывать, есть ли
  он в HEAD хоть под каким-то именем), либо, проще, при неудачном
  `checkout`/неизвестном статусе не добавлять путь в `paths` и не
  учитывать его в журнале как «отброшенный», раз откат фактически не
  случился.

- minor — `tests/test_timeout_checkpoint.py:108,177,198,238,264`,
  `tests/test_checkpoint_external_step_artifacts.py:224` — шесть
  новых/изменённых тестов (`test_dirty_tree_commits_with_message_sha_
  and_journal_entry`, `test_git_diff_failure_commits_nothing_and_
  journals_nothing`, `test_git_commit_failure_commits_nothing_and_
  journals_nothing`, `test_developer_mandate_excludes_task_dir_from_
  code_commit`, `test_non_developer_role_discards_change_outside_task_
  dir`, `test_timeout_marker_carried_and_deletion_still_matches_across_
  flavors`) не несут в докстринге явную заявку `Ловит мутацию: …`
  (skills/test-authoring.md, п.3 review-checklist) — докстринги
  объясняют, ПОЧЕМУ понадобилась правка теста/новый тест, но не
  формулируют явно, какая мутация им ловится (для двух новых тестов в
  `test_timeout_checkpoint.py` вообще нет описания сценария поломки, для
  остальных четырёх — оно растворено в объяснении контекста). Приёмочные
  тесты `tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/test_ac*.py`
  этим не страдают — там заявка явная и точная во всех случаях.
  Предложение: добавить явную строку «Ловит мутацию: …» в перечисленные
  докстрины (содержательно материал для неё уже есть в тексте — не
  требует нового анализа, только формулировки).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/checkpoint.py:134-199 | `_discard_out_of_mandate_changes` не обрабатывает git-статус `R` (staged rename) — новый путь не в HEAD, `checkout --` падает без проверки кода возврата | вне-мандатный файл остаётся на диске незакоммиченным, журнал AC-3 ложно сообщает об откате | обработать `code[:1] == "R"` отдельной веткой (оба пути rename) или не отчитываться об откате при неудачном checkout |
| R1-F2 | open | tests/test_timeout_checkpoint.py:108,177,198,238,264; tests/test_checkpoint_external_step_artifacts.py:224 | 6 новых/изменённых тестов без явной заявки «Ловит мутацию: …» в докстринге | ревьювер следующей итерации не может сверить тест с заявленной мутацией по правилу review-checklist п.3 | добавить явную строку «Ловит мутацию: …» в докстринги перечисленных тестов |

## Вердикт

changes_requested — исправить R1-F1 (обработка staged rename в
`_discard_out_of_mandate_changes`, с тестом на этот сценарий: например,
`git mv` файла из `tasks/<id>/` в код и наоборот, застейдженные до
таймаута) и R1-F2 (докстрины «Ловит мутацию»). Остальное — SPEC
реализован корректно, планка и новые тесты зелёные.

## Проверено исполнением

- `python3 scripts/guard.py tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md tasks/01M1NBWTSXEJB24PXR417YF1VA/PLAN.md` — `GUARD: ок (2 файлов)`.
- `python3 -m unittest tests.test_timeout_checkpoint tests.test_checkpoint_external_step_artifacts -v` — 33 теста, все зелёные.
- `python3 -m unittest discover -s tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests -p "test_ac*.py" -v` — 11 тестов (AC-1..AC-8), все зелёные.
- `python3 -m unittest discover -s tests` — 1390 тестов, `OK` (AC-9, полный регресс-щит).
- `python3 scripts/codebase_map.py` — карта расходится с деревом только строкой `built_at_sha`, содержимое свежее (правку отменил, не коммитил).
- Ручная проверка R1-F1: `git init`, коммит `tasks/T1/foo.py`, `git mv tasks/T1/foo.py orchestrator/foo.py`, `git status --porcelain=v1 --untracked-files=all` → `R  tasks/T1/foo.py -> orchestrator/foo.py`; `git reset -q -- orchestrator/foo.py` + `git checkout -- orchestrator/foo.py` → код возврата 1, `error: pathspec 'orchestrator/foo.py' did not match any file(s) known to git`, файл остался на диске — воспроизводит поведение, которое даёт `_discard_out_of_mandate_changes` в этом сценарии.
- Контрольная проверка (что типичный, НЕ застейдженный случай работает верно): та же пара путей БЕЗ `git mv` (обычное удаление + новый untracked-файл) — `git status` даёт раздельные `D`/`??`, оба конца рема корректно обрабатываются (файл восстановлен, новый — удалён).

## Предложения системе

- Класс «различение git-статуса по первому символу без учёта `R`
  (rename)» — если подобная логика (откат/удаление по мандату путей)
  понадобится ещё раз где-то ещё в пульте, стоит сразу закладывать ветку
  для rename, а не по факту находки на ревью.
