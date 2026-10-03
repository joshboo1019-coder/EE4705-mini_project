#!/usr/bin/env bash
# Change contributed by Student B (assist), pending review by the group
#
# tools/make_submission_zip.sh — build minilab_1.3_group_9.zip from a commit.
#
#   tools/make_submission_zip.sh <commit> [--video PATH ...] [--report PATH ...]
#                                [--keep REPO_PATH ...] [--out DIR]
#
#   tools/make_submission_zip.sh HEAD --video demo.mp4 --report report.pdf --out ~/submit
#
# Source files come from `git archive <commit>`, so untracked or ignored files
# (.env, .venv/, *.pt, local recordings) can never leak in. Videos/report are
# copied from the paths given. Large files (> MAX_MB, default 5) under
# eval/results/ and docs/ are dropped unless named with --keep. The staged
# tree is scanned for API-key / private-key patterns and the build aborts on
# any hit (file:line is printed, never the secret).
set -euo pipefail

NAME="minilab_1.3_group_9"
MAX_MB="${MAX_MB:-5}"

usage() {
    sed -n '4,9p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-2}"
}
die() { echo "make_submission_zip: ERROR: $*" >&2; exit 1; }

[[ $# -ge 1 ]] || usage
case "$1" in -h|--help) usage 0 ;; -*) usage ;; esac
COMMIT_ARG="$1"; shift
VIDEOS=(); REPORTS=(); KEEPS=(); OUT_DIR="$PWD"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --video)  [[ $# -ge 2 ]] || usage; VIDEOS+=("$2"); shift 2 ;;
        --report) [[ $# -ge 2 ]] || usage; REPORTS+=("$2"); shift 2 ;;
        --keep)   [[ $# -ge 2 ]] || usage; KEEPS+=("$2"); shift 2 ;;
        --out)    [[ $# -ge 2 ]] || usage; OUT_DIR="$2"; shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage ;;
    esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT="$(git -C "$REPO" rev-parse --verify --quiet "${COMMIT_ARG}^{commit}")" \
    || die "not a commit: $COMMIT_ARG"
for f in ${VIDEOS[@]+"${VIDEOS[@]}"} ${REPORTS[@]+"${REPORTS[@]}"}; do
    [[ -f "$f" && ! -L "$f" ]] || die "not a regular file: $f"
done
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
ZIP="$OUT_DIR/$NAME.zip"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/submission.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/$NAME"
mkdir -p "$ROOT"

echo "Building $NAME.zip from $COMMIT ($(git -C "$REPO" log -1 --format=%s "$COMMIT"))"

# --- 1. choose files from the commit's tree -----------------------------------
is_included() {
    case "$1" in
        core/*|skills/*|dialogue/*|perception/*|tools/*|tests/*|assets/*|docs/*) return 0 ;;
        main.py|README.md|requirements.txt|pyproject.toml) return 0 ;;
        eval/results/*|eval/run_env.sh) return 0 ;;
        eval/*/*) return 1 ;;
        eval/*.py|eval/*.md) return 0 ;;   # incl. prompt_v*.py
    esac
    return 1
}
is_excluded() {   # never shipped, whatever the commit contains
    local base="${1##*/}"
    case "/$1/" in */.venv/*|*/venv/*|*/__pycache__/*|*/.git/*) return 0 ;; esac
    case "$base" in .env|.env.*|*.pt|*.pyc|*.onnx|*.key|*.pem) return 0 ;; esac
    case "$1" in eval/results/stt/*.wav) return 0 ;; esac
    return 1
}
is_kept() {
    local k
    for k in ${KEEPS[@]+"${KEEPS[@]}"}; do [[ "$1" == "$k" ]] && return 0; done
    return 1
}

mb() { awk -v b="$1" 'BEGIN { printf "%.1f MB", b / 1048576 }'; }
FILES=(); DROPPED=()
MAX_BYTES=$(( MAX_MB * 1024 * 1024 ))
while IFS= read -r -d '' entry; do
    meta="${entry%%$'\t'*}"; path="${entry#*$'\t'}"
    read -r mode type _obj size <<<"$meta"
    is_included "$path" || continue
    if [[ "$type" != blob || "$mode" == 120000 ]]; then
        DROPPED+=("$path (symlink/submodule)"); continue
    fi
    if is_excluded "$path"; then DROPPED+=("$path (excluded pattern)"); continue; fi
    if (( size > MAX_BYTES )); then
        case "$path" in
            eval/results/*|docs/*)
                if ! is_kept "$path"; then
                    DROPPED+=("$path ($(mb "$size") > ${MAX_MB} MB; --keep to include)")
                    continue
                fi ;;
            *) echo "  note: large file kept: $path ($(mb "$size"))" ;;
        esac
    fi
    FILES+=("$path")
done < <(git -C "$REPO" ls-tree -r -l -z "$COMMIT")
(( ${#FILES[@]} > 0 )) || die "no files selected from $COMMIT"

git -C "$REPO" --literal-pathspecs archive --format=tar "$COMMIT" -- "${FILES[@]}" \
    | tar -x -C "$ROOT"

# --- 2. videos, report, provenance ---------------------------------------------
copy_into() {   # copy_into DIR FILE...
    local dir="$1" f; shift
    mkdir -p "$ROOT/$dir"
    for f in "$@"; do
        [[ -e "$ROOT/$dir/${f##*/}" ]] && die "duplicate file name in $dir/: ${f##*/}"
        cp "$f" "$ROOT/$dir/"
    done
}
mkdir -p "$ROOT/videos" "$ROOT/report"
if (( ${#VIDEOS[@]} )); then
    copy_into videos "${VIDEOS[@]}"
else
    echo "No demo videos were passed to tools/make_submission_zip.sh (--video PATH)." \
        > "$ROOT/videos/README.md"
    echo "  warning: no --video given; videos/ holds a placeholder README"
fi
if (( ${#REPORTS[@]} )); then
    copy_into report "${REPORTS[@]}"
else
    printf '%s\n' "# Report placeholder" "" \
        "The group report goes here: rebuild with" \
        "\`tools/make_submission_zip.sh <commit> --report path/to/report.pdf\`." \
        > "$ROOT/report/README.md"
    echo "  warning: no --report given; report/ holds a placeholder README"
fi
printf 'Built from commit %s (%s)\n' "$COMMIT" \
    "$(git -C "$REPO" log -1 --format='%cd, %s' --date=short "$COMMIT")" \
    > "$ROOT/SOURCE_COMMIT.txt"

# --- 3. secret scan: abort on any hit, print file:line only --------------------
KEY_LITERALS=(
    -e '(^|[^A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}'
    -e 'AIza[0-9A-Za-z_-]{30,}'
    -e '-----BEGIN [A-Z ]*PRIVATE KEY-----'
)
# NAME = value assignments with a long, real-looking value (placeholders such
# as "placeholder", "your-key-here", "sk-..." or "$VAR" are ignored).
KEY_ASSIGN='(DASHSCOPE|OPENAI|GOOGLE)_API_KEY["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_-]{16,}'
HITS="$(
    cd "$STAGE"
    { grep -rnIE "${KEY_LITERALS[@]}" . || true; } | awk -F: '{print $1 ":" $2}'
    { grep -rnoIE "$KEY_ASSIGN" . || true; } | awk -F: '{
        f = $1; l = $2; sub(/^[^:]*:[^:]*:/, "")
        if (tolower($0) !~ /placeholder|dummy|example|your|xxxx|changeme|here|fake|redacted/)
            print f ":" l }'
)"
if [[ -n "$HITS" ]]; then
    echo "make_submission_zip: ABORT — possible secret(s) in the staged tree:" >&2
    sort -u <<<"$HITS" | sed 's|^\./|  |' >&2
    echo "Remove them from the commit (and rotate the key) before submitting." >&2
    exit 1
fi

# --- 4. zip + final checks -------------------------------------------------------
TMP_ZIP="$STAGE/$NAME.zip"
(cd "$STAGE" && zip -qr -X "$TMP_ZIP" "$NAME")
unzip -Z1 "$TMP_ZIP" > "$STAGE/listing.txt"   # file, not a pipe: no SIGPIPE under pipefail
if grep -qE '(^|/)(\.env(\..*)?|\.venv/.*|[^/]+\.pt)$' "$STAGE/listing.txt"; then
    die "zip listing contains .env / .venv / *.pt — refusing to write it"
fi
mv -f "$TMP_ZIP" "$ZIP"

if (( ${#DROPPED[@]} )); then
    echo "Dropped from the commit's tree:"
    printf '  %s\n' "${DROPPED[@]}"
fi
COUNT="$(grep -vc '/$' "$STAGE/listing.txt")"
echo "Wrote $ZIP"
echo "  size: $(du -h "$ZIP" | cut -f1) ($(stat -c %s "$ZIP") bytes), files: $COUNT"
