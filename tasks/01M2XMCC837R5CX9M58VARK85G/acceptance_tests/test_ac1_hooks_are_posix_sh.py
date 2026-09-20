"""AC-1: файлы `scripts/git-hooks/pre-commit` и `pre-push` существуют и
написаны на POSIX sh без bash-измов и внешних интерпретаторов.

Красен до реализации: каталога `scripts/git-hooks/` в репозитории нет вовсе — оба файла отсутствуют.
"""
import subprocess
import unittest

from _hooks import HOOK_NAMES, HOOKS_DIR

# Признаки, которых в POSIX sh быть не может: конструкции bash/ksh и вызовы
# посторонних интерпретаторов. PATH роли ограничен манифестом стека
# (SPEC, требование 1) — хук обязан обходиться git и оболочкой.
FORBIDDEN = (
    "[[", "]]", "<<<", "&>", "${!", "$'",
    "function ", "declare ", "typeset ", "source ", "echo -e",
    "python", "perl", "ruby", "node", "bash",
)

ALLOWED_SHEBANGS = ("#!/bin/sh", "#!/usr/bin/env sh")


class HookScriptsArePosixShTest(unittest.TestCase):

    def test_ac1_both_hooks_exist_and_are_posix_sh(self):
        """Оба хука лежат в `scripts/git-hooks/`, начинаются с sh-шебанга,
        разбираются `sh -n` и не несут ни bash-измов, ни вызовов
        посторонних интерпретаторов.

        Ловит мутацию: автор пишет `pre-push` на bash (шебанг `#!/bin/bash`
        или условие `[[ "$ref" == refs/heads/main ]]`) либо зовёт из хука
        `python3` — под ограниченным манифестом PATH такой хук на машине
        роли не исполнится, и проверка ниже покраснеет на шебанге/
        запрещённой подстроке.
        """
        for name in HOOK_NAMES:
            path = HOOKS_DIR / name
            with self.subTest(hook=name):
                self.assertTrue(path.is_file(), f"нет файла хука {path}")
                source = path.read_text(encoding="utf-8")

                first_line = source.splitlines()[0].strip() if source else ""
                self.assertIn(first_line, ALLOWED_SHEBANGS,
                              f"{name}: шебанг {first_line!r} — не POSIX sh")

                syntax = subprocess.run(["/bin/sh", "-n", str(path)],
                                        capture_output=True, text=True)
                self.assertEqual(syntax.returncode, 0,
                                 f"{name}: sh -n не разобрал скрипт: "
                                 f"{syntax.stderr}")

                # Комментарии из сверки исключены: объяснение «почему не
                # bash» в комментарии хука — не bash-изм.
                code = "\n".join(
                    line for line in source.splitlines()
                    if not line.strip().startswith("#")).lower()
                for token in FORBIDDEN:
                    self.assertNotIn(
                        token, code,
                        f"{name}: найден не-POSIX-признак {token!r}")


if __name__ == "__main__":
    unittest.main()
