#!/bin/sh

set -e

usage() {
    cat <<EOF
Use: $0 [-d <destdir>] [<language>]

  -d <destdir>   Output base directory for .mo files.
                 .mo files are written to:
                   <destdir>/<lang>/LC_MESSAGES/manapak.mo
                 Default: share/locale/ relative to the project root.

  <language>     Compile only this language (e.g. it, fr, pt_BR).
                 Default: compile all languages found in po/.
EOF
}

DESTDIR=""
LANGUAGE=""

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -d|--destdir)
            if [ -z "$2" ]; then
                echo "$0: error: -d requires a non-empty argument" >&2
                exit 1
            fi
            DESTDIR="$2"
            shift 2
            ;;
        -d=*|--destdir=*)
            DESTDIR="${1#*=}"
            if [ -z "$DESTDIR" ]; then
                echo "$0: error: -d= requires a non-empty value" >&2
                exit 1
            fi
            shift
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "$0: error: unknown option '$1'" >&2
            echo "Run '$0 --help' for usage." >&2
            exit 1
            ;;
        *)
            if [ -n "$LANGUAGE" ]; then
                echo "$0: error: unexpected extra argument '$1'" >&2
                echo "Run '$0 --help' for usage." >&2
                exit 1
            fi
            LANGUAGE="$1"
            shift
            ;;
    esac
done

if [ -n "$DESTDIR" ]; then
    case "$DESTDIR" in
        -*)
            echo "$0: error: destdir must not start with '-': $DESTDIR" >&2
            exit 1
            ;;
    esac
    _clean=$(printf '%s' "$DESTDIR" | tr -d ' \t')
    if [ -z "$_clean" ]; then
        echo "$0: error: destdir must not be empty or whitespace" >&2
        exit 1
    fi
fi

if [ -n "$LANGUAGE" ]; then
    case "$LANGUAGE" in
        *[!a-zA-Z0-9_@.-]*)
            echo "$0: error: invalid language identifier '$LANGUAGE'" >&2
            exit 1
            ;;
    esac
fi

cd "$(readlink -f "$(dirname "$0")/..")"

if [ -z "$DESTDIR" ]; then
    DESTDIR="$PWD/share/locale"
fi

update_mo() {
    _po="$1"
    _lang="$(basename "$_po")"
    _lang="${_lang%.po}"
    _target="$DESTDIR/$_lang/LC_MESSAGES/manapak.mo"
    printf 'compiling %s -> %s\n' "$_po" "$_target"
    /bin/mkdir --parents "$(dirname "$_target")"
    /usr/bin/msgfmt --check --output-file="$_target" "$_po"
}

if [ -n "$LANGUAGE" ]; then
    find "$PWD/po" -type f -name "${LANGUAGE}.po" | while IFS= read -r l; do
        update_mo "$l"
    done
else
    find "$PWD/po" -type f -name '*.po' | while IFS= read -r l; do
        update_mo "$l"
    done
fi
