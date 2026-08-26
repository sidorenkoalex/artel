---
task: T042
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Авто-коммит регенерированной карты кодовой базы оркестратором на merge_gate

## Фаза A — гейт плана
Покрытие требований в PLAN.md полное (таблица 1–6 → шаг 1). Шаг 1 — единая
проверяемая единица размера MR (~40 строк логики + два файла тестов), не
«сделать всё» — оправдано тем, что вся логика завязана на одну
merge-последовательность и не расползается по модулям. Подход (встраивание
в `orchestrator/fsm.py`, `gitcmd.git` для git-вызовов, прямой
`subprocess.run` для регенерации по образцу `brief._regenerate_map`) не
конфликтует с конвенциями и существующей архитектурой. Раздел «Влияние на
систему» проверен против фактического diff — соответствует (см. ниже).
Гейт плана пройден.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_regenerate_and_commit_map` вызывается в `cmd_approve` между merge и push (`orchestrator/fsm.py:519`), гоняет `scripts/codebase_map.py`. Подтверждено прогоном `tests/test_fsm_map_regen.py` и `tasks/T042/acceptance_tests/test_map_regen_on_merge.py` (AC-1/AC-2). |
| 2 | OK | Сверка через `_map_content_without_sha` (fsm.py:15-22) игнорирует только `built_at_sha:`; коммит с сообщением `«карта кодовой базы: регенерация после merge <id>»` (fsm.py:74-76). AC-1 зелёный. |
| 3 | OK | При отсутствии содержательной разницы — `git checkout -- docs/codebase-map.md` через `gitcmd.git`, коммита нет (fsm.py:60-67). AC-2 зелёный. |
| 4 | OK | `git push` вынесен из цикла merge-команд в отдельный шаг после `_regenerate_and_commit_map` (fsm.py:519-524); один push на merge-коммит и коммит карты. Подтверждено `Ac1...Test` (`subcommands.count("push") == 1`). |
| 5 | Реализовано не так | Штатные отказы (regen rc≠0, `git add`/`commit`/`checkout` вернули ненулевой код) действительно не блокируют merge — incident заводится, push выполняется, задача уходит в `done` (AC-3 зелёный). Но гарантия «функция никогда не бросает исключение» (fsm.py:41-42) не выполнена целиком — см. Замечание 1: два необёрнутых вызова способны кинуть исключение, которое дойдёт до `cmd_approve` и сорвёт `git push`/переход в `done`, то есть нарушит именно то, что требование 5 обещает. |
| 6 | OK | Единственный не-git `subprocess.run` — регенерация карты (не git-вызов). Статическая проверка AST (`NewGitCallsGoThroughGitcmdTest`, AC-4) зелёная — прямых `subprocess.run(["git", ...])` в `fsm.py` нет. |

## Замечания

- major — `orchestrator/fsm.py:52-53` и `orchestrator/fsm.py:59` — в
  `_regenerate_and_commit_map` два вызова не защищены от исключений, хотя
  докстринг функции (fsm.py:41-42) и требование 5 SPEC явно обещают, что
  «эта функция никогда не бросает исключение», а любой провал уходит в
  incident без остановки merge:
  - `regen = subprocess.run(["python3", "scripts/codebase_map.py"], ...)`
    (строка 52) — `subprocess.run` умеет бросать `OSError`
    (`FileNotFoundError`, если `python3` не резолвится в PATH среды,
    `PermissionError` и т.п.), и это НЕ обёрнуто в `try/except`, в отличие
    от первого чтения файла строкой выше (46-49), где та же категория
    ошибки уже поймана.
  - `regenerated = map_path.read_text(encoding="utf-8")` (строка 59) — тот
    же файл, что уже один раз читался с `try/except OSError` (46-49),
    здесь читается без защиты.
  Сценарий поломки: `python3` недоступен в среде запуска оркестратора (или
  файл карты стал недоступен между двумя чтениями — гонка/квота диска) →
  `subprocess.run`/`read_text` кидает `OSError` → исключение уходит из
  `_regenerate_and_commit_map` необработанным (в `cmd_approve`,
  `orchestrator/fsm.py:519`, вызов этой функции ничем не обёрнут) → `git
  push` (строка 520) не выполняется, `store.set_state(..., "done", ...)`
  не вызывается → merge-коммит уже применён к локальному чекауту `main`
  (checkout/pull/merge выше уже прошли), но не запушен, а задача осталась
  в `merge_gate` в БД — ровно то, что требование 5 запрещает («push
  выполняется в любом случае», «провал... не блокирует переход в done»).
  Ни один из тестов (`tests/test_fsm_map_regen.py`,
  `tasks/T042/acceptance_tests/...`) не бьёт по этому пути — они проверяют
  только `regen.returncode != 0`, не исключение из самого
  `subprocess.run`/`read_text`.
  Предложение: обернуть оба вызова (строки 52-53 и 59) в тот же
  `try/except OSError` → `_map_regen_incident`, что уже есть для первого
  чтения (46-49); добавить юнит-тест на `subprocess.run` кидающий
  `OSError` (`side_effect=OSError(...)`) и на `read_text` второго чтения,
  падающий аналогично. Тот же паттерн (`_regenerate_map`,
  `orchestrator/brief.py:80,85`) страдает тем же пробелом — не блокер этой
  задачи (не в её зоне, `brief.py` не тронут diff'ом), но стоит записать в
  беклог отдельной строкой: там цена ошибки ниже (это не merge-путь), но
  дефект тот же.

## Тесты
Прогнаны:
- `python3 -m unittest tests.test_fsm_map_regen -v` — 9/9 ok.
- `python3 -m unittest tasks.T042.acceptance_tests.test_map_regen_on_merge -v` —
  6/6 ok (AC-1..AC-4, AC-6; AC-5 размечен `manual` с обоснованием,
  прецедент T036).
- `python3 -m unittest discover -s tests -v` — 634 теста, 3 упавших
  (`tests/test_multitarget.py::RoleEnvTest`, git-идентичность в env).
  Проверено на `main` (чистый worktree, без diff этой ветки) — те же 3
  теста падают там же, по той же причине (локальный git-конфиг машины
  просачивается в `GIT_AUTHOR_NAME`/`GIT_COMMITTER_EMAIL`/сообщение об
  отсутствии идентичности). Не регрессия этой задачи — AC-5 выполнен.
- `python3 scripts/codebase_map.py` вручную: после регенерации разница с
  закоммиченной `docs/codebase-map.md` — только `built_at_sha`; карта в
  этой ветке содержательно свежа (рабочее дерево возвращено `git checkout
  --` после проверки).
Тесты покрывают требования (не структуру): мутация «убрать откат при
отсутствии содержательных отличий» ловится AC-2/`test_only_built_at_sha_...`;
мутация «не заводить incident» ловится всеми `test_*_failure_*`
юнит-тестами и AC-3; мутация «push внутри цикла merge» ловится
`Ac1...Test` (порядок `commit` < `push`, единственный `push`). Единственный
непокрытый мутационно путь — сам предмет Замечания выше (необработанное
исключение).

## Вердикт
changes_requested — исправить Замечание 1 (обернуть `subprocess.run` и
второе чтение карты в `_regenerate_and_commit_map` в `try/except OSError`,
как уже сделано для первого чтения), добавить тест на этот путь. Остальное
— готово к мержу без изменений.
