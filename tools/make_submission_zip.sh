#!/usr/bin/env bash
# Owner: ALL (shared submission tooling)
# Change contributed by Student B (assist), pending review by the group
#
# tools/make_submission_zip.sh — build the course submission zip from a git tag.
#
#   tools/make_submission_zip.sh --tag TAG [--task2 MP4] [--task3 MP4] [--task4 MP4]
#       [--bonus MP4] [--report PDF] [--out DIR] [--name NAME] [--draft] [--keep PATH ...]
#
#   tools/make_submission_zip.sh --tag final --task2 v2.mp4 --task3 v3.mp4 \
#       --task4 v4.mp4 --bonus vb.mp4 --report report.pdf --out ~/submit
#
# The source tree comes from `git archive <TAG>` (any ref works: --commit is an
# alias of --tag), never from the working tree, so untracked/ignored files
# (.env, .venv/, *.pt, local recordings) cannot leak in. Zip root:
#   Video_Task2.mp4 Video_Task3.mp4 Video_Task4.mp4 Video_Bonus.mp4 <report>.pdf
#   README.md main.py core/ skills/ dialogue/ perception/ assets/ eval/ tools/ tests/ docs/ ...
# Dropped from the tag's tree: .env*, *.pt, *.onnx, *.pyc, __pycache__/, every
# *.mp4 (only the four videos passed as arguments ship), eval/results/stt/**/*.wav,
# and raw e2e traces: under eval/e2e/results/ only each run's summary.md and any
# *.csv are kept. Files > MAX_MB (default 5) under eval/results/ and docs/ are
# dropped unless named with --keep. Without --draft a missing video/report is an
# error; with --draft the zip is built anyway and the missing items are listed.
# The packed tree is scanned for API-key patterns (sk-..., AIza..., key_...,
# DASHSCOPE/OPENAI/GEMINI/GOOGLE...=<real value>); any hit aborts and deletes
# the zip, printing file:line only (never the value).
set -euo pipefail

NAME="minilab_1.3_group_9"   # the handout's example is project_1.3_group_<N>.zip: --name to override
MAX_MB="${MAX_MB:-5}"

usage() {
    sed -n '5,12p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-2}"
}
die() { echo "make_submission_zip: ERROR: $*" >&2; exit 1; }

