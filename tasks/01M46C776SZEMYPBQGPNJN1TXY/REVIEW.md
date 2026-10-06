---
task: 01M46C776SZEMYPBQGPNJN1TXY
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Полный прогон tests/ пульта на дереве «ветка плюс приложения PLAN»

## Фаза A — план

- Таблица покрытия полна: требования 1–7 разнесены по шагам 1–3, шаг 4 —
  юнит-тесты и карта.
- Шаги размером с MR: общий узел, перевод гейта мержа, три потребителя,
  тесты. Микроопераций и шага «сделать всё» нет.
- Подход не спорит с архитектурой. Узел вынесен из гейта мержа
  (`apply_in_order`, `read_plan`), гейт мержа зовёт его же; это
  требование 7, а не параллельная копия. «Влияние на систему» совпадает
  с diff: 5 файлов `orchestrator/`, 1 новый тест, карта. Защищённые пути
  и существующие тесты не тронуты (`git diff --stat f7a46d84...HEAD --
  tests/ conftest.py targets.yaml .github skills templates gates.yaml
  roles.yaml` — только три новых файла `tests/`, одни добавления). Откат
  описан: revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `appendix_tree.suite_tree`: автогейт (`fsm_autogate.py` ~303) и approve (`fsm.py` ~1111) получают `branch=t["branch"]`, то есть голову ветки. `suite-run` (`suite_run.py` ~460) — HEAD рабочей копии плюс `_carry_uncommitted`. Разбор — `guard.plan_appendices`, наложение — `git_apply` через `apply_in_order` по порядку PLAN, источник — `artifact_source.resolve` + `artifact_branch.show`, как у гейта мержа. |
| 2 | OK | `git worktree add --detach` в `mkdtemp`. В `finally` контекстного менеджера: `worktree remove --force`, `rmtree`, `prune`. Рабочая копия только читается (`diff --name-only`, `ls-files --others`, копирование файлов). AC-5/AC-8 зелёные. |
| 3 | OK | Не артель или PLAN без приложений: `SuiteTree(wt, …)`. AC-9 зелёный по всем трём входам. |
| 4 | OK | Неприменимое приложение: `_inapplicable_refusal` называет номер и пути. Сбой `rev-parse`, `worktree add`, листинга или копирования — `root=None`. Автогейт возвращает «автогейт: …», approve — «approve отклонён» (`--accept-red` отказ не снимает, это правильно), `suite-run` — «отказ — …» с `green=False`. Непрочитанный PLAN (`artifact_branch.show` → `None`) деградирует в прогон без приложений с пометкой в detail — так же, как на гейте мержа (требование 1: тот же источник и тот же исход); в «Не входит» это не противоречит. |
| 5 | OK | `SuiteTree.mark` дописывает «[с приложениями PLAN: <пути>]» к detail зелёного и красного прогона и к записи `--accept-red` (approve); к условию «полный набор зелёный» и отказу (автогейт); строка «прогон ветки […]» в отчёте `suite-run`. AC-10 зелёный. |
| 6 | OK | `_base` в `suite_run.py` не тронут, AC-11 зелёный. Итог гейта по sha с грязного дерева приложений не сохраняется: `clean_tree_sha` → `None`, `acceptance.py:842-872`. |
| 7 | OK | `_apply_plan_appendices` зовёт `apply_in_order` с тем же `_appendix_already_in_main`. Отказ `_return_inapplicable_appendix` получает те же `appendix`/`answer`. Текст «приложения PLAN не прочитаны» побайтно прежний (`unread` = прежняя строка «PLAN.md не читается с ветки …»). `_FULL_SUITE_APPENDIX_PREFIXES` не тронут. AC-12 и прежние тесты гейта мержа зелёные. |

## Замечания

Нет замечаний уровня blocker/major/minor.

Проверено, дефектов не найдено:
- `return` и исключение внутри `with suite_tree(...)` (approve, `suite-run`) — уборку выполняет `finally` генератора. Исключение в `_prepared` тоже проходит через `finally` до отдачи значения.
- Гонка `git worktree prune` с параллельным временным деревом другого прогона: `prune` снимает только записи с отсутствующим каталогом, живое дерево не трогает.
- Тесты `tests/test_fsm_autogate.py` передают в `_autogate_conditions` `conn=object()`. `read_plan` передаёт `conn` только в `artifact_source.resolve`, а та его не использует (`artifact_source.py:24-26`), поэтому `AttributeError` не будет.
- `tests/test_appendix_tree.py`: у обоих методов есть заявки «Ловит мутацию», и мутации наблюдаемы. Тесты не повторяют долгоживущие файлы: перенос удалённого и неотслеживаемого файла и пропуск уже наложенного приложения там не проверяются.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_appendix_tree.py tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py` — 25 passed за 128 с. Это оба долгоживущих файла задачи (после правки фикстуры по ANSWER-1) и юнит-тесты узла. Каталог `acceptance_tests/` задачи несёт только `long_lived.sha256.txt`, разовой планки нет, поэтому `plank-run` гонять нечего.
- `python3 -m pytest -q -p no:cacheprovider tests/test_plan_appendix.py tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py tests/test_fsm_merge_gate_scratch_worktree_cleanup.py tests/test_fsm_autogate.py tests/test_fsm_autogate_long_lived.py tests/test_approve_acceptance_full_suite.py tests/test_suite_run.py tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` — 115 passed, 8 subtests passed за 199 с. Это затронутые модули: гейт мержа, автогейт, approve, `suite-run`.
- Временная мутация в `orchestrator/appendix_tree.py:127-128`: из `_carry_uncommitted` убран листинг `ls-files --others`. `tests/test_appendix_tree.py::PreparedTreeTest::test_uncommitted_deletion_and_untracked_file_reach_the_tree` покраснел: 1 failed, 1 passed. Код возвращён `git checkout`, `git status --porcelain` пуст.
- Ослабление тестов не обнаружено: `git diff --stat f7a46d84...HEAD -- tests/ …` показывает только новые файлы. Правка долгоживущего файла 688e1f82 сделана командой `amend-tests` по ANSWER-1, проверки не менялись. CI коммита 688e1f82 зелёный (по пакету).

## Предложения системе

- review-checklist / форма REVIEW: наблюдение без дефекта (например, осознанная деградация «PLAN не прочитан → прогон без приложений») не во что записать, кроме комментария таблицы. Любая строка в «Замечаниях» обязана попасть в реестр и тогда блокирует `approved`. Пригодилась бы явная секция «наблюдения без записи в реестр».
