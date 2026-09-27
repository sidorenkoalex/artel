"""AC-6 (SPEC 01M3H3K73XBMJMD0EPXZX6HYY9):
`docs/reference/role-home/codex/AGENTS.md` документирует интерпретатор и
PATH, которые видит шаг Codex, а изменение соседнего `config.toml`
отражено в нём же.

Красен до реализации: сегодняшний `AGENTS.md` референса не упоминает ни
PATH, ни интерпретатор шага вовсе — он описывает изоляцию дома роли,
авторизацию и `--ignore-rules`, и роль, которой нужен интерпретатор
пульта, ищет его перебором (инцидент 27.09, «Контекст» SPEC).

Файлы референса читаются с диска рабочей копии сознательно: это файлы
РЕПОЗИТОРИЯ (зона задачи), а не артефакты задачи, — источником артефактов
остаётся артефактная ветка. Адрес каталога называет сам провайдер
(`home_reference()`), не литерал планки.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _step_env import DOC_FILE, ProviderStepEnvSandbox  # noqa: E402

#: Ключи курируемого конфига, относящиеся к окружению команд шага и его
#: PATH: их появление в `config.toml` критерий требует отразить в
#: `AGENTS.md`. Узнаются по имени, а не перечислением: какой именно ключ
#: выберет PLAN, планка не знает (SPEC требование 1).
SHELL_KEY_RE = re.compile(r"shell|env|path", re.I)

#: Адрес интерпретатора пульта — то, чем «интерпретатор, который видит
#: шаг» называется конкретно (`config.VENV_DIR`, SPEC
#: 01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 4).
VENV_ADDRESS = ".artel/venv"


class CodexRoleHomeDocsTest(ProviderStepEnvSandbox):

    def test_ac6_agents_md_documents_the_interpreter_and_the_path_of_the_step(self):
        """`AGENTS.md` референса называет PATH шага и интерпретатор, который
        шаг видит, — с его адресом (`.artel/venv`), а не намёком.

        Ловит мутацию: правка документации свелась к упоминанию самого
        механизма («PATH собирает role_env») без интерпретатора и его
        адреса — роль читает в доме то же, что читала 27.09, и снова ищет
        `python3.13` перебором; утверждение про адрес интерпретатора
        откажет.
        """
        text = self.curated_doc_text()

        self.assertIn("PATH", text, "PATH шага в AGENTS.md не описан")
        self.assertRegex(text, r"(?i)python|интерпретатор")
        self.assertIn(VENV_ADDRESS, text,
                      "адрес интерпретатора пульта в AGENTS.md не назван")

    def test_ac6_shell_environment_keys_of_the_config_are_reflected_in_the_doc(self):
        """Каждый ключ курируемого `config.toml`, относящийся к окружению
        команд шага и его PATH, назван в `AGENTS.md`: правка конфига без
        правки документа критерием не допускается.

        Ловит мутацию: решение задаётся ключом курируемого `config.toml`
        (например политикой окружения оболочки), а `AGENTS.md` о нём молчит
        — Оператор, разворачивая дом роли руками, не знает, чем держится
        паритет, и теряет его первой же чисткой конфига.
        """
        doc_text = self.curated_doc_text()
        keys = sorted(key for key in self.curated_config()
                      if SHELL_KEY_RE.search(key))

        for key in keys:
            with self.subTest(key=key):
                # Ключ адресуется точечным именем (`секция.ключ`), а в
                # тексте документа он может стоять и частями — поэтому
                # требуется имя секции и имя самого ключа, а не буквальная
                # склейка.
                for part in (key.split(".")[0], key.split(".")[-1]):
                    self.assertIn(part, doc_text,
                                  f"ключ {key} конфига дома роли не отражён "
                                  f"в {DOC_FILE}")


if __name__ == "__main__":
    unittest.main()
