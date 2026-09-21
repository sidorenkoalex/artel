"""AC-4: `models.yaml` — защищённый путь и допустимый путь `doc-commit`
с префиксом коммита `config:`.

Красен до реализации: `models.yaml` нет ни в `config.PROTECTED_PATHS`, ни
в `notes.DOC_COMMIT_CONFIG_PATHS` — команда `doc-commit` на этот путь
сегодня отказывает как на постороннем.
"""
import unittest

import _models
from orchestrator import config, notes


class ProtectedPathTest(unittest.TestCase):

    def test_ac4_models_yaml_is_in_protected_paths(self):
        """`models.yaml` в список защищённых путей этой частью НЕ входит
        — он войдёт частью 2 линии (01M300A14K).

        Правка подтеста — решение Оператора 20.09 по возврату из
        verifying: CI-джоб `protected-paths` (.github/workflows/ci.yml)
        читает `config.PROTECTED_PATHS` из ВЕТКИ PR, поэтому ветка,
        которая создаёт `models.yaml` и одновременно объявляет его
        защищённым, красит собственный PR на создании этого файла;
        провести путь приложением к PLAN тоже нельзя — гейт приложений
        сверяется со списком главной копии. Защита включается частью 2,
        когда файл уже в главной копии.

        Ловит мутацию: путь внесён в список этой веткой — джоб
        `protected-paths` снова падает на создании файла, и задача не
        может дойти до мержа.
        """
        self.assertNotIn(_models.CATALOG_NAME, config.PROTECTED_PATHS)


class DocCommitPathTest(unittest.TestCase):
    """Канал Оператора мимо главной копии (`orchestrator/notes.py`)."""

    def request(self, message: str = "смена цены") -> dict:
        return {"kind": notes.DOC_COMMIT_KIND, "path": _models.CATALOG_NAME,
                "content": "", "message": message}

    def test_ac4_doc_commit_accepts_models_yaml(self):
        """`doc-commit models.yaml` не отказывает по списку допустимых
        путей.

        Ловит мутацию: путь добавлен только в защищённые
        (`config.PROTECTED_PATHS`), но не в допустимые пути `doc-commit` —
        Оператор защитил файл от ролей и отрезал себя от единственной
        команды, которой он его правит.
        """
        self.assertIn(_models.CATALOG_NAME, notes.DOC_COMMIT_CONFIG_PATHS)
        self.assertIsNone(
            notes._doc_commit_path_refusal(_models.CATALOG_NAME),
            f"doc-commit отказывает пути {_models.CATALOG_NAME}")

    def test_ac4_doc_commit_message_carries_the_config_prefix(self):
        """Сообщение коммита `doc-commit` на этот путь начинается с
        `config:`, а не с `docs:`.

        Ловит мутацию: префикс выбирается по единственной ветке «`docs/`
        или `docs`» и новый путь конфигурации получает `docs:` — история
        правок конфигурации перестаёт отличаться от правок документации.
        """
        message = notes._commit_message("", self.request(), None)

        self.assertTrue(
            message.startswith(f"config: {_models.CATALOG_NAME} "),
            f"сообщение коммита doc-commit: {message!r}")


if __name__ == "__main__":
    unittest.main()
