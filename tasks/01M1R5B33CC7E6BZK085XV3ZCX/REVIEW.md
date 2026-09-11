---
task: 01M1R5B33CC7E6BZK085XV3ZCX
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: B2 ТЗ-1: репозиторный контекст target для git/gh-слоя

## Фаза A — гейт плана

PLAN.md вводит единый модуль `orchestrator/repo_context.py` (`RepoContext`,
`resolve`, `path_or_none`, `git`) и минимальным добавлением опционального
`repo=`/`cwd=` переводит на него все 13 точек реестра SPEC. Подход не
конфликтует с существующей архитектурой (тот же приём деградации, что уже
несёт `fsm._origin_main_source`; тот же паттерн `repo=None` self-default,
что уже применяют `gitcmd.head_sha`/`is_clean`). Шаги — 12 штук, каждый
проверяемая единица (один модуль/файл на шаг), таблица покрытия требований
полна (все 6 требований адресованы). Решение «монолит, не нарезка»
обосновано порогом самого ТЗ (реестр 13 строк < порога 15) — принято.

Расширение зон (ANSWER-2: `orchestrator/repo_context.py`,
`orchestrator/pull.py`, `orchestrator/doctor/`, `orchestrator/stack.py`) —
законный мост Оператора под реальный дрейф адресов (R3/R5, смержены после
даты SPEC), сверено с diff — ни одного файла сверх зон SPEC ∪ ANSWER-2
∪ автогенерируемого `docs/codebase-map.md`. Фаза A пройдена без замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (единый узел контекста) | OK | `orchestrator/repo_context.py` — `resolve`/`path_or_none`/`git`, self без чтения targets.yaml, внешний target — путь/remote/base из targets.yaml. Покрыт `tests/test_repo_context.py` + приёмочный AC-1. |
| 2 (`ci.gh` с контекстом) | OK | `ci.gh(repo=)` дописывает `--repo <url>` в конец argv; `gh(repo=None)` — байт-в-байт прежний вызов. AC-2 зелёный. |
| 3 (сверка/подтяжка по контексту) | OK | `fsm._pull_main_or_escalate` резолвит ctx и передаёт `repo_path` в `pull.evaluate`; `doctor/branch_freshness.py` фетчит `origin/<base>` контекста для target ≠ self. AC-4/AC-5 зелёные. |
| 4 (merge/карта/RETRO по контексту) | реализовано не полностью | Основной поток (scratch-worktree, merge, push `refs/heads/<base>`, условный пропуск карты/RETRO) корректен и покрыт AC-12/AC-13 зелёными тестами — но см. R1-F1: очистка scratch-worktree (`_drop_scratch_worktree`) для внешнего target выполняется в НЕПРАВИЛЬНОМ репозитории и не деregистрирует worktree там, где он реально заведён. |
| 5 (гейт ёмкости + diff ревью-пакета) | OK | `_capacity_gate` больше не пропускается безусловно для target ≠ self, считает diff в клоне контекста тем же `git_diff_part`, что и review-пакет. AC-9/AC-10/AC-16 зелёные. |
| 6 (сквозной тест на двух репозиториях) | OK | `tasks/.../acceptance_tests/` — 39/39 методов зелёные (прогнал сам, см. «Проверено исполнением»), включая все три класса `test_ac15_ac16_ac17_end_to_end.py`. Правка планки AC-4/AC-15 — легитимным каналом `amend-tests` (см. ниже). |

## Замечания

