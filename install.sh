#!/usr/bin/env bash
# ==============================================================================
# Post-it Reminders - Universal Linux Installer
# Supporta: Ubuntu/Debian, Fedora/RHEL, Arch Linux, openSUSE e derivate.
# ==============================================================================

set -e

# Colori per il terminale
C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[32m'
C_BLUE='\033[34m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_CYAN='\033[36m'

echo -e "${C_BOLD}${C_BLUE}====================================================${C_RESET}"
echo -e "${C_BOLD}${C_YELLOW}  📌 Installatore Universale Promemoria Post-it      ${C_RESET}"
echo -e "${C_BOLD}${C_BLUE}====================================================${C_RESET}"
echo ""

# Rilevamento percorsi
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/postit-app"
ICONS_BASE="$HOME/.local/share/icons/hicolor"
APPS_DIR="$HOME/.local/share/applications"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

# 1. Rilevamento Distribuzione Linux
DISTRO="unknown"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="$ID"
    DISTRO_LIKE="$ID_LIKE"
fi

echo -e "${C_CYAN}[1/6]${C_RESET} Rilevata distribuzione Linux: ${C_BOLD}$DISTRO${C_RESET} ($PRETTY_NAME)"

# 2. Controllo e Installazione Dipendenze di Sistema
echo -e "${C_CYAN}[2/6]${C_RESET} Verifica dipendenze (Python 3, Tkinter, libnotify)..."

check_tkinter() {
    python3 -c "import tkinter" &>/dev/null
}

install_dependencies() {
    echo -e "${C_YELLOW}Installazione dipendenze richieste... (potrebbe essere richiesta la password di sudo)${C_RESET}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -y && sudo apt-get install -y python3-tk libnotify-bin cron
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-tkinter libnotify cronie
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --needed --noconfirm tk libnotify cronie
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y python3-tk libnotify-tools cron
    else
        echo -e "${C_RED}[Avviso] Gestore pacchetti non riconosciuto. Assicurati di aver installato python3-tk e libnotify manualmente.${C_RESET}"
    fi
}

if ! check_tkinter; then
    echo -e "${C_YELLOW}Tkinter non trovato per Python 3.${C_RESET}"
    if [ "$EUID" -eq 0 ]; then
        install_dependencies
    elif sudo -n true 2>/dev/null || [ -t 0 ]; then
        install_dependencies
    else
        echo -e "${C_RED}[Errore] Tkinter mancante. Installa 'python3-tk' (Ubuntu/Debian) o 'python3-tkinter' (Fedora) prima di proseguire.${C_RESET}"
        exit 1
    fi
else
    echo -e "${C_GREEN}✓ Python 3 e Tkinter sono già disponibili.${C_RESET}"
fi

# 3. Creazione Directory Utente
echo -e "${C_CYAN}[3/6]${C_RESET} Configurazione cartelle utente..."
mkdir -p "$BIN_DIR" "$DATA_DIR" "$APPS_DIR" "$SYSTEMD_USER_DIR"

# 4. Installazione Binari e Script
echo -e "${C_CYAN}[4/6]${C_RESET} Installazione script eseguibili in $BIN_DIR..."
install -m 755 "$PROJECT_DIR/src/postit_manager.py" "$BIN_DIR/postit_manager.py"
install -m 755 "$PROJECT_DIR/src/postit-runner.sh" "$BIN_DIR/postit-runner.sh"
ln -sf "$BIN_DIR/postit-runner.sh" "$BIN_DIR/postit-manager"

# Inizializzazione dati di base se non presenti
if [ ! -f "$DATA_DIR/reminders.json" ]; then
    "$BIN_DIR/postit_manager.py" --list >/dev/null 2>&1 || true
fi

# 5. Installazione Icone e Desktop Entry
echo -e "${C_CYAN}[5/6]${C_RESET} Registrazione icone del tema e lanciatore desktop..."

# Icona SVG di riferimento
install -m 644 "$PROJECT_DIR/assets/icon.svg" "$DATA_DIR/icon.svg"

# Generazione icone se Pillow è installato, altrimenti copia icone precompilate
if [ -d "$PROJECT_DIR/assets/icons" ] && [ "$(ls -A "$PROJECT_DIR/assets/icons" 2>/dev/null)" ]; then
    for size in 256 128 64 48 32; do
        if [ -f "$PROJECT_DIR/assets/icons/icon-$size.png" ]; then
            mkdir -p "$ICONS_BASE/${size}x${size}/apps"
            install -m 644 "$PROJECT_DIR/assets/icons/icon-$size.png" "$ICONS_BASE/${size}x${size}/apps/postit-manager.png"
        fi
    done
elif command -v python3 &>/dev/null; then
    python3 "$PROJECT_DIR/assets/generate_icons.py" 2>/dev/null || true
fi

# Copia SVG scalabile
mkdir -p "$ICONS_BASE/scalable/apps"
install -m 644 "$PROJECT_DIR/assets/icon.svg" "$ICONS_BASE/scalable/apps/postit-manager.svg"

# Aggiornamento cache icone di sistema
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICONS_BASE" 2>/dev/null || true
fi

# Installazione file .desktop con path espansi
DESKTOP_TARGET="$APPS_DIR/postit-manager.desktop"
sed -e "s|Exec=.*|Exec=$BIN_DIR/postit-runner.sh|" \
    "$PROJECT_DIR/desktop/postit-manager.desktop" > "$DESKTOP_TARGET"
chmod 644 "$DESKTOP_TARGET"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

# 6. Configurazione Servizio Background (Systemd Daemon + Cron)
echo -e "${C_CYAN}[6/6]${C_RESET} Configurazione schedulatore di sistema..."

SERVICE_FILE="$SYSTEMD_USER_DIR/postit-daemon.service"
install -m 644 "$PROJECT_DIR/systemd/postit-daemon.service" "$SERVICE_FILE"

if command -v systemctl &>/dev/null && systemctl --user is-system-running &>/dev/null; then
    systemctl --user daemon-reload || true
    systemctl --user enable --now postit-daemon.service || true
    echo -e "${C_GREEN}✓ Demone utente postit-daemon attivato con systemd.${C_RESET}"
fi

# Sincronizzazione automatica crontab come backup
"$BIN_DIR/postit-runner.sh" --sync-cron >/dev/null 2>&1 || true

echo ""
echo -e "${C_BOLD}${C_GREEN}====================================================${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}  🎉 Installazione completata con successo!          ${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}====================================================${C_RESET}"
echo ""
echo -e "Puoi avviare l'applicazione in qualsiasi momento con:"
echo -e "  ${C_BOLD}${C_CYAN}postit-manager${C_RESET}"
echo -e "oppure cercando ${C_BOLD}'Promemoria Post-it'${C_RESET} nel menu applicazioni della tua distribuzione."
echo ""

# Controllo PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "${C_YELLOW}[Nota] $HOME/.local/bin non sembra essere presente nel tuo PATH.${C_RESET}"
    echo -e "Aggiungi la riga seguente a ${C_BOLD}~/.bashrc${C_RESET} o ${C_BOLD}~/.zshrc${C_RESET}:"
    echo -e "  ${C_CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${C_RESET}"
    echo ""
fi
