from functools import reduce

from invoke import Runner

from tasks import (
    dev_python_version,
    ns,
    project_folder,
    supported_python_versions,
    tasks_folder,
    tests_folder,
)
from tasks.helpers import (
    Collection,
    check_python_version,
    get_additional_args_string,
    info,
    ok,
    poetry_venv,
    pr,
    task_in_poetry_env_matrix,
)


#
# Project specific function
#
def install_project_dependencies(c: Runner, quiet: bool = True) -> None:
    if not quiet:
        info("poetry install")
    c.run("poetry install", pty=True)


#
# DEFAULT TASK
#
@ns.task(name="ci", default=True)
def ci(c):
    checks(c)
    tests_matrix(c)


#
# PROJECT INIT
#
init = Collection("init")
ns.add_collection(init)


@init.task(name="dev", default=True)
def init_task(c):
    with poetry_venv(c, dev_python_version):
        install_project_dependencies(c, quiet=False)


@init.task(name="githooks")
def init_githooks(c):
    cmd = "git config core.hooksPath .githooks"
    info(cmd)
    c.run(cmd, pty=True)


#
# LINTERS AND FORMATTER
#
@ns.task(name="checks")
def checks(c, python_version=dev_python_version):
    info("Checks started")
    check_python_version(python_version)

    with poetry_venv(c, python_version):
        install_project_dependencies(c, quiet=False)

        def check(cmd):
            pr(cmd, c, pty=True)

        check(f"black --check {project_folder} {tests_folder} {tasks_folder}")
        check(f"isort --check {project_folder} {tests_folder} {tasks_folder}")
        check(f"flake8 {project_folder} {tasks_folder}")
        check(f"mypy --strict --no-error-summary {project_folder}")

    ok("Checks done")


#
# TESTS
#
tests = Collection("tests")
ns.add_collection(tests)

ok_msg = "Test run complete!"


@tests.task(name="launch", default=True)
def tests_launch(c, python_version=dev_python_version):
    _tests_launch_in_venv(c, python_version=python_version)
    ok(ok_msg)


@tests.task(name="spec")
def tests_spec(c, python_version=dev_python_version):
    _tests_launch_in_venv(c, python_version, args="-p no:sugar --spec")
    ok(ok_msg)


@tests.task(name="cov")
def tests_cov(c, python_version=dev_python_version):
    _tests_launch_in_venv(c, python_version, coverage=True)
    tests_html(c)
    ok(ok_msg)


@tests.task(name="html")
def tests_html(c):
    pr("xdg-open coverage/cov_html/index.html", c)
    info("Test report opened in the browser")


@tests.task(name="matrix")
@task_in_poetry_env_matrix(python_versions=supported_python_versions)
def tests_matrix(c, coverage: bool = False):
    _tests_launch(c, coverage=coverage)


def _tests_launch_in_venv(
    c, python_version=dev_python_version, args: str = "", coverage: bool = False
) -> None:
    check_python_version(python_version)
    with poetry_venv(c, python_version):
        _tests_launch(c, args, coverage)


def _tests_launch(c: Runner, args: str = "", coverage: bool = False) -> None:
    install_project_dependencies(c, quiet=False)
    coverage_str = ""
    if coverage:
        coverage_str = " --cov=vcrpy_encrypt --cov-report html:coverage/cov_html"
    if args != "" and args[0] != "":
        args = f" {args}"
    additional_args = get_additional_args_string()
    pr(f"pytest{args}{additional_args}{coverage_str}", c, pty=True)


#
# VCRPY CASSETTES
#
cassettes = Collection("cassettes")
ns.add_collection(cassettes)


@cassettes.task(name="clean")
def cassettes_clean(c):
    pr("rm -rf tests/cassettes", c)
    ok("Cassettes cache cleaned")


#
# ACT
#
act = Collection("act")
act_pr = Collection("pr")
act.add_collection(act_pr)
ns.add_collection(act)
act_secrets_file = ".secrets"


@act_pr.task(name="launch", default=True)
def act_pr_launch(c):
    pr(
        "act -W .github/workflows/pr.yml --artifact-server-path /tmp/act pull_request",
        c,
        pty=True,
    )


@act_pr.task(name="shell")
def act_pr_shell(c, stage):
    pr(
        f"docker exec --env-file {act_secrets_file} -it act-pr-{stage} bash",
        c,
        pty=True,
    )


@act_pr.task(name="clean")
def act_pr_clean(c):
    stages = ["checks"]
    containers = reduce(lambda x, y: f"{x} act-pr-{y}", stages, "")
    pr(f"docker rm -f {containers}", c, pty=True)


@act_pr.task(name="clean-cache")
def act_clean_cache(c):
    pr(
        "docker volume list --filter 'name=^act' | grep local | awk '{print $2}' | "
        "xargs -n1 docker volume rm",
        c,
    )
    ok("Act docker volumes deleted")