- major — `orchestrator/fsm_merge_gate.py:79-81` (`_drop_scratch_worktree`),
  вызовы на строках 115, 130, 313, 487 — очистка scratch-worktree после
  плотницкого merge всегда идёт через голый `gitcmd.git("worktree",
  "remove", "--force", str(repo))`, то есть безусловно в `config.ROOT`
  (см. `gitcmd.git`: `cwd=config.ROOT` без `-C`). Для target ≠ self
  scratch создаётся ЧЕРЕЗ `repo_context.git(ctx, "worktree", "add", ...)`
  — то есть регистрируется в `ctx.path/.git/worktrees/`, а не в
  `config.ROOT`. Эмпирически проверил на настоящем git (два bare-репо,
  `worktree add` в repo_b, `worktree remove` из repo_a): `git worktree
  remove` из чужого репозитория падает `fatal: '<path>' is not a working
  tree` (код 128), возврат `_drop_scratch_worktree` не проверяется вовсе
  — ошибка молча проглатывается, `shutil.rmtree` стирает directory с
  диска, но административная запись `ctx.path/.git/worktrees/<name>/`
  остаётся висеть (`git worktree list` в клоне target'а продолжит
  показывать её как «prunable»). Эффект — на КАЖДОМ approve/merge
  внешнего target (успешном или с разбором конфликта, оба пути зовут ту
  же функцию) клон target'а копит мусорные worktree-записи без предела;
  ни `tasks/.../acceptance_tests/test_ac12_ac13_merge_gate_and_postmerge.py`,
  ни юнит-тесты не проверяют состояние `.git/worktrees/` после merge,
  поэтому дефект не поймался прогоном (39/39 приёмочных, 733 юнит-теста
  зелёные — не противоречит этой находке, они не смотрят в этот угол).
  Для self дефекта нет (`ctx.path == config.ROOT`, add и remove
  симметрично идут в один и тот же репозиторий) — регрессия целиком
  новая, введена этой задачей вместе с AC-12.
  Предложение: `_drop_scratch_worktree` обязан знать репозиторий, в
  котором worktree РЕАЛЬНО зарегистрирован (проще всего — принять `ctx`
  и звать `repo_context.git(ctx, "worktree", "remove", "--force",
  str(repo))` вместо голого `gitcmd.git(...)`), и это `ctx` протащить
  через все 4 вызывающих места (`_handle_merge_conflict`,
  `_guard_task_root_or_refuse`, `_publish_merge_artifacts`,
  `_perform_carpentry_merge` уже несёт `ctx` — пробросить дальше).

