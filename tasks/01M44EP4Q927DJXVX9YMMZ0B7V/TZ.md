---
task: 01M44EP4Q927DJXVX9YMMZ0B7V
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Помощник планки от пульта

# ТЗ: планка не трогает окружение пульта напрямую — помощник от пульта рядом с acceptance_tests/

Источник: бэклог, строка «Планка не трогает окружение пульта напрямую:
помощник от пульта + guard» (приоритет 1, $30; ревизия 26.09: пункт (2)
сделан задачей 01M2XJKKPH, остаток — пункт (1) помощник и пункт (3) строка
скила); прецеденты 12.09 AC-8 01M2B6K3EM (PLAN.md с диска), 13.09 AC-4
01M2CN465W (merge-base с локальной main, равной пину). Решение Оператора
05.10 «заводи вторую волну».

Факты (пин 1d2229b7, сверка кода 05.10):
- Планка выкладывается в рабочую копию кода только пультом и только на
  время прогона: `orchestrator/acceptance.py::materialize_from_branch`
  (~310-363, читает `acceptance_tests/` из ссылки документов через
  `artifact_branch.ls_tree`/`artifact_branch.show`), `::materialize_files`
  (~387-395, черновик `plank-run` в `tests_writing`), общий узел записи
  `::_write_plank` (~366-384: файл на диске, которого нет в наборе,
  удаляется), обёртка с уборкой `::plank_in_code_copy` (~409-427) и
  `::drop_from_code_copy` (~398-406). Потребители: `orchestrator/pull.py::
  _materialize_and_run_plank` (~510), `orchestrator/advance_gates/
  tests_writing.py::_tests_writing_acceptance_dir` (~140-158),
  `orchestrator/advance_gates/acceptance.py` (~259, ~265),
  `orchestrator/fsm_advance.py` (~207), `orchestrator/amend.py` (~978),
  `orchestrator/plank_run.py` (~135). Модуля-помощника пульт при выкладке
  не кладёт: в планке оказываются только файлы ссылки документов (или
  черновика).
- С этапа 2 ADR-0021 ссылка документов — `refs/artifacts/<id>` в клоне
  проекта (`orchestrator/artifact_branch.py::branch_name` ~56,
  `::task_repo` ~86, `::repo_for_target` ~70); рабочая копия задачи —
  git worktree этого клона `.artel/projects/<проект>/worktrees/<id>`
  (`orchestrator/workspace.py::path` ~123-127), поэтому ссылка видна из
  рабочей копии. При этом `artifact_branch.show`/`ls_tree`, вызванные из
  планки, ищут клон через `config.PROJECTS`/`config.DB`, а `config.ROOT`
  планки — корень рабочей копии (`orchestrator/config.py` ~9-11, ~48):
  там нет ни `.artel/state.db`, ни клона, и узел отвечает «репозиторий
  проекта задачи не найден» (`artifact_branch.NO_REPO_REASON` ~117).
  Рабочий путь у планки сейчас один — `gitcmd.show(...)` без `repo`
  (`orchestrator/gitcmd.py::git` ~32-47 зовёт git в `config.ROOT`), он
  держится на том, что `config.ROOT` планки оказался worktree клона.
- База диффа задачи у пульта — одна точка: `orchestrator/gitcmd.py::
  diff_base` (~383-411, merge-base с `refs/remotes/origin/<main>`, иначе
  с локальной основной веткой) и `::diff_base_source` (~414-427). Гейт
  зон берёт её и `gitcmd.diff_names(base, branch)` (`orchestrator/
  advance_gates/zones.py::_zones_gate` ~199-210).
- Проверка применимости приложения PLAN у пульта — `orchestrator/
  advance_gates/plan_appendix.py::git_apply` (~73-104: дифф файлом,
  `git apply` с флагами); обратная проверка «уже наложено» —
  `orchestrator/fsm_merge_gate.py::_appendix_already_in_main` (~805-827,
  `--reverse --check`).
- Роли пишут этот набор сами, в каждой задаче заново: модуль `_plank.py`
  планок 01M443HPZBMJGCHVGV4JQN88RS и 01M443HV9SJYVYQTHJSQ87QV68
  (ссылки документов в клоне) держит `CODE_ROOT = Path(__file__).
  resolve().parents[3]`, правку `sys.path`, `plan_or_fail` через
  `gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`, `base_or_fail`
  через `gitcmd.diff_base`, собственный `changed_paths` (`git diff
  --name-only base --` по рабочему дереву, не по коммитам) и собственное
  «чистое дерево» (`git archive HEAD` + `git init`) для наложения
  приложений.
- Пункт (2) строки бэклога сделан наполовину: `scripts/guard.py::
  scan_artifact_disk_reads` (~1674) и `::artifact_disk_read_errors_
  from_files` (~1620) ловят чтение артефакта с диска, гейт —
  `orchestrator/advance_gates/tests_writing.py::_tests_writing_artifact_
  source_gate` (~186-209). Проверки «git со ссылкой main без origin/» в
  `scripts/guard.py` нет. Рецепт отказа
  `ARTIFACT_DISK_READ_RECIPE_TMPL` (~1486) называет
  `gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`.
- Имена первого уровня `acceptance_tests/`: `scripts/guard.py::
  ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` (~1128) допускает `_<имя>.py`;
  зарезервированного пультом имени нет.
