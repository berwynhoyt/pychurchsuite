# PyChurchSuite and Tools

In addition to the Python library, this site contains user tools for ChurchSuite:

1. [DocExport Tool](https://github.com/berwynhoyt/pychurchsuite/blob/main/README-docexport.md) – create beautiful church service plans as a Word document.
2. [PyChurchSuite (below)](#pychurchsuite-python-library) – Python library for simple ChurchSuite scripting (used to create DocExport Tool).

## PyChurchSuite Python Library

The `churchsuite` Python package makes it easy to create Python apps and scripts for the ChurchSuite API v2. Not only does it provide a class that supports queries to ChurchSuite, it also automates Churchsuite login, and capture of the user's `client_id`. This is the same module used for the [DocExport app](https://github.com/berwynhoyt/pychurchsuite/blob/main/README-docexport.md). It requires Python >= 3.12 for backslashes in f-strings.

## Quick Examples

To print all the people in your database:

```python
import churchsuite

cs = churchsuite.Churchsuite(auth=churchsuite.user_auth())
people = cs.get('addressbook/contacts', per_page=100, status='active')
for p in people:
	print(f"{p.first_name} {p.last_name}: {p.email}")
```

To make a web app that does the same in a browser:

```python
import os
import secrets
from flask import Flask
from churchsuite.web import ChurchsuiteApp

app = Flask(__name__)
app.config['SESSION_COOKIE_SECURE'] = True  # require secure https (set to False only for localhost debugging below)
app.config['SECRET_KEY'] = secrets.token_hex()  # see churchsuite/config_defaults.py for an explanation

cs = ChurchsuiteApp(app)

@app.route('/')
def home():
    return """Click <a href="/people">here</a> to see everyone."""

@app.route('/people')
@cs.login_required
def people():
    people = cs.get('addressbook/contacts', per_page=100, status='active')
    return '<br>'.join(f"{p.first_name} {p.last_name}: {p.email}" for p in people)

if __name__ == "__main__":
    app.config['SESSION_COOKIE_SECURE'] = False # https not required for localhost debugging
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # allow debug using insecure http://localhost
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
```

This app is in [`example-app/main.py`](https://github.com/berwynhoyt/pychurchsuite/blob/main/example-app/main.py), ready to copy and deploy. You can test it on your local computer by simply running `python main.py` and browsing to `localhost:8080`. However, first you will have to set up a new app on ChurchSuite to point the "Redirect URI" to `localhost:8080/login/callback`.

See [`docexport_web.py`](https://github.com/berwynhoyt/pychurchsuite/blob/main/churchsuite/tools/docexport_web.py) for a web app that is more realistic, but still short.

## Installation

Install [Python](https://www.python.org/downloads/) >= 3.12, then install this package into your project's virtual environment:

```bash
# Set up a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

pip install pychurchsuite
```

Now you're ready to create your own Python script or web app.

A **local Python** script can authenticate without a web app using `churchsuite.user_auth()`. It needs [your ChurchSuite API keys](https://developer.churchsuite.com/auth). Set environment variables `CHURCHSUITE_CLIENT_ID` and `CHURCHSUITE_CLIENT_SECRET`. Or put them in `config.py` in the current directory:

```python
USER_CLIENT_ID = "your-client-id"
USER_CLIENT_SECRET = "your-client-secret"
```

To check that your keys work, run `churchsuite` to print an access token. To test web login on `localhost:8080`, run `python -m churchsuite.web`.

## Developing this package

To change the package itself, clone it and install it into a virtual environment in editable mode. Then your edits take effect immediately. With [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/berwynhoyt/pychurchsuite.git
cd pychurchsuite
uv sync                      # create .venv/ and install this package and its dependencies
source .venv/bin/activate
```

Without uv, replace `uv sync` with `python -m venv .venv`, activate it as above, then run: `pip install -e .`

Now the tool commands should work, as well as running a tool file directly with `python`:

```bash
docexport --version                       # run a command
python churchsuite/tools/docexport.py -h  # run a tool file directly
python -m churchsuite.web                 # run the login test server
docexport-web                             # run the DocExport web app on localhost:8080
```

Activate `.venv/` in each new terminal (though many code editors do this automatically). If the dependencies in `pyproject.toml` change, run `uv sync` again.

Without this setup, `python churchsuite/tools/docexport.py` fails with `No module named 'churchsuite'`. That is because Python searches `sys.path` for imports, not the file's parent directory.

To release a new version to PyPI, see [RELEASING.md](https://github.com/berwynhoyt/pychurchsuite/blob/main/RELEASING.md).

## OAuth Authorization

In the context of a Flask web app, the Python module also implements all the pages needed to for the app to login to ChurchSuite using OAuth. This can be done by simply applying the decorator `@cs.login_required` to any route handler function (after the @app.route decorator), as shown in the app example above. Any route that requires access to ChurchSuite data may have this decorator and the user will first be required to login if necessary. The login will fetch an `access_token` from ChurchSuite and store it in the web session which the ChurchsuiteApp instance will subsequently use for every access to ChurchSuite data.

The Python module also automates capture of `client_id` from the user. Ordinarily the user would have to supply a `client_id` so that ChurchSuite knows which customer to login for church database access. The `client_id` can then be preserved in a browser cookie for future use. Alternatively, a `client_id` may be supplied in a URL parameter. All this is automated by the Python module. The user is asked for their `client_id` and given instructions on how to obtain it. Their `client_id` is preserved in a browser cookie for 400 days (the maximum allowed), and the user is also given a URL that includes the `client_id` to use in future, if they prefer. This client-specific URL may be given ChurchSuite users by the church administrator so that the user never has to worry about a `client_id`.

## Running your own ChurchSuite app in the cloud using Google Services

[Instructions here](https://github.com/berwynhoyt/pychurchsuite/blob/main/README-python-hosted.md) show how to let Google Cloud host your ChurchSuite web app for free (you don't need your own physical server). It can either run your ChurchSuite app as a service or you can make it run your Python script periodically to automate periodic ChurchSuite tasks.

