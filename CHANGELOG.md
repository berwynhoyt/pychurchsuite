# Changelog

## v1.3.1:

Attenders:

- Web apps and scripts can now import attenders and run it directly, without running the command.
  For example: `attenders.run(attenders.parse_args(['--attendance', '4/8']), out=stream)`.

## v1.3.0:

All the tools now install together as one Python package, with one shared version number.

- Install the commands with `uv tool install pychurchsuite`, or the library with `pip install pychurchsuite`.
- New commands get installed: `churchsuite`, `docexport`, `docexport-web` and `attenders`.
- API keys for commands and scripts may now come from environment variables or a user config file.

Churchsuite library:

- Flask support moves to `churchsuite.web`: use `from churchsuite.web import ChurchsuiteApp`.
  The old form still works `from churchsuite import ChurchsuiteApp`.
- `import churchsuite` no longer loads Flask, so scripts start faster.
- New `churchsuite.user_auth()` finds API user credentials for scripts.
  It reads `CHURCHSUITE_CLIENT_ID` and `CHURCHSUITE_CLIENT_SECRET` from the environment.
  Otherwise it reads `config.py` from the current directory, then from the user config directory.
- New `churchsuite` command, or `python -m churchsuite`, prints an access token for experimenting, e.g. with curl.
- Test the login server with `python -m churchsuite.web`, instead of `churchsuite.py --app`.

Attenders:

- `people.py` is renamed `attenders`, and now runs as the `attenders` command.

DocExport:

- `docexport_app.py` is renamed `docexport_web.py` to match its new `docexport-web` command.
- Run the web app locally with the `docexport-web` command.

Earlier releases gave each tool its own version number, as listed below.

## Earlier churchsuite.py releases

### v1.2.0:

- New Churchsuite.put() and delete() methods.
- New get_by_name(), get_tag_id(), get_flow_id(), get_stages() and get_stage_id() methods look up ids by name.
- Name lookups are case-insensitive unless case_sensitive=True is given.
- Tag, flow and stage lookups take a module parameter (default 'addressbook').
- Churchsuite.get1() is renamed request(), and can now make any type of request.
- Running churchsuite.py directly prints an access token for testing. Use --app to test the login server.

Bugfixes:

- Logging in no longer gives a server error when the login session has expired.
- Requests no longer hang forever if ChurchSuite stops responding.
- API errors now include ChurchSuite's own explanation of what went wrong.
- Trace logs now show the correct HTTP method, not always GET.
- Login bookmark links now work when the page URL has several query parameters.
- The client ID in bookmark links is no longer encoded twice.
- Custom login CSS given to one app no longer affects other apps.
- The login page heading now has correctly nested HTML.

### v1.1.0:

- Churchsuite.post() method is now supported
- Churchsuite.get() method now automatically captures all pages of returned results using repeated requests unless page=n is explicity specified.
- Churchsuite.get() and post() methods now allow just the endpoint to be specified and will automatically prepend the churchsuite API url 'https://api.churchsuite.com/v2' with joining slash if necessary.
- Lists and tuples passed as parameters to get() are now automatically and transparently encoded as multiple-url parameters with the parameter name correctly suffixed with '[]'.
- Updated tools to specify the specific scopes they require (now that ChurchSuite supports this) rather than 'full_access'.

Bugfixes:

- Now correctly handles multiple scopes being specified (previously failed because it joined them with commas instead of spaces).
- Updated contacts.py to work with the new standard of client secrets being stored in config.py

### v1.0.0: First public release

## Earlier DocExport releases (docexport.py and docexport_app.py)

### v1.2.1: Bugfixes:

- `--pagesize letter` and `--starts-from YYYY-MM-DD` no longer crash.
- The web app no longer gives a server error for `?max_age_days=30`.
- Plan names with times like `10:30am` no longer crash sorting.
- "Afternoon" and "evening" plans now sort after morning plans on the same day.
- `12pm` plans now sort at noon, and `12am` plans at midnight.
- The web app heading now has correctly nested HTML.

### v1.2.0: Sort 'draft' and 'published' plans properly, and sort by the hour within the day.

### v1.1.0: Release that supports churchsuite.py v1.1.0 updates, which allows it to work when there are more than 50 service plans.

### v1.0.0: First public release

## Earlier people.py releases (now attenders)

### v1.0.0: First public release:

* Allows adding people to tags and flows.
* Allow those people to be selected based on their attendance frequency and/or their tag/flow membership.
