# Записка spec_auditor — 01M6QZ4RR80B2BYM9AXG5ZMAS4

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, spec_sha 9794add0.
- Главное: AC-1 недостижим. Сведённый `test_profile` всегда несёт
  `weakening_scope`/`mutation_claim_scope` из `policy`:
  - дописывает `targets._flatten`, `orchestrator/targets.py:866-868`;
  - обязательны по `PROFILE_OPTIONAL`, `:93-94`, и `_check_profile`,
    `:1164-1170`.
  Проверено прогоном `merge_local` в памяти. Сравнивать надо
  `description.test_profile` слоя с файлом.
- Файл compose для AC-1 требует ещё `long_lived_dir`/`long_lived_name`.
  Без `compose_mount` отказ звучит «нет поля 'test_profile.compose_mount' —
  обязательно при 'runner: compose'».
- `yamlmini.mapping`: `""` → `{}`; блочный список и `[a, b]` → YamlError;
  повторный ключ — последний молча побеждает; `{b: 1}` — строка.
- `_render` пропускает точку в ключе, поэтому имя компонента с точкой
  неоднозначно (`description.components.app.runner`).

## Не сработало
- Запись в /tmp запрещена; пробы писал в каталог документов и убрал
  командой task-rm.

## Где остановился
- Аудит завершён, guard ок.

## Чего не хватило
- Правила «weakening_scope живёт в policy, но обязателен в профиле» не
  было ни в ТЗ, ни в карте. Нашёл в `targets._flatten` и `_check_profile`.
