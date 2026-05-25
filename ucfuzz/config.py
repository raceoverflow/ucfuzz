"""
Package-level constants.

``VERSION`` is read from the installed package metadata so there is a single
source of truth in ``pyproject.toml``.  Falls back to ``"dev"`` when the
package is not installed (e.g. running straight from the repository).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    VERSION: str = version("ucfuzz")
except PackageNotFoundError:
    VERSION = "dev"
