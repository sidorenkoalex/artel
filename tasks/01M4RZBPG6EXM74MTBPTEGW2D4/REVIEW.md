---
task: 01M4RZBPG6EXM74MTBPTEGW2D4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Записка следующему шагу и «Чего не хватило» (К-2б)

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–15 разнесены по шагам 1–4, у 13 есть ссылка на долгоживущие файлы test_author.
- Шаги размером с MR (guard + гейт мержа / checkpoint / brief + role_prompt / юнит-тест + карта), не микрооперации.
- Подход не конфликтует с архитектурой: освобождение записки сделано по образцу `is_task_passport`, контракт детали записи держит один модуль (`checkpoint.py`), а `brief.py` импортирует его лениво, без цикла. «Влияние на систему» совпадает с diff: 5 модулей зоны и 5 тестов требования 14, в которых добавлена только одна подмена. Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `guard.STEP_NOTE_ROLES` (scripts/guard.py:1907); `TASK_ROOT_ALLOWED_MD` дополнен точными именами через `re.escape`, не маской. Кортеж используют checkpoint (`_STEP_NOTE_AUTHORS`, `parse_step_note_saved`) и role_prompt (`step_note_name`); таблица brief сверена с кортежем тестом `tests/test_step_note_contract.py` |
| 2 | OK | `is_step_note` проверяет уровень `parent.parent.name == "tasks"`. Записка пропускается в `guard --all`, в проверке одного файла (guard.py ~4475) и в `fsm_merge_gate._task_docs_violations` |
| 3 | OK | `_filter_step_notes` стоит после фильтра посторонних файлов и до конфликт-гварда. «Написана шагом» решается сравнением sha объекта git с выкладкой, а при пустой выкладке — с головой ссылки. Записи «чужая записка отброшена» и «записка слишком велика» (`>`, байты). Конфликт-гвард не тронут; удаление фазы 4 записку не задевает, потому что у записки нет frontmatter `type: questions` |
| 4 | OK | `harvest_code_copy_docs` передаёт `role=None`; записка исключена и из возвращаемого набора |
| 5 | OK | Запись о сохранении делается только при непустом `detail` коммита и только для своей записки, написанной шагом; список вычисляется до коммита. Сборка и разбор детали — в `checkpoint.py`. Бриф берёт автора и порядок из разбора и учитывает только записи `actor == orchestrator` |
| 6 | OK | `role_prompt.step_note_note` — один абзац, только при `docs_dir`; путь, четыре раздела, `str()` констант, обе фразы дословно; требования коммитить нет |
| 7 | OK | Фраза добавлена для spec_auditor и reviewer |
| 8 | OK | `_selected_step_notes`: своя последняя + `max` по `id` среди `STEP_NOTE_FOREIGN_AUTHORS[R]` |
| 9 | OK | Текст читается `artifact_branch.show` по `artifact_source.resolve`; сверка sha256 с пометкой и записью журнала; «не прочитана: <причина>»; пустая после `.strip()` записка блока не даёт |
| 10 | OK | `_journal_component(..., body=)`: хэш берётся от текста до нейтрализации, в границу идёт тело с заменённым id запуска. Заголовок `### label` вне границы называет файл, автора и время. Строки о границе и о данных роли на месте. Блок дописывается в `mission_brief_package` для всех ролей; runner передаёт `brief_text` любой роли (runner.py:705) |
| 11 | OK | Срез `raw[:4096]` с `errors="ignore"` (вход — валидный UTF-8, теряется только неполный хвостовой символ); пометка с N стоит вне границы |
| 12 | OK | Раздел «Чего не хватило» с пояснением в миссии; пульт его не разбирает |
| 13 | OK | Перечень мутаций закрыт пятью долгоживущими файлами и `tests/test_step_note_contract.py` |
| 14 | OK | Пять тестов получили только подмену `brief.step_notes_block`, утверждения не тронуты (сверено по diff) |
| 15 | OK | Карта свежая: перегенерация не дала расхождений вне `built_at_sha` |

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний в этой итерации нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m4rzbpg6exm74mtbptegw2d4_note_{autocommit,brief,guard,merge_gate,mission}.py tests/test_step_note_contract.py` — 38 passed, 143 subtests passed.
- `python3 -m pytest -q tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py tests/test_docs_dir_layout.py tests/test_role_prompt_test_author_mission.py tests/test_long_lived_manifest.py` — 37 passed, 18 subtests (тесты требования 14).
- `python3 -m pytest -q tests/test_brief.py tests/test_checkpoint_external_step_artifacts.py tests/test_checkpoint_stray_acceptance_files.py tests/test_timeout_checkpoint.py tests/test_01m490tdwemdq700vxtkyanf7k_passport_guard.py tests/test_guard_task_root_subdirectory.py tests/test_guard_extraneous_acceptance_files.py tests/test_fsm_merge_gate_done_snapshot.py "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::MissionTest"` — 108 passed, 26 subtests.
- `artel.py plank-run 01M4RZBPG6EXM74MTBPTEGW2D4` — отказ «планки нет»: в ссылке нет `test_*.py`, планка задачи — только долгоживущие файлы; они прогнаны выше.
- Временная мутация 1: в `checkpoint.parse_step_note_saved` снята проверка роли — `tests/test_step_note_contract.py::test_detail_of_unknown_role_or_other_form_is_not_parsed` красный (subtest `operator`). Код возвращён (`git checkout`).
- Временная мутация 2: в `brief._step_note_part` `body = text` (без нейтрализации id) — `test_ac17_forged_close_marker_stays_inside_boundary` красный. Код возвращён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — пусто; файл возвращён, `git status` чистый.

## Предложения системе

- `orchestrator/plank_run.py`: у задачи, где планка состоит только из долгоживущих файлов `tests/`, `plank-run` отвечает «планки нет» вместо прогона этих файлов. Это подтверждает и ревью (то же отметил PLAN); ревьюверу приходится гонять их pytest вручную.
