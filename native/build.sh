#!/usr/bin/env bash
# build.sh - build the CatBa native C runtime.
#
# Discovers Python development headers from the active Python, then compiles
# the native runtime and tests with GCC (C23).
#
# Usage:
#   ./build.sh                # build and run tests (default)
#   ./build.sh server         # build the server binary
#   ./build.sh tests          # build and run native tests
#
# Environment:
#   CC       - C compiler (default: gcc)
#   SAN      - "asan" to enable AddressSanitizer + UBSan + LeakSanitizer
#   CFLAGS   - extra compiler flags
#
# The runtime embeds the user's installed CPython. It does not bundle Python.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/src"
TESTS="$SCRIPT_DIR/tests"
BUILD="$SCRIPT_DIR/build"

CC="${CC:-gcc}"
OS="$(uname -s 2>/dev/null || echo unknown)"

mkdir -p "$BUILD"

# --- discover Python ---
PY_INCLUDE="$(python3 -c 'import sysconfig; print(sysconfig.get_path("include"))' 2>/dev/null \
           || python  -c 'import sysconfig; print(sysconfig.get_path("include"))')"
PY_VERSION="$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("py_version_nodot"))' 2>/dev/null \
           || python  -c 'import sysconfig; print(sysconfig.get_config_var("py_version_nodot"))')"
PY_EXEC="$(python3 -c 'import sys; print(sys.executable)' 2>/dev/null || python -c 'import sys; print(sys.executable)')"
PY_DLLDIR="$(dirname "$PY_EXEC")"
PY_LIBDIR="$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))' 2>/dev/null \
          || python  -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"

# --- flags ---
WARN="-Wall -Wextra -Werror"
STD="-std=c23"
if [ "${SAN:-}" = "asan" ]; then
    SAN_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -g"
else
    SAN_FLAGS=""
fi

# --- platform source selection ---
case "$OS" in
    MINGW*|MSYS*|CYGWIN*)
        PLATFORM_SRC="$SRC/platform_win.c"
        PY_LINK="-L$PY_DLLDIR -lpython$PY_VERSION -lws2_32"
        ;;
    *)
        PLATFORM_SRC="$SRC/platform_posix.c"
        PY_LINK="-L$PY_LIBDIR -lpython$PY_VERSION"
        ;;
esac

# --- compile one source file to an object ---
compile_src() {
    local src_path="$1"
    local base
    base="$(basename "${src_path%.c}")"
    local obj="$BUILD/$base.o"
    $CC $STD $WARN $SAN_FLAGS -I"$SRC" -I"$PY_INCLUDE" ${CFLAGS:-} \
        -c "$src_path" -o "$obj" || return 1
    echo "$obj"
}

# --- link a target from object files ---
link_target() {
    local out="$1"; shift
    $CC $SAN_FLAGS -o "$out" "$@" $PY_LINK ${CFLAGS:-} || return 1
}

# --- build server binary from all available runtime sources ---
build_server() {
    local objs=""
    # Platform source
    local plat_obj
    plat_obj="$(compile_src "$PLATFORM_SRC")" || return 1
    objs="$objs $plat_obj"
    # Runtime sources (only those that exist)
    for f in arena.c http_parser.c socket.c python_runtime.c bridge.c serializer.c server.c; do
        if [ -f "$SRC/$f" ]; then
            local obj
            obj="$(compile_src "$SRC/$f")" || return 1
            objs="$objs $obj"
        fi
    done
    link_target "$BUILD/catba-native" $objs || return 1
    echo "built: $BUILD/catba-native"
}

# --- build and run a single test ---
build_test() {
    local test_src="$1"
    local name
    name="$(basename "${test_src%.c}")"
    local objs=""
    # Platform source
    local plat_obj
    plat_obj="$(compile_src "$PLATFORM_SRC")" || return 1
    objs="$objs $plat_obj"
    # Any runtime sources the test might need (compile what exists)
    for f in arena.c http_parser.c socket.c python_runtime.c bridge.c serializer.c server.c; do
        if [ -f "$SRC/$f" ]; then
            local obj
            obj="$(compile_src "$SRC/$f")" || return 1
            objs="$objs $obj"
        fi
    done
    # Test source itself
    local test_obj
    test_obj="$(compile_src "$test_src")" || return 1
    objs="$objs $test_obj"
    link_target "$BUILD/$name" $objs || return 1
    echo "built: $BUILD/$name"
    "$BUILD/$name" || return 1
}

# --- build and run all tests ---
build_tests() {
    local any_built=0
    for test_src in "$TESTS"/test_*.c; do
        [ -f "$test_src" ] || continue
        build_test "$test_src" || return 1
        any_built=1
    done
    if [ "$any_built" -eq 0 ]; then
        echo "no tests found" >&2
        return 1
    fi
}

case "${1:-tests}" in
    server)  build_server ;;
    tests)   build_tests ;;
    all)     build_server; build_tests ;;
    *)       echo "usage: $0 [server|tests|all]" >&2; exit 1 ;;
esac
