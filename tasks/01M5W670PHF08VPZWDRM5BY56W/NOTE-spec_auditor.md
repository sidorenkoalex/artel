# Записка spec_auditor — 01M5W670PHF08VPZWDRM5BY56W (аудит 2, spec_sha cd9a29b6)

## Выяснено
- Рабочий каталог (HEAD 58d9b72) позади origin/main: А0 только в origin/main (5705cfd) — сверять через `git show origin/main:…`.
- Замечания первого аудита закрыты ANSWER-1 и редакцией SPEC (белый список с `GET /projects/:id` и pipelines?ref, head_sha локальный, «не запущен», unknown/X-Total, зоны части 2).
- Новое: origin/main tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:411-520 (`test_ac9_no_support_literals_outside_targets`) — AST-сторож: сравнение `forge` с литералом "github"/"gitlab" вне targets.py и EXEMPT — красный. Диспетчер forge.py/ci.py по полю `forge` на `==` его заденет; SPEC сторож не упоминает. Обход — именованная константа или словарь (сторож ловит только ast.Constant).
- test_doctor.py:670 (без token_slot) — skip остаётся: hosting_token → (None, None), SPEC треб. 4 трактует как «нет токена» — сходится.
- A0 ac7: НЕ сходится — фикстура initialized_tmp_root → TmpRootTest → isolate_keychain_and_role (tests/sandbox.py:1619, :656-670) отдаёт `test-token-<слот>`; после части 2 doctor пойдёт живым HTTP на https://localhost (SPEC.md:463-465 неверен).
- Статус конвейера не учитывается: мосты (`trigger:`) не видны в /jobs → конвейер failed с видимыми success = green по треб. 6.
- github pipeline_status: отображение итогов не задано, AC-13 слабый.

## Где остановился
- Вердикт concerns (О-1…О-6), SPEC-AUDIT.md записан, guard ок.

## Чего не хватило
- Где А0 (не в рабочем каталоге, а в origin/main).
