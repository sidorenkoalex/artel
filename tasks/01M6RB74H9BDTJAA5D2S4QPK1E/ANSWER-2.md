---
task: 01M6RB74H9BDTJAA5D2S4QPK1E
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Основание: решение Оператора 06.11.2026 на гейте SPEC («мандат + убрать сверку»): существующим тестам с вымышленными записями GitLab без `commit_author` разрешено добавить это поле.

## Мандат

Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py

Пояснение: в этих файлах разрешено только добавить поле `machine.commit_author` (адрес — адрес подменённого владельца токена) в вымышленные записи проектов GitLab; утверждения, имена тестов и прочие поля записей не меняются.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py — вымышленная запись GitLab получает `machine.commit_author` | поддержка пары хостинг/гейт при `new` | да: утверждение прежнее, меняется только фикстура | tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:161 (то же утверждение) | ок |
| tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py — вымышленная запись GitLab получает `machine.commit_author` | отказ неподдержанного проекта при `new` | да: утверждение прежнее, меняется только фикстура | tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:399 (то же утверждение) | ок |

Независимая проверка: подтверждаю — аудит SPEC назвал строки `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:161` и `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:399`, сессия Оператора сверила, что нужна только правка записей.
