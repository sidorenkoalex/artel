---
task: 01M443BPQEA9ZMJ3R50THNB1MF
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решения Оператора 04.10 по эскалации — вариант (а) по всем четырём вопросам.

1. Метод test_ac5_answer_in_dev_without_markers_keeps_old_refusal переписать под тем же именем: файл с маркером мандата тестов не в начале строки принимается как указание (запись «указание Оператора», ни записи мандата, ни элемента в журнале). Свойство «цитата маркера — не мандат» сохраняется.
2. В test_developer_step_has_no_package дописать три вызова fetch_ref_sha (fetch, rev-parse, update-ref по приватной ссылке, сверка по префиксу refs/artel/fetch/), комментарий метода дополнить пунктом о подтяжке. Ничего не подменять.
3. docs/operator-session.md — правка в ветке задачи (путь не защищённый, ошибка ТЗ Оператора); предложенный абзац принят.
4. Оба решения сверх SPEC оставить: подтяжка перед шагом без прогона планки и её пропуск, пока метка конфликта ждёт шага роли. Описать в PLAN («Подход»).

Ослабление тестов разрешено: tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py::AnswerInDevWithoutMarkersTest::test_ac5_answer_in_dev_without_markers_keeps_old_refusal, tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package
Расширение зон разрешено: docs/operator-session.md
