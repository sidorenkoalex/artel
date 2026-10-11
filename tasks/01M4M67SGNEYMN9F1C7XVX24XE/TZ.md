---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Этап 4 ADR-0021, часть A: мерж артели не кладёт в main снимок задачи и RETRO

# ТЗ: Этап 4 ADR-0021, часть A — мерж артели не кладёт в main снимок задачи и RETRO

Источник: ADR-0021 (`docs/adr/0021-project-area-and-immutable-pult.md`
~223, этап 4: «отмена наложения снимка и коммита RETRO на main»);
ADR-0018 п.4 и условия уборки `tasks/` (~74); строка бэклога 27.09
«Отмена наложения снимка на main и уборка каталога tasks/»; сверка сессии
10.10–11.10 по origin/main 415f1de4; решение Оператора 11.10.2026 — две
задачи (A — наложение и чтения из main, B — исторические снимки), уборку
`tasks/` делает Оператор отдельным коммитом после A и B.

Факты (origin/main 415f1de4):
- Наложение снимка: `orchestrator/fsm_merge_gate.py::_overlay_artifact_snapshot`
  (~356, коммит «<id>: снимок артефактной ветки поверх merge» ~406),
  единственный вызов ~1076 в шаге публикации мержа; сразу за ним
  `_guard_task_root_or_refuse` (~1077, тело ~442) и для артели
  `_guard_all_or_refuse` (~463) — оба проверяют `tasks/<id>/` в дереве
  мержа.
- RETRO в main: только для артели (`repo_context.is_artel`, ~1080) —
  `fsm_postmerge._generate_and_commit_retro` (~197): done-RETRO
  «<id>: RETRO задачи» (`docs/retro/<id>.md`, `retro.RETRO_DIR_REL` ~50) и
  killed-RETRO долгов (~228–237), долг определяется отсутствием
  `retro.retro_path(<id>)` в дереве мержа. Для внешнего проекта RETRO в
  main уже не коммитится — остаётся только в коммите закрытия
  `refs/artifacts/<id>` (`orchestrator/snapshot.py`); у артели коммит
  закрытия с RETRO.md тоже есть.
- `retro.build_done` пишет адрес `{merge_sha}:tasks/<id>/` (~577) — адрес
  наложенного дерева.
- Прочие читатели, привязанные к main: `orchestrator/cleanup.py:21-22`
  (`artifacts_in_main`, `ls-tree main -- tasks/<id>`);
  `scripts/guard.py --all` (~4156–4195) и CI (`.github/workflows/ci.yml`
  ~43–44) — уже пропускают отсутствующий `tasks/`, закрытость задачи —
  по `docs/retro/<id>.md`; `orchestrator/doctor/orphans.py:142`;
  `orchestrator/budget.py:366,397` (пересчёт по `docs/retro/T*.md` —
  исторические RETRO остаются в main).
- Тесты, завязанные на наложение: `tests/test_plan_appendix.py:789-793`
  («нет коммита снимка»), `tests/test_main_ci_line.py:321` (подмена
  `_overlay_artifact_snapshot` по имени); вероятно
  `tests/test_fsm_retro.py`, `tests/test_retro_artifact_branch_reads.py`.

Требуется:
1. Мерж задачи артели больше не кладёт в main каталог `tasks/<id>/` и не
   коммитит в main RETRO задачи (`docs/retro/<id>.md`) и killed-RETRO
   долгов: в main уходят merge кодовой ветки, приложения PLAN и карта
   кодовой базы. RETRO задачи — только в коммите закрытия
   `refs/artifacts/<id>` (как у внешнего проекта сегодня); его содержание
   не беднеет: исход, счётчики, стоимость, перечень применённых
   приложений PLAN.
2. Ни один шаг мержа и постмержа не перегенерирует RETRO ликвидированных
   задач на каждом мерже из-за отсутствия `docs/retro/<id>.md`.
3. Защиты, которые сегодня опираются на наложенный `tasks/<id>/`
   (`_guard_task_root_or_refuse`, `_guard_all_or_refuse`), сохраняют
   смысл: посторонний файл документов задачи по-прежнему ловится — на
   дереве ссылки документов задачи или ином источнике, не на main; если
   проверка теряет предмет, это обосновано в SPEC, ослабления нет.
4. Читатели, привязанные к `tasks/<id>/` или `docs/retro/<id>.md` в main
   (`cleanup.artifacts_in_main`, адрес в `retro.build_done`), работают и для задач, чьих документов в main нет:
   источник — `refs/artifacts/<id>`. Исторические `docs/retro/*.md` и
   каталоги `tasks/*` в main остаются читаемыми до уборки Оператора.
5. Внешний проект: поведение мержа не меняется.
6. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38); правка защищённых путей — только
   приложением PLAN.

Критерии приёмки (направление; планку пишет test_author):
- Мерж задачи артели в песочнице: в истории main после merge нет коммита
  «снимок артефактной ветки поверх merge» и «RETRO задачи», в дереве
  main нет `tasks/<id>/` и `docs/retro/<id>.md`; в `refs/artifacts/<id>`
  есть RETRO.md с исходом done, стоимостью и перечнем приложений.
- Ликвидированная задача без `docs/retro/<id>.md`: следующий мерж не
  коммитит её killed-RETRO в main.
- Посторонний файл в документах мержащейся задачи по-прежнему даёт отказ
  перехода (или SPEC обосновывает, почему предмет проверки исчез).
- Внешний проект: мерж как сегодня.
- Мутация «наложение снимка оставлено» ловится.

Зоны: orchestrator/fsm_merge_gate.py, orchestrator/fsm_postmerge.py,
orchestrator/retro.py, orchestrator/cleanup.py, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/snapshot.py, orchestrator/budget.py,
orchestrator/doctor/, orchestrator/artifact_branch.py, orchestrator/store.py,
orchestrator/config.py, orchestrator/catalog.py, orchestrator/fsm.py,
orchestrator/acceptance.py, orchestrator/suite_run.py, orchestrator/suite_lock.py,
scripts/, .github/workflows/ci.yml, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, docs/design-system.md, templates/, skills/,
CLAUDE.md, models.yaml, roles.yaml, targets.yaml, tasks/, docs/retro/,
.artel/.

Не входит: исторические снимки для каталогов без `refs/artifacts`
(задача B); удаление `tasks/*` и правка ссылок в скилах, шаблонах,
`docs/invariants.md`, `docs/design-system.md`, пересмотр ADR-0020 п.2 —
коммит Оператора после A и B; удаление исторических `docs/retro/*.md`;
мелкие строки RETRO (sha в «Итог: done», заметка killed).

Рамка: $45.

Набор моделей: по умолчанию.