- minor — `tests/test_repo_context.py` (все 9 тестовых методов классов
  `ResolveSelfTest`, `ResolveExternalTargetTest`, `PathOrNoneTest`,
  `GitHelperTest`) — ни один метод не несёт докстринга с заявкой `Ловит
  мутацию: …` и сценарным описанием (только имя метода, без пояснения),
  вопреки конвенции `skills/test-authoring.md`/review-checklist п.3,
  которую этот же diff сам демонстрирует для другого файла
  (`tests/test_branch_freshness_gate.py::
  test_pull_freshness_fetches_inside_the_target_clone_not_the_pult` несёт
  полноценную заявку). Сами тесты не тавтологичны (реально ловят
  правдоподобные мутации — например, `test_self_target_does_not_touch_
  targets_yaml` упадёт, если `resolve()` попытается читать targets.yaml
  ДО проверки `target_name == DEFAULT_TARGET`), но без явной заявки
  ревьювер каждой следующей итерации вынужден домысливать чувствительность
  теста заново. Предложение: добавить в докстринг каждого метода строку
  `Ловит мутацию: …` (например, для `test_external_target_reads_targets_
  yaml` — «поля ctx перепутаны местами / read из config.ROOT вместо
  targets.yaml»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/fsm_merge_gate.py:79-90 (+ вызовы 125,140,324,493,610) | `_drop_scratch_worktree` принимает `ctx: repo_context.RepoContext` и зовёт `repo_context.git(ctx, "worktree", "remove", "--force", str(repo))` вместо голой `gitcmd.git` — дерегистрация идёт в репозитории-владельце worktree; `ctx` протащен через `_handle_merge_conflict`, `_guard_task_root_or_refuse`, `_publish_merge_artifacts` (параметр `is_self: bool` заменён на `ctx`, `is_self` вычисляется внутри как `ctx.path == config.ROOT`) до всех 5 вызовов. Регресс закрыт новым тестом на двух настоящих git-репозиториях: `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py` (3 метода — external-дерегистрация, self не тронут внешним ctx, self-путь остаётся byte-identical); мутационно проверено — временный откат фикса на голую `gitcmd.git` красит ровно этот тест. Единственный существующий вызывающий тест (`tests/test_guard_task_root_subdirectory.py::MergeGateGuardRefusesSubdirectoryFileTest`) обновлён на новую сигнатуру (передаёт self-контекст `repo_context.resolve(config.DEFAULT_TARGET)`). | клон внешнего target копит мусорные записи `.git/worktrees/` на каждом merge_gate approve, без предела | принять `ctx`/`repo_context` в `_drop_scratch_worktree` и всех 4 вызывающих местах, деregистрировать worktree там, где он заведён |
| R1-F2 | fixed | tests/test_repo_context.py (все 9 методов) | каждому методу добавлен докстринг «Ловит мутацию: …» с конкретным сценарием (перепутанные поля `RepoContext`, чтение targets.yaml не в том порядке, исключение вместо `None`, `path_or_none`/`repo_context.git` перепутавшие self/external ветку) — по образцу `tests/test_branch_freshness_gate.py`, названному ревьювером. | следующая итерация ревью не может свериться с заявленной чувствительностью теста, конвенция test-authoring нарушена | добавить докстринг с конкретной мутацией в каждый тестовый метод файла |

## Вердикт

changes_requested — один major (R1-F1, класс «многорепозиторная git-админ
операция без ctx», конкретный и воспроизведённый эмпирически) и один minor
(R1-F2, конвенция докстрингов тестов). Остальная реализация (12 из 13 точек
реестра, все 6 требований, 17 AC приёмочной планки) корректна и подтверждена
исполнением — доводка не масштабная, ожидаю точечного фикса
`_drop_scratch_worktree` + докстрингов, без пересмотра подхода.

## Проверено исполнением

- `python3 -m pytest tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests -o timeout=90 -q` — 39 passed (все 17 AC).
- `python3 -m unittest tests.test_repo_context tests.test_gitcmd_branch_reads tests.test_ci_status tests.test_ci_status_kind_gate tests.test_github_adapter tests.test_capacity_gate tests.test_review_package tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve tests.test_acceptance tests.test_acceptance_tests_flow tests.test_doctor tests.test_merge_gate_ci_wait tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_map_regen tests.test_fsm_retro tests.test_fsm_advance_gate_smoke tests.test_fsm_advance_gate_framework tests.test_zones_gate tests.test_zones_approve tests.test_advance_guard tests.test_pull tests.test_multitarget tests.test_multitarget_invariants tests.test_git_fixation tests.test_auto_cycle tests.test_invariants` — Ran 733 tests, OK.
- `python3 -m unittest tests.test_invariants.NoNetworkAddressesInTestsTest -v` — 2/2 OK (в т.ч. мутационный `test_synthetic_dns_hostname_fixture_is_caught` — DNS-фикс коммита 6a7edcd2 не ослабил сканер).
- `python3 scripts/codebase_map.py` на голове ветки и `git diff docs/codebase-map.md` без строки `built_at_sha` — пусто: карта содержательно свежая, актуализирована этой же задачей.
- Ручной репро на настоящем git (два временных bare-подобных репозитория, `subprocess`, не в `config.ROOT`/не в дереве разработчика): `git worktree add --detach` в repo_b, затем `git worktree remove --force <path>` из repo_a — код возврата 128, `fatal: '<path>' is not a working tree`, запись в `repo_b`'s `git worktree list` не исчезает — подтверждает R1-F1 эмпирически, не гипотезой.
- Зоны: `git diff --stat` от общего предка до HEAD ветки сверен построчно с zones SPEC ∪ расширением ANSWER-2 — расхождений нет (кроме автогенерируемого `docs/codebase-map.md`).
- Правка планки (лок `a460ff4c -> 68171e0e`): `git log`/`git show 68171e0e` — коммит от `Artel Orchestrator` (не от роли разработчика), правка — добавление фикстуры `commit_minimal_plank` и промежуточного `store.set_state(..., "verifying", ...)`; ни один существующий assert не удалён и не ослаблен, только добавлен шаг порядка состояний (ADR-0015). Провенанс соответствует требованию review-checklist (штатный канал `amend-tests`, ANSWER-1.md).

## Предложения системе

- Класс дефекта «функция, оперирующая worktree admin-командами
  (`git worktree add/remove/prune`), должна знать репозиторий-владелец
  worktree, а не физический путь к нему» — легко упустить при
  расширении self-only git-кода на многорепозиторный контекст (эта же
  задача корректно развела `git diff`/`git merge`/`git status` внутри
  scratch через `gitcmd.in_repo`, но не саму регистрацию/дерегистрацию
  worktree). Стоит явно назвать этот класс в `orchestrator/repo_context.py`
  докстринге как предостережение для следующих задач, трогающих
  `git worktree`.
