""" Print a ChurchSuite access token for experimenting, e.g. with curl. Run with: churchsuite, or python -m churchsuite """

import sys

import churchsuite

COMMANDS = """\
Other commands in the pychurchsuite package:
  docexport                  Export upcoming service plans from ChurchSuite into docx files
  docexport-web              Run the DocExport web app on localhost:8080
  attenders                  Select regular or irregular attenders, optionally adding them to a tag or flow
  python -m churchsuite.web  Run a localhost server to test login
Run docexport or attenders with -h for their options."""

def main():
    if '-h' in sys.argv[1:] or '--help' in sys.argv[1:]:
        print(COMMANDS)
        return
    print("Run churchsuite -h for a list of other commands\n")
    try:
        cs = churchsuite.Churchsuite(auth=churchsuite.user_auth())
    except churchsuite.ChurchError as e:
        sys.exit(f"Error: {e}")
    print(f"Here is your churchsuite access token to use with curl for testing:\n{cs.access_token}\n")
    print("Run python -m churchsuite.web to run as a localhost server and test login")


if __name__ == "__main__":
    main()
