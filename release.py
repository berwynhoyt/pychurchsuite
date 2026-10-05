#!/usr/bin/env python3
""" Check that the repository is ready to release, then create the version tag.
    Pushing the tag makes GitHub Actions publish the release to PyPI. See RELEASING.md.
"""

import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

def git(*args):
    """ Run a git command and return its output """
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()

def fail(message):
    sys.exit(f"Not ready to release: {message}")

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # run from the repository root
    with open('churchsuite/__init__.py') as f:
        version = re.search(r"^__version__ = '([^']+)'", f.read(), re.MULTILINE).group(1)
    tag = f'v{version}'
    print(f"Checking release {tag}")

    if git('status', '--porcelain'):
        fail("commit or stash your changes first.")
    if git('branch', '--show-current') != 'main':
        fail("check out the main branch first.")
    try:
        git('fetch', '--quiet', 'origin', 'main')
    except subprocess.CalledProcessError as e:
        fail(f"could not fetch origin main: {e.stderr.strip()}")
    ahead, behind = git('rev-list', '--left-right', '--count', 'HEAD...origin/main').split()
    if ahead != '0' and behind != '0':
        fail(f"main and origin/main have diverged ({ahead} ahead, {behind} behind). Reconcile them first.")
    if behind != '0':
        fail(f"main is {behind} commit(s) behind origin/main. Pull them first.")
    if ahead != '0':
        fail(f"main is {ahead} commit(s) ahead of origin/main. Push them first.")
    if git('tag', '--list', tag):
        fail(f"tag {tag} already exists. Update __version__ in churchsuite/__init__.py.")
    with open('CHANGELOG.md') as f:
        if not re.search(rf'^#* *{re.escape(tag)}:', f.read(), re.MULTILINE):
            fail(f"CHANGELOG.md needs a '{tag}:' heading, without '(unreleased)'.")
    try:
        urllib.request.urlopen(f'https://pypi.org/pypi/pychurchsuite/{version}/json')
        fail(f"version {version} is already on PyPI.")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    # Build into a temporary directory, just to catch build errors before tagging
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['uv', 'build', '--quiet', '--out-dir', tmp], check=True)

    if input(f"All checks passed. Create tag {tag}? [y/N] ").lower() != 'y':
        sys.exit("No tag created.")
    print("Enter optional release message suffix below.")
    message = input(f"  Release {tag}: ").strip()
    tag_message = f"Release {tag}{': '+message if message else ''}"
    git('tag', '--annotate', tag, '--message', tag_message)
    print(f"Created tag {tag}. To publish it, run: git push origin {tag}")


if __name__ == "__main__":
    main()
