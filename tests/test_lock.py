"""requirements.lock must pin every package the report and notebook extras ask for.

Without this, adding a package to pyproject.toml and forgetting the lock goes unnoticed.
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def normalise(name):
    # pip treats "Foo_Bar", "foo-bar" and "foo.bar" as the same package.
    return re.sub(r"[-_.]+", "-", name).lower()


def package_name(requirement):
    # "pandas>=2.2" -> "pandas": the name is everything before the first version sign.
    return normalise(re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0])


def pinned_names():
    names = set()
    for line in (ROOT / "requirements.lock").read_text().splitlines():
        if "==" in line and not line.startswith("#"):
            names.add(normalise(line.split("==")[0]))
    return names


def test_report_and_notebook_packages_are_pinned():
    with open(ROOT / "pyproject.toml", "rb") as f:
        extras = tomllib.load(f)["project"]["optional-dependencies"]
    wanted = {package_name(r) for extra in ("report", "notebook") for r in extras[extra]}

    missing = sorted(wanted - pinned_names())

    assert missing == [], f"not pinned in requirements.lock: {missing}"
