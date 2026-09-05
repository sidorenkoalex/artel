---
task: 01M1SG9YKBFG2G5YQDVBR6BVC8
type: spec
author_role: analyst
status: ready
schema_version: 4
zones: docs/reference/role-home/claude/settings.json, tests/
budget_usd: 15
---

# SPEC: автопамять CLI отключена у ролей курируемого слоя

## Контекст
Роли тратят конец шага на записи в личную автопамять CLI
(`.artel/home/.claude/projects/.../memory/`): test_author задачи B2
(01M1R5B33C…) упёрся в таймаут 45 мин на этом, 124 млн токенов. Память
ролям не нужна по построению — всё, что должно пережить шаг, лежит в
артефактах задачи, скилах и референсе слоя ролей (ADR-0005). CLI
поддерживает отключение автопамяти настройкой `autoMemoryEnabled: false`
в `settings.json` каталога конфигурации.

## Требования
1. В референсе слоя ролей `docs/reference/role-home/claude/settings.json`
   задан ключ `"autoMemoryEnabled": false`.
2. Тест в `tests/` проверяет, что референсный `settings.json` содержит
   этот ключ со значением `false`.
3. Существующая проверка doctor, сравнивающая деплой и референс
   role-home по файлам (в т.ч. по `settings.json`), не ослабляется —
   остаётся действующей и покрывающей этот файл.

## Критерии приёмки

AC-1. `docs/reference/role-home/claude/settings.json` содержит ключ
`"autoMemoryEnabled"` со значением `false`.

AC-2. В `tests/` есть тест, который читает
`docs/reference/role-home/claude/settings.json` и проверяет, что ключ
`autoMemoryEnabled` присутствует и равен `false`.

AC-3. Существующие тесты `orchestrator.doctor.check_role_home_reference`
(сверка деплоя и референса role-home, включая `settings.json`) остаются
зелёными и не ослаблены изменением этой задачи.

AC-4. Существующие файлы памяти в
`.artel/home/.claude/projects/*/memory/` этой задачей не удаляются и
не изменяются.

## Не входит

- Переменная окружения `CLAUDE_CODE_DISABLE_AUTO_MEMORY` через runner
  (зона `runner.py` занята задачей путей брифа 01M1RQ12JV…; отдельная
  строка — предмет будущей задачи).
- Правка скилов.
- Чистка накопленной автопамяти ролей.
- Раскатка изменённого `settings.json` в
  `.artel/home/.claude/settings.json` — операторское действие после
  мержа (деплой при холодном старте), не часть этой задачи.

## Материалы
- Копилка 05.09, `docs/backlog.md`, приоритет 1.
- Судьба накопленных файлов памяти (кандидат: прочитать на ревизии как
  материал К2, затем `prune`) и раскатка референса в
  `.artel/home/.claude/settings.json` после мержа — операторские
  действия вне этой задачи; RETRO генерируется детерминированно из
  БД и не несёт свободного текста, поэтому оба пункта — заметка
  Оператору себе на будущее, не критерий приёмки этой задачи.
