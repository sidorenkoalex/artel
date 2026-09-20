"""Приёмочный тест AC-7 задачи 01M2XMCG167615YS9EZD9TYJWV: сообщение
коммита несёт префикс вида пути — `docs: <путь> — <message>` для
`docs/**` и `config: <путь> — <message>` для `roles.yaml`/`gates.yaml`/
`targets.yaml`.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — коммита не появляется вовсе, `origin_subject()` остаётся
сообщением фикстурного коммита песочницы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CONFIG_REL, DOC_REL, DocCommitSandbox  # noqa: E402

DOC_MESSAGE = "раздел про мьютекс мержа"
CONFIG_MESSAGE = "модель ревьювера"


class CommitMessagePrefixTest(DocCommitSandbox):

    def test_ac7_docs_path_commit_message_uses_docs_prefix(self):
        """Коммит по пути `docs/**` подписан `docs: <путь> — <message>`
        целиком, без отсебятины вокруг.

        Ловит мутацию: сообщение собирается одним общим префиксом на оба
        вида путей (например всегда `docs:`) — этот тест остаётся
        зелёным, а парный ниже краснеет; обратная перепутанность
        префиксов краснит уже этот.
        """
        source = self.source_file("# Роадмап\n\nНовый раздел.\n")

        self.run_artel("doc-commit", DOC_REL, "--from", str(source),
                       "--message", DOC_MESSAGE)

        self.assertEqual(self.origin_subject(),
                         f"docs: {DOC_REL} — {DOC_MESSAGE}")

    def test_ac7_operator_config_path_commit_message_uses_config_prefix(self):
        """Коммит по пути конфигурации Оператора (`roles.yaml`) подписан
        `config: <путь> — <message>`.

        Ловит мутацию: префикс выбирается по факту наличия точки/
        расширения, а не по виду пути, и конфигурация получает тот же
        `docs:` — тест красен на несовпадении строки целиком.
        """
        source = self.source_file("developer:\n  model: sonnet\n",
                                  name="roles.yaml")

        self.run_artel("doc-commit", CONFIG_REL, "--from", str(source),
                       "--message", CONFIG_MESSAGE)

        self.assertEqual(self.origin_subject(),
                         f"config: {CONFIG_REL} — {CONFIG_MESSAGE}")


if __name__ == "__main__":
    unittest.main()
