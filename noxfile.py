import argparse
import shutil
from typing import Any, List, Optional, Tuple

import nox

# Default targets launched by nox
nox.options.sessions = ["checks", "tests.matrix"]
# Default backend for the venvs
nox.options.default_venv_backend = "venv"
# Fail the whole run if a target fails
nox.options.stop_on_first_error = True

# Python version used in the matrix
supported_python_versions = ["3.7", "3.8", "3.9", "3.10"]
# Python version linked in the '.venv' dev venv, used for quick tests, publish, IDEs, etc
dev_python_version = supported_python_versions[0]

# Project specific
project_folder = "vcrpy_encrypt"
tests_folder = "tests"


#
# PROJECT INIT
#
@nox.session(venv_backend="none")
def init(session: nox.Session):
    """Install the dev venv and link it to './.venv'."""
    _use_env(session)


@nox.session(name="init.githooks", venv_backend="none")
def init_githooks(session: nox.Session):
    """Install all provided githooks."""
    shell("git config core.hooksPath .githooks", session)


#
# LINTERS AND FORMATTER
#
@nox.session(python="3.7", reuse_venv=True)
def checks(session: nox.Session):
    """Check the codebase with linters and formatters."""
    install_from_poetry_lock(["black", "isort", "flake8", "mypy"], session)
    shell(f"black --check -q {project_folder} {tests_folder} noxfile.py", session)
    shell(f"isort --check {project_folder} {tests_folder} noxfile.py", session)
    shell(f"flake8 {project_folder}", session)
    shell(f"mypy --strict --no-error-summary {project_folder}", session)


def install_from_poetry_lock(pkgs: List[str], session: nox.Session) -> None:
    """Use poetry to produce a constraint file and install all given packages with it.
    This is useful to install a dependencies subset while maintaining the version constraint."""
    tmp = session.create_tmp()
    session.run_always(
        "poetry",
        "export",
        "--dev",
        "--without-hashes",
        "-o",
        f"{tmp}/c.txt",
        external=True,
    )
    session.run_always("pip", "install", "-c", f"{tmp}/c.txt", *pkgs, silent=False)
    shutil.rmtree(tmp)


#
# TESTS
#
@nox.session(venv_backend="none")
def tests(session: nox.Session):
    """Launch tests inside the dev venv."""
    launch_tests(session, poetry=True)


@nox.session(name="tests.spec", venv_backend="none")
def tests_spec(session: nox.Session):
    """Launch tests inside the dev venv as a spec list."""
    args = "-p no:sugar --spec"
    launch_tests(session, additional_args=args.split(" "), poetry=True)


@nox.session(name="tests.cov", venv_backend="none")
def tests_cov(session: nox.Session):
    """Launch the test suite in the dev venv, record coverage data, open the html report."""
    session.notify("tests.cov.update")
    session.notify("tests.cov.report")


@nox.session(name="tests.cov.update", venv_backend="none")
def tests_cov_update(session: nox.Session):
    """Launch the test suite and record coverage data."""
    launch_tests(session, poetry=True, coverage=True)


@nox.session(name="tests.cov.report", venv_backend="none")
def tests_cov_report(session: nox.Session):
    """Open the latest coverage report in the browser."""
    shell("xdg-open coverage/cov_html/index.html", session)


@nox.session(name="tests.matrix", reuse_venv=True)
@nox.parametrize("python", supported_python_versions, ids=supported_python_versions)
def matrix_tests(session: nox.Session):
    """Launch the test suite against a supported python version."""
    shell_always("poetry install", session)
    launch_tests(session, coverage=(session.python == dev_python_version))


def launch_tests(
    session: nox.Session,
    additional_args: Optional[List[str]] = None,
    poetry=False,
    coverage=False,
) -> None:
    """Build the test command and execute it."""
    cmd = ["pytest"]
    if poetry:
        cmd = ["poetry", "run"] + cmd
    if coverage:
        cmd += ["--cov=vcrpy_encrypt", "--cov-report", "html:coverage/cov_html"]
    if additional_args:
        cmd += additional_args
    if session.posargs:
        cmd += session.posargs
    session.run(*cmd, "tests", external=True)


