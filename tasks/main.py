from functools import reduce

from invoke import Collection, Runner, task

from tasks import (
    dev_python_version,
    ns,
    project_folder,
    supported_python_versions,
    tasks_folder,
    tests_folder,
)
from tasks.helpers import (
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
@task(default=True)
def ci(c):
    checks(c)
    tests_matrix(c)


ns.add_task(ci, "ci")


#
# PROJECT INIT
#
@task(default=True)
def init(c):
    with poetry_venv(c, dev_python_version):
        install_project_dependencies(c, quiet=False)


@task
def init_githooks(c):
    cmd = "git config core.hooksPath .githooks"
    info(cmd)
    c.run(cmd, pty=True)


init_coll = Collection("init")
init_coll.add_task(init, "dev")
init_coll.add_task(init_githooks, "githooks")
ns.add_collection(init_coll)


#
# LINTERS AND FORMATTER
#
@task
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


ns.add_task(checks, "checks")


#
# TESTS
#
ok_msg = "Test run complete!"


@task(default=True)
def tests_launch(c, python_version=dev_python_version):
    _tests_launch_in_venv(c, python_version=python_version)
    ok(ok_msg)


@task
def tests_spec(c, python_version=dev_python_version):
    _tests_launch_in_venv(c, python_version, args="-p no:sugar --spec")
    ok(ok_msg)


@task
def tests_cov(c, python_version=dev_python_version):
    _tests_launch_in_venv(c, python_version, coverage=True)
    tests_html(c)
    ok(ok_msg)


@task
def tests_html(c):
    pr("xdg-open coverage/cov_html/index.html", c)
    info("Test report open in the browser")


@task
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
    pr("rm -rf tests/cassettes", c)
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
    pr(
        "act -W .github/workflows/pr.yml --artifact-server-path /tmp/act pull_request",
        c,
        pty=True,
    )


@task
def act_pr_shell(c, stage):
    pr(
        f"docker exec --env-file {act_secrets_file} -it act-pr-{stage} bash",
        c,
        pty=True,
    )


@task
def act_pr_clean(c):
    stages = ["checks"]
    containers = reduce(lambda x, y: f"{x} act-pr-{y}", stages, "")
    pr(f"docker rm -f {containers}", c, pty=True)


@task
def act_clean_cache(c):
    pr(
        "docker volume list --filter 'name=^act' | grep local | awk '{print $2}' | "
        "xargs -n1 docker volume rm",
        c,
    )
    ok("Act docker volumes deleted")


act_coll = Collection("act")
act_pr_coll = Collection("pr")
act_pr_coll.add_task(act_pr_launch, "launch")
act_pr_coll.add_task(act_pr_clean, "clean")
act_pr_coll.add_task(act_pr_shell, "shell")
act_coll.add_task(act_clean_cache, "clean_cache")
act_coll.add_collection(act_pr_coll)
ns.add_collection(act_coll)
