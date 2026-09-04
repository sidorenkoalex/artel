---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: Сверка свежести ветки против main артели на origin

## Фаза A: гейт плана

Таблица покрытия PLAN.md полна (требования 1–5 → шаги 1–3, включая
дробление 5 на шаги 1+3). Шаги — единицы размера MR (три независимых
узла: `fsm.py` сверка/подтяжка, `fsm_merge_gate.py` ветка `"fresh"`,
`_origin_main_source`/`targets`), не микрооперации и не «сделать всё».
Подход не конфликтует с существующей архитектурой: переиспользует
`commits_behind(base=...)`, `confirmed_ci_note`, `_wait_for_branch_ci_green`,
поле `url`/`base` записи target'а — новых абстракций, кроме двух функций,
не вводит. Один системный риск в подходе не учтён явно ни в PLAN, ни в
коде — см. замечание R1-F1 ниже (Фаза B).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сверка/подтяжка против origin, не пина) | OK | `fsm._origin_main_sha`/`_pull_main_or_escalate` (fsm.py:128–261); AC-1/AC-4 приёмочные и юнит-тесты зелёные. |
| 2 (гейт `merge_gate` ждёт CI циклом на пути "fresh" после push) | OK | `fsm_merge_gate.py:284–296` возвращает `("wait", branch)` вместо разового опроса; AC-5/AC-7 зелёные. |
| 3 (расхождение пина не влияет ни на что, кроме `doctor`) | Реализовано не полностью | AC-8 (реальное расхождение пина, fetch УСПЕШЕН) — зелёный. Но путь деградации ЭТОЙ ЖЕ функции (fetch неудачен ИЛИ конфигурация target'а неисправна) не эквивалентен «ничего не делать», как заявляет докстринг — см. R1-F1. |
| 4 (существующие тесты зелёные, расширены не переписаны) | OK | 1355/1355 тестов `tests/` зелёные, 9/9 приёмочных зелёные (см. «Проверено исполнением»). Единственная правка ВНУТРИ существующего теста protected-файла (`tests/test_branch_freshness_gate.py`, `assertIn(config.MAIN_BRANCH,...)` → `assertNotIn(...)+assertIn("FETCH_HEAD",...)`) — не ослабление: строгость сохранена/усилена, изменение неизбежно следует из того, что требование 1 разворачивает старое поведение на противоположное; прокомментировано ссылкой на AC-2. |
| 5 (remote/репозиторий из конфигурации target'а) | OK (minor) | `_origin_main_source` (fsm.py:128–164); AC-10 юнит-тест зелёный. Тест кроет только путь «сверка», не путь «подтяжка/merge» для внешнего target'а — приемлемо, поскольку оба используют один и тот же `base` (см. «Проверено исполнением»); отдельно — R1-F2 (косметика commit message). |

## Замечания

- major — `orchestrator/fsm.py:259-261,273-274` — деградация `base =
  _origin_main_sha(target_name) or "FETCH_HEAD"` не эквивалентна
  заявленному «ничего не делать» и не защищена от гонки между двумя
  теперь-НЕ-под-мьютексом точками вызова — сценарий поломки ниже.
  Предложение: на `_origin_main_sha() is None` (обе причины — `TargetsError`
  И неудачный `git fetch`) `_pull_main_or_escalate` обязана вернуть
  `"fresh"` немедленно (тот же путь, что и `not behind`), не подставлять
  литерал `"FETCH_HEAD"` ни в `commits_behind`, ни в `merge` — по образцу
  уже существующего в этом же PR узла `fsm_merge_gate._origin_main_sha`,
  который на `None` явно `sys.exit`'ит, а не подставляет такой литерал.

- minor — `orchestrator/fsm.py:274` — commit-сообщение подтяжки жёстко
  называет `config.MAIN_BRANCH` («подтяжка main») даже когда фактический
  источник merge — `base` внешнего target'а (например, `trunk` из
  `targets.yaml`, требование 5/AC-10). Не влияет ни на один AC, но вводит
  в заблуждение при чтении истории коммитов внешнего target'а.
  Предложение: подставлять реальное имя смерженной ветки (второй элемент
  `_origin_main_source(target_name)`), не `config.MAIN_BRANCH` буквально.

### Сценарий поломки R1-F1

`_origin_main_sha` докстринг (fsm.py:128 и далее) заявляет: «`None` —
... вызывающий код обязан деградировать так же, как при неответившем
git» и «сверка ниже деградирует на "ничего не делать"». На практике это
не так для ОБОИХ путей к `None`:

1. **Конкурентность, новая в этом PR.** До этой задачи `_pull_main_or_
   escalate` не делала `git fetch` вовсе в двух из трёх точек вызова
   (`in_dev -> review`, `acceptance -> merge_gate`) — только третья
   (окно `merge_gate`) защищена `merge_lock` (единственный мьютекс на
   весь пульт, `orchestrator/merge_lock.py:1-8`). Теперь ВСЕ три точки
   делают `gitcmd.git("fetch", ...)` в общем `config.ROOT`
   (`gitcmd.py:9-19` — `git()` всегда `cwd=config.ROOT`), а две из трёх
   — БЕЗ какой-либо сериализации между разными задачами. Две разные
   задачи, одновременно проходящие `in_dev -> review`, реалистично
   могут столкнуться на `git fetch` в одном и том же репозитории (lock
   ref-файлов) — один из двух `fetch` завершится ненулевым кодом.
2. **`FETCH_HEAD` в `config.ROOT` — общее, устойчивое состояние, не
   «пусто по умолчанию».** В живом пульте оно почти всегда содержит
   что-то от ПРЕДЫДУЩЕГО успешного фетча (свой собственный —
   self-target фетчится регулярно и этим узлом, и уже существующим
   `fsm_merge_gate._origin_main_sha`; либо чужой — другого target'а).
   Поэтому на `_origin_main_sha() is None` (сбой fetch ИЛИ
   `targets.TargetsError` неисправной записи target'а) `base` —
   литерал `"FETCH_HEAD"`, и `gitcmd.commits_behind(branch,
   base="FETCH_HEAD")` (`gitcmd.py:47-66`, выполняется тоже в
   `config.ROOT`) сравнивает ветку задачи НЕ «ни с чем», а с ЧЕМ
   ПОПАЛО, что там сейчас лежит — в том числе, для внешнего target'а,
   с main АРТЕЛИ (или наоборот). Заявленная докстрингом гарантия
   «молчаливый откат ... был бы ОПАСНЕЕ обычной деградации» (PLAN,
   узел 3) для этого случая НЕ выполняется — обычная деградация здесь
   и есть тот опасный откат.
3. **Merge внутри `wt_path` (fsm.py:273) той же строкой `"FETCH_HEAD"`
   резолвится в СОВСЕМ ДРУГОЙ файл.** Начиная с git 2.5 `FETCH_HEAD`
   приватен для каждого worktree (подтверждено `git worktree --help`:
   «sharing everything except per-worktree files» и `git help
   gitrepository-layout`: «most of files in $GIT_DIR are per-worktree
   with a few known exceptions» — ровно тот факт, на который сам
   докстринг `_origin_main_sha` (fsm.py, комментарий про «начиная с git
   2.5») ссылается как на причину НЕ использовать литерал `"FETCH_HEAD"`
   в обычном случае). `gitcmd.in_repo(wt_path, "merge", ...)` —
   `git -C <wt_path> merge ...` (`gitcmd.py:104-115`) — то есть merge
   резолвит `"FETCH_HEAD"` в приватном `FETCH_HEAD` `wt_path`, НЕ в том,
   что только что (или год назад) зафетчил `config.ROOT`. В типичном
   случае worktree задачи никогда сам не фетчил — merge отказывает
   («not something we can merge»), задача ложно эскалируется на пустом
   месте (шум, ложные эскалации по вине временного сбоя фетча). Худший
   случай — worktree задачи когда-то нёс собственный `FETCH_HEAD»
   (например, ролевой агент вручную гонял `git fetch`/`git pull` внутри
   своего worktree в рамках разработки) — тогда merge молча вольёт
   СТАРОЕ/ПОСТОРОННЕЕ содержимое этого приватного `FETCH_HEAD`, и задача
   решит, что подтянула актуальный main, хотя это не так.

Ни один AC не покрывает деградацию `_origin_main_sha() is None` внутри
`_pull_main_or_escalate` (все AC-1..AC-10 проверяют путь, где
`git fetch` реально успевает — приёмочная песочница `OriginDivergedSandbox`
всегда исполняет настоящий git без искусственного сбоя фетча) — дефект
не поймается существующим набором.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/fsm.py:258-266 | Деградация `_origin_main_sha() is None` подставляет литерал `"FETCH_HEAD"` вместо истинного no-op | Сравнение/merge против постороннего состояния `config.ROOT`; для merge — против приватного `FETCH_HEAD` чужого worktree (ложная эскалация в типичном случае, риск тихого неверного merge в худшем) | `base = _origin_main_sha(target_name)`; `if not base: return "fresh"` — ранний выход ДО `commits_behind`/`merge`, литерал `"FETCH_HEAD"` убран целиком (fsm.py:258-266). Регресс-тест `tests/test_branch_freshness_gate.py::test_advance_treats_origin_fetch_failure_as_fresh` (вырожденная `_origin_main_sha` — `"fresh"`, `commits_behind`/`merge`/`acceptance.run` не звонятся); существующие тесты этого файла и `tests/test_fsm_map_conflict_autoresolve.py`, ранее полагавшиеся на falsy-деградацию `fake_git` (пустая строка из `rev-parse FETCH_HEAD`), адаптированы под truthy-заглушку `fsm._origin_main_sha` в `setUp` (не ослабление — тот же путь исполнения, что и раньше, просто явный мок вместо случайной пустой строки фейка) |
| R1-F2 | fixed | orchestrator/fsm.py:273-276 | Commit-сообщение подтяжки жёстко называет `config.MAIN_BRANCH`, даже когда реальный источник merge — `base` внешнего target'а | Вводящее в заблуждение сообщение коммита для не-self target'а (не влияет ни на один AC) | `source_branch = _origin_main_source(target_name)[1]` (или `config.MAIN_BRANCH` — вырожденный случай, source уже подтверждён truthy выше), commit-сообщение — `f"подтяжка {source_branch}"` вместо литерала `config.MAIN_BRANCH` (fsm.py:273-276); для self-target `source_branch == config.MAIN_BRANCH` — поведение байт-в-байт не меняется |

## Вердикт

changes_requested — один major (R1-F1): исправить деградацию
`_origin_main_sha() is None` в `_pull_main_or_escalate`, не подставляя
литерал `"FETCH_HEAD"` ни в сверку, ни в merge. R1-F2 — по возможности
в этой же итерации, не блокирует.

## Проверено исполнением

- Обнаружено: рабочее дерево на входе несло непроиндексированные
  удаления всего `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` (SPEC/PLAN/
  acceptance_tests) — восстановлено `git checkout --
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` (по прецеденту памяти, без
  переписывания), `git status` после — чисто.
- `python3 -m unittest discover -s tests -q` — 1355 тестов, `OK`
  (включая полный `tests/test_branch_freshness_gate.py`,
  `tests/test_merge_gate_ci_wait.py`, `tests/test_ci_status_kind_gate.py`,
  `tests/test_invariants.py`, `tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_gitcmd_branch_reads.py`).
- `python3 -m unittest discover -s tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests -p "test_ac*.py" -v` (запущено из каталога приёмочных тестов) — 9 тестов (AC-1..AC-9-заглушка), `OK`.
- `python3 scripts/codebase_map.py` (регенерация) — diff с закоммиченным `docs/codebase-map.md` отличается ТОЛЬКО строкой `built_at_sha` (сверено `git diff docs/codebase-map.md | grep -v '^[+-]built_at_sha'` — пусто, кроме заголовка); карта не устарела по содержимому. Рабочее дерево возвращено `git checkout -- docs/codebase-map.md`.
- Прочитаны точечно (сверх пакета, для проверки R1-F1): `orchestrator/gitcmd.py` (`git`, `commits_behind`, `in_repo`, `head_sha`), `orchestrator/fsm_merge_gate.py:203-424` (существующий узел `_origin_main_sha`/`_cmd_approve_merge_gate_cycle`, эталон безопасной деградации через `sys.exit`, а не литерал), `orchestrator/merge_lock.py:1-40` (подтверждение: мьютекс — один на весь пульт, охватывает только окно `merge_gate`), `orchestrator/targets.py` (`target()`/`TargetsError`, поля `url`/`base`), `orchestrator/store.py` (поле `target` записи задачи), `orchestrator/config.py` (`MERGE_GATE_CI_WAIT_CEILING_SEC`/`_POLL_SEC`, `DEFAULT_TARGET`).
- `git worktree --help` и `git help gitrepository-layout` (git 2.50.1) — подтверждён факт, на котором строится R1-F1: `FETCH_HEAD` — файл, приватный для каждого linked worktree, не общий.
- `git log --oneline --all -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/REVIEW.md` — пусто: подтверждено, что это первая итерация ревью (iteration: 1 корректен).

## Предложения системе

(пусто)
