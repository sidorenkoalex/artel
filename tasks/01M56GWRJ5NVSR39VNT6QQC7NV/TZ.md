---
task: 01M56GWRJ5NVSR39VNT6QQC7NV
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Чекпоинт developer коммитит свои долгоживущие файлы внешнего проекта

# Чекпоинт developer коммитит свои долгоживущие файлы внешнего проекта

## Факты

Строка бэклога 18.10 (П3), аудит SPEC 01M55VGDHXQ55YR2YXXBPAHTNB (О-1). После мержа 01M55VGDHX гейт зон признаёт зоной новый файл задачи `test_<id>_*.py` в `long_lived_dir` профиля внешнего проекта, добавленный developer (паритет с `tests/` артели в `config.COMMON_ZONES`). Но WIP-чекпоинт developer (`orchestrator/checkpoint.py:229-235`, `_commit_worktree_change`) снимает со стейджа пути вне `_zone_paths` (`:1531-1545`: заявленные зоны + `config.COMMON_ZONES` + `tasks/<id>/`); у внешнего проекта `COMMON_ZONES` артели к `backend/tests/test_<id>_x.py` не относятся — незакоммиченный файл developer пульт не закоммитит (а чекпоинт подтяжки откажет), разработчик вынужден коммитить его сам. Чекпоинт test_author после 01M551W0TFCT2XRQ71XFXJDKB9 уже признаёт свои файлы по профилю (`Profile.is_long_lived`).

## Требуется

1. У задачи внешнего проекта зоны WIP-чекпоинта developer (и чекпоинта подтяжки, если он тем же узлом) включают собственные долгоживущие файлы задачи — пути, для которых `Profile.is_long_lived(task_id, path)` истинно; тем же источником профиля, что гейт зон после 01M55VGDHX. Прочие пути `long_lived_dir` в зону не входят. `config.COMMON_ZONES` не меняется.
2. Отказ определения профиля — зоны чекпоинта не расширяются (сегодняшнее поведение).
3. У артели чекпоинт не меняется; зафиксировать тестами до правки.
4. Тесты детерминированы, без сети: учебный внешний проект, задача с зонами `backend/src/` — незакоммиченный `backend/tests/test_<id>_x.py` developer коммитится чекпоинтом; `backend/tests/test_other.py` — снимается со стейджа; у артели — прежние исходы.

Критерии приёмки:
- чекпоинт developer внешнего проекта коммитит свои долгоживущие файлы без зоны `long_lived_dir`;
- чужие файлы каталога и чекпоинт артели — прежние.

Зоны: `orchestrator/checkpoint.py`, `tests/`.

Только чтение: `orchestrator/project_profile.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: гейт зон (сделан 01M55VGDHX); чекпоинт test_author (сделан 01M551W0TF).

Рамка: $25. Набор моделей — по умолчанию.
