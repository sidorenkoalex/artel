# Записка spec_auditor (итерация 3, SPEC sha 8ae17298…)

## Выяснено
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.
- Решения ANSWER-1 (1–11, У1–У4) и решения гейта №2 в SPEC внесены; матрица SPEC = матрица ANSWER-1.
- Новые находки:
  - М4: external_brief `test_ac9`, сценарии 1–3 (`run_scenario` :510–552) краснеют. В `PROJECT_ENTRY` нет `knowledge`, а треб. 3 даёт пометку только при `knowledge`; перечень SPEC не говорит добавить `knowledge` в фикстуру.
  - М5: `assertNotEqual` на :459 BothConventionFilesTest теряет предмет; судьба не названа.
  - П1: AC-9 без отказа stamp на symlink `conventions.md` и прочих случаев треб. 7.
  - Н2: N для файлов не `*.md`.
  - Ф1: у соседки список обвязки — требование 5, не 4.
- Соседка 01M5T19041 — в `tests_writing` (гейт SPEC прошла).

## Не сработало
- `cd … && git`, составные bash и `grep` с некоторыми шаблонами требуют подтверждения — только одиночные команды с абсолютными путями.

## Где остановился
- Аудит завершён.

## Чего не хватило
- Как ведут себя сценарии `test_ac9` без `knowledge` — пришлось прослеживать `_project_conventions_parts` (brief.py:777) вместе с `PROJECT_ENTRY` теста.
