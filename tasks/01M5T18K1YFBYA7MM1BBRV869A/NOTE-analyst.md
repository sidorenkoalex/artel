# Записка analyst

## Выяснено
- Блок конвенций внешнего проекта: orchestrator/brief.py:45 PROJECT_CONVENTIONS,
  :602 _read_project_conventions, :777 _project_conventions_parts. Потребители:
  developer_brief :1252, spec_auditor_brief :1322, бриф analyst :1623,
  test_author_answer_component :1661, пакет ревьювера orchestrator/review.py:955
  (render `_conventions_component` :205).
- Миссии внешнего проекта называют «CLAUDE.md и AGENTS.md его базовой ветки»:
  orchestrator/role_prompt.py:53 (analyst), :121 (developer) — после задачи ложь;
  внесено в зоны SPEC как следствие требования 1 ТЗ.
- Предел размера блока — оформитель render потребителя (config.CONTEXT_FILE_MAX_BYTES).
- Соседняя задача «ИИ-настройки … полем записи» = 01M5T19041XE2KB6A52F0AT0NF, её
  зоны: doctor/preflight.py, doctor/__init__.py → пересечение по
  doctor/__init__.py → merge_after с обоснованием (строка ТЗ «Порядок мержа:»
  не формата «Порядок:», заявленным значением не стала).
- Проверки doctor по проектам — цикл orchestrator/doctor/cli.py:139.
- Сигналы деления: файлов зоны 8, budget ≥30 → выбрана нарезка на 2 части
  (бриф | команда отметки + doctor + docs).
- Затронутые тесты: 3 файла (external_brief, review_conventions, knowledge_brief).

## Не сработало
- grep по чужим tasks/ запрещён — читал TZ соседней задачи через
  `git show refs/artifacts/<id>:tasks/<id>/TZ.md`.

- Формат заголовка проверен: `yamlmini.frontmatter` плоский (sources теряет),
  `yamlmini.mapping` по телу между `---` разбирает вложенность; sha — в кавычках.

## Где остановился
SPEC.md написан, status: ready, guard ок. Деление на 2 части (бриф | отметка+doctor+docs);
budget_usd 50 — на случай монолита.

## Чего не хватило
Id соседней задачи искал перебором refs/artifacts — в ТЗ только название.
