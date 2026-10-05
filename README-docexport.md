## DocExport Tool

This is a tool that exports church service plans as beautiful, clean, `docx` files. Compare this [docx sample](https://github.com/berwynhoyt/pychurchsuite/raw/refs/heads/main/examples/2026-04-05_9am_Morning_Service_(draft).docx) with ChurchSuite's [original pdf](https://github.com/berwynhoyt/pychurchsuite/raw/refs/heads/main/examples/2026-04-05_9am_Morning_Service.pdf) of the same service.

You can [try it yourself here](https://serviceplans.ts.r.appspot.com/) if your church uses ChurchSuite.

At that same link you can even create a hyperlink directly to your own church's service plans, and bookmark it or add it as a menu item in My ChurchSuite (to set it up go to `ChurchSuite->Menu->Settings->Profile->My ChurchSuite->Add external link`). You can only set up such links in My Churchsuite, as ChurchSuite itself does not yet let you add custom links.

### Features

The exported docx service plans features:

* Service leaders can more easily highlight or add their own notes than they could with the pdf.
* A clearer format for service leaders to find their place on the page.
* It automatically highlights in red any 'responsive readings' that comes after "all:", "everyone:", "together:", or "people:"
* It stops red text when it gets to a double-new-line or when it gets to a "Leader:" line.
* It emboldens "Leader:", "Minister, or "Reader:"
* "Song", "Hymn" and "Psalm" headings are displayed in green along with the song title.
* Level-2 section headings are omitted if the heading is not followed by text contents, omitting empty sections.

## Automating DocExport

If you want to automate DocExport, for example exporting these files daily, you can run it as a Python command-line program. First [install uv](https://docs.astral.sh/uv/getting-started/installation/), then install DocExport with it:

```sh
$ uv tool install pychurchsuite
```

Then give it [your ChurchSuite API keys](https://developer.churchsuite.com/auth). Set environment variables `CHURCHSUITE_CLIENT_ID` and `CHURCHSUITE_CLIENT_SECRET`. Or put them in a `config.py` file. On Linux and macOS, that file goes in `~/.config/churchsuite/`. On Windows, it goes in `%APPDATA%\churchsuite\`:

```python
USER_CLIENT_ID = "your-client-id"
USER_CLIENT_SECRET = "your-client-secret"
```

Now run it:

```sh
$ docexport --fontsize 16
Creating 2026-05-03 9am Morning Service.docx
Creating 2026-05-03 5pm Service.docx
```

