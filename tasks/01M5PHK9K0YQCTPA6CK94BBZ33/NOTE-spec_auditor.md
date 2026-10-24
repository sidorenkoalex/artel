## Выяснено
- Числа SPEC подтвердились: 2493/609/160 строк, 42+3+8 тестов, 43/4/8 строк «Ловит мутацию» (литералы CLAIM :91 и :69). Песочница — строки 47–899, OutcomeGateSandbox :296–899; IdOutcomeGateSandbox кончается на :516, а не на :520.
- AC-8 («нет наследников unittest.TestCase») противоречит треб. 7/AC-7: IdOutcomeGateSandbox → GitignoreCommittedRealGitSandbox → RealGitSandbox → TmpRootTest(unittest.TestCase) (tests/sandbox.py:1581,1897,2047), а лежать она должна в самом test_outcome_gate_module.py.
- Список совпадающих имён в SPEC неверен: на верхнем уровне при другом содержимом совпадают только GATE_ACTIONS, VITEST_KIND, spec_text. OLD/NEW/HINT/js_names/VITEST_IT/PLANK_JS_PREFIX в outcome_gate нет вовсе; answer_proc/runner_files — методы, в пространстве имён модуля они не сталкиваются. GATE_ACTIONS в списке пропущен.
- AC-18 «docs/codebase-map.md не изменён» строже ТЗ («руками не правится») и расходится с conventions-core (регенерировать карту при правке tests/*.py) и с волной 1а (7ea8ae48 менял карту в ветке).
- Под pytest падение setUp у наследника TestCase — FAILED (до), а у фикстуры — ERROR at setup (после); в AC-3 описан только второй случай.
## Не сработало
- В песочнице Bash нельзя ls/cat/awk и `cd &&` — читать через python3 heredoc, относительные пути.
## Где остановился
- SPEC-AUDIT.md написан, вердикт fail; guard прогнан.
## Чего не хватило
- Как guard видит вызов `box.method()` (не видит) — `_HelperScope.function` в scripts/guard.py:1902.
