import re
from contextlib import contextmanager
from functools import reduce

from invoke import Collection, Result, Runner, task

# Python version used in the matrix
supported_python_versions = ["3.7", "3.8", "3.9", "3.10"]
# Python version linked in the '.venv' dev venv, used for quick tests, publish, IDEs, etc
dev_python_version = supported_python_versions[0]

# Project specific
project_folder = "vcrpy_encrypt"
tests_folder = "tests"


ns = Collection()


#
# PROJECT INIT
#
@task(default=True)
def init(c):
    _env_use(c)
    install_project_dependencies(c)


@task
def init_githooks(c):
    c.run("git config core.hooksPath .githooks", pty=True)


init_coll = Collection("init")
init_coll.add_task(init, "dev")
init_coll.add_task(init_githooks, "githooks")
ns.add_collection(init_coll)


#
# LINTERS AND FORMATTER
#
@task
def checks(c, python_version=dev_python_version):
    check_python_version(python_version)
    with poetry_venv(c, python_version):
        install_project_dependencies(c)
        c.run(
            f"poetry run black --check {project_folder} {tests_folder} tasks.py",
            pty=True,
        )
        c.run(
            f"poetry run isort --check {project_folder} {tests_folder} tasks.py",
            pty=True,
        )
        c.run(f"poetry run flake8 {project_folder}", pty=True)
        c.run(f"poetry run mypy --strict --no-error-summary {project_folder}", pty=True)


ns.add_task(checks, "checks")


#
# TESTS
#
@task(default=True)
def tests_launch(c, python_version=dev_python_version):
    check_python_version(python_version)
    _tests_launch(c, python_version)
    ok("Test run complete!")


@task
def tests_spec(c, python_version=dev_python_version):
    check_python_version(python_version)
    _tests_launch(c, python_version, args="-p no:sugar --spec")
    ok("Test run complete!")


@task
def tests_cov(c, python_version=dev_python_version):
    check_python_version(python_version)
    _tests_launch(c, python_version, coverage=True)
    tests_html(c)
    ok("Test run complete!")


@task
def tests_html(c):
    c.run("xdg-open coverage/cov_html/index.html")
    info("Test report open in the browser")


@task
def tests_matrix(c):
    # TODO trasformarlo in un context manager o un decorator in modo da astrarre la logica dal contenuto
    info("Tests matrix started")
    results = {}
    for venv in supported_python_versions:
        try:
            info(f"Venv {venv}: enabled")
            _tests_launch(c, venv)
            ok(f"Venv {venv}: success")
            results[venv] = "success"
        except (Exception,):
            error(f"Venv {venv}: FAILED", exit_now=False)
            results[venv] = "failure"
    info("Tests matrix result:")
    for venv in supported_python_versions:
        color = Colors.OKGREEN if results[venv] == "success" else Colors.FAIL
        print(f"\t{color} - python{venv}: {results[venv]}{Colors.ENDC}")


def _tests_launch(
    c, python_version=dev_python_version, args: str = "", coverage: bool = False
) -> None:
    with poetry_venv(c, python_version):
        install_project_dependencies(c)
        coverage_str = ""
        if coverage:
            coverage_str = " --cov=vcrpy_encrypt --cov-report html:coverage/cov_html"
        c.run(f"poetry run pytest {args}{coverage_str}", pty=True)


tests_coll = Collection("tests")
tests_coll.add_task(tests_matrix, "matrix")
tests_coll.add_task(tests_launch, "launch")
tests_coll.add_task(tests_spec, "spec")
tests_coll.add_task(tests_cov, "cov")
tests_coll.add_task(tests_html, "html")
ns.add_collection(tests_coll)


#
# VCRPY CASSETTES
#
@task
def cassettes_clean(c):
    c.run("rm -rf tests/cassettes")
    ok("Cassettes cache cleaned")


cass_coll = Collection("cassettes")
cass_coll.add_task(cassettes_clean, "clean")
ns.add_collection(cass_coll)


#
# ACT
#
act_secrets_file = ".secrets"


@task(default=True)
def act_pr_launch(c):
    c.run(
        "act -W .github/workflows/pr.yml --artifact-server-path /tmp/act pull_request",
        pty=True,
    )


@task
def act_pr_shell(c, stage):
    c.run(
        f"docker exec --env-file {act_secrets_file} -it act-pr-{stage} bash", pty=True
    )


