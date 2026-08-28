---
task: T051
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: Сверка свежести ветки до гейта

Блокер итерации 1 снят Оператором через ADR-0006 (инвариант 12 сужен по
направлению, не по подкоманде). Ревью ниже — по фактическому diff
`23139e2..HEAD` (коммиты после эскалации итерации 1: `8587ea5`, `23139e2`
были уже приняты; проверялись `6f615d6`, `56a6ecc`, `19c737c`, `f7c22f3`)
и по `git diff main...HEAD` для сверки зоны (требование 11). Пакет ревью
дал пустой инкрементальный diff (sha предыдущего вердикта в пакете
совпал с текущим HEAD) — читал реальные изменения напрямую по git log,
причина отмечена явно.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сверка в двух точках перехода) | OK | `fsm._pull_main_or_escalate` (fsm.py:169-232) вызывается из `_cmd_advance` (in_dev, fsm.py:667) и `_cmd_approve` (acceptance, fsm.py:780) — единственная точка сверки, как заявлено в PLAN. |
| 2 (определение отставания) | OK | `gitcmd.commits_behind` — без изменений с итерации 1, юнит-тесты зелёные (прогнал `tests/test_gitcmd_branch_reads.py` — 79/79 ok). |
| 3 (подтяжка + прогон приёмки) | OK | `git -C <worktree> merge --no-ff main -m "..."` + `acceptance.run(wt_path/"tasks"/task_id)` — воспроизвёл приёмочным `test_ac1_...` (реальный git): `is_ancestor(c1, new_head)` и `is_ancestor(c2, new_head)` оба true — не rebase, main подтянут. |
| 4 (переход только после успеха обоих шагов) | OK | Оба места вызова: `if _pull_main_or_escalate(...): return False/return` — переход (`store.set_state`) не достижим, если функция вернула `True`. Подтвердил юнит-тестами `tests/test_branch_freshness_gate.py` (conflict/red-acceptance ветки останавливают переход). |
| 5 (конфликт → escalated, `merge --abort`, main цел) | OK | `test_ac2_conflicting_pull_escalates_aborts_merge_and_leaves_branches_untouched` (реальный конфликтующий merge) — зелёный: `branch_head() == c1` (откат), `main_head() == c2` (main цел), `status --porcelain` без `UU`, в файле нет `<<<<<<<`. |
| 6 (красные приёмочные после подтяжки → escalated, merge остаётся) | OK | `test_ac3_red_tests_after_successful_pull_escalate_but_keep_the_merge` — зелёный: HEAD ветки задачи ушёл вперёд (не откачен), `is_ancestor(c1, new_head)` и `is_ancestor(c2, new_head)` оба true, `main_head() == c2`. |
| 7 (не отстала — поведение переходов байт-в-байт прежнее) | OK | `test_ac4_branch_even_with_main_advances_without_extra_merge_commit` — `parent_count(wt) == 1` (нет merge-коммита), `branch_head() == c1`, `main_head()` не изменился. Код: `if not behind: return False` — до git merge не доходит вовсе. |
| 8 (doctor: warn по отставшей активной задаче) | OK | Без изменений с итерации 1 (`orchestrator/doctor.py`/`config.py` — `git diff 23139e2..HEAD` пуст для обоих файлов); ранее принятый minor (мок AC-5 глушил git заодно с claude) исправлен приёмом `_claude_only_run`/`_claude_only_popen` — см. «Замечания». |
| 9 (молчаливый пропуск в песочницах без git) | OK | `test_ac6_indev_to_review_advances_normally_without_a_real_git_branch` (fake_git, реальных веток нет) — переход проходит как обычно; `commits_behind` возвращает `None` → `_pull_main_or_escalate` возвращает `False` до какого-либо git-вызова. |
| 10 (подтяжка не трогает main) | OK | Проверено в AC-1/2/3 (`main_head()` неизменен во всех трёх сценариях — успех, конфликт, красная приёмка). Merge всегда `-C <worktree>`, никогда не в `config.ROOT`. |
| 11 (правки только в orchestrator/, тестах, карте) | OK | `git diff --stat main...HEAD`: `orchestrator/{config,doctor,fsm,gitcmd}.py`, `tests/{test_branch_freshness_gate,test_doctor,test_gitcmd_branch_reads}.py`, `docs/codebase-map.md`, собственные `tasks/T051/*`. `docs/adr/0006-*.md`/`docs/invariants.md`/правка `tests/test_invariants.py` (сузившая инвариант 12) не входят в diff к main — это отдельный коммит Оператора (`0d98cc5`), уже слитый В main и подтянутый в ветку задачи её же собственным механизмом (`6f615d6`, "актуализация ветки от main"); правка неослабляемого теста по ADR — легитимно только руками Оператора (ADR-0002), что и произошло. |

