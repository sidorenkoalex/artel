# Записка spec_auditor

## Выяснено
- Визит 2 (spec_sha af308e64…): все 8 пунктов возврата Оператора отражены в SPEC (треб. 3, 6, 7, 8; AC-1, AC-3, AC-5–AC-7, AC-13, AC-17; «Не входит»).
- Факты о коде верны: artel.py:2562, role_prompt.py:197/:503, gitcmd.py:25/:1123/:259-276, docs/stack.md:529-535/:568-578, repo_context.clone_path = PROJECTS/<имя>/repo (клон артели ≠ ROOT).
- НОВОЕ, проверено руками: git при старте ставит свой exec-path первым в PATH детей. Внутри `!`-псевдонима PATH[0] = /Library/Developer/CommandLineTools/usr/libexec/git-core, `command -v git` → …/git-core/git. Значит вложенный git из pager/fsmonitor/`!`-псевдонима идёт МИМО обёртки на PATH — утверждение треб. 3 «вложенный git идёт через PATH» ложно.
- `git -c core.fsmonitor='git clean -fX' status` во временном репозитории вне ROOT повис (>120 с, видимо рекурсия: вложенный git наследует -c через GIT_CONFIG_PARAMETERS и снова зовёт fsmonitor). AC-7 в форме fsmonitor без таймаута вешает тест.
- Существующие тесты текст docs/stack.md и полный набор _ROLE_ALLOWED_COMMANDS не закрепляют (только докстринги).

## Не сработало
- pkill/ls в Bash под запретом; повисший фоновый тест остановлен TaskStop.

## Где остановился
- SPEC-AUDIT.md: verdict concerns (П1 exec-path, П2 fsmonitor-зависание/аргументы хука).

## Чего не хватило
- Знания, что git подменяет PATH детям (exec-path первым) — нигде в репозитории не записано.
