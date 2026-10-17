---
task: 01M551W0TFCT2XRQ71XFXJDKB9
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Долгоживущие тесты по профилю проекта: задание автора тестов и чекпоинт

# Долгоживущие тесты по профилю проекта: задание автора тестов и чекпоинт

## Факты

Основание — строка копилки 29.09 (`docs/backlog.md`, пункт «2а» задания test_author) и подключение внешнего проекта sled (`targets.yaml`: `long_lived_dir: backend/tests`, `long_lived_name: test_<id>_<name>.py`). С D0-1 каталог и шаблон имени долгоживущих тестов — поля профиля проекта (`project_profile.Profile.long_lived_dir`, `long_lived_name`), и часть пульта уже читает их оттуда: гейт выхода из `tests_writing` (`orchestrator/advance_gates/tests_writing.py:381-402`, `profile.is_long_lived`), перечень долгоживущих файлов (`orchestrator/advance_gates/acceptance.py:117`), `amend.py`, `preflight.py`, полный прогон (`acceptance.py:1380`). `guard.long_lived_path_prefix` и `guard.is_long_lived_test_path` (`scripts/guard.py:2959-2971`) принимают каталог и шаблон параметрами.

Значения артели по умолчанию (`tests/`, `test_<id>_<name>.py`) вместо профиля проекта задачи остаются в:
- задании роли (`orchestrator/role_prompt.py:36` — `guard.long_lived_path_prefix(task_id)` без профиля; текст пунктов «2а» у test_author, `:76-83`, и «3» у developer, `:114`, называет каталог `tests/`);
- чекпоинте шага test_author (`orchestrator/checkpoint.py:376` — отбор кандидатов `guard.is_long_lived_test_path(task_id, p)`; `:383` — `ls_tree_files(base, "tests", …)`; `:497` — `_role_may_delete`);
- скиле `skills/test-authoring.md` (раздел о долгоживущих файлах называет `tests/`).

Следствие для sled: автор тестов получает указание писать в `tests/` корня (каталога тестов у sled там нет), а файл, написанный по профилю в `backend/tests/`, чекпоинт не признаёт своим и откатывает как правку вне мандата.

## Требуется

1. Задание роли (test_author и developer) называет каталог и префикс имени долгоживущего файла по профилю проекта задачи (`long_lived_dir`, `long_lived_name`), тем же источником профиля, которым пользуется гейт выхода из `tests_writing`.
2. Чекпоинт test_author (отбор кандидатов, сверка с базой ветки, право удаления своих файлов) использует тот же каталог и шаблон профиля проекта задачи.
3. `skills/test-authoring.md` — защищённый путь: аналитик в SPEC приводит готовый текст правки раздела о долгоживущих файлах (вместо буквального `tests/` — «каталог долгоживущих тестов проекта, назван в задании роли»; правила для артели по смыслу не меняются); правку вносит Оператор командой `doc-commit` после мержа.
4. Аналитик сверяет по коду, не осталось ли других мест с буквальным `tests/` или вызовом `guard.long_lived_path_prefix` / `is_long_lived_test_path` без параметров профиля на пути задачи внешнего проекта, и перечисляет их в SPEC: найденные в зонах — в требования, вне зон — эскалация до SPEC.
5. Для артели (профиль без отличий от значений по умолчанию) текст задания, отбор и коммит долгоживущих файлов чекпоинтом не меняются ни на байт; зафиксировать это тестами до правки.
6. Тесты детерминированы, без сети: учебный внешний проект с `long_lived_dir` вне корня (например, `backend/tests`) — задание test_author называет этот каталог; файл роли по шаблону в нём чекпоинт коммитит, а файл в `tests/` корня (не по профилю) откатывает.

Критерии приёмки:
- у артели задание test_author и developer и поведение чекпоинта прежние;
- у учебного внешнего проекта задание называет `backend/tests/test_<id>_`, чекпоинт коммитит файл роли в `backend/tests/` и откатывает файл не по профилю;
- SPEC содержит готовый текст правки `skills/test-authoring.md`.

Зоны: `orchestrator/role_prompt.py`, `orchestrator/checkpoint.py`, `tests/`.

Только чтение: `skills/test-authoring.md`, `scripts/guard.py`, `orchestrator/project_profile.py`, `orchestrator/targets.py`, `orchestrator/advance_gates/`, `targets.yaml`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: правка гейта выхода из `tests_writing` и перечня долгоживущих файлов (уже по профилю); первая задача на sled; песочница (D1а).

Рамка: $25. Набор моделей — по умолчанию.
