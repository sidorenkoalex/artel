---
task: 01M5PCB66D936FDGG7H09CVGA1
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_doc_commit.py, tests/test_doc_commit_suite_gate.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_doc_commit_held_base.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_notes_batch_flush_edges.py

Основание: мандат Оператора 23.10.2026 (дословно: «Волна сведения тестов по note; после бери все остальные модули в работу - даю мандат»); решение Оператора 24.10.2026 вести волну 1б параллельно («ок»); ADR-0027 п. 8; ADR-0020 п. 8, ветвь «удаление без замены долгоживущим тестом — решением Оператора» для `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py` и `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py` (свойства переносятся в `tests/test_doc_commit_module.py`); объём — требования 2–4 ТЗ: перенос с дословными ожиданиями и удаление дублей по таблицам мутаций; удаление утверждения без переноса, ослабление сравнения, `skip`/`xfail`, подъём пределов не разрешены. Мандат снимает находки обоих гейтов по этим путям — `test_integrity` и `outcome_integrity`.

Независимая проверка: повтор `mutation-run` сессией при Операторе на зафиксированном наборе патчей (база — шесть исходных файлов, голова — `tests/test_doc_commit_module.py`) и сверка утверждений по синтаксическому дереву до approve на merge_gate — обязательны.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| tests/test_doc_commit.py | `doc-commit`: отказы, сверка, отправка | остаётся | `tests/test_doc_commit_module.py`; таблица мутаций «после» | перенос |
| tests/test_doc_commit_suite_gate.py | гейт полного набора на правке конфигурации | остаётся | `tests/test_doc_commit_module.py`; таблица мутаций «после» | перенос |
| tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py | сверка удержанной записи с базой (сценарий 02.10) | остаётся | `tests/test_doc_commit_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_doc_commit_held_base.py | удержание `doc-commit` с базой | остаётся | `tests/test_doc_commit_module.py`; таблица мутаций «после» | перенос |
| tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py | `doc-commit` по пути и сообщению | остаётся | `tests/test_doc_commit_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_notes_batch_flush_edges.py | края пакетного сброса с правкой конфигурации | остаётся | `tests/test_doc_commit_module.py`; таблица мутаций «после» | перенос |