#
# ENV MANAGEMENT
#
@nox.session(name="env.use", venv_backend="none")
def env_use(session: nox.Session):
    """Change dev venv. E.g.: nox -s env.use -- 3.8"""
    env = _parse_env(session.posargs)
    _use_env(session, env)


@nox.session(name="env.clean", venv_backend="none")
def env_clean(session):
    """Delete all nox venv and the dev venv."""
    shell("rm -rf .nox", session)
    shell("rm -rf .venv", session)


@nox.session(name="env.rebuild", venv_backend="none")
def env_rebuild(session):
    """Rebuild all needed venvs."""
    shell("rm -rf .nox", session)
    shell_always(f"nox -s checks --install-only", session)
    shell_always(f"nox -s tests.matrix --install-only", session)


def _use_env(session: nox.Session, env: str = dev_python_version) -> None:
    """Use the specified venv version as '.venv'."""
    # Ensure the env is up-to-date
    shell_always(f"nox -s tests.matrix({env}) --install-only", session)
    # Make sure the .venv symlink is reset
    shell_always(f"rm -f .venv", session)
    # Link the venv to '.venv' so that IDEs can find it easily (and use it for testing/debugging)
    # Also, this will be the default venv used by poetry in the project root
    venv_folder = f".nox/tests-matrix-{env.replace('.', '-')}"
    shell_always(f"ln -sf {venv_folder} .venv", session)


def _parse_env(to_parse: Optional[List[str]]) -> str:
    """Use argparse to validate and choose the venv version."""
    parser = argparse.ArgumentParser(description="Choose a venv version.")
    parser.add_argument(
        "env",
        type=str,
        nargs="?",
        choices=supported_python_versions,
        default=dev_python_version,
        help="The venv version",
    )
    args: argparse.Namespace = parser.parse_args(args=to_parse)
    return args.env


#
# VCRPY CASSETTES
#
@nox.session(name="cassettes.clean", venv_backend="none")
def clear_cassettes(session):
    """Delete all cached tests cassettes."""
    shell("rm -rf tests/cassettes", session)


#
# ACT
#
act_prod_ctx = "act-prod-ci"
act_dev_ctx = "act-dev-ci"
act_secrets_file = ".secrets"


@nox.session(name="act.prod", venv_backend="none")
def act_prod(session):
    """Test with act the GitHub action 'prod' workflow."""
    cmd = parse_act_cmd(session.posargs)
    if cmd == "run":
        shell("act -W .github/workflows/prod.yml", session)
    elif cmd == "shell":
        shell(
            f"docker exec --env-file {act_secrets_file} -it {act_prod_ctx} bash",
            session,
        )
    elif cmd == "clean":
        shell(f"docker rm -f {act_prod_ctx}", session)


@nox.session(name="act.dev", venv_backend="none")
def act_dev(session):
    """Test with act the GitHub action 'dev' workflow."""
    cmd = parse_act_cmd(session.posargs)
    if cmd == "run":
        shell("act -W .github/workflows/dev.yml", session)
    elif cmd == "shell":
        shell(
            f"docker exec --env-file {act_secrets_file} -it {act_dev_ctx} bash", session
        )
    elif cmd == "clean":
        shell(f"docker rm -f {act_dev_ctx}", session)


def parse_act_cmd(to_parse: Optional[List[str]]) -> str:
    """Use argparse to validate and choose the act command."""
    options = ["run", "shell", "clean"]
    parser = argparse.ArgumentParser(description="Choose an ACT command.")
    parser.add_argument(
        "cmd",
        type=str,
        nargs="?",
        choices=options,
        default=options[0],
        help="The act command",
    )
    args: argparse.Namespace = parser.parse_args(args=to_parse)
    return args.cmd


