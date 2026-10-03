---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Отмена CI на документах и режима `guard --artifact-branch`

## Соответствие SPEC

Фаза A (план): таблица покрытия полна (требования 1–6 → шаги 1–3 и
приложения 1–3). Шаги размером с MR. Подход совпадает с ADR-0021 п.12:
защищённые пути — приложениями, код — в ветке, всё уходит одним мержем.
Раздел «Влияние на систему» сходится с диффом: в ветке изменены только
`scripts/guard.py`, `scripts/ci_push_class.py`, три файла `tests/` и
карта — всё в `zones`. Защищённые пути в ветке не тронуты. Путь отката
описан (revert merge-коммита).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (ci.yml приложением) | OK | Приложение 1: `artifact/**` убран из `on.push.branches`, развилка `GUARD_ARGS`/`--artifact-branch` убрана (`python3 scripts/guard.py --all`), условие `canary-guid-leak` больше не ссылается на `refs/heads/artifact/`. На наложенном дереве `grep artifact ci.yml` находит только комментарии и `refs/artifacts/` сторожа ссылок. |
| 2 (класс `artifact/` в ci_push_class) | OK | `scripts/ci_push_class.py:116-118`: правило удалено, `artifact/<x>` идёт общим правилом не-`main` ветки. |
| 3 (режим guard) | OK | `ARTIFACT_BRANCH_FLAG`, `_artifact_branch_report`, `is_draft_lenient`, `basic_frontmatter_errors`, `DRAFT_LENIENT_TYPES`, `BASIC_META_FIELDS` и параметр `artifact_branch_mode` удалены. `git grep` по `orchestrator/ scripts/ tests/ skills/` находит только тексты тестов об отсутствии режима. Модульный докстринг и комментарии `main()`/`_content_errors` поправлены. Путь без флага в `main()` дословно прежний. |
| 4 (без новых гейтов и ослаблений) | OK | Гейты не тронуты. Мягкий режим черновиков снят — это ужесточение. `fsm.guard_refuses`/`check` параметр режима не передавали. |
| 5 (invariants.md + test_invariants.py приложением) | OK | Приложения 2 и 3 проходят `git apply --check` (проверено мной). На наложенном дереве номер 36 один, `| 39 |` — порядок FSM, дублей номеров нет. `CiJobsByPushClassInvariantTest` — 9 passed. ADR-0003/0007/0015 ссылаются на 39, ADR-0016 уточнён. Ссылки в `docs/research/…` и `docs/backlog.md` не правлены, обоснование в PLAN выдерживает критику (вне зон и вне защищённых путей, бэклог по SPEC только читается). |
| 6 (перечень тестов) | OK | Перечень в PLAN совпадает с диффом `tests/`. Мандат — ANSWER-1, уточнён ANSWER-2 (файл `tests/test_guard_artifact_branch_mode.py` целиком и три метода `tests/test_ci_push_class.py`). Подробная сверка — в «Замечаниях». |

## Замечания

Замечаний уровня blocker/major/minor нет. Что именно проверено:

- **Сверка утверждений с base, `tests/test_ci_push_class.py`.** Утверждения
  `test_artifact_branch_is_code_false…` → `…_code_true…` (`assertFalse` →
  `assertTrue`, `run.assert_not_called()` сохранён) и
  `OutputFormatTest::test_script_prints_code_and_reason_lines` (вход
  сменён на `pull_request`, проверки «две строки, `code=` первой, код 0»
  сохранены) изменены прямо по требованию 2 SPEC и покрыты мандатом.
  `test_artifact_branch_code_is_false` удалён. Его свойство, обращённое
  требованием 2, держит долгоживущий AC-1. Сужения данных под неизменными
  утверждениями (`setUp`, циклы, фикстуры) в диффе нет.
- **`tests/test_guard_artifact_branch_mode.py`.** 12 методов
  `IsDraftLenientTest`/`BasicFrontmatterErrorsTest` и 3 метода
  `CheckContentDefaultIsUnaffectedTest` проверяли только удалённые по
  требованию 3 функции и параметр. Удаление покрыто ANSWER-2.
  Сохранённый `test_default_call_reports_full_content_errors_for_a_draft`
  утверждения не менял. Новая заявка мутации («льготный режим для
  черновика») наблюдаема: список ошибок потеряет «отсутствует
  обязательная секция».
