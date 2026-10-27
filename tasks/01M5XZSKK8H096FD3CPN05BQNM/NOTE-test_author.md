## Выяснено
- Часть 1 (01M5XZSKK8GZTECA2KWAFHE029, поля `full_suite`/`ci_job`) не влита: запись с `full_suite: ci` не грузится. Поэтому все 46 методов красные (merge-тесты: гейт вне границы, False без записей; AC-9: «контекст проекта не разрешён» на выходе из tests_writing).
- Все 13 AC — свойства кода. Покрыты одним долгоживущим файлом tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py (pytest, 46 методов). Каталога acceptance_tests/ нет: plank-run отвечает «планки нет», переход это допускает. preflight: всё «пройдена».
- Стенд — `CiGateBox(MergeOutcomeSandbox)`, его поднимает `tests.fixtures._sandbox`. Хостинг подменён через `mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": FakeForge})`. Гейт зовётся напрямую: `outcome_integrity.merge_gate_escalates(conn, id, state, lambda: main)`, потому что approve для gitlab закрыт (`SUPPORTED_FORGES`).
- Сбой подготовки = запись MERGE_PREPARE_ACTION + SystemExit, задача остаётся в merge_gate. Отказ = MERGE_REFUSAL_ACTION + escalated + True.
- Тесты проверены временным стабом (поля в targets/project_profile, `_judge_ci` в outcome_integrity): 46/46 зелёные, 11 мутаций стаба ловятся. Стаб откачен через `git checkout`.
- AC-8 «модуль не найден в голове»: проверяется только сам отказ, вид находки не утверждается — SPEC не говорит, как такую запись сопоставлять (аудит, D2).
## Не сработало
- В Bash не работают cd в составной команде с чтением файлов, `$VAR`, `rm`, `cat`. Работают абсолютные пути, python3 и `os.remove`.
- Сначала шпион отказывал чтению файлов блокировки во всех тестах — это ломало AC-9. Теперь отказ включается флагом `fail_locks` только в AC-11.
## Где остановился
- Шаг закончен: файл написан, preflight пройден, прогон красный по верной причине.
## Чего не хватило
- SPEC не называет функцию перевода отчёта в CaseResult (AC-7). Перевод проверяется через идентификаторы в находках гейта и сверкой с `outcome.parse_junit`.
