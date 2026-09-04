---
task: 01M1KCSTBYF1CRJBSY4P6VYQEA
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

Вопрос ревьювера (итерация 1, красный залоченный тест AC-19) —
решено ручным каналом ADR-0012, Оператором: в
`acceptance_tests/test_ac18_ac19_attention_alert_closes_on_next_transition.py`
в `setUp` класса AC-19 добавлены подмены `gitcmd.show`/
`gitcmd.ls_tree_files` (по образцу `tests/test_auto_cycle.py::
AutoCycleTest`, только для этого класса — подмена в общей песочнице
`_sandbox.py` ломала AC-6/AC-10), в двух тестах AC-19 дописаны заявки
«Ловит мутацию» (R1-F3). Утверждения тестов не менялись, другие файлы
планки не тронуты; коммит `1c4e19a7` в артефактной ветке, лок
переведён на него, запись в журнале задачи; планка на голове ветки:
«Ran 25 tests — OK».

Ревьюверу: эскалация снята; вердикт по существу — `approved` либо
`changes_requested` по оставшемуся R1-F2 (заявки «Ловит мутацию» в
`tests/test_stall_alerts.py`, зона developer) на ваше усмотрение;
R1-F3 закрыт правкой выше — отразить в реестре. Форма REVIEW.md:
секции «Соответствие SPEC», «Замечания», «Реестр замечаний»,
«Вердикт» — заголовки второго уровня.
