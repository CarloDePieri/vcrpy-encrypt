import re
import signal
import sys
from contextlib import contextmanager
from typing import Callable, Dict, List

from invoke import Collection, Result, Runner, task

from tasks import dev_python_version, ns, supported_python_versions

#
# ENV MANAGEMENT
#

# Global variable used to handle ctrl+c
keyboard_interrupted = False


def env_use(
    c: Runner,
    python_version: str = dev_python_version,
    link: bool = True,
    quiet: bool = False,
    super_quiet: bool = False,
) -> None:
    """Activate a poetry virtual environment. Optionally link it to .venv."""
    c.run(
        f"poetry env use python{python_version}{' -q' if super_quiet else ''}", pty=True
    )
    if link:
        venv_path = c.run("poetry env info -p", hide=True).stdout.rstrip("\n")
        c.run(f"rm -f .venv && ln -sf {venv_path} .venv")
    ok(f"Env {python_version}{'' } activated", quiet)


@contextmanager
def poetry_venv(c: Runner, python_version: str):
    """Context manager that will execute all commands inside with the selected poetry
    virtualenv.
    It will restore the previous virtualenv (if one was active) after it's done.

    ```python
    @task
    def get_version(c):
        with poetry_venv(c, '3.7'):
            c.run("poetry run python --version")
    ```

    """
    # TODO handle cache
    # try to get the active venv
    check_old_env = c.run("poetry env info -p", hide=True, warn=True)  # type: Result
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
        env_use(
            c, python_version, link=should_link_new_env, quiet=True, super_quiet=True
        )

    try:
        # inject the python version in the Runner object
        c.poetry_python_version = python_version
        # execute the wrapped code block
        yield
    finally:
        if should_restore_old_env:
            env_use(c, old_env_python_version, link=True, quiet=True, super_quiet=True)


def task_in_poetry_env_matrix(python_versions: List[str]):
    """A decorator that allows to repeat an invoke task in the specified poetry venvs.
    Must be called between the @task decorator and the decorated function, like this:

    ```python
    @task
    @task_in_poetry_env_matrix(python_versions: ['3.7', '3.8']
    def get_version(c):
        c.run("poetry run python --version")
    ```

    """

    def wrapper(decorated_function):
        def task_wrapper(c, *args, **kwargs):

            # Make sure ctrl+c is handled correctly
            signal.signal(signal.SIGINT, _ctrl_c_handler)

            # Check all proposed python version are valid
            for version in python_versions:
                check_python_version(version)

            info("Job matrix started")
            results = {}

            # Define a job (it's the decorated function!)
            def job():
                decorated_function(c, *args, **kwargs)

            # For every python version, execute the job
            for version in python_versions:
                results[version] = _execute_job(c, version, job)

            # Print a final report
            _print_job_matrix_report(results, python_versions)

        return task_wrapper

    return wrapper


def _execute_job(c: Runner, version: str, job: Callable) -> str:
    """Execute the defined job in the selected poetry env, returning the result
    as a string."""
    global keyboard_interrupted

    if not keyboard_interrupted:
        try:
            with poetry_venv(c, version):
                info(f"Venv {version}: enabled")
                job()
            ok(f"Venv {version}: success")
            return "success"

        except (Exception,):
            if keyboard_interrupted:
                error(f"Venv {version}: INTERRUPTED", exit_now=False)
                return "interrupted"
            else:
                error(f"Venv {version}: FAILED", exit_now=False)
                return "failure"
    else:
        return "skipped"


def _ctrl_c_handler(_, __) -> None:
    """When ctrl-c is captured, set the 'keyboard_interrupted' global variable."""
    global keyboard_interrupted
    keyboard_interrupted = True
    raise KeyboardInterrupt


def _print_job_matrix_report(
    results: Dict[str, str], python_versions: List[str]
) -> None:
    """Print a report at the end of a matrix job run."""
    # Print the matrix result
    info("Job matrix result:")
    for venv in python_versions:
        state = results[venv]
        color = {
            "success": Colors.OKGREEN,
            "interrupted": Colors.FAIL,
            "failure": Colors.FAIL,
            "skipped": Colors.OKBLUE,
        }[state]
        print(f"\t{color} - python{venv}: {state}{Colors.ENDC}")
    # Print a final result message
    results_values = results.values()
    if "failure" in results_values:
        error("Failed")
    elif "interrupted" in results_values:
        error("Interrupted")
    elif "skipped" in results_values:
        warn("Done (but some job skipped!)")
    else:
        ok("Done")


@task
def env_use_task(c, python_version=dev_python_version):
    check_python_version(python_version)
    env_use(c, python_version)


@task
def env_list(c):
    c.run("poetry env list", pty=True)


@task
def env_clean(c):
    c.run("rm -rf .venvs && rm -f .venv")
    ok("Virtual envs deleted")


@task
def env_rebuild(c):
    # This should stay here, to avoid circular import
    from tasks.main import install_project_dependencies

    env_clean(c)
    for venv in supported_python_versions:
        if venv != dev_python_version:
            env_use(c, venv, link=False, quiet=True)
            install_project_dependencies(c)
    env_use(c, dev_python_version, link=True, quiet=True)
    install_project_dependencies(c)
    ok("Virtual envs rebuilt")


env = Collection("env")
env.add_task(env_use_task, "use")
env.add_task(env_list, "list")
env.add_task(env_clean, "clean")
env.add_task(env_rebuild, "rebuild")
ns.add_collection(env)


#
# LOGGING
#
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


def warn(msg, quiet: bool = False):
    if not quiet:
        print(f"{Colors.WARNING}{Colors.BOLD}inv{Colors.ENDC} > {msg}")


def error(msg, exit_now: bool = True) -> None:
    print(f"{Colors.FAIL}{Colors.BOLD}inv{Colors.ENDC} > {msg}")
    if exit_now:
        exit(1)


#
# MISC
#
def check_python_version(python_version: str):
    if python_version not in supported_python_versions:
        error(
            f"Unsupported python version: choose between {supported_python_versions}",
        )


def get_version_from_venv_path(path: str) -> str:
    regex = r"py(?P<version>\d.+\d)"
    match = re.findall(regex, path)[0]
    return match


def pr(cmd, c, echo: bool = True, **kwargs) -> None:
    patched_cmd = f"poetry run {cmd}"
    if echo:
        info(patched_cmd)
    c.run(patched_cmd, **kwargs)


def get_additional_args() -> List[str]:
    if "--" not in sys.argv:
        return []
    else:
        delimiter = sys.argv.index("--") + 1
        return sys.argv[delimiter:]


def get_additional_args_string() -> str:
    def wrap_in_quote(x: str) -> str:
        # Try to handle quoted arguments
        if " " in x:
            return f'"{x}"'
        else:
            return x

    args = list(map(wrap_in_quote, get_additional_args()))
    if args:
        return " " + " ".join(args)
    else:
        return ""
