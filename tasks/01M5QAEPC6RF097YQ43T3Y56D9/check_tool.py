"""Временная сверка планки по диску (удаляется к концу шага).

python3 check_tool.py <файл планки> [-k …]
"""
import os
import sys

sys.dont_write_bytecode = True  # без __pycache__ в каталоге документов
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "acceptance_tests"))
sys.path.insert(1, D)
import pytest  # noqa: E402

sys.exit(pytest.main([os.path.join(D, "acceptance_tests", sys.argv[1]),
                      "-p", "no:cacheprovider", f"--confcutdir={D}", "-q",
                      "-o", "addopts=", *sys.argv[2:]]))
