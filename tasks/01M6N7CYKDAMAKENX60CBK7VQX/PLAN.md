---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Ручной мерж для GitHub, часть 2 — открытие пары `github` + `target-human`

## Подход
Пара открывается одной строкой `SUPPORTED_PAIRS`; всё опасное в проекте людей
закрывается признаками, а не литералом хостинга (сторож литералов AC-12):

- повтор CI — `targets.merged_by_project_people` записи клона
  (`ci.people_rerun_refusal`): `trigger_rerun` отказывает до любого `gh`
  (после прежнего отказа GitLab — его текст не меняется), `ci-rerun` —
  после проверок `--reason` и до `ci.verifying_status`, в любом состоянии;
- `policy.ci_required_jobs` — атрибут реализации `READS_CI_REQUIRED_JOBS`
  реестра `forge.IMPLEMENTATIONS` (через `targets._hosting_registry`), проверка
  в `targets.check` (после `_check_delivery` локального слоя — текст отказа
  формы прежний);
- закрытие PR при `kill` — `forge.ci_by_pipeline` (хостинг без конвейеров
  заводит PR) вместо `_forge_of(target) == "github"`; у проекта людей вместо
  `gh pr close` — фраза «PR не тронут: MR вливают люди проекта» рядом с
  исходом удаления ветки (до отправки) и дописью к прежнему тексту (после);
- `doctor`: для `target-human` хостинга без конвейеров строка
  `project-ci-file-no-paths` всегда, проверка каталога `.github/workflows/`
  пробным именем файла (длиннее всех записей, первый символ не совпадает с
  символом после каталога ни в одной записи) по `config.is_protected_path`;
  GitLab — прежняя `check_ci_file_no_paths`.

Бюджет SPEC ($85) не пересматривается.

## Шаги
1. `orchestrator/targets.py`: `SUPPORTED_PAIRS` + комментарий;
   `_check_ci_required_jobs`; `orchestrator/gitlab_adapter.py`:
   `READS_CI_REQUIRED_JOBS = True`.
2. `orchestrator/ci.py`: `_people_project`, `people_rerun_refusal`, отказ в
   `trigger_rerun`; `orchestrator/ci_rerun.py`: отказ до чтения статуса.
3. `orchestrator/cleanup.py`: признак PR-хостинга, `PR_LEFT_TO_PROJECT_PEOPLE`.
4. `orchestrator/doctor/project_checks.py`: `check_workflows_dir_no_paths`,
   условие построения строки.
5. Три файла мандата `ANSWER-1.md`: перенос `github` + `target-human` в
   поддержанные, новый текст причины, равенства сохранены.
6. `python3 scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (без новых исключений; AC-3 зелёный) |
| 3 | 4 |
| 4 | 4 (закрепление тестами test_author, код не менялся) |
| 5 | 1–3 (полный цикл — tests/…_people_flow.py) |
| 6 | 6 |
| 7 | 2 |
| 8 | 1 |
| 9 | 3 |
| 10 | 5 |

## Влияние на систему
- Белый список отправок (`gitcmd.py`) не тронут (ANSWER-2): до отправки
  удаление ветки origin у проекта людей по-прежнему отказывается им, запись
  уборки несёт этот исход и «PR не тронут».
- Гейт мержа (`fsm_merge_gate.py`) не правлен: красный CI проекта людей идёт
  прежним путём неудачного повтора — `trigger_rerun` возвращает «ре-ран CI не
  запущен: …», задача остаётся на `merge_gate`.
- Для артели и записей `operator` (в т.ч. `github` + `operator`) поведение
  `trigger_rerun`, `ci-rerun`, `kill` прежнее; GitLab `target-human` — тексты
  отказа повтора и уборки прежние (отказ GitLab в `trigger_rerun` стоит
  первым; «PR не тронут» только у хостинга без конвейеров).
- Исключение сторожа `("cleanup.py", "_forge_of")` становится лишним
  (функция удалена) — сторож от этого не ослабляется.
- Существующие тесты вне мандата не правлены; в трёх файлах мандата случаи
  `gitlab` + `operator` и равенства сохранены (AC-13).
- Откат — revert одного merge-коммита.

## Риски
- `ci-rerun` проекта людей GitLab теперь отказывает раньше и другим текстом
  («ре-ран CI не запущен: проект … — MR вливают люди проекта …») —
  требование 7 касается любой записи `merged_by_project_people`; прежних
  тестов на этот путь у GitLab нет.

## Предложения системе
- Планка AC-13 (`acceptance_tests/test_mandate_files.py`) сверяет `HEAD`, а не
  рабочее дерево: разработчику, оставляющему код незакоммиченным по норме
  скила, `plank-run` красит AC-13 до коммита — стоит назвать это в миссии
  или выкладывать планку на дерево (skills/coding-standards.md, «Завершение хода»).
