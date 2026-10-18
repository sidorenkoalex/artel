# Записка spec_auditor

## Выяснено
- Аудит SPEC sha 6aa7c27a (вторая версия, после решения гейта №1 О-1..О-3): вердикт concerns, SPEC-AUDIT.md сдан (status: ready), guard ок.
- Все факты SPEC о коде подтверждены (checkpoint.py:230-238, 828-911/:895, 1491/:1531, 1564, 1669-1707, 514-590, 1710/own_zones :1770-1772; runner.py:1931; zones.py:285-292).
- Главная находка: `_stray_staged_paths` (checkpoint.py:1595) — `diff --cached --name-only` без `--no-renames`; переименование чужого test_other.py в своё test_<id>_x.py после правки уйдёт в коммит пульта вместе с удалением чужого (restore вызывается только при stray, :233-234, :897-898).
- Мелкое: AC-6 один вид отказа decide (skip/refusal, project_profile.py:140-159) и один путь; AC-2 только success-путь.

## Не сработало
- Составные bash-команды (`;`, `&&`, `cd`, `$var`) песочница отклоняет — по одной команде с абсолютными путями; эмпирическую проверку переименования в /tmp сделать не удалось (опирался на умолчание git diff.renames=true).

## Где остановился
- Аудит завершён.

## Чего не хватило
- Явного указания, через что вызывается restore для developer (только при stray) — нашёл чтением _wip_checkpoint/commit_success_checkpoint.