@task
def act_pr_clean(c):
    stages = ["checks"]
    containers = reduce(lambda x, y: f"{x} act-pr-{y}", stages, "")
    c.run(f"docker rm -f {containers}", pty=True)


@task
def act_clean_cache(c):
    c.run(
        "docker volume list --filter 'name=^act' | grep local | awk '{print $2}' | xargs -n1 docker volume rm"
    )


act_coll = Collection("act")
act_pr_coll = Collection("pr")
act_pr_coll.add_task(act_pr_launch, "launch")
act_pr_coll.add_task(act_pr_clean, "clean")
act_pr_coll.add_task(act_pr_shell, "shell")
act_coll.add_task(act_clean_cache, "clean_cache")
act_coll.add_collection(act_pr_coll)

ns.add_collection(act_coll)


#
# ENV MANAGEMENT
#
@task
def env_use(c, python_version=dev_python_version):
    check_python_version(python_version)
    _env_use(c, python_version)


def _env_use(
    c: Runner,
    python_version: str = dev_python_version,
    link: bool = True,
    quiet: bool = False,
    super_quiet: bool = False,
) -> None:
    c.run(
        f"poetry env use python{python_version}{' -q' if super_quiet else ''}", pty=True
    )
    if link:
        venv_path = c.run("poetry env info -p", hide=True).stdout.rstrip("\n")
        c.run(f"rm -f .venv && ln -sf {venv_path} .venv")
    ok(f"Env {python_version}{'' } activated", quiet)


@task
def env_list(c):
    c.run("poetry env list", pty=True)


@task
def env_clean(c):
    c.run("rm -rf .venvs && rm -f .venv")
    ok("Virtual envs deleted")


@task
def env_rebuild(c):
    env_clean(c)
    for venv in supported_python_versions:
        if venv != dev_python_version:
            _env_use(c, venv, link=False, quiet=True)
            install_project_dependencies(c)
    _env_use(c, dev_python_version, link=True, quiet=True)
    install_project_dependencies(c)
    ok("Virtual envs rebuilt")


@contextmanager
def poetry_venv(c: Runner, python_version: str):
    """Context manager that will execute all commands inside with the selected poetry virtualenv.
    It will restore the previous virtualenv after it's done."""
    # TODO handle cache
    # try to get the active venv
    check_old_env = c.run(f"poetry env info -p", hide=True, warn=True)  # type: Result
    old_env_exists = check_old_env.return_code == 0

    if old_env_exists:
        # Determine the old env python version
        old_env_python_version = get_version_from_venv_path(check_old_env.stdout)

        if python_version != old_env_python_version:
            # A new env needs to be activated
            should_activate_new_env = True
            should_link_new_env = False
            should_restore_old_env = True

        else:
            # The already active environment is the right one, do nothing
            should_activate_new_env = False
            should_link_new_env = False
            should_restore_old_env = False

    else:
        # poetry did not have an environment active
        old_env_python_version = None
        should_activate_new_env = True
        should_link_new_env = True
        should_restore_old_env = False

    if should_activate_new_env:
        _env_use(
            c, python_version, link=should_link_new_env, quiet=True, super_quiet=True
        )
    try:
        yield
    finally:
        if should_restore_old_env:
            _env_use(c, old_env_python_version, link=True, quiet=True, super_quiet=True)


def get_version_from_venv_path(path: str) -> str:
    regex = r"py(?P<version>\d.+\d)"
    match = re.findall(regex, path)[0]
    return match


def install_project_dependencies(c: Runner) -> None:
    c.run("poetry install", pty=True)


env = Collection("env")
env.add_task(env_use, "use")
env.add_task(env_list, "list")
env.add_task(env_clean, "clean")
env.add_task(env_rebuild, "rebuild")
ns.add_collection(env)


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def ok(msg, quiet: bool = False):
    if not quiet:
        print(f"{Colors.OKGREEN}{Colors.BOLD}inv{Colors.ENDC} > {msg}")


def info(msg, quiet: bool = False):
    if not quiet:
        print(f"{Colors.OKCYAN}{Colors.BOLD}inv{Colors.ENDC} > {msg}")


def error(msg, exit_now: bool = True) -> None:
    print(f"{Colors.FAIL}{Colors.BOLD}inv{Colors.ENDC} > {msg}")
    if exit_now:
        exit(1)


def check_python_version(python_version: str):
    if python_version not in supported_python_versions:
        error(
            f"Unsupported python version: choose between {supported_python_versions}",
        )
