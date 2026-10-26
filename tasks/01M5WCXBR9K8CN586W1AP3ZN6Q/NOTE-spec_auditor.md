# Записка spec_auditor — 01M5WCXBR9K8CN586W1AP3ZN6Q

## Выяснено
- Визит 2 (spec_sha ae4cb29…): все 5 пунктов прошлого аудита закрыты решением гейта №1 и правкой SPEC.
- `_GitHub` в forge.py:115-120 реализует только pipeline_status: forge.project_info/token_expiry для github — «не реализовано». GitHub-тесты doctor зовут check_base_branch("sled", entry) с необъявленным "sled" (tests/test_doctor.py:633-703): выбор реализации должен идти по переданному entry (forge.IMPLEMENTATIONS + getattr), не по forge.*(name) — иначе github-тесты покраснеют.
- test_non_github_forge_is_skipped: skip фактически из-за необъявленного "sled" (forge.py:172-175), не из-за url file:// — формулировку продиктовало решение гейта №4, не поднимаю как отклонение.
- AC-6 обходится модульной константой `GITLAB = "gitlab"` или модульным помощником с литералом: сторож А0 их не ловит (Compare с Name не watched literal; check_base_branch в EXEMPT).
- Правка isolate_keychain_and_role: guard.weakened_helpers назовёт её по смене литералов, гейт ищет вызывающих, но находок без потери утверждений нет — мандат ANSWER не нужен.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns (2 отклонения + примечание), guard: ок.

## Не сработало
- `sed -i` и `$?` в Bash требуют подтверждения — правки только через Edit.

## Чего не хватило
- Как выбрать github/gitlab без литерала при необъявленном имени — пришлось сверять forge._hosting и тесты test_doctor.
