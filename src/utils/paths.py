import os

# Data files ship with the repo, so they must be located relative to the source
# tree rather than the working directory - the server, the CLI and the tests all
# run from different places.
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def repo_path(*parts: str) -> str:
    """Absolute path to a file that ships with the repo."""
    return os.path.join(REPO_ROOT, *parts)
