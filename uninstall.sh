#!/usr/bin/env bash
# ==============================================================================
# Post-it Reminders - Uninstaller Script
# Rimuove in modo pulito l'applicazione, i servizi e le voci crontab dal sistema.
# ==============================================================================

set -e

C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_CYAN='\033[36m'

echo -e "${C_BOLD}${C_RED}====================================================${C_RESET}"
echo -e "${C_BOLD}${C_RED}  🗑️  Disinstallatore Promemoria Post-it            ${C_RESET}"
echo -e "${C_BOLD}${C_RED}====================================================${C_RESET}"
echo ""

# 1. Arresto e disabilitazione demone utente Systemd
echo -e "${C_CYAN}[1/5]${C_RESET} Disabilitazione servizio systemd postit-daemon..."
if command -v systemctl &>/dev/null && systemctl --user is-active postit-daemon &>/dev/null; then
    systemctl --user disable --now postit-daemon.service 2>/dev/null || true
    echo -e "${C_GREEN}✓ Servizio systemd arrestato e disabilitato.${C_RESET}"
fi
rm -f "$HOME/.config/systemd/user/postit-daemon.service"
if command -v systemctl &>/dev/null; then
    systemctl --user daemon-reload 2>/dev/null || true
fi

# 2. Pulizia job da Crontab
echo -e "${C_CYAN}[2/5]${C_RESET} Rimozione voci automatiche da crontab..."
if command -v crontab &>/dev/null; then
    CURRENT_CRON=$(crontab -l 2>/dev/null || true)
    if [ -n "$CURRENT_CRON" ]; then
        CLEANED_CRON=$(echo "$CURRENT_CRON" | sed '/POSTIT_APP_JOB/d' | sed '/=== BEGIN POSTIT_APP_JOBS/,/=== END POSTIT_APP_JOBS/d' | sed '/^$/N;/^\n$/D')
        if [ -z "$(echo "$CLEANED_CRON" | tr -d '[:space:]')" ]; then
            crontab -r 2>/dev/null || true
        else
            echo "$CLEANED_CRON" | crontab -
        fi
        echo -e "${C_GREEN}✓ Crontab ripulito.${C_RESET}"
    fi
fi

# 3. Rimozione file binari ed eseguibili
echo -e "${C_CYAN}[3/5]${C_RESET} Rimozione eseguibili da $HOME/.local/bin..."
rm -f "$HOME/.local/bin/postit_manager.py"
rm -f "$HOME/.local/bin/postit-runner.sh"
rm -f "$HOME/.local/bin/postit-manager"

# 4. Rimozione lanciatore Desktop e Icone
echo -e "${C_CYAN}[4/5]${C_RESET} Rimozione file .desktop e icone..."
rm -f "$HOME/.local/share/applications/postit-manager.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/postit-manager.svg"
for size in 256 128 64 48 32; do
    rm -f "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/postit-manager.png"
done
rm -f "$HOME/.local/share/pixmaps/postit-manager.png" "$HOME/.local/share/pixmaps/postit-manager.svg"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

# 5. Dati utente (opzione --purge)
echo -e "${C_CYAN}[5/5]${C_RESET} Gestione dati e promemoria salvati..."
if [ "$1" == "--purge" ]; then
    rm -rf "$HOME/.local/share/postit-app"
    echo -e "${C_YELLOW}Dati e promemoria salvati rimossi (--purge).${C_RESET}"
else
    echo -e "${C_GREEN}I tuoi promemoria salvati in $HOME/.local/share/postit-app sono stati mantenuti.${C_RESET}"
    echo -e "Se desideri rimuoverli completamente: ${C_BOLD}rm -rf $HOME/.local/share/postit-app${C_RESET}"
fi

echo ""
echo -e "${C_BOLD}${C_GREEN}Disinstallazione completata con successo!${C_RESET}"
