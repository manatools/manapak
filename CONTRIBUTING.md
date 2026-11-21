# Contributing to manapak

## Development requirements

Install:

- Python 3.9 or newer
- Poetry with `poetry-core`
- `python-manatools`
- PyGObject and the Flatpak typelib (`gir1.2-flatpak-1.0` on Debian-like systems)
- GTK, Qt or ncurses support from `python-manatools`
- `gettext` (`xgettext` and `msgfmt`) for translation updates
- `rsvg-convert` when regenerating hicolor PNG icons

## Local setup

```bash
poetry install
python -m manapak --help
python -m manapak --gtk
```

The UI backend can be selected with `--gtk`, `--qt` or `--ncurses`.

## Tests

Run all tests from the repository root:

```bash
pytest -q
```

Also validate syntax and the package contents:

```bash
python -m compileall -q manapak tests
python -c 'from poetry.core.masonry.api import build_wheel, build_sdist; build_wheel("dist"); build_sdist("dist")'
```

## Translations

Regenerate `po/manapak.pot` from the Python sources and the desktop entry, then
merge it into every language catalog:

```bash
tools/po-update.sh
```

Pass a language code to merge only that catalog:

```bash
tools/po-update.sh it
```

Create a catalog for a new language from the template:

```bash
msginit --locale=it --input=po/manapak.pot --output-file=po/it.po
```

Compile locally and launch using the local catalog:

```bash
python tools/po_build.py
python -m manapak --locales-dir "$PWD/share/locale"
```

Compiled `.mo` files are generated release/build artifacts and must not be committed.

## Icons

Regenerate hicolor PNG icons from the packaged SVG:

```bash
for size in 16 24 32 48 64 128 256; do
  rsvg-convert -w "$size" -h "$size" \
    manapak/resources/manapak.svg \
    -o "share/icons/hicolor/${size}x${size}/apps/manapak.png"
done
cp manapak/resources/manapak.svg share/icons/hicolor/scalable/apps/manapak.svg
```

## Code style

- Keep Flatpak access inside `manapak/flatpak_api.py`.
- Never invoke the Flatpak CLI or parse command output.
- Never touch AUI widgets from background threads; communicate through the UI queue.
- Keep changes focused and add tests for new behavior.
