""" Library to access ChurchSuite data conveniently """

import os
import json
import logging
import pprint
import runpy
import time

from types import SimpleNamespace

import requests


__version__ = '1.3.1'  # Version of the whole package, including tools. NOTE: remember to update CHANGELOG.md

class ChurchError(Exception): pass

api = 'https://api.churchsuite.com/v2'

def __getattr__(name):
    """ Backward compatibility shim: lets user import ChurchsuiteApp from either `churchsuite` or the newer preferred `churchsuite.web` """
    if name in ('ChurchsuiteApp', 'templates'):
        # Import Flask parts only when requested, so scripts need not spend time loading Flask.
        from . import web
        return getattr(web, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def user_config_dir():
    """ Return the per-user churchsuite config directory for this operating system.
        On Windows it is %APPDATA%\\churchsuite.
        Elsewhere it is $XDG_CONFIG_HOME/churchsuite (default ~/.config/churchsuite).
    """
    if os.name == 'nt':
        config_home = os.environ.get('APPDATA') or os.path.expanduser('~/AppData/Roaming')
    else:
        config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    return os.path.join(config_home, 'churchsuite')

def user_auth():
    """ Return (client_id, client_secret) of an API-enabled user, for command-line scripts.
        Use environment variables CHURCHSUITE_CLIENT_ID and CHURCHSUITE_CLIENT_SECRET if both are set.
        Otherwise read USER_CLIENT_ID and USER_CLIENT_SECRET from the first config.py that has them.
        Search the current directory, then the user config directory given by user_config_dir().
    """
    client_id = os.environ.get('CHURCHSUITE_CLIENT_ID')
    client_secret = os.environ.get('CHURCHSUITE_CLIENT_SECRET')
    if client_id and client_secret:
        return client_id, client_secret
    user_config = os.path.join(user_config_dir(), 'config.py')
    for path in ('config.py', user_config):
        if os.path.exists(path):
            config = runpy.run_path(path)
            if config.get('USER_CLIENT_ID') and config.get('USER_CLIENT_SECRET'):
                return config['USER_CLIENT_ID'], config['USER_CLIENT_SECRET']
    raise ChurchError("No ChurchSuite API user credentials found. Set environment variables CHURCHSUITE_CLIENT_ID and "
                      f"CHURCHSUITE_CLIENT_SECRET, or set USER_CLIENT_ID and USER_CLIENT_SECRET in config.py or {user_config}")

def dump_request(req):
    """ Debugging function to dump a PreparedRequest from request.Request().prepare() or response.request """
    output = f"{req.method} {req.path_url} HTTP/1.1\n"
    output += '\n'.join(f'{k}: {v}' for k, v in req.headers.items())
    output += "\n\n"
    if req.body is not None:
        # Decode body if it is in bytes, handling potential encoding issues
        output += req.body.decode('utf-8') if isinstance(req.body, bytes) else req.body
    return output

def joiner(*args):
    """ Join multiple args to the end of a url, separating them with '/' """
    return '/'.join(str(arg) for arg in args if arg is not None)

def raise_for_status(r):
    """ Like r.raise_for_status() but append the response body to the error, since it usually explains 4xx errors """
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if r.text:
            e.args = (f"{e} -- {r.text[:1000]}",)
        raise

def trace_logging():
    """ Detect whether trace-level logging is enabled with a log_level even more verbose than DEBUG (-vvv) """
    return logging.getLogger(__name__).getEffectiveLevel() < logging.DEBUG

class GoogleSecretManager:
    def __init__(self, project_id):
        self.project_id = project_id

    def get(self, secret_id, version_id="latest"):
        """ Access the value of given secret_id from Google Secret Manager; version_id can be "latest" or a specific number """
        # Additional requirement if this function is used: pip install google-cloud-secret-manager
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")


class Churchsuite:
    """ Class used to access ChurchSuite data """

    token_url = "https://login.churchsuite.com/oauth2/token"
    auth_url = "https://login.churchsuite.com/oauth2/authorize"
    scope = 'full_access'
    timeout = 30  # seconds to wait for the server to respond before giving up

    def __init__(self, auth=None, *, raw=None, scope=('full_access',), lazy_auth=False):
        """ Create ChurchSuite instance for access to ChurchSuite data.
            Attempt to authorize using user auth (client_id, client_secret).
            If the authorization expires later, re-authorize using the same auth.
            If filename raw is supplied, store all json text received from the server into that file.
            scope: is a list of scopes (default 'full_access') selected from: https://developer.churchsuite.com/auth#scopes
            lazy_auth: if True, delays authorization until it is first required
        """
        if not auth:
            raise ChurchError("You need to supply (client_id, client_secret) to Churchsuite class")
        self.auth = auth
        self.raw = raw
        if raw is not None:
            # truncate file
            open(raw, 'w').close()
        if not isinstance(scope, (list, tuple)):
            raise Exception("Scope specified to Churchsuite must be a list or tuple")
        self.scope = scope
        self._access_token = None
        if not lazy_auth:
            self.authorize()

    @property
    def access_token(self):
        if not self._access_token or time.time() >= self._token_expiry:
            self.authorize()
        return self._access_token

    def append_raw(self, text):
        if self.raw is not None:
            with open(self.raw, 'a') as f:
                f.write(text)

    def authorize(self):
        """ Return access_token using api_enbaled_user authorization with the authorization credentials self.auth """
        data = {'grant_type': 'client_credentials', 'scope': ' '.join(self.scope)}
        r = requests.post(self.token_url, auth=self.auth, json=data, headers={'Content-Type': 'application/json'}, timeout=self.timeout)
        raise_for_status(r)
        self._token_expiry = time.time() + float(r.json().get('expires_in')) - 60
        self._access_token = r.json().get('access_token')

    def _update_urlparams(self, params=None, **kwargs):
        """ Return a copy of params dict (default={}) but updated with kwargs, appending '[]' to the names of keys whose values are lists/tuple """
        if params is None:
            params = {}
        params = params.copy() # make sure not to clobber the input dict
        for k, v in kwargs.items():
            if isinstance(v, (list, tuple)):
                k = k + '[]'
                v = list(v)
            params[k] = v
        return params

    def request(self, url, id=None, item=None, *, urlparams=None, reqparams=None, request=requests.get):
        """ Performs a basic request like GET, fetching at most one page of a list result (not all pages like self.get does)
            and instead of return data, returns an object that contains data and may contain a pagination field.
            url: the network address to talk to
            id: if supplied, is prefixed with '/' and appended as a string to the url.
            item: if supplied, is prefixed with '/' and appended as a string to the url (after any /id)
            urlparams: are converted to url parameters: usual for GET, DELETE.
            reqparams: are converted to json data sent in the request body: usual for POST, PUT, PATCH.
            request: specifies the type of request: requests.get, requests.post, etc. to match http type GET, POST, etc.
        """
        url = joiner(url, id, item)
        if not url.startswith(api):
            url = joiner(api, url)
        r = request(url, headers={'Authorization': f'Bearer {self.access_token}'}, params=urlparams, json=reqparams, timeout=self.timeout)
        if trace_logging():
            logging.debug(f"request: {dump_request(r.request).replace('\n', '\n|  ')}")
        raise_for_status(r)
        if not r.content:
            return SimpleNamespace(data=None)  # e.g. DELETE returns 204 No Content so make it look like no data=None
        self.append_raw(json.dumps(r.json(), indent=4) + '\n')
        # Convert json dict to SimpleNamespace (recursively for sub-objects)
        object = json.loads(r.text, object_hook=lambda d: SimpleNamespace(**d))
        def formatted_response():
            return f"{r.request.method} {url} =>\n| {pprint.pformat(object).replace('\n', '\n| ')}"
        if trace_logging():
            logging.debug(formatted_response())
        if not hasattr(object, 'data'):
            raise Exception(f"No 'data' field found in response to {formatted_response()}")
        return object

    def get(self, url, id=None, item=None, *, params=None, **kwargs):
        """ Return 'data' field from ChurchSuite GET response as a SimpleNamespace, or list of SimpleNamespaces if the request returns a list.
            If the result is a list and 'page' is not specified in params or kwargs, then repeatedly fetch all pages and return as a single list.
            If id or item are supplied, they are prefixed with '/' and appended as strings to the url.
            If params dict is supplied, it is sent, merged with kwargs, as url params to the url.
        """
        params = self._update_urlparams(params, **kwargs)
        params['per_page'] = params.get('per_page', 250)  # if per_page not specified, set it to ChurchSuite maximum
        r = self.request(url, id, item, urlparams=params)
        if not isinstance(r.data, list) or 'page' in params:
            return r.data
        page = 2
        data = r.data
        while r.pagination.next_page:
            params = self._update_urlparams(params, page=page)
            r = self.request(url, id, item, urlparams=params)
            data += r.data
            page += 1
        return data

    def delete(self, url, id=None, item=None, *, params=None, **kwargs):
        """ Return 'data' field from ChurchSuite DELETE request as a SimpleNamespace, or list of SimpleNamespaces if the request returns a list.
            If id or item are supplied, they are prefixed with '/' and appended as strings to the url.
            If params dict is supplied, it is sent, merged with kwargs, as url params to the url.
        """
        params = self._update_urlparams(params, **kwargs)
        r = self.request(url, id, item, urlparams=params, request=requests.delete)
        return r.data

    def post(self, url, *, params=None, **kwargs):
        """ Return 'data' field from ChurchSuite POST request as a SimpleNamespace, or list of SimpleNamespaces if the request returns a list.
            If params dict is supplied, it is sent, merged with kwargs, as request body json params to the url.
        """
        params = params.copy() if params else {}
        params.update(kwargs)
        r = self.request(url, reqparams=params, request=requests.post)
        return r.data

    def put(self, url, *, params=None, **kwargs):
        """ Return 'data' field from ChurchSuite PUT request as a SimpleNamespace, or list of SimpleNamespaces if the request returns a list.
            If params dict is supplied, it is sent, merged with kwargs, as request body json params to the url.
        """
        params = params.copy() if params else {}
        params.update(kwargs)
        r = self.request(url, reqparams=params, request=requests.put)
        return r.data

    def id_by_name(self, items, name, case_sensitive=False):
        """ Search through items (list of SimpleNamespaces) for an item that has attribute name matching name and return its id attribute or None if it doesn't exist.
            Used, for example, by get_tag_id() to find tags by name
            If case_sensitive=False (default) then a case-matching tag id will be returned first, if it exists,
                otherwise a case-insensitive match will be returned if one exists.
            Only returns the id exact (possibly case-insensitive) matches, avoiding near matches captured by ChurchSuite's fuzzy search.
        """
        if not items:
            return None
        for item in items:  # First look for case-sensitive matches
            if item.name == name:
                return item.id
        if not case_sensitive:  # Next scan for case-insensitive matches
            for item in items:
                if item.name.lower() == name.lower():
                    return item.id
        return None

    def get_by_name(self, url, name, case_sensitive=False):
        """ Search for ChurchSuite list item by name at url and return its id or None if it doesn't exist.
            Used, for example, by get_tag_id() to find tags by name:
                `get_by_name('addressbook/tags', tag_name)`
            If case_sensitive=False (default) then a case-matching tag id will be returned if it exists,
                otherwise a case-insensitive match will be returned if one exists.
            Only returns id of exact (possibly case-insensitive) matches, avoiding near matches from ChurchSuite's fuzzy search.
        """
        params = self._update_urlparams({}, q=name)
        items = self.get(url, params=params)
        return self.id_by_name(items, name, case_sensitive=case_sensitive)

    def get_tag_id(self, tag_name, module='addressbook', case_sensitive=False):
        """ Return tag_id or None if the tag does not exist. """
        return self.get_by_name(f'{module}/tags', tag_name, case_sensitive=case_sensitive)

    def get_flow_id(self, flow_name, module='addressbook', case_sensitive=False):
        """ Return active flow_id or None if the flow does not exist. """
        return self.get_by_name(f'{module}/flows', flow_name, case_sensitive=case_sensitive)

    def get_stages(self, flow_id, module='addressbook'):
        """ Get a list of stages in specified flow """
        return self.get(f'{module}/flow_stages', flow_ids=[flow_id])

    def get_stage_id(self, stage_name, flow_id, module='addressbook', case_sensitive=False):
        """ Given flow_id, return the stage_id matching the flow's stage_name or None if the stage does not exist. """
        stages = self.get_stages(flow_id, module=module)
        return self.id_by_name(stages, stage_name, case_sensitive=case_sensitive)

# Test function to help a developer see the OAuth PKCE process flow in linear fashion
def test_manual_oauth(client_id, redirect_url=None):
    """ Fetch access access_token using oauth_app authorization with the supplied authorization credentials.
        This is a test function to simulate what occurs with authorize_app_stage{1,2}()
    """
    from requests_oauthlib import OAuth2Session
    oauth = OAuth2Session(client_id, redirect_uri=redirect_url, scope=('full_access',), pkce='S256')
    authorization_url, state = oauth.authorization_url(Churchsuite.auth_url)
    code_verifier = oauth._code_verifier  # fetch from private field as requests-oauthlib does not yet support a public access method
    # In a web app, you would save state for later: session['oauth_state'] = state
    # Simulate callback into Python here by making the user paste in the URL that came back to the browser from to the redirect_url
    print(f"Please authorize at:")
    print(f"    {authorization_url}")
    print()
    print(f"Note: after login, the browser may say the site can't be reached (because you're not running a web server).")
    print(f"But the URL shown in the address bar will still be suitable for pasting here.")
    authorization_response_url = input('Enter the full callback URL (shown in the browser address bar): ')
    # Check that request.args.get('state') != session.pop('oauth_state'); otherwise bomb out with error 400
    # code_verifier = session.pop('code_verifier')
    oauth = OAuth2Session(client_id, redirect_uri=redirect_url)
    oauth._code_verifier = code_verifier  # store into a private field as requests-oauthlib does not yet support a public access method
    json = oauth.fetch_token(Churchsuite.token_url, authorization_response=authorization_response_url, code_verifier=code_verifier)
    return json.get('access_token')