- Скил `skills/test-authoring.md` разделы «Источник артефактов задачи —
  только артефактная ветка» (~128-152) и «База диффа задачи — точка
  расхождения с `origin`» (~271-282) дают рецепты через `gitcmd.show`/
  `gitcmd.diff_base`; о помощнике пульта не говорит.
- `scripts/guard.py` в `config.PROTECTED_PATHS` (`orchestrator/
  config.py` ~694-700) не входит; `skills/`, `templates/`,
  `tests/test_invariants.py`, `**/conftest.py` — входят.

Требуется:
1. Модуль-помощник планки: исходный текст живёт в `orchestrator/` (имя
   модуля и имя файла выкладки — решение SPEC, без слова «artel» в
   имени; имя файла выкладки подходит под `_<имя>.py`). Помощник
   самодостаточен: импортирует только стандартную библиотеку и не
   зависит от `orchestrator/` рабочей копии (её код — предмет задачи и
   может быть сломан). Открытый набор:
   - `TASK_ID`, `CODE_ROOT` (корень рабочей копии кода, в которую
     выложена планка);
   - `artifact_text(name)` — текст `tasks/<id>/<name>` из ссылки
     документов задачи той ревизии, с которой выложена планка; файла нет
     — `None` либо именованное исключение (решение SPEC), сбой git —
     отличимый от «файла нет» исход;
   - `branch_diff()` и `changed_paths()` — дифф и список путей задачи от
     базы, посчитанной пультом при выкладке тем же
     `gitcmd.diff_base`/`gitcmd.diff_base_source`, что у гейта зон;
     база и её источник (`origin/<main>` или локальная ветка) доступны
     планке константами. SPEC решает, включает ли `changed_paths()`
     незакоммиченное рабочее дерево и неотслеживаемые файлы (гейт зон
     их включает), и фиксирует это в докстринге помощника;
   - `apply_check(diff, reverse=False)` — применимость unified-диффа к
     дереву HEAD рабочей копии без изменения рабочей копии и индекса
     (пустая строка — git согласился, иначе ответ git); `reverse=True` —
     обратное наложение «правка уже в дереве», тем же способом подачи
     диффа, что `plan_appendix.git_apply`.
2. Выкладка: `acceptance.materialize_from_branch` и
   `acceptance.materialize_files` кладут помощник рядом с
   `acceptance_tests/` (в сам каталог планки) с подставленными значениями
   (id задачи, путь репозитория ссылки, ревизия выкладки, база диффа);
   `_write_plank` его не удаляет как лишний; `drop_from_code_copy` убирает
   его вместе с планкой. Все потребители из фактов получают помощник без
   правки каждого. Помощник не попадает ни в ссылку документов (лок
   `tests_locked_sha`, автокоммит `orchestrator/checkpoint.py`), ни в
   кодовую ветку, ни в каталог документов задачи.
3. Имя файла помощника зарезервировано: файл с этим именем в планке
   ссылки документов (или в черновике `tests_writing`) отклоняет выход из
   `tests_writing` именованным действием с подсказкой «имя занято
   помощником пульта»; при выкладке файл пульта имеет приоритет.
4. Отказ гейта «планка читает артефакты с диска» и его рецепт
   (`ARTIFACT_DISK_READ_RECIPE_TMPL`, подсказка
   `_tests_writing_artifact_source_gate`) называют `artifact_text(name)`
   помощника вместо `gitcmd.show(...)`. Правило проверки не ослабляется.
5. Приложением к PLAN — раздел `skills/test-authoring.md`: помощник
   пульта (имя файла, четыре функции, константы) — единственный
   рекомендуемый способ читать артефакты, считать дифф задачи и
   проверять приложения; разделы ~128-152 и ~271-282 ссылаются на него.
6. Документ `docs/codebase-map.md` — строка о модуле-помощнике и о
   выкладке.
7. Тесты в `tests/` с заявками «Ловит мутацию» на пп. 1–4, в том числе:
   выкладка из ссылки и из черновика кладёт помощник, уборка его
   убирает; `artifact_text` читает ревизию выкладки, а не более позднюю
   голову ссылки; `changed_paths` совпадает со списком гейта зон на той
   же ветке при `origin/<main>`, ушедшей вперёд локальной ветки (сценарий
   13.09); `apply_check` прямой и обратный не меняют рабочую копию;
   помощник работает при `config.ROOT` рабочей копии без `.artel/`;
   файл с зарезервированным именем в планке — отказ выхода из
   `tests_writing`; помощник не попадает в коммит ссылки документов.
   Существующие тесты не ослабляются.

Зоны: orchestrator/ (новый модуль-помощник, orchestrator/acceptance.py,
orchestrator/advance_gates/tests_writing.py), scripts/guard.py, tests/,
docs/codebase-map.md.

Приложением: skills/test-authoring.md (п. 5).

Только чтение (не менять): .artel/, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, .github/workflows/ci.yml, conftest.py,
tests/test_invariants.py, docs/invariants.md.

Не входит: вторая половина пункта (2) бэклога — статический отказ на
вызов git со ссылкой основной ветки без `origin/` в планке (отдельная
строка копилки); переписывание исторических планок на помощник;
изменение гейтов зон и приложений PLAN, кроме чтения их примитивов.

Рамка: $30.