Карта (`docs/codebase-map.md`): регенерировал `python3 scripts/codebase_map.py` — разошёлся только `built_at_sha` (текущий HEAD против записанного), содержимое идентично; это штатный случай, отдельно разбираемый `tests/test_fsm_map_regen.py::test_only_built_at_sha_differs_is_equal` — не дефект.

Полный прогон: `python3 -m unittest discover -s tests` — 762/762 зелёных (включая `test_invariants.py::MergeOnlyFromMergeGateTest` целиком, сузившийся по ADR-0006 свип не нашёл посторонних merge). `tasks/T051/acceptance_tests/` — 8/8 зелёных (все AC, включая ранее красные AC-2/AC-3 итерации 1).

## Замечания

Без blocker/major.

- minor — `tasks/T051/acceptance_tests/test_ac5_doctor_warns_lagging_branch.py:16-38` (`_claude_only_run`/`_claude_only_popen`) — дефект мока итерации 1 исправлен по образцу `tests/test_doctor.py::claude_only_run`/`claude_only_popen`, но реализован локальной копией внутри приёмочного теста, а не общим хелпером в `tests/sandbox.py` — тот же класс дублирования, что уже отмечен дважды (итерация 1 REVIEW.md, PLAN «Предложения системе» этой итерации). Не блокирует: приём корректен, тест зелёный, воспроизвёл — `mock.patch.object(doctor.subprocess, "run", side_effect=_claude_only_run)`/`Popen` пропускают всё, кроме `args[0] == "claude"`, в настоящий `subprocess`, так что `commits_behind` внутри `all_checks()` бьёт по реальному git песочницы. Правка вне зоны роли reviewer (артефакт test_author/developer в приёмочных тестах) — переношу как наблюдение, не как требование к этой итерации.

## Вердикт

approved — требования 1-11 и критерии AC-1–AC-6 реализованы и проверены: воспроизвёл ключевые сценарии напрямую (реальный конфликтующий merge для AC-2, реальная красная приёмка после подтяжки для AC-3, отсутствие лишнего merge-коммита для AC-4, песочница без git для AC-6), прогнал полный юнит-сьют (762/762) и все приёмочные T051 (8/8). ADR-0006 сузил инвариант 12 корректно — по направлению («в main мержит только `approve` из `merge_gate`»), а не по подкоманде, ядро инварианта не ослаблено (подтверждено прогоном `test_invariants.py` целиком), единственный разрешённый merge вне гейта строго ограничен: `-C <worktree задачи>`, вливает `main`, не упоминает ветку задачи. Diff в зоне `orchestrator/`, тестов и `tasks/T051/*`; правка защищённого `test_invariants.py`/`docs/invariants.md` — легитимный коммит Оператора по ADR, унаследованный веткой через собственный механизм T051, не самодеятельность роли. Один minor — дублирование тестового хелпера вместо переиспользования — не блокирует.

## Предложения системе

- Класс «мок `subprocess.run`/`Popen`, общий на несколько модулей оркестратора, глушит больше, чем задумано» пойман уже трижды в этом репозитории на одном и том же паттерне (`tests/test_doctor.py:122-137` — источник приёма; T051 итерация 1 — воспроизведённый баг; T051 итерация 2 — приём скопирован локально в `tasks/T051/acceptance_tests/test_ac5_...py` вместо переиспользования). Стоит вынести `claude_only_run`/`claude_only_popen` в `tests/sandbox.py`, иначе следующая задача с `doctor`-приёмочным тестом наступит на тот же класс бага в четвёртый раз.
