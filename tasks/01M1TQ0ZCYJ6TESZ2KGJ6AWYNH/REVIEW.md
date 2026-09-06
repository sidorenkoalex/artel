---
task: 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: артефактная ветка новой задачи заводится от origin/main, а не от пина

## Фаза A: проверка плана

1. Покрытие требований SPEC таблицей PLAN.md полное (1→шаги 1-2, 2→шаг 2
   констатацией, 3→шаг 3, 4→шаг 4) — сверено построчно с разделом
   «Требования» SPEC.md, разрывов нет.
2. Шаги — проверяемые единицы размера MR (три функции: `gitcmd.
   fetch_head_sha`, `artifact_branch._new_branch_parent`, `doctor.
   check_artifact_branch_parent_ancestry`), не микрооперации и не «сделать
   всё».
3. Подход не конфликтует с конвенциями: новый git-примитив укладывается
   в существующий стиль `gitcmd.py` (пара `(значение, причина)`, `res is
   None`-деградация); включение в цепочку `or` ровно на месте старого
   `branch_head_sha(config.MAIN_BRANCH)` сохраняет короткое замыкание
   AC-4 без явного if. Решение по требованию 3 (новая проверка, не
   расширение чужой) обосновано и проверено мной независимо — ниже.

Независимая проверка обоснования шага 3 (не принимал слова PLAN на
веру): `git log origin/artifact/01m1tq0x14y5b3c87wc0q31pk2 --oneline`
показывает последний шаг `test_author` (SPEC/TZ/acceptance_tests),
шага `developer`/PLAN.md нет — расширять действительно нечего на
момент этой разработки. Довод PLAN подтверждён.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `gitcmd.fetch_head_sha` + `artifact_branch._new_branch_parent`, включено в `commit_files` вместо старого `branch_head_sha(config.MAIN_BRANCH)`; `git fetch` не двигает HEAD/индекс главной копии. |
| 2 | OK | Констатация подтверждена кодом: `catalog._new_external_artifact_branch` (вызывается для ЛЮБОГО target из `cmd_new`) зовёт `artifact_branch.commit_files` безусловно — отдельного пути для внешнего target нет и не появилось. |
| 3 | OK | `doctor.check_artifact_branch_parent_ancestry` — отдельная новая проверка (обоснование выбора между «расширить»/«новая» проверено мной независимо выше), `warn` при расхождении, `skip` без origin, вписана в `all_checks`. |
| 4 | OK | 4а/4б/4в покрыты приёмочными тестами AC-1/AC-6, AC-2, AC-7 (см. «Проверено исполнением»); 4г — `tests/test_artifact_branch*.py` не существует (подтверждено `find` независимо), `tests/test_catalog*.py` зелёные без правки ассертов. |

## Замечания

Замечаний нет.

## Реестр замечаний

Пусто — итерация 1, замечаний не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/ -v`
  — 7/7 зелёных (AC-1/AC-6, AC-2, AC-4, AC-5×2, AC-7). Прочитал каждый
  тестовый файл и `_sandbox.py`: докстринги несут «Ловит мутацию: …» с
  конкретным сценарием (замена origin на пин, отсутствие origin, отказ
  расширять цепочку `or` условно и т.д.), сценарии правдоподобны и
  реально проверяются сравнением sha/детектом файла-маркера/строки
  журнала, а не мысленным пересказом. `_sandbox.py` использует
  `tests.sandbox.RealGitSandbox` (настоящий git, не заглушка) — предмет
  проверки (поведение `git fetch`/`merge-base`) заглушкой не изобразить.
- `python3 -m pytest tests/test_gitcmd_branch_reads.py tests/
  test_gitcmd_carpentry.py tests/test_gitcmd_check_ignore.py tests/
  test_git_fixation.py tests/test_catalog_new_race.py tests/
  test_catalog_status_log.py tests/test_artifact_materialization.py
  tests/test_multitarget.py tests/test_multitarget_invariants.py -q` —
  151 passed, 14 subtests passed (2 мин 6 сек).
- `python3 -m pytest tests/test_doctor.py -q` — 122 passed, 3 subtests
  passed (полный файл, включает уже существующие проверки doctor +
  сам факт, что `all_checks` с новой проверкой в списке не ломает
  остальные тесты модуля).
- `find tests -iname "*artifact_branch*" -o -iname "*catalog*"` —
  подтвердил независимо от PLAN, что `tests/test_artifact_branch*.py`
  действительно не существует (AC-8, глобу нечего ловить); существующие
  `test_catalog_new_race.py`/`test_catalog_status_log.py` — в списке
  выше, зелёные.
- `python3 scripts/codebase_map.py` (регенерация во временную копию,
  сравнение построчно с закоммиченной версией через `grep -v
  '^built_at_sha:'`, затем `git checkout -- docs/codebase-map.md` —
  рабочее дерево оставлено чистым) — содержимое совпало байт-в-байт,
  кроме строки `built_at_sha`; регенерация карты этим коммитом
  корректна.
- `git log origin/main --first-parent --format='%ae' | sort | uniq -c`
  — проверил независимую гипотезу (не вошла в замечания, т.к. не
  подтвердилась): не полирует ли история `main` коммитами identity
  `orchestrator@artel.invalid` (той же, что несёт КАЖДЫЙ коммит
  артефактной ветки), что могло бы сломать эвристику `_artifact_branch_
  first_commit_parent` (граница по первому несовпадению email при
  обходе назад). 613/5/1 — все коммиты `--first-parent` main реальных
  людей/CI-идентичностей, ни одного `orchestrator@artel.invalid`;
  эвристика безопасна на сегодняшней истории. Не блокер и не
  предложение системе — фиксирую как проверенную гипотезу, не риск.
- Diff по `tests/` в этом MR — пуст (`git diff --stat` показывает
  только `docs/codebase-map.md`, `orchestrator/artifact_branch.py`,
  `orchestrator/doctor.py`, `orchestrator/gitcmd.py`): существующие
  ассерты не тронуты, ослабления/удаления гейтов и лимитов нет.
- `git status --short` после всех прогонов — чисто (кроме untracked
  `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/`, ожидаемо), рабочее дерево не
  оставлено с посторонними правками.

## Предложения системе

Пусто.
