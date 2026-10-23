import os

from .direct_git import prefer_direct_git

DIRECT_GIT_DIR = prefer_direct_git(os.environ)
