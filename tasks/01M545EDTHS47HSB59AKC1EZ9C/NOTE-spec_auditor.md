# Записка spec_auditor

## Выяснено
- sha SPEC = fc88e2b3 (сверено git hash-object).
- Адреса SPEC верны: misc_checks.py:92 (gh repo view), artifact_branches.py:126-146 (_push_closing_sha, push на :137 через gitcmd.in_repo → git("-C", source)), brief.project_skills_refusal(target, entry) brief.py:593, repo_context.clone_path :75-79, keychain.token(slot).
- orchestrator/config.py — в config.COMMON_ZONES (config.py:799), отсутствие в zones не отклонение.
- Порога FETCH_HEAD в config.py нет — новая константа.
- Опыт git 2.50: сброс через GIT_CONFIG_COUNT (credential.helper= + помощник пульта) убирает и глобальный, и URL-помощник для `git credential fill`, но `git config --get-all credential.helper` всё равно печатает чужой глобальный помощник → буквальный AC-3 п.1 требует подмены GIT_CONFIG_GLOBAL.
- Артель: рабочие копии/клон лежат в .artel/projects/artel/, у записи артели token_slot artel-token (токен модели, Ф-4 родителя) — AC-1 не фиксирует этот путь.
- ci.gh знает проект только по repo= (URL); trigger_rerun/find_run_id/stuck (ci.py:1148,1207,1240) зовут gh без repo.

- tests/test_doctor.py:670-692 (BaseBranchCheckTest, plain TestCase, EXTERNAL_ENTRY без token_slot) ждут ok/warn от check_base_branch("sled") — по треб. 1-2 покраснеют или полезут в настоящий keychain; tests/sandbox.py keychain.token не подменяет.

## Не сработало
- rm/ls в оболочке шага недоступны (command not found) — удалял через python3 os.unlink.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Отклонения О-1…О-5, Ф-1.

## Чего не хватило
- Родительский SPEC читается только `git show refs/artifacts/01M53B45XW3J56RJHGD70TD8A2:tasks/.../SPEC.md`.
