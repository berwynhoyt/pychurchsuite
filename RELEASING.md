# Releasing pychurchsuite to PyPI

Releases are published to [PyPI](https://pypi.org/project/pychurchsuite/) automatically when you push a version tag like `v1.3.0`. This runs GitHub Actions [release workflow](.github/workflows/release.yml). It builds the package, checks it, and uploads it. PyPI trusts the workflow through [Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so there are no API tokens to create or store.

## Very first release to PyPI

1. Create an account on [PyPI](https://pypi.org/account/register/), with two-factor authentication.
2. On PyPI, go to *Your account -> Publishing*, and add a "pending publisher" for GitHub with:
   - PyPI project name: `pychurchsuite`
   - Owner: `berwynhoyt`
   - Repository name: `pychurchsuite`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

   The first release then creates the project on PyPI. If you rename the GitHub repository, update these settings to match.
3. On GitHub, go to the repository's *Settings -> Environments*, and create an environment called `pypi`.
   Optionally, add yourself as a required reviewer. Each release then waits for your approval before uploading.

## Each release

1. Update `__version__` in `churchsuite/__init__.py`.
   PyPI never accepts the same version number twice, even if you delete a release.
2. In `CHANGELOG.md`, remove "(unreleased)" from the version heading.
3. Commit these changes on `main`.
4. Run the release script. It checks that everything is ready, then offers to create the version tag:

   ```sh
   python release.py
   ```

   It checks for uncommitted changes, the `main` branch, an unused tag and version, and the changelog heading.
   It also test-builds the package, which needs [uv](https://docs.astral.sh/uv/).
5. Push the commit and the tag, e.g. for version 1.3.0:

   ```sh
   git push origin main v1.3.0
   ```

6. Watch the release run in the repository's *Actions* tab, and approve it if you added a reviewer.
7. Check that the new version installs from PyPI:

   ```sh
   uv tool install --force --refresh pychurchsuite
   docexport --version
   ```

8. Optionally, create a GitHub release from the tag, and paste in its `CHANGELOG.md` section.

If the workflow fails before uploading, nothing reaches PyPI. Fix the problem, then delete and recreate the tag:

```sh
git tag -d v1.3.0 && git push origin :refs/tags/v1.3.0
```

Deploying the DocExport web app to Google Cloud is a separate step, described in [README-python-hosted.md](README-python-hosted.md).
