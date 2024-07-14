from typing import List, Optional, Union, Literal

from invoke import task


poetry_pypi_testing = "testpypi"

# Supported python version lists - these must also be valid executable in your path
legacy_supported_python_versions = ["python3.8", "python3.9"]
supported_python_versions = ["python3.10", "python3.11", "python3.12"]
# Use the minimum python version required by the package
default_python_bin = legacy_supported_python_versions[0]


# If the most currently activated python version is desired, use 'inv install -p latest'
@task
def install(c, python=default_python_bin):
    if python == "latest":
        # don't do anything here: poetry will use the default python version
        pass
    else:
        c.run("poetry env use {}".format(python))
    c.run("poetry install")


@task
def rm_venv(c):
    c.run("rm -rf .venv")


# Use this to change quickly python version
@task(rm_venv)
def reinstall(c, python=default_python_bin):
    install(c, python)


@task
def build(c):
    c.run("poetry build")


@task(build)
def publish_coverage(c):
    c.run("poetry run coveralls")


@task(build)
def publish_test(c):
    c.run(f"poetry publish -r {poetry_pypi_testing}")


@task(build)
def publish(c):
    c.run("poetry publish")


@task()
def test(c, s=False, m=None):
    marks = ""
    if m is not None:
        marks = f" -m {m}"
    capture = ""
    if s:
        capture = " -s"
    c.run(f"poetry run pytest{capture}{marks}", pty=True)


@task()
def test_spec(c, m=None):
    marks = ""
    if m is not None:
        marks = f" -m {m}"
    c.run(f"poetry run pytest -p no:sugar --spec{marks}", pty=True)


@task()
def test_all_python_versions(c, coverage=False):
    test_all_legacy_python_versions(c, coverage)
    test_all_new_python_versions(c, coverage)


@task()
def test_all_new_python_versions(c, coverage=False):
    # Run the tests on an inverted supported_python_versions list, so that the last one is the default one so
    # no reset is needed
    python_versions = supported_python_versions.copy()
    python_versions.reverse()
    test_python_versions(c, python_versions, coverage)


@task()
def test_all_legacy_python_versions(c, coverage=False):
    # Run the tests on an inverted supported_python_versions list, so that the last one is the default one so
    # no reset is needed
    python_versions = legacy_supported_python_versions.copy()
    python_versions.reverse()
    test_python_versions(c, python_versions, coverage)


def test_python_versions(c, python_versions: List[str], coverage=False):
    cov = ""
    if coverage:
        cov = " --cov=vcrpy_encrypt"
    python_version_checked = ""
    for version in python_versions:
        print("\n>>> Make sure cassettes folder is empty\n")
        clear_cassettes(c)
        print(f"\n>>> Installing python venv with version: {version}\n")
        reinstall(c, python=version)
        print(f"\n>>> Running tests with version: {version}\n")
        result = c.run(f"poetry run pytest{cov}", pty=True, warn=True)
        if result.ok:
            python_version_checked += f" {version}"
        else:
            print(f"\n>>> Could not test correctly under {version} - stopping here!")
            exit(1)
    print(f"\n>>> All test passed! Python version tested:{python_version_checked}")
    print(f"\n>>> Current venv python version: {python_versions[-1]}")


@task()
def clear_cassettes(c):
    c.run("rm -rf tests/cassettes")
    print("Cleared!")


@task()
def test_cov(c, m=None):
    c.run("mkdir -p coverage")
    marks = ""
    if m is not None:
        marks = f" -m {m}"
    c.run(
        f"poetry run pytest --cov=vcrpy_encrypt --cov-report annotate:coverage/cov_annotate --cov-report "
        f"html:coverage/cov_html{marks}", pty=True)


@task(test_cov)
def html_cov(c):
    c.run("xdg-open coverage/cov_html/index.html")


#
# ACT
#
act_legacy_prefix = "act-ci-legacy-ci"
act_new_prefix = "act-ci-ci"
act_secrets_file = ".secrets"
AvailableContainer = Union[Literal["new"], Literal["legacy"]]


@task()
def act(c, shell: Optional[AvailableContainer] = None, clean: Optional[AvailableContainer] = None):
    if shell and clean:
        print("Only one argument between shell and clean can be specified.")
        exit(1)

    def _get_container_id(container_type: AvailableContainer) -> str:
        valid_ctx = ["new", "legacy"]
        if container_type not in valid_ctx:
            container_list = ", ".join(map(lambda s: f"'{s}'", valid_ctx))
            print(f"Invalid container name. Choose between {container_list}.")
            exit(1)
        if container_type == "new":
            act_container_prefix = act_new_prefix
        else:
            act_container_prefix = act_legacy_prefix
        return c.run(f"docker ps | grep {act_container_prefix} | cut -d' ' -f1", hide=True).stdout.strip()

    if shell:
        act_ctx = _get_container_id(shell)
        c.run(f"docker exec --env-file {act_secrets_file} -it {act_ctx} bash", pty=True)
    elif clean:
        act_ctx = _get_container_id(clean)
        c.run(f"docker rm -f {act_ctx}", pty=True)
    else:
        c.run("act -W .github/workflows/ci.yml", pty=True)
