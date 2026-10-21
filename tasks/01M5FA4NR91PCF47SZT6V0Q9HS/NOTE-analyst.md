## Выяснено
- Круг 3 (возврат с spec_gate, решения круга 2: AC-19 без вложенного прогона, статика + динамика; требование 3 — метка снимается `--drop`, только если не осталось записей того же run_stamp).
- Разбор наследования 116 классов перечня (ast, main f1f805b6): 91 → RealGitSandbox (tests/sandbox.py:1897), 19 → TmpRootTest (:1581), CanaryPoolDriftCheckTest подменяет config.ROOT в setUp (test_doctor_canary_pool.py:249), CmdCanaryTemplateSelectionTest — подмена по требованию 5.
- 3 класса test_invariants наследуют FsmTest: ROOT настоящий, подмена только на время fsm.cmd_approve (test_invariants.py:245–267).
- MainCopyGitUnchangedDuringTaskTest (test_invariants.py:3155) — голый TestCase без setUp, изоляция только вложенной Flow(TaskFlowSandbox) в методе (:3177–3186). Статическое правило Оператора его не пропустит, править файл нельзя.
- _live_dir = config.ROOT/.artel/<CANARY_LIVE_DIRNAME> (canary.py:2797).

## Не сработало
- `ls`, `$?`, `awk` в Bash под ролью отказывают/требуют подтверждения; Read и grep без подстановок работают.

## Где остановился
- QUESTIONS.md (2 вопроса: признак для MainCopyGitUnchanged, FsmTest как основа), guard ок. SPEC.md не тронут — после ANSWER: переписать требование 5/AC-19 по п.1 круга 2 + ответу, требование 3/AC-9/AC-14 по п.4 (метка снимается только без оставшихся записей run_stamp), удалить QUESTIONS.md.

## Чего не хватило
- Знания, что FsmTest держит ROOT настоящим: пришлось читать setUp test_invariants.py:149–317.
