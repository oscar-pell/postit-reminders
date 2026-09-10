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

# 1. Rilevamento Distribuzione Linux e Gestore Pacchetti
DISTRO="unknown"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="$ID"
    DISTRO_LIKE="$ID_LIKE"
fi

PKG_MGR="unknown"
if command -v dnf5 &>/dev/null; then
    PKG_MGR="dnf5"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
elif command -v microdnf &>/dev/null; then
    PKG_MGR="microdnf"
elif command -v rpm-ostree &>/dev/null; then
    PKG_MGR="rpm-ostree"
elif command -v yum &>/dev/null; then
    PKG_MGR="yum"
elif command -v apt-get &>/dev/null; then
    PKG_MGR="apt-get"
elif command -v apt &>/dev/null; then
    PKG_MGR="apt"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"
elif command -v zypper &>/dev/null; then
    PKG_MGR="zypper"
elif command -v apk &>/dev/null; then
    PKG_MGR="apk"
fi

echo -e "${C_CYAN}[1/6]${C_RESET} Rilevata distribuzione: ${C_BOLD}$DISTRO${C_RESET} ($PRETTY_NAME)"
echo -e "      Gestore pacchetti rilevato: ${C_BOLD}$PKG_MGR${C_RESET}"

# 2. Controllo e Installazione Dipendenze di Sistema
echo -e "${C_CYAN}[2/6]${C_RESET} Verifica dipendenze (Python 3, Tkinter, libnotify)..."

check_python() {
    command -v python3 &>/dev/null
}

check_tkinter() {
    python3 -c "import tkinter" &>/dev/null
}

try_install_package() {
    local cmd="$1"
    set +e
    if [ "$EUID" -eq 0 ]; then
        eval "$cmd"
    else
        eval "sudo $cmd"
    fi
    local res=$?
    set -e
    return $res
}

install_sys_package() {
    local target="$1" # "python" o "tkinter"
    local cmd=""

    case "$PKG_MGR" in
        dnf5)
            [ "$target" = "python" ] && cmd="dnf5 install -y python3" || cmd="dnf5 install -y python3-tkinter libnotify"
            ;;
        dnf)
            [ "$target" = "python" ] && cmd="dnf install -y python3" || cmd="dnf install -y python3-tkinter libnotify"
            ;;
        microdnf)
            [ "$target" = "python" ] && cmd="microdnf install -y python3" || cmd="microdnf install -y python3-tkinter libnotify"
            ;;
        rpm-ostree)
            [ "$target" = "python" ] && cmd="rpm-ostree install --idempotent -y python3" || cmd="rpm-ostree install --idempotent -y python3-tkinter libnotify"
            ;;
        yum)
            [ "$target" = "python" ] && cmd="yum install -y python3" || cmd="yum install -y python3-tkinter libnotify"
            ;;
        apt-get|apt)
            [ "$target" = "python" ] && cmd="apt-get update -y && apt-get install -y python3" || cmd="apt-get update -y && apt-get install -y python3-tk libnotify-bin"
            ;;
        pacman)
            [ "$target" = "python" ] && cmd="pacman -S --needed --noconfirm python" || cmd="pacman -S --needed --noconfirm tk libnotify"
            ;;
        zypper)
            [ "$target" = "python" ] && cmd="zypper install -y python3" || cmd="zypper install -y python3-tk libnotify-tools"
            ;;
        apk)
            [ "$target" = "python" ] && cmd="apk add python3" || cmd="apk add py3-tkinter libnotify"
            ;;
        *)
            return 1
            ;;
    esac

    try_install_package "$cmd"
}

# Controllo Python 3
if ! check_python; then
    echo -e "${C_RED}Python 3 non trovato.${C_RESET}"
    if [ "$PKG_MGR" != "unknown" ] && ([ "$EUID" -eq 0 ] || command -v sudo &>/dev/null); then
        echo -e "${C_YELLOW}Tentativo di installazione di Python 3 tramite $PKG_MGR...${C_RESET}"
        install_sys_package "python" || true
    fi
    if ! check_python; then
        echo -e "${C_RED}[Errore critico] Python 3 è indispensabile per l'applicazione. Installalo prima di procedere.${C_RESET}"
        exit 1
    fi
fi