- **Заявки мутаций.** Проверены временной мутацией во временной копии
  дерева, рабочий каталог не трогал:
  - возврат правила `artifact/` → `code=False` — красные
    `test_artifact_branch_is_code_true_without_touching_git_or_gh` и
    `test_ac1_…`;
  - возврат параметра `artifact_branch_mode` в `check_content` —
    красный `test_ac2_check_content_has_no_artifact_branch_mode_parameter`.

  Четыре новых `test_planted_*` приложения 2 сами вносят мутацию в текст
  `ci.yml` и утверждают находку — на наложенном дереве зелёные.
- **Долгоживущие свойства.** AC-1/AC-2 держит
  `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`
  (`Группа: долгоживущий`, свойства кода — граница верна). AC-3/AC-4
  после применения приложений держит `CiJobsByPushClassInvariantTest`
  в `tests/test_invariants.py`. Разовая планка
  `test_ac3_ac4_plan_attachments.py` проверяет факт задачи (приложения
  PLAN), помечена разовой — верно.
- **Повтор долгоживущего.** Переименованный
  `test_artifact_branch_is_code_true_…` пересекается с AC-1 по `code`,
  но проверяет отдельное свойство (git/gh не вызываются). Метод
  существовал в base и правлен по мандату — повтором по ADR-0020 п.4
  не считаю.
- **Код в общем виде.** Под литералы планки ничего не подогнано.
  `--artifact-branch` теперь обычный незнакомый аргумент: трактуется как
  путь, «файл не найден», код 1 — ровно то, что требует AC-2.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved — 0 blocker/major. Код отвечает требованиям 2–4. Приложения 1–3
применяются на чистом дереве и дают зелёный
`CiJobsByPushClassInvariantTest`. Изменения тестов покрыты мандатом
ANSWER-1/ANSWER-2 и требованиями SPEC.

## Проверено исполнением

- `guard.plan_appendices(PLAN.md)`: 3 приложения, ошибок разбора нет.
  `git apply --check -v` всех трёх подряд на чистом дереве HEAD 77e5787b
  — «Checking patch» по 7 файлам, код 0.
- Временная копия HEAD (`git archive` в /tmp) с наложенными приложениями
  1–3:
  - `python3 -m pytest tests/test_invariants.py -k CiJobsByPushClass` —
    9 passed;
  - `grep artifact .github/workflows/ci.yml` находит только комментарии
    и `refs/artifacts/` сторожа ссылок;
  - в `docs/invariants.md` одна строка `| 36 |`, дублей номеров нет;
  - `grep 'инвариант* 3[69]' docs/adr` — ссылки ADR-0003/0015 на 39,
    ADR-0016 на первый 36.
- `python3 -m pytest tests/test_ci_push_class.py
  tests/test_guard_artifact_branch_mode.py
  tests/test_guard_extraneous_acceptance_files.py
  tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py
  tests/test_guard_schema.py tests/test_guard_zones.py
  tests/test_advance_guard.py` в рабочем каталоге — 107 passed,
  34 subtests passed.
- Временные мутации во временной копии, код потом возвращён:
  - правило `artifact/` → `code=False` — 2 failed (названы выше);
  - параметр `artifact_branch_mode` возвращён в `check_content` —
    1 failed (`test_ac2_check_content_has_no_artifact_branch_mode_parameter`).
- `artel.py plank-run 01M41VTQJ9DSX64NFMFAF9W53B` — и без файла, и с
  `test_ac3_ac4_plan_attachments.py` — отказ сторожем полного набора,
  код 2 (воспроизводит наблюдение разработчика). Поэтому планку прогнал
  `python3 -m unittest discover -s <каталог документов>/acceptance_tests
  -p test_ac3_ac4_plan_attachments.py`, без копирования в рабочий каталог
  — Ran 7 tests, OK. После прогона `git worktree list` чист: временное
  дерево планки убрано.
- `scripts/codebase_map.py` во временной git-копии HEAD — содержимое
  карты без строки `built_at_sha` совпадает с закоммиченной: карта свежа.

## Предложения системе

- `orchestrator/plank_run.py` + сторож роли полного прогона: `plank-run
  <id> [файл]` в шаге ревьювера отказывает «полный прогон набора
  запрещён» (код 2) даже с явно названным файлом. Прямой `pytest
  <каталог документов>/acceptance_tests/<файл>` отказывает так же,
  проходит только `unittest discover -s … -p <файл>`. Штатная команда
  планки непригодна в шагах developer и reviewer этой задачи (подтверждаю
  копилку PLAN). Сторож, видимо, сопоставляет командную строку
  вложенного pytest с шаблоном `tasks/<id>/acceptance_tests/`, которому
  абсолютный путь не соответствует.
