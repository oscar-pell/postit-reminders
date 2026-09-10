#!/usr/bin/env bash
# ==============================================================================
# Post-it Reminders - Universal Linux Graphical Environment Runner
# Compatibile con Wayland e X11 su Ubuntu, Fedora, Arch, Debian, openSUSE, ecc.
# ==============================================================================

set -e

USER_ID=$(id -u)
USER_HOME="${HOME:-$(getent passwd "$USER_ID" | cut -d: -f6)}"

# 1. Configurazione Variabili XDG e D-Bus
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$USER_ID}"
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ] && [ -S "$XDG_RUNTIME_DIR/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
fi

# 2. Rilevamento Display Server (Wayland / X11 / Xwayland)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=":0"
fi

if [ -z "$WAYLAND_DISPLAY" ]; then
    # Cerca socket Wayland attivo in XDG_RUNTIME_DIR
    WAYLAND_SOCK=$(find "$XDG_RUNTIME_DIR" -maxdepth 1 -name "wayland-*" 2>/dev/null | head -n 1)
    if [ -n "$WAYLAND_SOCK" ]; then
        export WAYLAND_DISPLAY="$(basename "$WAYLAND_SOCK")"
    fi
fi

# 3. Rilevamento dinamico credenziali XAUTHORITY per Xwayland / X11
# Su GNOME Wayland (Mutter), KDE Plasma Wayland (KWin), e server X11 tradizionali
if [ -z "$XAUTHORITY" ] || [ ! -r "$XAUTHORITY" ]; then
    for candidate in \
        "$(ls "$XDG_RUNTIME_DIR"/.mutter-Xwaylandauth.* 2>/dev/null | head -n 1)" \
        "$(ls "$XDG_RUNTIME_DIR"/xauth_* 2>/dev/null | head -n 1)" \
        "$XDG_RUNTIME_DIR/.Xauthority" \
        "$USER_HOME/.Xauthority"; do
        if [ -n "$candidate" ] && [ -r "$candidate" ]; then
            export XAUTHORITY="$candidate"
            break
        fi
    done
fi

# 4. Individuazione Script Python
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/postit_manager.py" ]; then
    TARGET_PY="$SCRIPT_DIR/postit_manager.py"
elif [ -f "$USER_HOME/.local/bin/postit_manager.py" ]; then
    TARGET_PY="$USER_HOME/.local/bin/postit_manager.py"
else
    echo "[Errore] postit_manager.py non trovato in $SCRIPT_DIR o $USER_HOME/.local/bin" >&2
    exit 1
fi

PYTHON_BIN="$(which python3 || which python || echo "/usr/bin/python3")"

exec "$PYTHON_BIN" "$TARGET_PY" "$@"
