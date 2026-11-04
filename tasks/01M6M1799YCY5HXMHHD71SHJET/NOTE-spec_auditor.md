# Записка spec_auditor

## Выяснено
- Визит 5 (spec_sha 150cb7e3…): три отклонения визита 4 (AC-1 другое имя, `api` в AC-14/AC-13, правило имён в github_call) сняты решением гейта №4 и отражены в SPEC (треб. 1, 7; AC-1, AC-13, AC-14).
- Факты кода по HEAD 89698bf92 подтверждены: forge.py:127-212, ci.py:39-116/257-283, github_adapter.py:107-115/340-343/372-458, fsm_merge_gate.py:1587-1590/1672-1714/1840-1908, targets.py:590-592/699-706, repo_context.py:85-97.
- Прежние тесты: стенды с forge github — только gate operator (mr_delivery.py:1462, rewrite_flow.py:104, fail_closed:92); моков `mr_assignee` нет; тест формы интерфейса forge нет.
- Новое отклонение (concerns): AC-3 через `approve` требует `url` записи вида https/scp (иначе `_GitHub.open_mr` не даст iid), а белый список отправки target-human требует `remote.origin.url` клона == `url` записи и запрещает insteadOf (gitcmd.py:926-936) — с локальным голым origin отправки пульта на пути к гейту отказывают; SPEC форму стенда не называет.

## Не сработало
- `gh` в песочнице не запускается — тексты gh не проверены опытом (ТЗ: проба Оператора).

## Где остановился
SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
Где пульт сверяет origin клона с url записи — нашёл в gitcmd._config_redirect_refusal (gitcmd.py:915).
