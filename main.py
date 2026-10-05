""" Default entrypoint for Cloud Run, which runs `gunicorn -b :8080 main:app` unless a Procfile overrides it """

from churchsuite.tools.docexport_web import app