# Controllo Tkinter
if ! check_tkinter; then
    echo -e "${C_YELLOW}Modulo grafico Tkinter non trovato per Python 3.${C_RESET}"
    
    SUDO_AVAILABLE=false
    if [ "$EUID" -eq 0 ]; then
        SUDO_AVAILABLE=true
    elif command -v sudo &>/dev/null; then
        SUDO_AVAILABLE=true
    fi

    if [ "$SUDO_AVAILABLE" = true ] && [ "$PKG_MGR" != "unknown" ]; then
        echo -e "${C_YELLOW}Tentativo di installazione dipendenze tramite $PKG_MGR (potrebbe richiedere password di sudo)...${C_RESET}"
        install_sys_package "tkinter" || true
    fi

    if check_tkinter; then
        echo -e "${C_GREEN}✓ Tkinter installato con successo.${C_RESET}"
    else
        echo ""
        echo -e "${C_BOLD}${C_YELLOW}┌────────────────────────────────────────────────────────────────────────┐${C_RESET}"
        echo -e "${C_BOLD}${C_YELLOW}│ ⚠️  AVVISO: Pacchetti di sistema non installati o sudo non disponibile │${C_RESET}"
        echo -e "${C_BOLD}${C_YELLOW}└────────────────────────────────────────────────────────────────────────┘${C_RESET}"
        echo -e "L'applicazione verrà comunque installata regolarmente nella tua cartella utente (~/.local/bin)."
        echo -e "Per avviare l'interfaccia grafica su questa macchina, chiedi all'amministratore di sistema"
        echo -e "oppure esegui con un account dotato di privilegi di amministratore:"
        case "$PKG_MGR" in
            dnf5)
                echo -e "  ${C_BOLD}${C_CYAN}sudo dnf5 install -y python3-tkinter libnotify${C_RESET}"
                ;;
            dnf)
                echo -e "  ${C_BOLD}${C_CYAN}sudo dnf install -y python3-tkinter libnotify${C_RESET}"
                ;;
            microdnf)
                echo -e "  ${C_BOLD}${C_CYAN}sudo microdnf install -y python3-tkinter libnotify${C_RESET}"
                ;;
            rpm-ostree)
                echo -e "  ${C_BOLD}${C_CYAN}sudo rpm-ostree install python3-tkinter libnotify${C_RESET}"
                echo -e "  ${C_YELLOW}Nota: Su sistemi Fedora Silverblue/Atomic/Bazzite puoi anche usare:${C_RESET}"
                echo -e "    ${C_CYAN}toolbox enter${C_RESET}"
                ;;
            yum)
                echo -e "  ${C_BOLD}${C_CYAN}sudo yum install -y python3-tkinter libnotify${C_RESET}"
                ;;
            apt-get|apt)
                echo -e "  ${C_BOLD}${C_CYAN}sudo apt install -y python3-tk libnotify-bin${C_RESET}"
                ;;
            pacman)
                echo -e "  ${C_BOLD}${C_CYAN}sudo pacman -S --needed tk libnotify${C_RESET}"
                ;;
            zypper)
                echo -e "  ${C_BOLD}${C_CYAN}sudo zypper install -y python3-tk libnotify-tools${C_RESET}"
                ;;
            apk)
                echo -e "  ${C_BOLD}${C_CYAN}sudo apk add py3-tkinter libnotify${C_RESET}"
                ;;
            *)
                echo -e "  ${C_BOLD}${C_CYAN}Fedora/RHEL: sudo dnf install -y python3-tkinter (o dnf5 / rpm-ostree)${C_RESET}"
                echo -e "  ${C_BOLD}${C_CYAN}Ubuntu/Debian: sudo apt install -y python3-tk${C_RESET}"
                ;;
        esac
        echo ""
        echo -e "Alternative in spazio utente (senza bisogno di sudo):"
        if command -v conda &>/dev/null; then
            echo -e "  • ${C_BOLD}Conda (trovato nel sistema):${C_RESET} ${C_CYAN}conda install -c conda-forge tk${C_RESET}"
        else
            echo -e "  • ${C_BOLD}Ambiente Conda / Mamba:${C_RESET} ${C_CYAN}conda install -c conda-forge tk${C_RESET}"
        fi
        if command -v brew &>/dev/null; then
            echo -e "  • ${C_BOLD}Homebrew (trovato nel sistema):${C_RESET} ${C_CYAN}brew install python-tk${C_RESET}"
        fi
        if command -v toolbox &>/dev/null; then
            echo -e "  • ${C_BOLD}Fedora Toolbox:${C_RESET} esegui l'app all'interno di un container toolbox (${C_CYAN}toolbox enter${C_RESET})"
        fi
        echo ""
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
if [ -f "$PROJECT_DIR/assets/icon.png" ]; then
    install -m 644 "$PROJECT_DIR/assets/icon.png" "$DATA_DIR/icon.png"
fi

# Copia icone per il fallback pixmaps
mkdir -p "$HOME/.local/share/pixmaps"
install -m 644 "$PROJECT_DIR/assets/icon.svg" "$HOME/.local/share/pixmaps/postit-manager.svg"
if [ -f "$PROJECT_DIR/assets/icon.png" ]; then
    install -m 644 "$PROJECT_DIR/assets/icon.png" "$HOME/.local/share/pixmaps/postit-manager.png"
fi

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

# Copia SVG scalabile nel tema hicolor
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

# Sincronizzazione automatica crontab (se disponibile) come backup
if command -v crontab &>/dev/null; then
    "$BIN_DIR/postit-runner.sh" --sync-cron >/dev/null 2>&1 || true
    echo -e "${C_GREEN}✓ Crontab configurato come schedulatore secondario di backup.${C_RESET}"
else
    echo -e "${C_GREEN}✓ Schedulatore: attivo demone utente systemd (crontab non presente, non necessario).${C_RESET}"
fi

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
