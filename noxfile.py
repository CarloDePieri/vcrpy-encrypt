from typing import Optional, List

import argparse
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


#
# TESTS
#
@nox.session(reuse_venv=True)
def checks(session: nox.Session):
    """Check the codebase with linters and formatters."""
    session.install("flake8")
    session.install("black")
    shell(f"black --check {project_folder} {tests_folder} noxfile.py", session)
    shell(f"flake8 {project_folder}", session)


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


@nox.session(
    name="tests.matrix",
    reuse_venv=True
)
@nox.parametrize("python", supported_python_versions, ids=supported_python_versions)
def matrix_tests(session, python):
    """Launch the test suite against a supported python version."""
    shell_always("poetry install", session)
    launch_tests(session, coverage=(python == dev_python_version))


def launch_tests(session: nox.Session, additional_args: Optional[List[str]] = None, poetry=False, coverage=False) -> None:
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
        help="The venv version"
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
        shell(f"docker exec --env-file {act_secrets_file} -it {act_prod_ctx} bash", session)
    elif cmd == "clean":
        shell(f"docker rm -f {act_prod_ctx}", session)


@nox.session(name="act.dev", venv_backend="none")
def act_dev(session):
    """Test with act the GitHub action 'dev' workflow."""
    cmd = parse_act_cmd(session.posargs)
    if cmd == "run":
        shell("act -W .github/workflows/dev.yml", session)
    elif cmd == "shell":
        shell(f"docker exec --env-file {act_secrets_file} -it {act_dev_ctx} bash", session)
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
        help="The act command"
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


@nox.session(name="publish.tag", venv_backend="none")
def publish_tag(session: nox.Session):
    """Bump the version, create and push the tag."""
    pass


#
# UTILITIES
#
def shell(cmd_string: str, session: nox.Session) -> None:
    """Convenient way to execute a shell command, wraps Session.run.
    This works only when there's no spaces in commands arguments."""
    session.run(*cmd_string.split(" "), external=True)


def shell_always(cmd_string: str, session: nox.Session) -> None:
    """Convenient way to execute a shell command, wraps Session.run_always.
    This works only when there's no spaces in commands arguments."""
    session.run_always(*cmd_string.split(" "), external=True)
