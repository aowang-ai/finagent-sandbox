"""Repo-root resolution for the src-layout package."""

from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
SRC_DIR = PKG_DIR.parent
REPO_ROOT = SRC_DIR.parent