#
# BUILD & PUBLISH
#
@nox.session(venv_backend="none")
def build(session: nox.Session):
    """Let poetry build the whl package."""
    shell("poetry build", session)


@nox.session(name="publish.coverage", venv_backend="none")
def publish_coverage(session: nox.Session):
    """Upload coverage data with coveralls."""
    shell("poetry run coveralls", session)


@nox.session(name="publish.test", venv_backend="none")
def publish_test(session: nox.Session):
    """Upload the package to the test repo."""
    poetry_pypi_testing = "testpypi"
    shell(f"poetry publish -r {poetry_pypi_testing}", session)


@nox.session(name="publish.pypi", venv_backend="none")
def publish_prod(session: nox.Session):
    """Upload the package to the production PYPI repo."""
    shell(f"poetry publish", session)


#
# VERSION BUMPING
#
@nox.session(name="version.bump", venv_backend="none")
def version_bump(session: nox.Session):
    """Bump the version, commit and create the tag."""
    bump_rule = parse_bump_rule(session.posargs)

    current_version = session.run("poetry", "version", "-s", silent=True).replace(
        "\n", ""
    )
    next_version = confirm_version_bump_or_abort(current_version, bump_rule, session)

    session.run(
        "poetry",
        "version",
        next_version,
        external=True,
        silent=True,
    )
    shell("git add pyproject.toml", session)
    session.run(
        "git",
        "commit",
        "-m",
        f"bump version: {current_version} -> {next_version}",
        external=True,
        silent=True,
    )
    session.run(
        "git",
        "tag",
        "-a",
        f"v{next_version}",
        "-m",
        f"version {next_version}",
        external=True,
        silent=True,
    )


def confirm_version_bump_or_abort(
    current_version: str, bump_rule: str, session: nox.Session
) -> str:
    """Confirm the version bump."""

    if bump_rule == "custom":
        print(f"\nCurrent version: {current_version}")
        next_version = input("Next version: ")
    else:
        # Dry run to determine the next version
        tmp = session.create_tmp()
        shutil.copy("pyproject.toml", f"{tmp}/.")
        with session.chdir(tmp):
            session.run("poetry", "version", bump_rule, silent=True)
            next_version = session.run("poetry", "version", "-s", silent=True)
        shutil.rmtree(tmp)

    # Get confirmation
    print(f"\nProposed version bump: {current_version} -> {next_version}")
    answer = None
    while answer not in ["y", "n", ""]:
        answer = input("Are you sure? (Y/n) ").lower()
    print()
    if answer != "" and answer != "y":
        session.error()
    return next_version.replace("\n", "")


def parse_bump_rule(to_parse: Optional[List[str]]) -> str:
    """Use argparse to validate and choose a bump version rule."""
    options = [
        "patch",
        "minor",
        "major",
        "prepatch",
        "preminor",
        "premajor",
        "prerelease",
        "custom",
    ]
    parser = argparse.ArgumentParser(description="Choose a valid bump rule.")
    parser.add_argument(
        "rule",
        type=str,
        nargs=1,
        choices=options,
        help="The bump rule",
    )
    args: argparse.Namespace = parser.parse_args(args=to_parse)
    return args.rule[0]


def get_current_version(session):
    """Recover the project current version, as saved in the pyproject.toml file."""
    current_version = session.run("poetry", "version", "-s", silent=True)
    current_version = current_version.replace("\n", "")
    return current_version


#
# UTILITIES
#
def shell(cmd_string: str, session: nox.Session) -> Optional[Any]:
    """Convenient way to execute a shell command, wraps Session.run.
    This works only when there's no spaces in commands arguments."""
    return session.run(*cmd_string.split(" "), external=True)


def shell_always(cmd_string: str, session: nox.Session) -> Optional[Any]:
    """Convenient way to execute a shell command, wraps Session.run_always.
    This works only when there's no spaces in commands arguments."""
    return session.run_always(*cmd_string.split(" "), external=True)
