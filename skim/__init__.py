"""skim - AST-aware token optimizer for AI coding agents."""

try:
    from importlib.metadata import version

    __version__ = version("skimcode")
except Exception:
    __version__ = "0.1.0"
