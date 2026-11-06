---
task: 01M6RN8AMHNX6TVYRNJGMTAKXC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Служебная строка коммитов пульта по записи проекта: policy.commit_trailer

# Служебная строка коммитов пульта по записи проекта: policy.commit_trailer

## Факты

1. Каждый коммит пульта получает в последнем абзаце сообщения служебную строку `PULT_ACTOR_TRAILER = "Artel-Actor: orchestrator"` (`orchestrator/gitcmd.py:544`), её добавляет `pult_message` (`:585-593`) после строки `policy.co_author`. Пульт по строке решений не принимает (комментарий `:539-543`). Вызовы `pult_message`: `orchestrator/pull.py:473`, `:556`, `:1107`, `orchestrator/checkpoint.py:1887`, `orchestrator/artifact_branch.py:371`, `orchestrator/amend.py:806`, `orchestrator/snapshot.py:277`.
2. Коммиты пульта уходят в репозитории внешних проектов (ветки задач, `refs/artifacts/*`); служебная строка с именем пульта видна людям проекта в истории.
3. Существующий тест `tests/test_01m5wdb7jy0vjghvkcaba2qc5t_rewrite_flow.py:76` сверяет строку дословно (`TRAILER = "Artel-Actor: orchestrator"`).
4. Поля доставки раздела `policy` и их проверка — `orchestrator/targets.py` (`LOCAL_FIELDS` `:395-410`, `DELIVERY_POLICY_FIELDS` `:424-427`, `_check_delivery` `:664-720`, образец строкового поля — `co_author` `:721-725`).

## Требуется

1. Новое необязательное поле `policy.commit_trailer` локального слоя: строка; непустая — одна строка вида `<Ключ>: <значение>` (ключ — латиница, цифры и `-`, без пробелов), пустая строка — служебной строки нет. Иное (несколько строк, строка без «: », ключ с пробелом) — отказ загрузки записи с именем поля.
2. `pult_message` проекта с полем пишет его значение вместо `PULT_ACTOR_TRAILER`; при пустом значении служебной строки нет (строка `co_author`, если задана, остаётся последним абзацем). Без поля — прежнее сообщение побайтно (умолчание не меняется, тест факта 3 зелёный без правки).
3. Поле пишется командой `target-set <проект> policy.commit_trailer <значение>`.

## Критерии приёмки

- Given вымышленная запись с `commit_trailer: "Harness-Actor: orchestrator"`, When коммит пульта (чекпоинт, подтяжка, документы задачи), Then последний абзац сообщения — эта строка, `Artel-Actor` в сообщении нет;
- Given `commit_trailer: ""`, Then служебной строки нет; при заданном `co_author` последний абзац — строка `co_author`;
- Given запись без поля, Then сообщение прежнее побайтно;
- Given значение из двух строк, без «: » или с пробелом в ключе, When загрузка записи, Then отказ с именем поля `policy.commit_trailer`;
- `target-set <проект> policy.commit_trailer "Harness-Actor: orchestrator"` записывает поле с копией прежнего слоя; существующие тесты, включая `tests/test_01m5wdb7jy0vjghvkcaba2qc5t_rewrite_flow.py`, — зелёные без правки.

Безопасность тестов: вымышленные проекты и репозитории во временной песочнице (`tests.sandbox`), без сети; никогда — настоящий `.artel/targets.yaml`.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/gitcmd.py` (`pult_message`), `orchestrator/targets.py` (поле и проверка), `docs/codebase-map.md` (только генерацией), `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/pull.py`, `orchestrator/checkpoint.py`, `orchestrator/artifact_branch.py`, `orchestrator/amend.py`, `orchestrator/snapshot.py`, `orchestrator/projects.py`, `tests/test_01m5wdb7jy0vjghvkcaba2qc5t_rewrite_flow.py`, `tests/sandbox.py`.

Не входит:
- смена умолчания `PULT_ACTOR_TRAILER` (требует мандата на правку существующего теста — отдельным решением);
- шаблон текста сообщений коммитов;
- правка настоящего локального слоя `.artel/targets.yaml` в тестах и при разработке.

Приоритет 3.

Рамка: $20. Набор моделей — по умолчанию.
