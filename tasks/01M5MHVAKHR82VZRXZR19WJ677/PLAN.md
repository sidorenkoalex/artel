---
task: 01M5MHVAKHR82VZRXZR19WJ677
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Удалить тринадцать определений пульта, которые никто не вызывает

## Подход
Механическое удаление тринадцати определений таблицы SPEC «Контекст» вместе с
докстрингами, правка висячих упоминаний (требование 2) и перегенерация карты.
Ни один импорт не стал неиспользуемым: все имена, к которым обращались
удалённые определения (`workspace`, `gitcmd`, `json`, `re`, `Path`, `config`,
`store`, `_answer_texts`, `_mandate_items`, `_compare` …), используются и
остальным кодом модулей — импорты не трогались (требование 1, уточнение
Оператора). Свойства требований 3–4 держит долгоживущий файл автора тестов
`tests/test_01m5mhvakhr82vzrxzr19wj677_dead_definitions.py`, отдельный
дублирующий файл не пишется (так разрешает SPEC).

## Шаги
1. Удаление определений:
   `advance_gates/spec_audit.py` — `answer_names`;
   `advance_gates/test_integrity.py` — `assertion_observation`;
   `fixation.py` — `external_code_sha`; `gitcmd.py` — `is_clean`;
   `merge_after.py` — `has_mandate_line`; `pool_seal.py` — `guids_path`;
   `retro.py` — `retro_rel_path`, `retro_path` (`RETRO_DIR_REL` остаётся);
   `retro_corpus.py` — `read_cache`; `rounds.py` — `task_rounds`;
   `models.py` — `VERDICT_APPROVED`; `scripts/core_reference.py` —
   `SETTING_KEYS`, `SHA_HEX`.
2. Упоминания: `gitcmd.py` докстринги `commits_behind` и `diff_paths` —
   «что у `head_sha`» вместо пары с `is_clean`; `fixation.py` докстринг
   `default_code_sha` — «как и у `external_artifact_sha`»; комментарий над
   `VERDICT_RETURN` в `models.py` — пишутся `return` и `approved`, константа
   только для `return`, её читает сверка пары.
3. `python3 scripts/codebase_map.py` — карта перегенерирована.
4. Проверка: долгоживущий файл задачи — 2 passed, 13 subtests passed;
   `artel.py plank-run 01M5MHVAKHR82VZRXZR19WJ677` — 7 passed, код 0;
   `pytest tests/test_core_reference.py tests/test_merge_after.py
   tests/test_models.py tests/test_retro.py tests/test_retro_corpus.py
   tests/test_rounds.py` — 92 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 4 (долгоживущий файл автора тестов) |
| 4 | 4 (долгоживущий файл автора тестов) |
| 5 | 3 |
| 6 | 1, 4 — существующие тесты не правились |

## Влияние на систему
Удаляется только код без обращений (сверено grep по `orchestrator/`,
`scripts/` и AST-тестом AC-2); поведение пульта, гейты, тесты, лимиты не
меняются, существующие файлы `tests/` не правились. Откат — revert
merge-коммита задачи.

## Риски
Динамическое обращение по строке (`getattr(модуль, "имя")`) grep/AST не
видят; поиск по строковому имени в коде пульта таких обращений не нашёл.

## Предложения системе
- В venv пульта нет `pyflakes`: проверку «импорт стал неиспользуемым» пришлось
  делать чтением кода; планка AC-3 закрыла это, но разработчику нечем
  свериться до планки.
