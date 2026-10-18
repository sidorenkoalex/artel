---
task: 01M56G7SB1PSR277BN4CHJBCQC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Ревью-пакет задачи внешнего проекта: конвенции проекта, без карты пульта

## Подход
Одна развилка в `orchestrator/review.py::review_package` по признаку проекта
`brief.is_artel_task(conn, task_id)` (тот же `repo_context.is_artel`, что у
брифа):

- у задачи внешнего проекта сразу после формы вердикта (до ANSWER-n.md,
  стат-списка и diff) в `parts` добавляются куски
  `brief._project_conventions_parts(conn, task_id, "reviewer", run_id,
  _conventions_component)`. Чтение и пометки «файла нет» / «конвенции проекта
  не прочитаны: <причина>» (с записью журнала) — целиком в `brief.py`, в
  `review.py` чтения нет. `render` — новый закрытый помощник
  `review._conventions_component`, он зовёт `artifact_part(label, text, "",
  run_id)`: заголовок с путём, размером и sha256, тело в границах
  `brief.wrap_boundary` с общим `run_id` пакета;
- абзац об исключениях: у артели прежний текст побайтно; у внешней задачи —
  фраза об исключении `tasks/<id>/` из стат-списка и diff и короткое
  упоминание, что из diff исключён `docs/codebase-map.md` (с объёмом
  `excluded_note`), без джоба CI и команды `scripts/codebase_map.py`.

Место конвенций (требование 3): после формы вердикта. Это правила, по
которым ревьювер сверяет diff, поэтому они стоят рядом с формой и до решений
Оператора и diff — тем же местом проверял стаб test_author.

Требование 5: долгоживущий тест с литералом-эталоном пакета артели
(`tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`, AC-7) —
коммит ba3c8a3d шага test_author. Правка `review.py` приходит позже,
коммитом этого шага.

## Шаги
1. Развилка в `review_package`, помощник `_conventions_component`, абзац
   исключений по проекту, строка докстринга о порядке частей; регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`brief._project_conventions_parts`, пометки brief) |
| 2 | 1 (`_conventions_component` → `artifact_part` с `run_id`) |
| 3 | 1 (после формы вердикта, раздел «Подход») |
| 4 | 1 (абзац внешней задачи без джоба/команды) |
| 5 | тест ba3c8a3d до правки; ветка артели — прежний код |
| 6 | долгоживущий файл задачи (песочничный клон, без сети) |

Проверка: `python3 -m pytest tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py
tests/test_review_package_map.py tests/test_review_long_lived_exclude.py
tests/test_review_freshness.py tests/test_review_package.py
tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py
tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py tests/test_docs_dir_layout.py`
дало 209 passed, 29 subtests passed. Планки `acceptance_tests/` у задачи
нет: `plank-run` отвечает «планки нет».

## Влияние на систему
- У артели пакет не меняется: при `is_artel` код идёт прежними строками,
  это держит литерал AC-7. Гейт ёмкости (`advance_gates/capacity.py`) и
  `snapshot_exclude` не тронуты: состав diff прежний.
- У внешней задачи пакет вырастает на размер `CLAUDE.md`/`AGENTS.md`.
  Потолок файла (`CONTEXT_FILE_MAX_BYTES`) обрабатывает `artifact_part`, а
  деление на части — `context_package.discipline`, как для любых других
  компонентов.
- Нечитаемая база или файл пишут в журнал запись
  `brief.PROJECT_CONVENTIONS_UNREAD_ACTION` от роли `reviewer`, сборка при
  этом не падает.
- Откат — revert коммита с правкой `review.py`.

## Риски
- `brief._project_conventions_parts` закрыт по имени, но SPEC велит
  переиспользовать именно его, без дублирования чтения. Если его сигнатура
  изменится, сломаются оба вызова, и тесты задачи это поймают.

## Предложения системе
- Правило «литерал `tasks/` запрещён в долгоживущем файле, даже в докстрингах»
  видно только в `scripts/guard.py::long_lived_sign_hits` — стоило бы строки в
  skills/test-authoring.md (наблюдение test_author, подтверждаю).
