# manapak

`manapak` is a desktop application for checking and applying Flatpak updates through the Flatpak Python API (`gi.repository.Flatpak`).

## Features

- list installed Flatpak applications
- check which installed apps and runtimes have updates available
- update selected apps with `Flatpak.Transaction`
- operate in the background without blocking the main UI thread
- show Flatpak errors through dialogs if any

When checking for updates, `manapak` refreshes remote metadata in the background
before querying updates. This can add a short delay but avoids stale results.

## Security and privilege model

`manapak` relies on the Flatpak Python bindings and the Flatpak daemon. For user installs, no extra privileges are usually needed.

For system installs, Flatpak authorization is typically handled by the operating system's PolicyKit/Polkit mechanism. `manapak` does not call `pkexec` or other shell-based escalators directly. When `Flatpak` raises a permission-related `GLib.Error`, the app converts it into a user-facing message and asks the user to authenticate when the system requests it.

This keeps the application safe and backend-agnostic while still allowing system-wide updates when the user grants the required authorization.

## Artwork license

The manapak icon is original project artwork released under
[CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/). It is not the
Flatpak logo and does not imply endorsement by the Flatpak project. Details are
recorded in [NOTICE](NOTICE).

## Requirements

Runtime requirements:

- Python 3.9 or newer
- `python-manatools` >= 0.99.4 with a GTK, Qt or ncurses backend
- PyGObject
- Flatpak GObject Introspection typelib (`gir1.2-flatpak-1.0` or the distribution equivalent)

Development requirements:

- Poetry / `poetry-core`
- pytest
- gettext tools (`xgettext`, `msgfmt`, `msginit`, `msgmerge`)
- `rsvg-convert` to regenerate PNG application icons

## Install

```bash
poetry install
```

The package installs the `manapak` command, desktop entry and hicolor icons.

## Run

```bash
python -m manapak --help
```

or, from the project root:

```bash
PYTHONPATH=. python -m manapak
```

Enable logs:

```bash
python -m manapak --logging
python -m manapak --log-file /tmp/manapak.log --debug
```

Select a UI backend:

```bash
python -m manapak --gtk
python -m manapak --qt
python -m manapak --ncurses
```

## About and Help

The bottom action row provides Help and About dialogs. Application metadata, the SVG
logo and project links are registered with the active `manatools.aui` backend.

## Translations

Translation sources live in `po/`. Compile them locally with:

```bash
python tools/po_build.py
python -m manapak --locales-dir "$PWD/share/locale"
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for catalog extraction/update commands and the
full development workflow.
