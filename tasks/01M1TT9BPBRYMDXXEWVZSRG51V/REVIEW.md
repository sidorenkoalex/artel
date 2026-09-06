---
task: 01M1TT9BPBRYMDXXEWVZSRG51V
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: разрез orchestrator/doctor.py на пакет проверок

Примечание: `tasks/01M1TT9BPBRYMDXXEWVZSRG51V/SPEC.md` и `PLAN.md` не
вошли в ревью-пакет (артефакты не коммитятся в кодовую ветку — пакет
пытался читать их из кодовой ветки, где их и не может быть). Прочитаны
точечно из `artifact/01m1tt9bpbrymdxxewvzsrg51v` (`git show`), чтобы
провести Фазу A/B — без них нельзя было сверить требования и план по
существу.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 — пакет-фасад с полным экспортом (AC-1, AC-2, AC-10) | OK | `orchestrator/doctor/__init__.py` реэкспортирует все имена; `test_ac1_package_exists_with_init_and_exports_all_collected_names`, `test_ac10_facade_exports_the_fixed_name_list`, `test_ac2_*` — зелёные (прогнано). |
| 2 — перенос по разделам, тело не переписано (AC-3) | OK | 18 разделительных комментариев — по одному на файл (18 файлов-разделов); `test_ac3_sections_map_one_to_one_to_files_and_function_bodies_unchanged` сверяет AST-хеш 46 функций (со схлопыванием `doctor.<имя>` → `<имя>`) — зелёный. |
| 3 — ленивый доступ к коллаборантам через фасад (AC-4, AC-9) | OK | `grep` по `orchestrator/doctor/*.py` (кроме `__init__.py`) не находит ни одного прямого `import subprocess`/`shutil`/`from orchestrator import gitcmd`, ни прямого импорта любого другого коллаборанта (`store`/`config`/`alerts`/… — шире списка, который сканирует сам AC-9-тест); `test_ac9_submodules_have_no_direct_collaborator_import`, `test_ac4_cli_version_reads_subprocess_via_the_facade_attribute_live` — зелёные. |
| 4 — состав/порядок `all_checks` (AC-5, AC-11) | OK | `test_ac5_all_checks_names_and_statuses_are_unchanged`, `test_ac11_all_checks_name_order_is_unchanged` — зелёные на здоровом mock-репо. |
| 5 — регенерация карты / `docs/invariants.md` (AC-6, AC-7) | OK | `test_ac6_committed_map_matches_a_fresh_regeneration` (реальный прогон `scripts/codebase_map.py` и побайтовая сверка без `built_at_sha`) и `test_ac7_invariants_doc_has_no_stale_flat_doctor_path` — зелёные; `docs/invariants.md` действительно не называл `orchestrator/doctor.py` путём ни до, ни после. |
| 6 — `tests/` без правки ассертов/целей моков (AC-8) | OK | `git diff --stat` не содержит ни одного файла `tests/`; полный прогон затронутых модулей (список ниже) — зелёный, кроме заранее задокументированного в PLAN «Риски» отказа вне зоны. |
| 7 — планки закрытых задач не трогать, живые — эскалация, не правка (AC-12) | OK | Диф не касается `tasks/*/acceptance_tests/` закрытых задач; PLAN документирует sweep `grep -rho "doctor\.[a-zA-Z_]*"` по живым задачам-держателям на 06.09 — совпадений вне уже покрытого списка не найдено, эскалация не требовалась. |

Эскалации по ходу задачи (ANSWER-1/2/3) касались конфликта подтяжки
main и дефекта локального помощника планки (`_sandbox.py`, вне зоны
задачи — залоченный каталог планки); все три закрыты Оператором,
финальный шаг разработчика — подтверждающий прогон без правки кода
зоны задачи. Проверил результат по существу (не только факт наличия
ответов): текущий код и состав `all_checks`/фасада соответствуют тому,
что предписывают ANSWER-1 (перенос 3 функций main в `artifact_branches.py`
тем же приёмом) и ANSWER-2 (8 хешей + порядок `all_checks` после мержа) —
подтверждено собственным прогоном AST-хеш-теста и порядка `all_checks`,
не пересказом PLAN.

## Замечания

Нет.

## Реестр замечаний

Пусто — замечаний нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1TT9BPBRYMDXXEWVZSRG51V/acceptance_tests` — 11 из 11 зелёных (включая AC-1..AC-11).
- `python3 -m unittest tests.test_doctor tests.test_doctor_canary_pool tests.test_doctor_fix_ignored_artifacts tests.test_doctor_artifact_branch_ci tests.test_doctor_artifact_branch_sync tests.test_agent_failure tests.test_agent_log tests.test_agent_prompt tests.test_coldstart tests.test_git_fixation tests.test_invariants tests.test_liveness tests.test_merge_lock tests.test_multitarget tests.test_multitarget_invariants tests.test_pause_now tests.test_review_freshness tests.test_review_package tests.test_stall_alerts tests.test_step_cost tests.test_version tests.test_zone_lock tests.test_analyst_role tests.test_acceptance_tests_flow` (список PLAN, шаг 5, плюс `test_liveness`) — 723 теста, 1 провал: `tests.test_liveness.TerminateProcessGroupTest.test_kills_the_leader_and_returns_a_positive_count` — детерминированный отказ песочницы инструмента-агента (`os.killpg`), задокументирован в PLAN «Риски» первой итерации; подтвердил независимо: `orchestrator/liveness.py`/`tests/test_liveness.py` не входят в diff этой задачи (`git diff --stat` их не содержит), регресса нет.
- `grep -rn "^import \|^from "` по `orchestrator/doctor/*.py` — ни одного прямого импорта `subprocess`/`shutil`/`gitcmd`/иного коллаборанта в подмодулях, только `from orchestrator import doctor` (плюс безобидные стандартные модули без коллаборантской роли).
- `grep -n "doctor" docs/invariants.md` — нет пути `orchestrator/doctor.py`.
- `grep -n "COMMON_ZONES" -A2 orchestrator/config.py` — `orchestrator/doctor.py` в списке никогда не было, требование 5 «механика зон не трогается» выполнено тривиально.
- Сверка `SPEC.md`/`PLAN.md` этой задачи прочитана из `artifact/01m1tt9bpbrymdxxewvzsrg51v` (`git show`), т.к. в кодовой ветке их нет по конвенции.

## Предложения системе

- `docs/stack.md:50` называет путь `orchestrator/doctor.py::all_checks` — стух после разреза (функция теперь в `orchestrator/doctor/cli.py`, доступна как `doctor.all_checks`). Файл вне зоны этой SPEC (`orchestrator/doctor.py, orchestrator/doctor/, tests/, docs/invariants.md`), поэтому не требую правки в рамках задачи — но при следующем таком разрезе (`fsm_advance.py`/`fsm.py`/`guard.py`, названы SPEC как кандидаты) стоит явно сверять `docs/*.md` вне узкой зоны SPEC на упоминания переносимого файла, не только `docs/invariants.md`.
