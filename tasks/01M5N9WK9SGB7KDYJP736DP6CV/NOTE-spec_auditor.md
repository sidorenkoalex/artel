# Записка spec_auditor — 01M5N9WK9SGB7KDYJP736DP6CV

## Выяснено
- Все адреса SPEC сверены с guard.py на 2b187a3d: :865, :1040, :1082, :1089, :1155, :1312, :1395, :1492, :1828, :1949, :1968, :1999, :3982; `_helper_callers` test_integrity.py:788 — совпадают.
- `_assertion_records` питает не только наблюдение: `assertion_changes` (guard.py:2476 → MethodChange → двусторонний прогон), храповик `_counts` (test_integrity.py:1160-1168), `method_literal_keys` (guard.py:5263, approve «Меняемое поведение»). SPEC эти последствия не называет; у записи фикстуры роль строгости None → `_strictness_sign` даёт «не оценена» (guard.py:2391).
- Распознавание вызовов `_called_dotted_name` без разрешения псевдонимов (guard.py:1092, :1128): `from pytest import xfail` обходит форму (б).
- `_is_assertion` (guard.py:1565-1574) шире перечня формы (а): любой `<x>.assert*`/`<x>.fail`.
- Зона `tests/` пересекается с зоной А1 `tests/fixtures.py` по `zone_lock._paths_overlap` (zone_lock.py:243-252) — вопреки «зоны не пересекаются».
- tests/fixtures.py в worktree нет.

## Не сработало
- Составные bash-команды с cd/переменными требуют подтверждения — только одиночные grep с абсолютными путями.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Перечня потребителей `_assertion_records` в SPEC — искал grep'ом по orchestrator/ и scripts/.