REF=""; OUT_DIR="$PWD"; DRAFT=0; REPORT=""; KEEPS=()
declare -A VIDEO=([Video_Task2.mp4]="" [Video_Task3.mp4]="" [Video_Task4.mp4]="" [Video_Bonus.mp4]="")
VIDEO_ORDER=(Video_Task2.mp4 Video_Task3.mp4 Video_Task4.mp4 Video_Bonus.mp4)
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag|--commit) [[ $# -ge 2 ]] || usage; REF="$2"; shift 2 ;;
        --task2)  [[ $# -ge 2 ]] || usage; VIDEO[Video_Task2.mp4]="$2"; shift 2 ;;
        --task3)  [[ $# -ge 2 ]] || usage; VIDEO[Video_Task3.mp4]="$2"; shift 2 ;;
        --task4)  [[ $# -ge 2 ]] || usage; VIDEO[Video_Task4.mp4]="$2"; shift 2 ;;
        --bonus)  [[ $# -ge 2 ]] || usage; VIDEO[Video_Bonus.mp4]="$2"; shift 2 ;;
        --report) [[ $# -ge 2 ]] || usage; REPORT="$2"; shift 2 ;;
        --out)    [[ $# -ge 2 ]] || usage; OUT_DIR="$2"; shift 2 ;;
        --name)   [[ $# -ge 2 ]] || usage; NAME="${2%.zip}"; shift 2 ;;
        --keep)   [[ $# -ge 2 ]] || usage; KEEPS+=("$2"); shift 2 ;;
        --draft)  DRAFT=1; shift ;;
        -h|--help) usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage ;;
    esac
done
[[ -n "$REF" ]] || { echo "--tag TAG is required" >&2; usage; }
command -v zip >/dev/null && command -v unzip >/dev/null || die "needs zip and unzip"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT="$(git -C "$REPO" rev-parse --verify --quiet "${REF}^{commit}")" \
    || die "not a tag/commit: $REF"

# --- 0. deliverables: videos + report ------------------------------------------
MISSING=()
for v in "${VIDEO_ORDER[@]}"; do
    p="${VIDEO[$v]}"
    if [[ -z "$p" ]]; then MISSING+=("$v (not given)"); continue; fi
    [[ -f "$p" && ! -L "$p" ]] || die "not a regular file: $p (for $v)"
    [[ "${p,,}" == *.mp4 ]] || die "$p: expected an .mp4 file for $v"
    [[ -s "$p" ]] || die "$p is empty (for $v)"
done
REPORT_NAME=""
if [[ -z "$REPORT" ]]; then
    MISSING+=("report PDF (not given: --report PATH)")
else
    [[ -f "$REPORT" && ! -L "$REPORT" ]] || die "not a regular file: $REPORT"
    [[ "${REPORT,,}" == *.pdf ]] || die "$REPORT: the report must be a .pdf"
    REPORT_NAME="${REPORT##*/}"
fi
if (( ${#MISSING[@]} )) && (( ! DRAFT )); then
    printf 'make_submission_zip: missing deliverable: %s\n' "${MISSING[@]}" >&2
    die "pass every video and the report, or --draft to build an incomplete zip"
fi

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
ZIP="$OUT_DIR/$NAME.zip"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/submission.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/root"
mkdir -p "$ROOT"

echo "Building $NAME.zip from $REF = $COMMIT ($(git -C "$REPO" log -1 --format=%s "$COMMIT"))"
(( DRAFT )) && echo "  DRAFT build: missing deliverables are allowed"

# --- 1. choose files from the ref's tree ----------------------------------------
is_included() {
    case "$1" in
        core/*|skills/*|dialogue/*|perception/*|tools/*|tests/*|assets/*|docs/*|eval/*) return 0 ;;
        main.py|README.md|requirements.txt|pyproject.toml|.env.example|.gitignore) return 0 ;;
    esac
    return 1   # internal notes at the root (STATUS.md, MORNING_BRIEF.md) stay out
}
is_excluded() {   # never shipped, whatever the tag contains; echoes the reason
    local base="${1##*/}"
    case "/$1/" in */.venv/*|*/venv/*|*/__pycache__/*|*/.git/*) echo "cache/venv"; return 0 ;; esac
    case "$base" in
        .env.example) ;;
        .env|.env.*) echo ".env"; return 0 ;;
        *.pt|*.onnx|*.pyc|*.key|*.pem) echo "weights/bytecode/key"; return 0 ;;
        *.mp4|*.MP4) echo "local video (only the --taskN/--bonus videos ship)"; return 0 ;;
    esac
    case "$1" in
        eval/results/stt/*.wav) echo "voice recording"; return 0 ;;
        eval/e2e/results/*/summary.md|eval/e2e/results/*.csv) ;;
        eval/e2e/results/*) echo "raw e2e trace"; return 0 ;;
    esac
    return 1
}
is_kept() {
    local k
    for k in ${KEEPS[@]+"${KEEPS[@]}"}; do [[ "$1" == "$k" ]] && return 0; done
    return 1
}

mb() { awk -v b="$1" 'BEGIN { printf "%.1f MB", b / 1048576 }'; }
FILES=(); declare -A DROP_COUNT=(); DROP_BIG=()
MAX_BYTES=$(( MAX_MB * 1024 * 1024 ))
while IFS= read -r -d '' entry; do
    meta="${entry%%$'\t'*}"; path="${entry#*$'\t'}"
    read -r mode type _obj size <<<"$meta"
    is_included "$path" || continue
    if [[ "$type" != blob || "$mode" == 120000 ]]; then
        DROP_COUNT["symlink/submodule"]=$(( ${DROP_COUNT["symlink/submodule"]:-0} + 1 )); continue
    fi
    if reason="$(is_excluded "$path")"; then
        DROP_COUNT["$reason"]=$(( ${DROP_COUNT["$reason"]:-0} + 1 )); continue
    fi
    if (( size > MAX_BYTES )); then
        case "$path" in
            eval/results/*|docs/*)
                if ! is_kept "$path"; then
                    DROP_BIG+=("$path ($(mb "$size") > ${MAX_MB} MB; --keep to include)")
                    continue
                fi ;;
            *) echo "  note: large file kept: $path ($(mb "$size"))" ;;
        esac
    fi
    FILES+=("$path")
done < <(git -C "$REPO" ls-tree -r -l -z "$COMMIT")
(( ${#FILES[@]} > 0 )) || die "no files selected from $REF"

git -C "$REPO" --literal-pathspecs archive --format=tar "$COMMIT" -- "${FILES[@]}" \
    | tar -x -C "$ROOT"

# --- 2. videos, report, provenance -----------------------------------------------
for v in "${VIDEO_ORDER[@]}"; do
    [[ -n "${VIDEO[$v]}" ]] && cp "${VIDEO[$v]}" "$ROOT/$v"
done
if [[ -n "$REPORT" ]]; then
    [[ -e "$ROOT/$REPORT_NAME" ]] && die "report name $REPORT_NAME collides with a repo file"
    cp "$REPORT" "$ROOT/$REPORT_NAME"
fi
printf 'Built from %s = commit %s (%s)\n' "$REF" "$COMMIT" \
    "$(git -C "$REPO" log -1 --format='%cd, %s' --date=short "$COMMIT")" \
    > "$ROOT/SOURCE_COMMIT.txt"

# --- 3. zip ------------------------------------------------------------------------
TMP_ZIP="$STAGE/$NAME.zip"
(cd "$ROOT" && zip -qr -X "$TMP_ZIP" .)

# --- 4. key scan of the zip's contents: abort on any hit, print file:line only ---
SCAN="$STAGE/scan"
mkdir -p "$SCAN"
unzip -q "$TMP_ZIP" -d "$SCAN"
KEY_LITERALS=(
    -e '(^|[^A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}'
    -e 'AIza[0-9A-Za-z_-]{30,}'
    -e '-----BEGIN [A-Z ]*PRIVATE KEY-----'
)
# key_<long token with a digit> (identifiers such as key_env / key_callback are not keys)
KEY_PREFIXED='(^|[^A-Za-z0-9_])key_[A-Za-z0-9]{16,}'
# PROVIDER..._KEY = value, where value is not a placeholder, an env-var name or code
KEY_ASSIGN='(DASHSCOPE|OPENAI|GEMINI|GOOGLE)[A-Z0-9_]*["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[^[:space:]"'"'"',)]+'
HITS="$(
    cd "$SCAN"
    { grep -rnIE "${KEY_LITERALS[@]}" . || true; } | cut -d: -f1,2
    { grep -rnoIE "$KEY_PREFIXED" . || true; } | awk -F: '$3 ~ /[0-9]/ { print $1 ":" $2 }'
    { grep -rnoIE "$KEY_ASSIGN" . || true; } | awk -F: '{
        f = $1; l = $2; v = $0; sub(/^[^:]*:[^:]*:/, "", v)
        sub(/^[^=:]*[=:][[:space:]]*["'"'"']?/, "", v)        # keep the value only
        lv = tolower(v)
        if (length(v) < 8) next                               # too short to be a key
        if (v ~ /^[$<{]/ || v ~ /^\.\.\./) next               # $VAR, <key>, {..}, ...
        if (v ~ /^[A-Z0-9_]+$/) next                          # an env-var name
        if (v ~ /[.(\[]/) next                                # code: os.environ[...], f(...)
        if (lv ~ /placeholder|dummy|example|your|xxxx|changeme|here|fake|redacted|none|null|test|todo|replace/) next
        print f ":" l }'
)"
if [[ -n "$HITS" ]]; then
    echo "make_submission_zip: ABORT — possible secret(s) in the zip (file:line):" >&2
    sort -u <<<"$HITS" | sed 's|^\./|  |' >&2
    echo "Zip deleted. Remove them from the tag (and rotate the key) before submitting." >&2
    rm -f "$TMP_ZIP" "$ZIP"
    exit 1
fi
unzip -Z1 "$TMP_ZIP" > "$STAGE/listing.txt"   # file, not a pipe: no SIGPIPE under pipefail
if grep -qE '(^|/)(\.env(\.[^e].*)?|\.venv/.*|[^/]+\.(pt|pyc|onnx))$' "$STAGE/listing.txt"; then
    rm -f "$TMP_ZIP"
    die "zip listing contains .env / .venv / *.pt / *.pyc — refusing to write it"
fi
mv -f "$TMP_ZIP" "$ZIP"

# --- 5. report -----------------------------------------------------------------------
echo "Key scan: 0 hits"
if (( ${#DROP_COUNT[@]} )); then
    echo "Dropped from the tag's tree:"
    for r in "${!DROP_COUNT[@]}"; do printf '  %5d  %s\n' "${DROP_COUNT[$r]}" "$r"; done | sort -k2
fi
(( ${#DROP_BIG[@]} )) && printf '  large: %s\n' "${DROP_BIG[@]}"
echo "Contents (top 2 levels, file counts):"
grep -v '/$' "$STAGE/listing.txt" | awk -F/ '{ k = (NF > 2) ? $1 "/" $2 "/" : (NF == 2 ? $1 "/" : $1); n[k]++ }
    END { for (k in n) printf "  %-40s %s\n", k, (k ~ /\/$/ ? n[k] " files" : "") }' | LC_ALL=C sort
COUNT="$(grep -vc '/$' "$STAGE/listing.txt")"
echo "Wrote $ZIP"
echo "  size: $(du -h "$ZIP" | cut -f1) ($(stat -c %s "$ZIP") bytes), files: $COUNT"
if (( ${#MISSING[@]} )); then
    echo "DRAFT — missing deliverables:"
    printf '  - %s\n' "${MISSING[@]}"
fi
