#!/usr/bin/env python3
"""
Post-it Reminders Manager (Gestore Promemoria Desktop Avanzato)
Desktop utility universale per Linux (Ubuntu, Debian, Fedora, Arch, openSUSE, ecc.)
per la gestione di promemoria stile Post-it con finestre Always-on-Top, modalità
Post-it Desktop adesiva, richiamo orario automatico, palette colori personalizzabile,
formattazione testo ricca, Preset Rapido configurabile, supporto bilingue (Italiano/Inglese)
con auto-rilevamento della lingua di sistema e doppio scheduler (Systemd + Cron).
"""

import argparse
from datetime import datetime
import json
import locale
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from pathlib import Path

# Versione applicazione
APP_VERSION = "1.1.9"
GITHUB_REPO = "oscar-pell/postit-reminders"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, font
    TKINTER_AVAILABLE = True
except ImportError:
    tk = None
    ttk = None
    messagebox = None
    font = None
    TKINTER_AVAILABLE = False

# Percorsi di sistema dinamici basati su standard XDG
USER_HOME = Path.home()
APP_DIR = USER_HOME / ".local" / "share" / "postit-app"
ICONS_DIR = USER_HOME / ".local" / "share" / "icons" / "hicolor"
RUN_DIR = Path(f"/run/user/{os.getuid()}/postit-app") if Path(f"/run/user/{os.getuid()}").exists() else APP_DIR / "run"
RUN_DIR.mkdir(parents=True, exist_ok=True)

REMINDERS_FILE = APP_DIR / "reminders.json"
PRESET_FILE = APP_DIR / "preset.json"
CONFIG_FILE = APP_DIR / "config.json"
ICON_SVG = APP_DIR / "icon.svg"
ICON_PNG = APP_DIR / "icon.png"
RUNNER_SH = USER_HOME / ".local" / "bin" / "postit-runner.sh"
DESKTOP_FILE = USER_HOME / ".local" / "share" / "applications" / "postit-manager.desktop"

# Delimitatori Crontab
CRON_MARKER = "# POSTIT_APP_JOB"
CRON_BLOCK_START = "# === BEGIN POSTIT_APP_JOBS (Generato da Post-it Manager - NON MODIFICARE MANUALMENTE) ==="
CRON_BLOCK_END = "# === END POSTIT_APP_JOBS ==="

# Palette Temi Colore Post-it con etichette bilingue
COLOR_THEMES = {
    "yellow": {
        "name": "Giallo Classico",
        "name_it": "Giallo Classico",
        "name_en": "Classic Yellow",
        "bg": "#FEF9C3",
        "header": "#FDE047",
        "border": "#EAB308",
        "title": "#78350F",
        "text": "#1E293B",
        "badge_bg": "#FEF08A",
        "badge_border": "#CA8A04",
        "badge_fg": "#854D0E",
        "accent": "#EAB308",
        "highlight": "#FACC15"
    },
    "green": {
        "name": "Verde Menta",
        "name_it": "Verde Menta",
        "name_en": "Mint Green",
        "bg": "#DCFCE7",
        "header": "#86EFAC",
        "border": "#22C55E",
        "title": "#14532D",
        "text": "#1E293B",
        "badge_bg": "#BBF7D0",
        "badge_border": "#16A34A",
        "badge_fg": "#14532D",
        "accent": "#22C55E",
        "highlight": "#4ADE80"
    },
    "blue": {
        "name": "Azzurro Cielo",
        "name_it": "Azzurro Cielo",
        "name_en": "Sky Blue",
        "bg": "#E0F2FE",
        "header": "#7DD3FC",
        "border": "#0EA5E9",
        "title": "#0C4A6E",
        "text": "#1E293B",
        "badge_bg": "#BAE6FD",
        "badge_border": "#0284C7",
        "badge_fg": "#0369A1",
        "accent": "#0EA5E9",
        "highlight": "#38BDF8"
    },
    "purple": {
        "name": "Lilla Lavanda",
        "name_it": "Lilla Lavanda",
        "name_en": "Lavender Purple",
        "bg": "#F3E8FF",
        "header": "#D8B4FE",
        "border": "#A855F7",
        "title": "#581C87",
        "text": "#1E293B",
        "badge_bg": "#E9D5FF",
        "badge_border": "#9333EA",
        "badge_fg": "#6B21A8",
        "accent": "#A855F7",
        "highlight": "#C084FC"
    },
    "orange": {
        "name": "Arancio Pesca",
        "name_it": "Arancio Pesca",
        "name_en": "Peach Orange",
        "bg": "#FFEDD5",
        "header": "#FDBA74",
        "border": "#F97316",
        "title": "#7C2D12",
        "text": "#1E293B",
        "badge_bg": "#FED7AA",
        "badge_border": "#EA580C",
        "badge_fg": "#9A3412",
        "accent": "#F97316",
        "highlight": "#FB923C"
    },
    "pink": {
        "name": "Rosa Pastello",
        "name_it": "Rosa Pastello",
        "name_en": "Pastel Pink",
        "bg": "#FCE7F3",
        "header": "#F9A8D4",
        "border": "#EC4899",
        "title": "#831843",
        "text": "#1E293B",
        "badge_bg": "#FBCFE8",
        "badge_border": "#DB2777",
        "badge_fg": "#9D174D",
        "accent": "#EC4899",
        "highlight": "#F472B6"
    }
}


def get_color_name(color_key: str, lang: str = "it") -> str:
    """Restituisce il nome del colore localizzato nella lingua richiesta."""
    theme = COLOR_THEMES.get(color_key, COLOR_THEMES.get("yellow", {}))
    return theme.get(f"name_{lang}", theme.get("name", color_key))


# Dizionario di internazionalizzazione completo (Italiano / Inglese)
TRANSLATIONS = {
    "it": {
        "app_window_title": "Promemoria Post-it - Gestore Desktop",
        "app_title": "Promemoria Post-it",
        "app_subtitle": "Post-it Desktop interattivi, promemoria in sovraimpressione e collegamenti rapidi",
        "language_label": "Lingua:",

        "daemon_active": "● Demone: ATTIVO",
        "daemon_inactive": "⚠️ Demone: INATTIVO",
        "cron_active": "● Cron: ATTIVO",
        "cron_inactive": "⚠️ Cron: INATTIVO",
        "status_service_active_systemd": "● Servizio: ATTIVO (Systemd)",
        "status_service_active_cron": "● Servizio: ATTIVO (Cron)",
        "status_service_active_both": "● Servizio: ATTIVO (Systemd + Cron)",
        "status_service_inactive": "⚠️ Servizio: NON ATTIVO",
        "tooltip_service_systemd": "Il demone utente Systemd è attivo e controlla i tuoi promemoria ogni minuto in background.\nI promemoria appariranno puntualmente. (Crontab non necessario su questo sistema).\n\n💡 Clicca per informazioni sullo stato.",
        "tooltip_service_both": "Tutti i motori sono attivi: demone Systemd e schedulatore Crontab sincronizzati.\n\n💡 Clicca per informazioni sullo stato.",
        "tooltip_service_cron": "I promemoria sono pianificati tramite il servizio Crontab di sistema.\n\n💡 Clicca per informazioni sullo stato.",
        "tooltip_service_inactive": "Nessun servizio di notifica attivo in background.\nI promemoria non scatteranno automaticamente.\n\n💡 Clicca per avviare o sincronizzare il servizio.",
        "title_service_status": "Stato Servizio Promemoria",

        "status_ready": "Pronto.",
        "status_data": "Dati: {filename}",

        "form_section_title": "Crea o Modifica Post-it",
        "form_section_new": "➕ Nuovo Promemoria",
        "form_section_edit": "✏️ Modifica Promemoria",
        "badge_new_mode": "CREAZIONE",
        "badge_edit_mode": "MODIFICA",
        "btn_new_reminder": "Nuovo Promemoria",
        "btn_cancel_edit": "➕ Crea Nuovo Promemoria",
        "btn_cancel_edit_short": "✖ Annulla",
        "btn_preset_format": "⚡ Carica Preset: {title} ({time})",
        "btn_preset_empty": "⚡ Preset Rapido: (Nessun preset memorizzato - clicca qui)",
        "lbl_bg_color": "Colore Sfondo Post-it:",
        "lbl_time": "Orario (HH:MM):",
        "lbl_freq": "Frequenza:",
        "freq_weekdays": "Lun-Ven (Giorni feriali)",
        "freq_daily": "Ogni Giorno",
        "freq_short_weekdays": "Lun-Ven",
        "freq_short_daily": "Tutti i gg",
        "lbl_title": "Titolo:",
        "default_title": "Chiusura Attività",
        "lbl_formatting": "Testo Messaggio (Formattazione):",
        "btn_bold": "G",
        "btn_italic": "C",
        "btn_underline": "S",
        "btn_highlight": "🟡 Evidenzia",
        "btn_bullet": "• Elenco",
        "btn_heading": "Titolo H3",
        "btn_clean": "🧹 Pulisci",
        "default_message_text": "Ricordati di aggiornare le tue attività prima di staccare.",
        "lbl_links": "Collegamenti Rapidi (Opzionali):",
        "link1_default_label": "Link 1",
        "link2_default_label": "Link 2",
        "btn_save_reminder": "💾 Salva Promemoria",
        "btn_update_reminder": "💾 Aggiorna Modifiche",
        "btn_save_as_preset": "⭐ Salva come Preset",
        "btn_clear": "Pulisci",

        "table_section_title": "Elenco Promemoria",
        "table_active_count": "Promemoria Attivi ({count})",
        "table_double_click_hint": "💡 Doppio click per desktop • Ctrl/Shift per selezione multipla • Canc per eliminare",
        "col_time": "Orario",
        "col_freq": "Frequenza",
        "col_color": "Colore",
        "col_title": "Titolo",
        "col_links": "Link",
        "links_count": "{count} link",
        "no_links": "—",

        "btn_select_all": "Seleziona Tutti",
        "btn_deselect_all": "Deseleziona",
        "menu_select_all": "Seleziona tutti",
        "btn_desktop": "📌 Metti sul Desktop",
        "btn_test_alarm": "👁️ Testa Allarme Ora",
        "btn_set_as_preset": "⭐ Imposta come Preset",
        "btn_delete": "🗑️ Elimina",
        "btn_sync": "🔄 Sincronizza",

        "msg_no_preset_title": "Nessun Preset Memorizzato",
        "msg_no_preset_body": "Non hai ancora memorizzato un Preset Rapido.\n\nCome creare il tuo Preset:\n1. Compila i campi del modulo oppure seleziona un promemoria dalla tabella.\n2. Clicca sul pulsante '⭐ Salva come Preset'.\n\nI tuoi dati verranno memorizzati nel tuo profilo locale e potrai riutilizzarli al volo in qualsiasi momento!",
        "msg_missing_title_title": "Titolo Mancante",
        "msg_missing_title_body": "Inserisci almeno un titolo prima di salvare il Preset.",
        "msg_preset_saved_title": "Preset Memorizzato",
        "msg_preset_saved_body": "Il promemoria '{title}' è stato memorizzato come Preset Rapido!\n\n• Rimarrà salvato nel tuo sistema anche se elimini questo promemoria dalla tabella.\n• Potrai ricompilarlo all'istante ogni volta che vorrai cliccando su 'Carica Preset'.",
        "msg_preset_row_saved_body": "Il promemoria '{title}' è stato memorizzato come Preset Rapido!\n\n• Rimarrà salvato nel tuo sistema anche se elimini questo promemoria dalla tabella.\n• Se in futuro imposti un altro promemoria come preset, sovrascriverà questi dati.",
        "msg_preset_save_error": "Impossibile salvare il Preset.",
        "msg_no_selection_title": "Nessuna selezione",
        "msg_no_selection_preset": "Seleziona un promemoria dalla tabella da impostare come Preset.",
        "msg_no_selection_delete": "Seleziona un promemoria da eliminare.",
        "msg_invalid_time_title": "Orario non valido",
        "msg_invalid_time_body": "Inserisci un orario valido nel formato HH:MM (es. 18:00).",
        "msg_title_required_title": "Titolo obbligatorio",
        "msg_title_required_body": "Inserisci un titolo per il promemoria.",
        "msg_save_success_title": "Salvataggio Completato",
        "msg_save_success_body": "Il promemoria '{title}' è stato salvato ed è attivo nel sistema.",
        "msg_save_error": "Impossibile salvare il promemoria.",
        "msg_delete_confirm_title": "Conferma eliminazione",
        "msg_delete_confirm_body": "Vuoi davvero eliminare '{title}'?",
        "msg_delete_multiple_confirm_title": "Conferma eliminazione multipla",
        "msg_delete_multiple_confirm_body": "Vuoi davvero eliminare i {count} promemoria selezionati?",
        "msg_delete_error": "Impossibile eliminare il promemoria.",
        "msg_launch_error_title": "Errore Avvio",
        "msg_launch_error_body": "Impossibile avviare il Post-it sul desktop: {error}",
        "msg_sync_title": "Sincronizzazione",
        "msg_error_title": "Errore",
        "cron_sync_success": "Crontab sincronizzato con successo ({count} job attivi).",
        "cron_sync_error": "Errore nell'aggiornamento crontab: {error}",
        "cron_generic_error": "Errore generico crontab: {error}",
        "cron_not_installed": "Crontab non presente nel sistema (i promemoria sono gestiti dal demone di background).",
        "cron_not_installed_badge": "○ Cron: NON RICHIESTO",
        "cron_optional_badge": "○ Cron: OPZIONALE",

        "btn_check_update": "🔄 Aggiornamenti",
        "btn_update_available": "🎉 Aggiorna a {version}",
        "msg_checking_updates": "Verifica disponibilità aggiornamenti...",
        "msg_no_updates_title": "Nessun Aggiornamento",
        "msg_no_updates_body": "Post-it Reminders è già aggiornato all'ultima versione disponibile ({version}).",
        "msg_update_found_title": "Nuova Versione Disponibile",
        "msg_update_window_title": "Aggiornamento Software",
        "msg_update_header": "Nuova versione disponibile su GitHub!",
        "msg_current_version": "Versione installata:",
        "msg_latest_version": "Nuova versione:",
        "msg_release_notes": "Note di rilascio:",
        "btn_update_now": "🚀 Aggiorna Ora",
        "btn_view_github": "🌐 Apri su GitHub",
        "btn_close_dialog": "Più tardi",
        "msg_update_in_progress": "Download e installazione dell'aggiornamento in corso...",
        "msg_update_success_title": "Aggiornamento Completato",
        "msg_update_success_body": "Applicazione aggiornata alla versione {version}.\n\nRiavvia per utilizzare le nuove funzionalità.",
        "msg_update_relaunch_confirm_title": "Aggiornamento Completato",
        "msg_update_relaunch_confirm_body": "Applicazione aggiornata alla versione {version}.\n\nVuoi riavviarla adesso per applicare subito le novità?",
        "status_updated_manual_restart": "✓ Aggiornato a {version}. Riavvia l'applicazione per applicare le novità.",
        "msg_update_error_title": "Errore Aggiornamento",
        "msg_update_error_body": "Impossibile completare l'aggiornamento automatico: {error}\n\nPuoi scaricare l'aggiornamento manualmente da GitHub.",
        "sync_all_success": "✓ Demone Systemd e Crontab sincronizzati con successo!",
        "sync_daemon_success": "✓ Demone Systemd ricaricato con successo (promemoria attivi)!",
        "sync_manual_done": "✓ Schedulatore sincronizzato.",

        "tree_context_edit": "✏️ Modifica nel modulo",
        "tree_context_new": "➕ Crea nuovo promemoria",
        "status_new_mode": "Modulo reimpostato: modalità creazione nuovo promemoria.",
        "status_edit_mode": "✏️ Modifica di '{title}'. Clicca 'Nuovo Promemoria' per crearne un altro da zero.",
        "status_preset_loaded": "✓ Preset '{title}' caricato nel modulo.",
        "status_preset_stored": "⭐ Preset '{title}' memorizzato con successo!",
        "status_form_cleared": "Modulo ripulito (modalità nuovo promemoria).",
        "status_reminder_loaded": "Caricato promemoria per modifica: '{title}'",
        "status_reminder_saved": "✓ Promemoria '{title}' salvato!",
        "status_reminder_deleted": "Promemoria eliminato.",
        "status_reminders_deleted_multiple": "✓ Eliminati {count} promemoria con successo.",
        "status_multiple_selected": "{count} promemoria selezionati. Premi Canc o clicca Elimina.",
        "status_multiple_desktop_launched": "📌 Posizionati {count} post-it sul desktop.",
        "status_desktop_launched": "📌 Post-it posizionato sul desktop (processo indipendente).",
        "status_alarm_tested": "🚨 Test sovraimpressione allarme inviato a schermo!",

        "postit_default_title": "Promemoria",
        "postit_pin_on": "📌 In Primo Piano",
        "postit_pin_off": "🔓 Normale (Desktop)",
        "postit_status_pinned": "Fissato sopra tutte le finestre",
        "postit_status_unpinned": "Libero (può andare sotto le finestre)",
        "postit_btn_alarm": "🚨 SOVRAIMPRESSIONE",
        "postit_alarm_banner": "🚨 È arrivato l'orario stabilito! Controlla i tuoi compiti",
        "postit_alarm_status": "⏰ È scattato l'orario del promemoria!",
        "postit_alarm_notification_body": "È arrivato l'orario stabilito!",
        "postit_press_esc": "Premi Esc per chiudere",
        "postit_btn_done": "✓ Ho Fatto / Chiudi",
        "postit_lbl_links": "Collegamenti Rapidi:",
        "postit_default_link_label": "Apri Collegamento",
        "postit_url_opened": "✓ Apertura '{label}' nel browser completata!",
        "postit_no_message": "Nessun messaggio."
    },
    "en": {
        "app_window_title": "Post-it Reminders - Desktop Manager",
        "app_title": "Post-it Reminders",
        "app_subtitle": "Interactive desktop sticky notes, overlay alarms, and quick action links",
        "language_label": "Language:",

        "daemon_active": "● Daemon: ACTIVE",
        "daemon_inactive": "⚠️ Daemon: INACTIVE",
        "cron_active": "● Cron: ACTIVE",
        "cron_inactive": "⚠️ Cron: INACTIVE",
        "status_service_active_systemd": "● Service: ACTIVE (Systemd)",
        "status_service_active_cron": "● Service: ACTIVE (Cron)",
        "status_service_active_both": "● Service: ACTIVE (Systemd + Cron)",
        "status_service_inactive": "⚠️ Service: INACTIVE",
        "tooltip_service_systemd": "Systemd user daemon is active and checks reminders every minute in background.\nReminders will trigger on time. (Crontab not required on this system).\n\n💡 Click for service details.",
        "tooltip_service_both": "All notification engines active: Systemd daemon and Crontab are synchronized.\n\n💡 Click for service details.",
        "tooltip_service_cron": "Reminders are scheduled via system Crontab service.\n\n💡 Click for service details.",
        "tooltip_service_inactive": "No background monitoring active.\nReminders will not trigger automatically.\n\n💡 Click to sync or start the service.",
        "title_service_status": "Reminder Service Status",

        "status_ready": "Ready.",
        "status_data": "Data: {filename}",

        "form_section_title": "Create or Edit Post-it",
        "form_section_new": "➕ New Reminder",
        "form_section_edit": "✏️ Edit Reminder",
        "badge_new_mode": "NEW",
        "badge_edit_mode": "EDITING",
        "btn_new_reminder": "New Reminder",
        "btn_cancel_edit": "➕ Create New Reminder",
        "btn_cancel_edit_short": "✖ Cancel",
        "btn_preset_format": "⚡ Load Preset: {title} ({time})",
        "btn_preset_empty": "⚡ Quick Preset: (No preset stored - click for info)",
        "lbl_bg_color": "Post-it Background Color:",
        "lbl_time": "Time (HH:MM):",
        "lbl_freq": "Frequency:",
        "freq_weekdays": "Mon-Fri (Weekdays)",
        "freq_daily": "Every Day",
        "freq_short_weekdays": "Mon-Fri",
        "freq_short_daily": "Daily",
        "lbl_title": "Title:",
        "default_title": "Wrap-up Tasks",
        "lbl_formatting": "Message Body (Formatting):",
        "btn_bold": "B",
        "btn_italic": "I",
        "btn_underline": "U",
        "btn_highlight": "🟡 Highlight",
        "btn_bullet": "• Bullet",
        "btn_heading": "Heading H3",
        "btn_clean": "🧹 Clean",
        "default_message_text": "Remember to update your tasks before clocking out.",
        "lbl_links": "Quick Action Links (Optional):",
        "link1_default_label": "Link 1",
        "link2_default_label": "Link 2",
        "btn_save_reminder": "💾 Save Reminder",
        "btn_update_reminder": "💾 Update Changes",
        "btn_save_as_preset": "⭐ Save as Preset",
        "btn_clear": "Clear",

        "table_section_title": "Reminders List",
        "table_active_count": "Active Reminders ({count})",
        "table_double_click_hint": "💡 Double-click for desktop • Ctrl/Shift for multi-select • Del to delete",
        "col_time": "Time",
        "col_freq": "Frequency",
        "col_color": "Color",
        "col_title": "Title",
        "col_links": "Links",
        "links_count": "{count} links",
        "no_links": "—",

        "btn_select_all": "Select All",
        "btn_deselect_all": "Deselect All",
        "menu_select_all": "Select all",
        "btn_desktop": "📌 Put on Desktop",
        "btn_test_alarm": "👁️ Test Alarm Now",
        "btn_set_as_preset": "⭐ Set as Preset",
        "btn_delete": "🗑️ Delete",
        "btn_sync": "🔄 Synchronize",

        "msg_no_preset_title": "No Preset Stored",
        "msg_no_preset_body": "You haven't stored a Quick Preset yet.\n\nHow to create your Preset:\n1. Fill out the form or select a reminder from the table.\n2. Click the '⭐ Save as Preset' button.\n\nYour data will be stored locally in your profile and can be reloaded anytime with a single click!",
        "msg_missing_title_title": "Missing Title",
        "msg_missing_title_body": "Please enter at least a title before saving the Preset.",
        "msg_preset_saved_title": "Preset Saved",
        "msg_preset_saved_body": "Reminder '{title}' has been saved as your Quick Preset!\n\n• It persists on your system even if you delete this reminder from the table.\n• You can instantly autofill it anytime by clicking 'Load Preset'.",
        "msg_preset_row_saved_body": "Reminder '{title}' has been saved as your Quick Preset!\n\n• It persists on your system even if you delete this reminder from the table.\n• Setting another reminder as preset in the future will overwrite these values.",
        "msg_preset_save_error": "Could not save Preset.",
        "msg_no_selection_title": "No Selection",
        "msg_no_selection_preset": "Select a reminder from the table to set as Preset.",
        "msg_no_selection_delete": "Select a reminder to delete.",
        "msg_invalid_time_title": "Invalid Time",
        "msg_invalid_time_body": "Please enter a valid time in HH:MM format (e.g. 18:00).",
        "msg_title_required_title": "Title Required",
        "msg_title_required_body": "Please enter a title for the reminder.",
        "msg_save_success_title": "Saved Successfully",
        "msg_save_success_body": "Reminder '{title}' has been saved and is active on the system.",
        "msg_save_error": "Could not save the reminder.",
        "msg_delete_confirm_title": "Confirm Deletion",
        "msg_delete_confirm_body": "Do you really want to delete '{title}'?",
        "msg_delete_multiple_confirm_title": "Confirm Multiple Deletion",
        "msg_delete_multiple_confirm_body": "Do you really want to delete the {count} selected reminders?",
        "msg_delete_error": "Could not delete reminder.",
        "msg_launch_error_title": "Launch Error",
        "msg_launch_error_body": "Could not launch sticky note on desktop: {error}",
        "msg_sync_title": "Synchronization",
        "msg_error_title": "Error",
        "cron_sync_success": "Crontab synchronized successfully ({count} active jobs).",
        "cron_sync_error": "Error updating crontab: {error}",
        "cron_generic_error": "Generic crontab error: {error}",
        "cron_not_installed": "Crontab is not installed on this system (reminders are managed by background daemon).",
        "cron_not_installed_badge": "○ Cron: NOT REQUIRED",
        "cron_optional_badge": "○ Cron: OPTIONAL",

        "btn_check_update": "🔄 Check Updates",
        "btn_update_available": "🎉 Update to {version}",
        "msg_checking_updates": "Checking for updates...",
        "msg_no_updates_title": "Up to Date",
        "msg_no_updates_body": "Post-it Reminders is already up to date ({version}).",
        "msg_update_found_title": "New Version Available",
        "msg_update_window_title": "Software Update",
        "msg_update_header": "New version available on GitHub!",
        "msg_current_version": "Installed version:",
        "msg_latest_version": "Latest version:",
        "msg_release_notes": "Release notes:",
        "btn_update_now": "🚀 Update Now",
        "btn_view_github": "🌐 View on GitHub",
        "btn_close_dialog": "Later",
        "msg_update_in_progress": "Downloading and installing update...",
        "msg_update_success_title": "Update Complete",
        "msg_update_success_body": "Application updated to version {version}.\n\nPlease restart to use the new features.",
        "msg_update_relaunch_confirm_title": "Update Complete",
        "msg_update_relaunch_confirm_body": "Application updated to version {version}.\n\nDo you want to restart now to apply changes?",
        "status_updated_manual_restart": "✓ Updated to {version}. Please restart the application to apply changes.",
        "msg_update_error_title": "Update Error",
        "msg_update_error_body": "Unable to complete automatic update: {error}\n\nYou can update manually from GitHub.",
        "sync_all_success": "✓ Systemd Daemon and Crontab successfully synchronized!",
        "sync_daemon_success": "✓ Systemd Daemon successfully reloaded (active reminders)!",
        "sync_manual_done": "✓ Scheduler synchronized.",

        "tree_context_edit": "✏️ Edit in form",
        "tree_context_new": "➕ Create new reminder",
        "status_new_mode": "Form reset: new reminder creation mode.",
        "status_edit_mode": "✏️ Editing '{title}'. Click 'New Reminder' to create another from scratch.",
        "status_preset_loaded": "✓ Preset '{title}' loaded into form.",
        "status_preset_stored": "⭐ Preset '{title}' saved successfully!",
        "status_form_cleared": "Form cleared (new reminder mode).",
        "status_reminder_loaded": "Loaded reminder for editing: '{title}'",
        "status_reminder_saved": "✓ Reminder '{title}' saved!",
        "status_reminder_deleted": "Reminder deleted.",
        "status_reminders_deleted_multiple": "✓ Successfully deleted {count} reminders.",
        "status_multiple_selected": "{count} reminders selected. Press Del or click Delete.",
        "status_multiple_desktop_launched": "📌 Placed {count} sticky notes on desktop.",
        "status_desktop_launched": "📌 Sticky note placed on desktop (independent process).",
        "status_alarm_tested": "🚨 Alarm overlay test sent to screen!",

        "postit_default_title": "Reminder",
        "postit_pin_on": "📌 Always on Top",
        "postit_pin_off": "🔓 Normal (Desktop)",
        "postit_status_pinned": "Pinned above all windows",
        "postit_status_unpinned": "Desktop sticky (can go behind windows)",
        "postit_btn_alarm": "🚨 OVERLAY ALARM",
        "postit_alarm_banner": "🚨 Scheduled reminder time arrived! Check your tasks",
        "postit_alarm_status": "⏰ Reminder time has arrived!",
        "postit_alarm_notification_body": "Your scheduled reminder time has arrived!",
        "postit_press_esc": "Press Esc to close",
        "postit_btn_done": "✓ Done / Close",
        "postit_lbl_links": "Quick Action Links:",
        "postit_default_link_label": "Open Link",
        "postit_url_opened": "✓ Opened '{label}' in browser!",
        "postit_no_message": "No message."
    }
}


def get_system_language() -> str:
    """Rileva la lingua di sistema preferita ('it' o 'en')."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val:
            val_clean = val.split(".")[0].lower()
            if val_clean.startswith("it"):
                return "it"
            if val_clean.startswith("en"):
                return "en"
    try:
        loc = locale.getdefaultlocale()[0]
        if loc and loc.lower().startswith("it"):
            return "it"
    except Exception:
        pass
    return "en"


class ConfigStore:
    """Gestione configurazioni persistenti dell'applicazione (lingua, preferenze)."""

    @staticmethod
    def load() -> dict:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    @staticmethod
    def get_language() -> str:
        cfg = ConfigStore.load()
        lang = cfg.get("language")
        if lang in ("it", "en"):
            return lang
        return get_system_language()

    @staticmethod
    def set_language(lang: str) -> bool:
        if lang not in ("it", "en"):
            return False
        cfg = ConfigStore.load()
        cfg["language"] = lang
        APP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


def t(key: str, lang: str = None, **kwargs) -> str:
    """Funzione helper di traduzione con interpolazione di parametri e fallback."""
    if not lang:
        lang = ConfigStore.get_language()
    dict_lang = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = dict_lang.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# Promemoria generici di benvenuto per prima installazione
DEFAULT_WELCOME_REMINDERS = {
    "it": {
        "id": "benvenuto-01",
        "time": "18:00",
        "frequency": "Lun-Ven (Giorni feriali)",
        "title": "Benvenuto in Post-it Reminders!",
        "text": "**Questo è il tuo primo post-it:**\n• Modifica orario, frequenza e colori a tuo piacimento.\n• Inserisci collegamenti rapidi ai tuoi siti preferiti.\n• Clicca su **⭐ Salva come Preset** per memorizzare il tuo template personale e riutilizzarlo con un click!",
        "color": "yellow",
        "links": [],
        "enabled": True
    },
    "en": {
        "id": "benvenuto-01",
        "time": "18:00",
        "frequency": "Mon-Fri (Weekdays)",
        "title": "Welcome to Post-it Reminders!",
        "text": "**This is your first sticky note:**\n• Customize time, frequency, and colors as you like.\n• Add quick action links to your favorite tools.\n• Click **⭐ Save as Preset** to store your personal template and reuse it anytime!",
        "color": "yellow",
        "links": [],
        "enabled": True
    }
}
DEFAULT_WELCOME_REMINDER = DEFAULT_WELCOME_REMINDERS["it"]


class PresetStore:
    """Gestione del Preset Rapido configurabile e indipendente."""

    @staticmethod
    def load() -> dict | None:
        if PRESET_FILE.exists():
            try:
                with open(PRESET_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("title"):
                        return data
            except Exception as e:
                print(f"[Warning] Impossibile leggere preset.json: {e}")
        return None

    @staticmethod
    def save(preset_data: dict) -> bool:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(PRESET_FILE, "w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[Error] Impossibile salvare preset.json: {e}")
            return False

    @staticmethod
    def clear() -> bool:
        try:
            if PRESET_FILE.exists():
                PRESET_FILE.unlink()
            return True
        except Exception:
            return False


def get_system_font_family() -> str:
    """Rileva la migliore famiglia di font installata sul sistema Linux."""
    try:
        available = font.families()
        for candidate in ["Ubuntu", "Inter", "Cantarell", "Noto Sans", "DejaVu Sans", "Liberation Sans", "Sans"]:
            if candidate in available:
                return candidate
    except Exception:
        pass
    return "Sans"


def configure_dialog_fonts(root_widget=None, sys_font: str = None):
    """
    Configura una tipografia compatta, elegante e proporzionata per tutti gli alert, popup e messagebox Tkinter.
    Riduce la dimensione predefinita dei testi di alert (che in Tkinter è 12pt grassetto)
    ad una dimensione compatta (8pt normale), evitando che i messaggi appaiano sproporzionati o enormi.
    """
    if not sys_font:
        sys_font = get_system_font_family()

    # Riconfigurazione font di sistema Tkinter usati dai dialoghi
    for name, sz, wt in [
        ("TkCaptionFont", 8, "normal"),       # Testo principale messaggi in tk_messageBox (era 12 bold!)
        ("TkDefaultFont", 8, "normal"),       # Testo secondario e widget standard
        ("TkHeadingFont", 9, "bold"),         # Intestazioni
        ("TkTooltipFont", 8, "normal"),       # Tooltip
        ("TkSmallCaptionFont", 8, "normal"),  # Didascalie piccole
        ("TkIconFont", 8, "normal"),          # Testo icone
        ("TkMenuFont", 8, "normal"),          # Voci di menu
    ]:
        try:
            f = font.nametofont(name)
            f.configure(family=sys_font, size=sz, weight=wt)
        except Exception:
            pass

    # Impostazione opzioni del database Tcl per tk_messageBox (msgbox.tcl)
    if root_widget:
        try:
            root_widget.option_add("*Dialog.msg.font", f"{sys_font} 8 normal")
            root_widget.option_add("*Dialog.dtl.font", f"{sys_font} 8 normal")
            root_widget.option_add("*Dialog.msg.wrapLength", "420")
            root_widget.option_add("*Dialog.dtl.wrapLength", "420")
            root_widget.option_add("*Dialog*font", f"{sys_font} 8 normal")
            root_widget.option_add("*Dialog*Label*font", f"{sys_font} 8 normal")
            root_widget.option_add("*Dialog*Button*font", f"{sys_font} 8 normal")
            root_widget.option_add("*Message*font", f"{sys_font} 8 normal")
        except Exception:
            pass


def apply_app_icon(window):
    """Imposta le icone della finestra in tutte le risoluzioni standard per Dock GNOME/KDE e Taskbar."""
    cached_images = []
    for size in [256, 128, 64, 48, 32]:
        p = ICONS_DIR / f"{size}x{size}" / "apps" / "postit-manager.png"
        if p.exists():
            try:
                img = tk.PhotoImage(file=str(p))
                cached_images.append(img)
            except Exception:
                pass

    if not cached_images and ICON_PNG.exists():
        try:
            cached_images.append(tk.PhotoImage(file=str(ICON_PNG)))
        except Exception:
            pass

    if cached_images:
        try:
            window.iconphoto(True, *cached_images)
            window._app_icons_ref = cached_images
        except Exception:
            pass


def send_system_notification(title: str, message: str, urgency: str = "critical", app_name: str = None):
    """Invia una notifica di sistema desktop cross-desktop tramite libnotify / notify-send se disponibile."""
    if not shutil.which("notify-send"):
        return
    icon_name = "postit-manager"
    clean_msg = re.sub(r"(\*\*|\*|__|\=\=|###\s*)", "", message)
    if not app_name:
        app_name = t("app_title")
    try:
        subprocess.Popen(
            ["notify-send", "-u", urgency, "-i", icon_name, "-a", app_name, title, clean_msg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def open_url(url: str):
    """Apre un URL nel browser predefinito di sistema."""
    clean_url = url.strip()
    if not clean_url:
        return
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        clean_url = "https://" + clean_url
    try:
        subprocess.Popen(
            ["xdg-open", clean_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        webbrowser.open(clean_url)


def is_pid_alive(pid: int) -> bool:
    """Verifica se un processo con dato PID è attualmente attivo nel sistema."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except Exception:
        return False


def signal_existing_reminder(rem_id: str, is_alarm: bool = False) -> bool:
    """
    Controlla se esiste già un'istanza attiva della finestra per questo promemoria.
    Se attiva, invia SIGUSR1 per portarla in primo piano / allarme e ritorna True.
    Altrimenti ritorna False.
    """
    lock_file = RUN_DIR / f"window_{rem_id}.active"
    if not lock_file.exists():
        return False
    try:
        pid_str = lock_file.read_text().strip()
        if pid_str.isdigit():
            pid = int(pid_str)
            if is_pid_alive(pid):
                if is_alarm:
                    try:
                        os.kill(pid, signal.SIGUSR1)
                    except Exception:
                        pass
                return True
            else:
                try:
                    lock_file.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass
    return False


def acquire_reminder_lock(rem_id: str, is_alarm: bool = False) -> tuple[bool, Path]:
    """
    Tenta di acquisire in modo atomico (O_CREAT | O_EXCL) il lockfile per il promemoria.
    Se un'altra istanza è già attiva:
      - Invia SIGUSR1 se è richiesta la modalità allarme.
      - Ritorna (False, lock_path).
    Se il file esiste ma il PID registrato non è più attivo (stale lock):
      - Rimuove il lock obsoleto e riprova l'acquisizione atomica.
    Ritorna (True, lock_path) se il lock è stato acquisito con successo.
    """
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = RUN_DIR / f"window_{rem_id}.active"
    current_pid = os.getpid()

    for _ in range(2):
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w") as f:
                f.write(str(current_pid))
            return True, lock_file
        except FileExistsError:
            try:
                pid_str = lock_file.read_text().strip()
                if pid_str.isdigit():
                    pid = int(pid_str)
                    if is_pid_alive(pid):
                        if is_alarm:
                            try:
                                os.kill(pid, signal.SIGUSR1)
                            except Exception:
                                pass
                        return False, lock_file
            except Exception:
                pass

            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass

    return True, lock_file


def release_reminder_lock(lock_file: Path):
    """Rilascia il lockfile solo se appartiene al processo corrente."""
    try:
        if lock_file and lock_file.exists():
            content = lock_file.read_text().strip()
            if content == str(os.getpid()):
                lock_file.unlink(missing_ok=True)
    except Exception:
        pass


class ReminderStore:
    """Gestione dati JSON persistente con scrittura atomica sicura."""

    @staticmethod
    def ensure_storage():
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not REMINDERS_FILE.exists():
            lang = ConfigStore.get_language()
            welcome = DEFAULT_WELCOME_REMINDERS.get(lang, DEFAULT_WELCOME_REMINDERS["en"])
            ReminderStore.save_all([welcome])

    @staticmethod
    def load_all() -> list:
        ReminderStore.ensure_storage()
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[Warning] Impossibile leggere {REMINDERS_FILE}: {e}")
        return []

    @staticmethod
    def save_all(reminders: list) -> bool:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = REMINDERS_FILE.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(reminders, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, REMINDERS_FILE)
            return True
        except Exception as e:
            print(f"[Error] Errore nel salvataggio su {REMINDERS_FILE}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            return False

    @staticmethod
    def get_by_id(rem_id: str) -> dict | None:
        for rem in ReminderStore.load_all():
            if rem.get("id") == rem_id:
                return rem
        return None

    @staticmethod
    def add_or_update(reminder: dict) -> bool:
        reminders = ReminderStore.load_all()
        rem_id = reminder.get("id")
        if not rem_id:
            rem_id = f"rem-{uuid.uuid4().hex[:8]}"
            reminder["id"] = rem_id

        updated = False
        for i, existing in enumerate(reminders):
            if existing.get("id") == rem_id:
                reminders[i] = reminder
                updated = True
                break
        if not updated:
            reminders.append(reminder)

        return ReminderStore.save_all(reminders)

    @staticmethod
    def delete_by_id(rem_id: str) -> bool:
        reminders = ReminderStore.load_all()
        new_list = [r for r in reminders if r.get("id") != rem_id]
        if len(new_list) != len(reminders):
            return ReminderStore.save_all(new_list)
        return False


class CronManager:
    """Gestione sincronizzazione atomica con Crontab con tolleranza ai sistemi senza cron (es. Fedora default)."""

    @staticmethod
    def is_crontab_available() -> bool:
        """Verifica se il comando crontab è presente nel sistema."""
        return shutil.which("crontab") is not None

    @staticmethod
    def is_cron_service_active() -> bool:
        if not CronManager.is_crontab_available():
            return False
        for srv in ["cron", "crond"]:
            try:
                res = subprocess.run(["systemctl", "is-active", srv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.stdout.strip() == "active":
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def is_daemon_service_active() -> bool:
        try:
            res = subprocess.run(["systemctl", "--user", "is-active", "postit-daemon"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return res.stdout.strip() == "active"
        except Exception:
            return False

    @staticmethod
    def get_current_crontab() -> str:
        if not CronManager.is_crontab_available():
            return ""
        try:
            res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass
        return ""

    @staticmethod
    def sync_reminders(reminders: list, lang: str = None) -> tuple[bool, str]:
        if not lang:
            lang = ConfigStore.get_language()

        if not CronManager.is_crontab_available():
            return False, t("cron_not_installed", lang)

        try:
            current_crontab = CronManager.get_current_crontab()
            lines = current_crontab.splitlines()

            filtered_lines = []
            in_managed_block = False
            for line in lines:
                if line.strip() == CRON_BLOCK_START:
                    in_managed_block = True
                    continue
                if line.strip() == CRON_BLOCK_END:
                    in_managed_block = False
                    continue
                if in_managed_block or CRON_MARKER in line:
                    continue
                filtered_lines.append(line)

            runner_path = str(RUNNER_SH.resolve()) if RUNNER_SH.exists() else str(Path(__file__).resolve())
            new_cron_jobs = []
            active_reminders = [r for r in reminders if r.get("enabled", True)]

            for rem in active_reminders:
                time_str = rem.get("time", "18:00").strip()
                match = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", time_str)
                if not match:
                    continue
                hour, minute = int(match.group(1)), int(match.group(2))

                freq = rem.get("frequency", "Lun-Ven (Giorni feriali)")
                dow = "1-5" if any(k in freq for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"]) else "*"

                cmd = f"{runner_path} --popup --alarm --id {rem['id']}"
                job_line = f"{minute} {hour} * * {dow} {cmd} {CRON_MARKER}"
                new_cron_jobs.append(job_line)

            all_lines = [l for l in filtered_lines if l.strip()]
            if new_cron_jobs:
                all_lines.append(CRON_BLOCK_START)
                all_lines.extend(new_cron_jobs)
                all_lines.append(CRON_BLOCK_END)

            new_crontab_content = "\n".join(all_lines) + ("\n" if all_lines else "")

            if not new_crontab_content.strip():
                subprocess.run(["crontab", "-r"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(
                    ["crontab", "-"],
                    input=new_crontab_content,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
            return True, t("cron_sync_success", lang, count=len(new_cron_jobs))
        except FileNotFoundError:
            return False, t("cron_not_installed", lang)
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() or str(e)
            return False, t("cron_sync_error", lang, error=err)
        except Exception as e:
            return False, t("cron_generic_error", lang, error=str(e))


class UpdateManager:
    """Gestione verifica e installazione aggiornamenti tramite GitHub Releases."""

    @staticmethod
    def parse_version(ver_str: str) -> tuple:
        if not ver_str:
            return (0, 0, 0)
        clean = re.sub(r"^[^\d]*", "", str(ver_str).strip())
        parts = []
        for p in clean.split("."):
            try:
                m = re.match(r"^\d+", p)
                parts.append(int(m.group(0)) if m else 0)
            except Exception:
                parts.append(0)
        return tuple(parts)

    @staticmethod
    def check_for_updates() -> tuple[bool, dict | None, str]:
        """
        Controlla l'ultima release disponibile su GitHub.
        Ritorna: (has_update: bool, release_info: dict | None, latest_tag: str)
        Include fallback a raw.githubusercontent.com in caso di rate-limit API o problemi di rete.
        """
        current_ver = UpdateManager.parse_version(APP_VERSION)
        api_err = None

        # 1. Tentativo primario con GitHub Releases API
        try:
            req = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={
                    "User-Agent": "PostitReminders-App",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    latest_tag = data.get("tag_name", "").strip()
                    latest_ver = UpdateManager.parse_version(latest_tag)
                    has_update = latest_ver > current_ver
                    return has_update, data, latest_tag
                else:
                    api_err = f"HTTP {resp.status}"
        except Exception as e:
            api_err = str(e)

        # 2. Fallback resiliente via raw.githubusercontent.com (evita blocchi da 403 rate-limit o API down)
        try:
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/src/postit_manager.py"
            req_raw = urllib.request.Request(raw_url, headers={"User-Agent": "PostitReminders-App"})
            with urllib.request.urlopen(req_raw, timeout=8) as resp:
                if resp.status == 200:
                    chunk = resp.read(4096).decode("utf-8", errors="ignore")
                    m = re.search(r'APP_VERSION\s*=\s*[\"\']([^\"\']+)[\"\']', chunk)
                    if m:
                        remote_ver_str = m.group(1).strip()
                        remote_ver = UpdateManager.parse_version(remote_ver_str)
                        if remote_ver > current_ver:
                            tag_str = f"v{remote_ver_str}" if not remote_ver_str.startswith("v") else remote_ver_str
                            synthetic_release = {
                                "tag_name": tag_str,
                                "name": f"v{remote_ver_str}",
                                "body": f"Nuova versione {remote_ver_str} disponibile su GitHub (rilevata tramite sorgente)."
                            }
                            return True, synthetic_release, tag_str
                        else:
                            return False, None, remote_ver_str
        except Exception:
            pass

        return False, None, api_err or "Impossibile contattare GitHub"

    @staticmethod
    def perform_automatic_update(release_info: dict) -> tuple[bool, str]:
        """
        Scarica e installa l'ultima versione dell'applicazione.
        Tenta prima l'aggiornamento tramite git se presente un repository locale valido,
        altrimenti scarica e aggiorna sia i binari utente (~/.local/bin) che lo script in esecuzione.
        """
        tag = release_info.get("tag_name", "main")
        err_details = []

        # 1. Tentativo con git se esiste un repository locale
        candidate_git_dirs = [
            Path(__file__).resolve().parent.parent,
            USER_HOME / "postit-reminders"
        ]
        for g_dir in candidate_git_dirs:
            if (g_dir / ".git").is_dir() and (g_dir / "install.sh").exists():
                try:
                    subprocess.run(
                        ["git", "fetch", "--all", "--tags"],
                        cwd=str(g_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=20,
                        check=True
                    )
                    checked_out = False
                    for target_ref in [tag, f"tags/{tag}", "main", "origin/main"]:
                        try:
                            subprocess.run(
                                ["git", "checkout", "-f", target_ref],
                                cwd=str(g_dir),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=15,
                                check=True
                            )
                            if target_ref in ["main", "origin/main"]:
                                subprocess.run(
                                    ["git", "reset", "--hard", "origin/main"],
                                    cwd=str(g_dir),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    timeout=15,
                                    check=True
                                )
                            checked_out = True
                            break
                        except Exception:
                            continue

                    if checked_out:
                        try:
                            subprocess.run(
                                ["bash", str(g_dir / "install.sh")],
                                cwd=str(g_dir),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=45,
                                check=True
                            )
                        except Exception:
                            bin_dir = USER_HOME / ".local" / "bin"
                            bin_dir.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(g_dir / "src" / "postit_manager.py", bin_dir / "postit_manager.py")
                            shutil.copy2(g_dir / "src" / "postit-runner.sh", bin_dir / "postit-runner.sh")
                            (bin_dir / "postit_manager.py").chmod(0o755)
                            (bin_dir / "postit-runner.sh").chmod(0o755)

                        return True, f"Aggiornato con successo da repository locale ({tag})."
                except Exception as ex_git:
                    err_details.append(f"Git: {ex_git}")

        # 2. Aggiornamento diretto da GitHub Raw
        try:
            def fetch_file(subpath: str) -> str:
                candidates = [tag, tag.lstrip("v"), f"v{tag}", "main"]
                seen = set()
                last_err = None
                for ref in candidates:
                    if ref in seen:
                        continue
                    seen.add(ref)
                    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{ref}/{subpath}"
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "PostitReminders-App"})
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            if resp.status == 200:
                                return resp.read().decode("utf-8")
                    except Exception as e_ref:
                        last_err = e_ref
                raise RuntimeError(f"Impossibile scaricare {subpath}: {last_err}")

            py_code = fetch_file("src/postit_manager.py")
            sh_code = fetch_file("src/postit-runner.sh")

            bin_dir = USER_HOME / ".local" / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)

            tmp_py = bin_dir / "postit_manager.py.tmp"
            tmp_py.write_text(py_code, encoding="utf-8")
            tmp_py.chmod(0o755)

            # Controllo sintassi Python prima della sostituzione
            res_test = subprocess.run([sys.executable, "-m", "py_compile", str(tmp_py)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res_test.returncode != 0:
                tmp_py.unlink(missing_ok=True)
                return False, "File scaricato non valido (errore di compilazione Python)."

            target_py = bin_dir / "postit_manager.py"
            tmp_py.replace(target_py)
            target_py.chmod(0o755)

            target_sh = bin_dir / "postit-runner.sh"
            target_sh.write_text(sh_code, encoding="utf-8")
            target_sh.chmod(0o755)

            symlink_mgr = bin_dir / "postit-manager"
            try:
                if symlink_mgr.is_symlink() or not symlink_mgr.exists():
                    symlink_mgr.unlink(missing_ok=True)
                    symlink_mgr.symlink_to(target_sh)
            except Exception:
                pass

            # Aggiorna anche il file attualmente in esecuzione se diverso da ~/.local/bin/postit_manager.py
            current_exec = Path(__file__).resolve()
            if current_exec != target_py and current_exec.is_file():
                try:
                    current_exec.write_text(py_code, encoding="utf-8")
                    current_exec.chmod(0o755)
                    runner_sib = current_exec.parent / "postit-runner.sh"
                    if runner_sib.is_file():
                        runner_sib.write_text(sh_code, encoding="utf-8")
                        runner_sib.chmod(0o755)
                except Exception:
                    pass

            # Aggiorna anche cartella clone standard ~/postit-reminders se presente
            std_clone_py = USER_HOME / "postit-reminders" / "src" / "postit_manager.py"
            if std_clone_py.is_file() and std_clone_py != target_py and std_clone_py != current_exec:
                try:
                    std_clone_py.write_text(py_code, encoding="utf-8")
                    std_clone_py.chmod(0o755)
                    (USER_HOME / "postit-reminders" / "src" / "postit-runner.sh").write_text(sh_code, encoding="utf-8")
                except Exception:
                    pass

            if CronManager.is_daemon_service_active():
                try:
                    subprocess.run(["systemctl", "--user", "restart", "postit-daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

            return True, f"Aggiornato con successo alla versione {tag} in {bin_dir}."
        except Exception as e:
            msg = f"{e}"
            if err_details:
                msg += f" (Dettagli: {'; '.join(err_details)})"
            return False, f"Errore durante l'aggiornamento: {msg}"


class ToolTip:
    """Semplice e affidabile tooltip Tkinter per visualizzare spiegazioni al passaggio del mouse."""
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def set_text(self, text):
        self.text = text

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            try:
                tw.attributes("-topmost", True)
            except Exception:
                pass
            label = tk.Label(
                tw,
                text=self.text,
                justify=tk.LEFT,
                background="#0F172A",
                foreground="#F8FAFC",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Sans", 8),
                padx=8,
                pady=6,
                wraplength=380
            )
            label.pack()
        except Exception:
            pass

    def hide_tip(self, event=None):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


def render_markdown_release_notes(text_widget: tk.Text, raw_text: str, sys_font: str):
    """Formatta e renderizza in modo professionale le note di rilascio GitHub in un widget Text.
    Pulisce i caratteri speciali, normalizza line-breaks, converte elementi Markdown
    (intestazioni, elenchi puntati/numerati, grassetto, corsivo, codice) e crea hyperlink cliccabili.
    """
    import html
    text_widget.configure(state=tk.NORMAL)
    text_widget.delete("1.0", tk.END)

    if not raw_text or not raw_text.strip():
        text_widget.insert(tk.END, "Nessuna nota di rilascio fornita.")
        text_widget.configure(state=tk.DISABLED)
        return

    # Normalizzazione codifiche, ritorni a capo e caratteri speciali
    cleaned = raw_text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    cleaned = html.unescape(cleaned)

    # Configurazione tag
    f_h1 = (sys_font, 11, "bold")
    f_h2 = (sys_font, 10, "bold")
    f_h3 = (sys_font, 9, "bold")
    f_body = (sys_font, 9)
    f_bold = (sys_font, 9, "bold")
    f_italic = (sys_font, 9, "italic")
    f_code = ("Monospace", 8)
    f_quote = (sys_font, 8, "italic")

    text_widget.tag_configure("h1", font=f_h1, foreground="#1E3A8A", spacing1=8, spacing3=3)
    text_widget.tag_configure("h2", font=f_h2, foreground="#1D4ED8", spacing1=6, spacing3=2)
    text_widget.tag_configure("h3", font=f_h3, foreground="#2563EB", spacing1=5, spacing3=2)
    text_widget.tag_configure("body", font=f_body, foreground="#334155", spacing1=1, spacing3=2)
    text_widget.tag_configure("num_item", font=f_body, foreground="#1E293B", lmargin1=8, lmargin2=22, spacing1=3, spacing3=2)
    text_widget.tag_configure("bullet_item", font=f_body, foreground="#334155", lmargin1=18, lmargin2=32, spacing1=2, spacing3=2)
    text_widget.tag_configure("subbullet_item", font=f_body, foreground="#475569", lmargin1=28, lmargin2=42, spacing1=2, spacing3=2)
    text_widget.tag_configure("quote_block", font=f_quote, foreground="#475569", background="#F8FAFC", lmargin1=20, lmargin2=20, spacing1=3, spacing3=3)
    text_widget.tag_configure("separator", font=(sys_font, 4), foreground="#CBD5E1")
    text_widget.tag_configure("bold", font=f_bold, foreground="#0F172A")
    text_widget.tag_configure("italic", font=f_italic, foreground="#475569")
    text_widget.tag_configure("code", font=f_code, background="#E2E8F0", foreground="#0F172A")

    inline_re = re.compile(
        r"(\[(?P<link_text>[^\]]+)\]\((?P<link_url>https?://[^\)]+)\))"
        r"|(?P<raw_url>https?://[^\s<>]+)"
        r"|(\*\*(?P<bold_text>[^*]+?)\*\*)"
        r"|(`(?P<code_text>[^`]+?)`)"
        r"|(\*(?P<italic_text>[^*]+?)\*)"
        r"|(_(?P<italic_u_text>[^_]+?)_)"
    )

    link_counter = 0

    def insert_inline(line_text, base_tag):
        nonlocal link_counter
        last_idx = 0
        for m in inline_re.finditer(line_text):
            start, end = m.span()
            if start > last_idx:
                chunk = line_text[last_idx:start]
                text_widget.insert(tk.END, chunk, (base_tag,))

            if m.group("link_text"):
                link_counter += 1
                ltag = f"url_link_{link_counter}"
                url = m.group("link_url")
                text_widget.tag_configure(ltag, font=(sys_font, 9, "underline"), foreground="#2563EB")
                text_widget.tag_bind(ltag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
                text_widget.tag_bind(ltag, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
                text_widget.tag_bind(ltag, "<Leave>", lambda e: text_widget.config(cursor=""))
                text_widget.insert(tk.END, m.group("link_text"), (base_tag, ltag))
            elif m.group("raw_url"):
                link_counter += 1
                ltag = f"url_link_{link_counter}"
                raw_u = m.group("raw_url")
                clean_u = raw_u.rstrip(".,;:)\"\'")
                punct = raw_u[len(clean_u):]
                text_widget.tag_configure(ltag, font=(sys_font, 9, "underline"), foreground="#2563EB")
                text_widget.tag_bind(ltag, "<Button-1>", lambda e, u=clean_u: webbrowser.open(u))
                text_widget.tag_bind(ltag, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
                text_widget.tag_bind(ltag, "<Leave>", lambda e: text_widget.config(cursor=""))
                text_widget.insert(tk.END, clean_u, (base_tag, ltag))
                if punct:
                    text_widget.insert(tk.END, punct, (base_tag,))
            elif m.group("bold_text"):
                text_widget.insert(tk.END, m.group("bold_text"), (base_tag, "bold"))
            elif m.group("code_text"):
                text_widget.insert(tk.END, f" {m.group('code_text')} ", (base_tag, "code"))
            elif m.group("italic_text"):
                text_widget.insert(tk.END, m.group("italic_text"), (base_tag, "italic"))
            elif m.group("italic_u_text"):
                text_widget.insert(tk.END, m.group("italic_u_text"), (base_tag, "italic"))

            last_idx = end

        if last_idx < len(line_text):
            text_widget.insert(tk.END, line_text[last_idx:], (base_tag,))

    lines = cleaned.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        l_indent = len(line) - len(line.lstrip())

        if not stripped:
            text_widget.insert(tk.END, "\n", ("body",))
            continue

        if stripped in ["---", "***", "___"]:
            text_widget.insert(tk.END, "─" * 45 + "\n", ("separator",))
            continue

        if stripped.startswith("### "):
            text_widget.insert(tk.END, "▫ " + stripped[4:] + "\n", ("h3",))
            continue
        elif stripped.startswith("## "):
            text_widget.insert(tk.END, stripped[3:] + "\n", ("h2",))
            continue
        elif stripped.startswith("# "):
            text_widget.insert(tk.END, stripped[2:] + "\n", ("h1",))
            continue

        if stripped.startswith(("│", ">")):
            quote_content = stripped.lstrip("│> ").strip()
            insert_inline(quote_content, "quote_block")
            text_widget.insert(tk.END, "\n", ("quote_block",))
            continue

        num_match = re.match(r"^(\d+\.)\s+(.*)", stripped)
        if num_match:
            num_prefix, rest = num_match.groups()
            text_widget.insert(tk.END, f"{num_prefix} ", ("num_item", "bold"))
            insert_inline(rest, "num_item")
            text_widget.insert(tk.END, "\n", ("num_item",))
            continue

        bullet_match = re.match(r"^([•\*\-\+])\s+(.*)", stripped)
        if bullet_match:
            _, rest = bullet_match.groups()
            tag = "subbullet_item" if l_indent >= 4 else "bullet_item"
            bullet_sym = "▪ " if l_indent >= 4 else "• "
            text_widget.insert(tk.END, bullet_sym, (tag, "bold"))
            insert_inline(rest, tag)
            text_widget.insert(tk.END, "\n", (tag,))
            continue

        insert_inline(stripped, "body")
        text_widget.insert(tk.END, "\n", ("body",))

    text_widget.configure(state=tk.DISABLED)


def render_formatted_text(text_widget: tk.Text, raw_text: str, theme: dict):
    """Renderizza testo formattato in stile Markdown all'interno del Text widget."""
    sys_font = get_system_font_family()
    text_widget.configure(state=tk.NORMAL)
    text_widget.delete("1.0", tk.END)

    f_base = font.Font(family=sys_font, size=10)
    f_bold = font.Font(family=sys_font, size=10, weight="bold")
    f_italic = font.Font(family=sys_font, size=10, slant="italic")
    f_header = font.Font(family=sys_font, size=11, weight="bold")

    text_widget.tag_configure("base", font=f_base, foreground=theme["text"])
    text_widget.tag_configure("bold", font=f_bold, foreground=theme["title"])
    text_widget.tag_configure("italic", font=f_italic, foreground=theme["text"])
    text_widget.tag_configure("underline", underline=1, foreground=theme["text"])
    text_widget.tag_configure("highlight", background=theme["highlight"], foreground="#1E293B", font=f_bold)
    text_widget.tag_configure("header", font=f_header, foreground=theme["title"], spacing3=4)
    text_widget.tag_configure("bullet", lmargin1=10, lmargin2=22, font=f_base, foreground=theme["text"])

    lines = raw_text.splitlines()
    for line_idx, line in enumerate(lines):
        if line_idx > 0:
            text_widget.insert(tk.END, "\n")

        if line.startswith("### "):
            text_widget.insert(tk.END, line[4:], "header")
            continue

        is_bullet = False
        content = line
        if line.startswith("• ") or line.startswith("- "):
            is_bullet = True
            content = "• " + line[2:]

        pattern = re.compile(r"(\*\*[^*]+?\*\*|\*[^*]+?\*|__[^_]+?__|==[^=]+?==)")
        parts = pattern.split(content)

        for part in parts:
            if not part:
                continue
            tags = ["bullet"] if is_bullet else ["base"]
            if part.startswith("**") and part.endswith("**") and len(part) >= 4:
                inner = part[2:-2]
                text_widget.insert(tk.END, inner, (*tags, "bold"))
            elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
                inner = part[1:-1]
                text_widget.insert(tk.END, inner, (*tags, "italic"))
            elif part.startswith("__") and part.endswith("__") and len(part) >= 4:
                inner = part[2:-2]
                text_widget.insert(tk.END, inner, (*tags, "underline"))
            elif part.startswith("==") and part.endswith("==") and len(part) >= 4:
                inner = part[2:-2]
                text_widget.insert(tk.END, inner, (*tags, "highlight"))
            else:
                text_widget.insert(tk.END, part, tuple(tags))

    text_widget.configure(state=tk.DISABLED)


class PostitWindow:
    """Finestra Post-it autonoma con pulsanti d'azione sempre visibili, bilingue e auto-sovraimpressione."""

    def __init__(self, reminder: dict, is_alarm_mode: bool = False, parent=None, lang: str = None, lock_file: Path = None):
        self.reminder = reminder
        self.is_alarm = is_alarm_mode
        self.parent = parent
        self.is_toplevel = parent is not None
        self.lang = lang or ConfigStore.get_language()

        rem_id = self.reminder.get("id", "default")
        if lock_file is not None:
            self.lock_file = lock_file
        else:
            _, self.lock_file = acquire_reminder_lock(rem_id, is_alarm=self.is_alarm)

        if self.is_toplevel:
            self.root = tk.Toplevel(parent)
        else:
            # Classi finestra distinte per evitare che GNOME Shell / Wayland raggruppi note da desktop e allarmi sollevandoli insieme
            win_class = "postit-alarm-popup" if self.is_alarm else "postit-desktop-note"
            self.root = tk.Tk(className=win_class)

        # Registrazione signal handler per risveglio allarme runtime da parte di demone o cron
        try:
            signal.signal(signal.SIGUSR1, self._handle_sigusr1)
        except Exception:
            pass

        color_key = self.reminder.get("color", "yellow")
        self.theme = COLOR_THEMES.get(color_key, COLOR_THEMES["yellow"])
        self.sys_font = get_system_font_family()
        configure_dialog_fonts(self.root, self.sys_font)
        self.is_pinned = self.is_alarm

        self._setup_window()
        self._build_ui()
        self._schedule_time_check()

        if self.is_alarm:
            self.trigger_alarm_mode()
        else:
            self._apply_pin_state()

    def _setup_window(self):
        title = self.reminder.get("title", t("postit_default_title", self.lang))
        self.root.title(f"📌 {title}")
        self.root.geometry("480x440")
        self.root.minsize(440, 380)
        self.root.configure(bg=self.theme["bg"])

        apply_app_icon(self.root)

        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w, h = 480, 440
        x = max(40, screen_w - w - 60)
        y = max(60, (screen_h - h) // 4)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda e: self.close())

    def _build_ui(self):
        self.outer_border = tk.Frame(self.root, bg=self.theme["border"], padx=2, pady=2)
        self.outer_border.pack(fill=tk.BOTH, expand=True)

        self.main_card = tk.Frame(self.outer_border, bg=self.theme["bg"])
        self.main_card.pack(fill=tk.BOTH, expand=True)

        # 1. HEADER
        self.header_frame = tk.Frame(self.main_card, bg=self.theme["header"], padx=14, pady=10)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)

        top_row = tk.Frame(self.header_frame, bg=self.theme["header"])
        top_row.pack(fill=tk.X)

        self.lbl_pin_icon = tk.Label(top_row, text="📌", bg=self.theme["header"], font=("Sans", 14))
        self.lbl_pin_icon.pack(side=tk.LEFT, padx=(0, 6))

        title_text = self.reminder.get("title", t("postit_default_title", self.lang))
        self.lbl_title = tk.Label(
            top_row,
            text=title_text,
            bg=self.theme["header"],
            fg=self.theme["title"],
            font=(self.sys_font, 11, "bold"),
            anchor="w"
        )
        self.lbl_title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_pin = tk.Button(
            top_row,
            text=t("postit_pin_on", self.lang) if self.is_pinned else t("postit_pin_off", self.lang),
            font=(self.sys_font, 8, "bold"),
            bg="#FFFFFF",
            fg=self.theme["title"],
            relief=tk.FLAT,
            cursor="hand2",
            padx=6,
            pady=3,
            command=self.toggle_pin
        )
        self.btn_pin.pack(side=tk.RIGHT, padx=(4, 0))

        time_text = self.reminder.get("time", "18:00")
        self.badge_frame = tk.Frame(
            top_row,
            bg=self.theme["badge_bg"],
            highlightbackground=self.theme["badge_border"],
            highlightthickness=1,
            padx=5,
            pady=2
        )
        self.badge_frame.pack(side=tk.RIGHT, padx=(0, 4))

        self.lbl_time = tk.Label(
            self.badge_frame,
            text=f"⏰ {time_text}",
            bg=self.theme["badge_bg"],
            fg=self.theme["badge_fg"],
            font=(self.sys_font, 8, "bold")
        )
        self.lbl_time.pack()

        sep = tk.Frame(self.main_card, bg=self.theme["border"], height=1)
        sep.pack(fill=tk.X)

        # Banner Allarme
        self.alarm_banner = tk.Frame(self.main_card, bg="#EF4444", padx=8, pady=4)
        self.lbl_alarm_banner = tk.Label(
            self.alarm_banner,
            text=t("postit_alarm_banner", self.lang),
            bg="#EF4444",
            fg="#FFFFFF",
            font=(self.sys_font, 9, "bold")
        )
        self.lbl_alarm_banner.pack()

        # 2. FOOTER
        footer_frame = tk.Frame(self.main_card, bg=self.theme["bg"], padx=14, pady=8)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_lbl = tk.Label(
            footer_frame,
            text=t("postit_press_esc", self.lang),
            bg=self.theme["bg"],
            fg="#64748B",
            font=(self.sys_font, 8, "italic")
        )
        self.status_lbl.pack(side=tk.LEFT)

        btn_done = tk.Button(
            footer_frame,
            text=t("postit_btn_done", self.lang),
            bg="#10B981",
            fg="#FFFFFF",
            activebackground="#059669",
            activeforeground="#FFFFFF",
            font=(self.sys_font, 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=4,
            command=self.close
        )
        btn_done.pack(side=tk.RIGHT)

        # 3. COLLEGAMENTI RAPIDI
        links = self.reminder.get("links", [])
        valid_links = [l for l in links if l.get("url", "").strip()]

        if valid_links:
            self.links_frame = tk.Frame(self.main_card, bg=self.theme["bg"], padx=16, pady=4)
            self.links_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 8))

            lbl_actions = tk.Label(
                self.links_frame,
                text=t("postit_lbl_links", self.lang),
                bg=self.theme["bg"],
                fg="#334155",
                font=(self.sys_font, 9, "bold"),
                anchor="w"
            )
            lbl_actions.pack(fill=tk.X, pady=(0, 6))

            for link in valid_links:
                label_txt = link.get("label", "").strip() or t("postit_default_link_label", self.lang)
                url_target = link.get("url", "").strip()

                btn_link = tk.Button(
                    self.links_frame,
                    text=f"🌐   {label_txt}   ↗",
                    bg="#2563EB",
                    fg="#FFFFFF",
                    activebackground="#1D4ED8",
                    activeforeground="#FFFFFF",
                    font=(self.sys_font, 10, "bold"),
                    relief=tk.FLAT,
                    cursor="hand2",
                    padx=14,
                    pady=7,
                    command=lambda u=url_target, l=label_txt: self._handle_click_url(u, l)
                )
                btn_link.pack(fill=tk.X, pady=3)

        # 4. CORPO TESTO
        content_frame = tk.Frame(self.main_card, bg=self.theme["bg"], padx=16, pady=6)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 4))

        txt_scroll = ttk.Scrollbar(content_frame, orient=tk.VERTICAL)
        self.txt_display = tk.Text(
            content_frame,
            bg=self.theme["bg"],
            fg=self.theme["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=2,
            pady=2,
            highlightthickness=0,
            cursor="arrow",
            yscrollcommand=txt_scroll.set
        )
        txt_scroll.config(command=self.txt_display.yview)

        txt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        raw_text = self.reminder.get("text", t("postit_no_message", self.lang))
        render_formatted_text(self.txt_display, raw_text, self.theme)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self._apply_pin_state()

    def _apply_pin_state(self):
        try:
            self.root.attributes("-topmost", self.is_pinned)
        except Exception:
            pass
        if self.is_pinned:
            self.btn_pin.config(text=t("postit_pin_on", self.lang), bg="#FDE047", fg="#78350F")
            self.status_lbl.config(text=t("postit_status_pinned", self.lang))
        else:
            self.btn_pin.config(text=t("postit_pin_off", self.lang), bg="#FFFFFF", fg="#475569")
            self.status_lbl.config(text=t("postit_status_unpinned", self.lang))

    def trigger_alarm_mode(self):
        self.is_pinned = True
        try:
            self.root.attributes("-topmost", True)
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.bell()
        except Exception:
            pass

        self.btn_pin.config(text=t("postit_btn_alarm", self.lang), bg="#EF4444", fg="#FFFFFF")
        self.alarm_banner.pack(fill=tk.X, after=self.header_frame)
        self.status_lbl.config(text=t("postit_alarm_status", self.lang), fg="#DC2626")

        send_system_notification(
            title=f"📌 {self.reminder.get('title', t('postit_default_title', self.lang))}",
            message=self.reminder.get("text", t("postit_alarm_notification_body", self.lang)),
            urgency="critical",
            app_name=t("app_title", self.lang)
        )
        self._flash_alarm(5)

    def _flash_alarm(self, count: int):
        if count <= 0:
            return
        curr_bg = self.alarm_banner.cget("bg")
        new_bg = "#B91C1C" if curr_bg == "#EF4444" else "#EF4444"
        self.alarm_banner.config(bg=new_bg)
        self.lbl_alarm_banner.config(bg=new_bg)
        self.root.after(400, lambda: self._flash_alarm(count - 1))

    def _schedule_time_check(self):
        self._check_time_trigger()
        self.root.after(10000, self._schedule_time_check)

    def _check_time_trigger(self):
        if self.is_alarm:
            return

        time_target = self.reminder.get("time", "").strip()
        freq = self.reminder.get("frequency", "Lun-Ven (Giorni feriali)")
        if not time_target:
            return

        now = datetime.now()
        now_time = now.strftime("%H:%M")
        weekday = now.weekday()

        is_weekdays = any(k in freq for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"])
        is_day_valid = not (is_weekdays and weekday >= 5)

        if is_day_valid and now_time == time_target:
            self.trigger_alarm_mode()

    def _handle_sigusr1(self, signum=None, frame=None):
        """Risponde al segnale SIGUSR1 inviato da demone o cron portando la finestra in allarme visivo e sonoro."""
        try:
            self.root.after(0, self.trigger_alarm_mode)
        except Exception:
            pass

    def _handle_click_url(self, url: str, label: str):
        open_url(url)
        self.status_lbl.config(text=t("postit_url_opened", self.lang, label=label), fg="#2563EB")

    def close(self):
        if hasattr(self, "lock_file"):
            release_reminder_lock(self.lock_file)

        if self.is_toplevel:
            self.root.destroy()
        else:
            self.root.destroy()
            sys.exit(0)

    def show(self):
        if not self.is_toplevel:
            self.root.mainloop()


class PostitManagerApp:
    """Finestra principale di gestione e configurazione promemoria con supporto bilingue e Preset dinamico."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.sys_font = get_system_font_family()
        self.lang = ConfigStore.get_language()
        configure_dialog_fonts(self.root, self.sys_font)

        self.root.title(t("app_window_title", self.lang))

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(1160, max(1060, screen_w - 60))
        win_h = min(800, max(720, screen_h - 100))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)

        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.minsize(1040, 700)

        # Apertura a tutto schermo / massimizzata automatica per la massima comodità visiva
        try:
            self.root.attributes("-zoomed", True)
        except Exception:
            try:
                self.root.state("zoomed")
            except Exception:
                try:
                    self.root.geometry(f"{screen_w}x{screen_h}+0+0")
                except Exception:
                    pass

        self.is_fullscreen = False
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Control-n>", self.switch_to_new_reminder_mode)
        self.root.bind("<Control-N>", self.switch_to_new_reminder_mode)
        self.root.bind("<Escape>", lambda e: self.switch_to_new_reminder_mode() if self.editing_id else None)

        apply_app_icon(self.root)

        self.editing_id = None
        self.selected_color = "yellow"
        self.latest_release_info = None
        self.latest_release_tag = ""

        self._init_styles()
        self._build_ui()
        self.refresh_reminders_table()
        self.update_preset_button()
        self.check_system_status()

        # Controllo automatico aggiornamenti GitHub in background
        self.root.after(1500, lambda: self.check_updates(manual=False))

    def toggle_fullscreen(self, event=None):
        """Alterna modalità schermo intero (F11)."""
        self.is_fullscreen = not getattr(self, "is_fullscreen", False)
        self.root.attributes("-fullscreen", self.is_fullscreen)

    def _init_styles(self):
        self.color_bg = "#F8FAFC"
        self.color_card = "#FFFFFF"
        self.color_border = "#E2E8F0"
        self.color_primary = "#3584E4"
        self.color_text = "#0F172A"
        self.color_muted = "#64748B"

        self.root.configure(bg=self.color_bg)
        configure_dialog_fonts(self.root, self.sys_font)

        style = ttk.Style()
        try:
            style.theme_use("clam")
            style.configure("TLabel", font=(self.sys_font, 9))
            style.configure("TButton", font=(self.sys_font, 9))
        except Exception:
            pass

        style.configure(
            "Treeview",
            background="#FFFFFF",
            foreground=self.color_text,
            rowheight=34,
            fieldbackground="#FFFFFF",
            font=(self.sys_font, 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#F1F5F9",
            foreground="#334155",
            font=(self.sys_font, 10, "bold"),
            padding=(6, 8)
        )
        style.map("Treeview", background=[("selected", "#3584E4")], foreground=[("selected", "#FFFFFF")])

    def _build_ui(self):
        header_bar = tk.Frame(self.root, bg="#FFFFFF", padx=24, pady=12, highlightbackground=self.color_border, highlightthickness=1)
        header_bar.pack(fill=tk.X, side=tk.TOP)

        hdr_left = tk.Frame(header_bar, bg="#FFFFFF")
        hdr_left.pack(side=tk.LEFT)

        lbl_app_icon = tk.Label(hdr_left, text="📝", font=("Sans", 22), bg="#FFFFFF")
        lbl_app_icon.pack(side=tk.LEFT, padx=(0, 10))

        title_box = tk.Frame(hdr_left, bg="#FFFFFF")
        title_box.pack(side=tk.LEFT)

        self.lbl_app_title = tk.Label(
            title_box,
            text=t("app_title", self.lang),
            font=(self.sys_font, 15, "bold"),
            bg="#FFFFFF",
            fg=self.color_text
        )
        self.lbl_app_title.pack(anchor="w")

        self.lbl_app_sub = tk.Label(
            title_box,
            text=t("app_subtitle", self.lang),
            font=(self.sys_font, 9),
            bg="#FFFFFF",
            fg=self.color_muted
        )
        self.lbl_app_sub.pack(anchor="w")

        hdr_right = tk.Frame(header_bar, bg="#FFFFFF")
        hdr_right.pack(side=tk.RIGHT)

        self.badge_service = tk.Label(
            hdr_right,
            text="● Servizio: ...",
            font=(self.sys_font, 9, "bold"),
            bg="#F1F5F9",
            fg="#475569",
            padx=10,
            pady=4,
            cursor="hand2"
        )
        self.badge_service.pack(side=tk.LEFT, padx=(0, 10))
        self.tooltip_service = ToolTip(self.badge_service, "")
        self.badge_service.bind("<Button-1>", lambda e: self.show_service_info_dialog())

        self.badge_daemon = self.badge_service
        self.badge_cron = self.badge_service

        # Pulsante Verifica Aggiornamenti / Notifica Release
        self.btn_check_update = tk.Button(
            hdr_right,
            text=t("btn_check_update", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#EFF6FF",
            fg="#1D4ED8",
            activebackground="#DBEAFE",
            activeforeground="#1E40AF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=9,
            pady=4,
            command=lambda: self.check_updates(manual=True)
        )
        self.btn_check_update.pack(side=tk.LEFT, padx=(0, 12))

        # Selettore di Lingua (Italiano / Inglese)
        lang_frame = tk.Frame(hdr_right, bg="#FFFFFF")
        lang_frame.pack(side=tk.LEFT)

        self.lbl_lang_icon = tk.Label(lang_frame, text="🌐", font=("Sans", 11), bg="#FFFFFF")
        self.lbl_lang_icon.pack(side=tk.LEFT, padx=(0, 4))

        self.combo_lang = ttk.Combobox(
            lang_frame,
            values=["🇮🇹 Italiano", "🇬🇧 English"],
            state="readonly",
            width=12,
            font=(self.sys_font, 9)
        )
        self.combo_lang.set("🇮🇹 Italiano" if self.lang == "it" else "🇬🇧 English")
        self.combo_lang.pack(side=tk.LEFT)
        self.combo_lang.bind("<<ComboboxSelected>>", self.on_language_change)

        main_content = tk.Frame(self.root, bg=self.color_bg, padx=18, pady=14)
        main_content.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(main_content, bg=self.color_bg, width=480)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 12))

        right_col = tk.Frame(main_content, bg=self.color_bg)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_form(left_col)
        self._build_list(right_col)

        status_bar = tk.Frame(self.root, bg="#FFFFFF", padx=18, pady=8, highlightbackground=self.color_border, highlightthickness=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = tk.Label(status_bar, text=t("status_ready", self.lang), font=(self.sys_font, 9), bg="#FFFFFF", fg=self.color_muted)
        self.lbl_status.pack(side=tk.LEFT)

        self.lbl_path = tk.Label(status_bar, text=t("status_data", self.lang, filename=REMINDERS_FILE.name), font=(self.sys_font, 9), bg="#FFFFFF", fg="#94A3B8")
        self.lbl_path.pack(side=tk.RIGHT)

    def on_language_change(self, event=None):
        """Gestore cambio lingua dal selettore UI."""
        val = self.combo_lang.get()
        new_lang = "it" if "Italiano" in val else "en"
        if new_lang != self.lang:
            self.lang = new_lang
            ConfigStore.set_language(new_lang)
            self.apply_language()

    def apply_language(self):
        """Applica la lingua selezionata aggiornando tutti i testi dell'interfaccia a caldo."""
        self.root.title(t("app_window_title", self.lang))
        self.lbl_app_title.config(text=t("app_title", self.lang))
        self.lbl_app_sub.config(text=t("app_subtitle", self.lang))
        self.check_system_status()

        if self.latest_release_info:
            self.btn_check_update.config(
                text=t("btn_update_available", self.lang, version=self.latest_release_tag),
                bg="#DCFCE7",
                fg="#15803D"
            )
        else:
            self.btn_check_update.config(
                text=t("btn_check_update", self.lang),
                bg="#EFF6FF",
                fg="#1D4ED8"
            )

        # Form & Mode
        if getattr(self, "editing_id", None):
            self.lbl_form_section.config(text=t("form_section_edit", self.lang))
            if hasattr(self, "badge_form_mode"):
                self.badge_form_mode.config(text=t("badge_edit_mode", self.lang))
            self.btn_save.config(text=t("btn_update_reminder", self.lang))
        else:
            self.lbl_form_section.config(text=t("form_section_new", self.lang))
            if hasattr(self, "badge_form_mode"):
                self.badge_form_mode.config(text=t("badge_new_mode", self.lang))
            self.btn_save.config(text=t("btn_save_reminder", self.lang))

        if hasattr(self, "btn_form_new"):
            self.btn_form_new.config(text="➕ " + t("btn_new_reminder", self.lang))
        if hasattr(self, "btn_table_new"):
            self.btn_table_new.config(text="➕ " + t("btn_new_reminder", self.lang))
        if hasattr(self, "btn_cancel_edit"):
            self.btn_cancel_edit.config(text=t("btn_cancel_edit", self.lang))

        self.update_preset_button()
        self.lbl_colors.config(text=t("lbl_bg_color", self.lang))
        self.lbl_selected_color_name.config(text=get_color_name(self.selected_color, self.lang))
        self.lbl_time.config(text=t("lbl_time", self.lang))
        self.lbl_freq.config(text=t("lbl_freq", self.lang))

        cur_freq = self.combo_freq.get()
        is_wk = any(k in cur_freq for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"])
        self.combo_freq.config(values=[t("freq_weekdays", self.lang), t("freq_daily", self.lang)])
        self.combo_freq.set(t("freq_weekdays", self.lang) if is_wk else t("freq_daily", self.lang))

        self.lbl_title.config(text=t("lbl_title", self.lang))
        self.lbl_toolbar.config(text=t("lbl_formatting", self.lang))
        self.btn_bold.config(text=t("btn_bold", self.lang))
        self.btn_italic.config(text=t("btn_italic", self.lang))
        self.btn_under.config(text=t("btn_underline", self.lang))
        self.btn_hl.config(text=t("btn_highlight", self.lang))
        self.btn_bullet.config(text=t("btn_bullet", self.lang))
        self.btn_h3.config(text=t("btn_heading", self.lang))
        self.btn_reset_fmt.config(text=t("btn_clean", self.lang))
        self.lbl_links.config(text=t("lbl_links", self.lang))

        self.btn_save_as_preset.config(text=t("btn_save_as_preset", self.lang))
        self.btn_clear.config(text=t("btn_clear", self.lang))

        # List & Table
        self.lbl_hint.config(text=t("table_double_click_hint", self.lang))
        if hasattr(self, "btn_select_all"):
            self.btn_select_all.config(text="🔘 " + t("btn_select_all", self.lang))
        self.tree.heading("time", text=t("col_time", self.lang))
        self.tree.heading("frequency", text=t("col_freq", self.lang))
        self.tree.heading("color", text=t("col_color", self.lang))
        self.tree.heading("title", text=t("col_title", self.lang))
        self.tree.heading("links", text=t("col_links", self.lang))

        self.btn_desktop.config(text=t("btn_desktop", self.lang))
        self.btn_alarm.config(text=t("btn_test_alarm", self.lang))
        self.btn_preset_from_row.config(text=t("btn_set_as_preset", self.lang))
        self.btn_delete.config(text=t("btn_delete", self.lang))
        self.btn_sync.config(text=t("btn_sync", self.lang))

        self.refresh_reminders_table()
        self.lbl_status.config(text=t("status_ready", self.lang))
        self.lbl_path.config(text=t("status_data", self.lang, filename=REMINDERS_FILE.name))

    def _build_form(self, container):
        card = tk.Frame(container, bg=self.color_card, padx=16, pady=14, highlightbackground=self.color_border, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        form_header = tk.Frame(card, bg=self.color_card)
        form_header.pack(fill=tk.X, pady=(0, 8))

        form_header_left = tk.Frame(form_header, bg=self.color_card)
        form_header_left.pack(side=tk.LEFT, fill=tk.Y)

        self.lbl_form_section = tk.Label(
            form_header_left,
            text=t("form_section_new", self.lang),
            font=(self.sys_font, 12, "bold"),
            bg=self.color_card,
            fg=self.color_text
        )
        self.lbl_form_section.pack(side=tk.LEFT)

        self.badge_form_mode = tk.Label(
            form_header_left,
            text=t("badge_new_mode", self.lang),
            font=(self.sys_font, 7, "bold"),
            bg="#DCFCE7",
            fg="#15803D",
            padx=6,
            pady=2,
            relief=tk.FLAT
        )
        self.badge_form_mode.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_form_new = tk.Button(
            form_header,
            text="➕ " + t("btn_new_reminder", self.lang),
            font=(self.sys_font, 8, "bold"),
            bg="#EFF6FF",
            fg="#1D4ED8",
            activebackground="#DBEAFE",
            activeforeground="#1E40AF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.switch_to_new_reminder_mode
        )
        self.btn_form_new.pack(side=tk.RIGHT)

        # PULSANTE PRESET RAPIDO DINAMICO (configurabile)
        self.btn_preset = tk.Button(
            card,
            text=t("btn_preset_empty", self.lang),
            font=(self.sys_font, 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=6,
            command=self.apply_preset
        )
        self.btn_preset.pack(fill=tk.X, pady=(0, 10))

        self.lbl_colors = tk.Label(card, text=t("lbl_bg_color", self.lang), font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        self.lbl_colors.pack(anchor="w")

        color_row = tk.Frame(card, bg=self.color_card)
        color_row.pack(fill=tk.X, pady=(4, 10))

        self.color_swatches = {}
        for c_key, c_val in COLOR_THEMES.items():
            btn_swatch = tk.Button(
                color_row,
                text="✓" if c_key == self.selected_color else "",
                bg=c_val["bg"],
                fg=c_val["title"],
                activebackground=c_val["header"],
                font=(self.sys_font, 10, "bold"),
                relief=tk.SOLID,
                bd=2 if c_key == self.selected_color else 1,
                cursor="hand2",
                width=3,
                command=lambda k=c_key: self.select_color(k)
            )
            btn_swatch.pack(side=tk.LEFT, padx=3)
            self.color_swatches[c_key] = btn_swatch

        self.lbl_selected_color_name = tk.Label(
            color_row,
            text=get_color_name(self.selected_color, self.lang),
            font=(self.sys_font, 9, "italic"),
            bg=self.color_card,
            fg="#64748B"
        )
        self.lbl_selected_color_name.pack(side=tk.LEFT, padx=(8, 0))

        row_time = tk.Frame(card, bg=self.color_card)
        row_time.pack(fill=tk.X, pady=(0, 8))

        col_time = tk.Frame(row_time, bg=self.color_card)
        col_time.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.lbl_time = tk.Label(col_time, text=t("lbl_time", self.lang), font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        self.lbl_time.pack(anchor="w")

        self.entry_time = tk.Entry(col_time, font=(self.sys_font, 11), bg="#F8FAFC", relief=tk.SOLID, bd=1)
        self.entry_time.insert(0, "18:00")
        self.entry_time.pack(fill=tk.X, pady=(2, 0))

        col_freq = tk.Frame(row_time, bg=self.color_card)
        col_freq.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))

        self.lbl_freq = tk.Label(col_freq, text=t("lbl_freq", self.lang), font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        self.lbl_freq.pack(anchor="w")

        self.combo_freq = ttk.Combobox(col_freq, values=[t("freq_weekdays", self.lang), t("freq_daily", self.lang)], state="readonly", font=(self.sys_font, 10))
        self.combo_freq.set(t("freq_weekdays", self.lang))
        self.combo_freq.pack(fill=tk.X, pady=(2, 0))

        self.lbl_title = tk.Label(card, text=t("lbl_title", self.lang), font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        self.lbl_title.pack(anchor="w")

        self.entry_title = tk.Entry(card, font=(self.sys_font, 10), bg="#F8FAFC", relief=tk.SOLID, bd=1)
        self.entry_title.insert(0, t("default_title", self.lang))
        self.entry_title.pack(fill=tk.X, pady=(2, 8))

        self.lbl_toolbar = tk.Label(card, text=t("lbl_formatting", self.lang), font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        self.lbl_toolbar.pack(anchor="w")

        tb_frame = tk.Frame(card, bg="#F1F5F9", padx=4, pady=3, relief=tk.SOLID, bd=1)
        tb_frame.pack(fill=tk.X, pady=(2, 0))

        self.btn_bold = tk.Button(tb_frame, text=t("btn_bold", self.lang), font=(self.sys_font, 9, "bold"), width=3, relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("**"))
        self.btn_bold.pack(side=tk.LEFT, padx=1)

        self.btn_italic = tk.Button(tb_frame, text=t("btn_italic", self.lang), font=(self.sys_font, 9, "italic"), width=3, relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("*"))
        self.btn_italic.pack(side=tk.LEFT, padx=1)

        self.btn_under = tk.Button(tb_frame, text=t("btn_underline", self.lang), font=(self.sys_font, 9, "underline"), width=3, relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("__"))
        self.btn_under.pack(side=tk.LEFT, padx=1)

        self.btn_hl = tk.Button(tb_frame, text=t("btn_highlight", self.lang), font=(self.sys_font, 8, "bold"), bg="#FEF08A", relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("=="))
        self.btn_hl.pack(side=tk.LEFT, padx=3)

        self.btn_bullet = tk.Button(tb_frame, text=t("btn_bullet", self.lang), font=(self.sys_font, 8), relief=tk.FLAT, cursor="hand2", command=self.insert_bullet)
        self.btn_bullet.pack(side=tk.LEFT, padx=1)

        self.btn_h3 = tk.Button(tb_frame, text=t("btn_heading", self.lang), font=(self.sys_font, 8, "bold"), relief=tk.FLAT, cursor="hand2", command=self.insert_h3)
        self.btn_h3.pack(side=tk.LEFT, padx=1)

        self.btn_reset_fmt = tk.Button(tb_frame, text=t("btn_clean", self.lang), font=(self.sys_font, 8), relief=tk.FLAT, cursor="hand2", command=self.clean_formatting)
        self.btn_reset_fmt.pack(side=tk.RIGHT, padx=1)

        self.txt_text = tk.Text(card, font=(self.sys_font, 10), bg="#F8FAFC", height=5, relief=tk.SOLID, bd=1, wrap=tk.WORD)
        self.txt_text.insert("1.0", t("default_message_text", self.lang))
        self.txt_text.pack(fill=tk.X, pady=(0, 8))

        self.lbl_links = tk.Label(card, text=t("lbl_links", self.lang), font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        self.lbl_links.pack(anchor="w")

        row_l1 = tk.Frame(card, bg=self.color_card)
        row_l1.pack(fill=tk.X, pady=(2, 4))
        self.entry_l1_label = tk.Entry(row_l1, font=(self.sys_font, 9), bg="#F8FAFC", width=12, relief=tk.SOLID, bd=1)
        self.entry_l1_label.pack(side=tk.LEFT, padx=(0, 4))
        self.entry_l1_url = tk.Entry(row_l1, font=(self.sys_font, 9), bg="#F8FAFC", relief=tk.SOLID, bd=1)
        self.entry_l1_url.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row_l2 = tk.Frame(card, bg=self.color_card)
        row_l2.pack(fill=tk.X, pady=(2, 10))
        self.entry_l2_label = tk.Entry(row_l2, font=(self.sys_font, 9), bg="#F8FAFC", width=12, relief=tk.SOLID, bd=1)
        self.entry_l2_label.pack(side=tk.LEFT, padx=(0, 4))
        self.entry_l2_url = tk.Entry(row_l2, font=(self.sys_font, 9), bg="#F8FAFC", relief=tk.SOLID, bd=1)
        self.entry_l2_url.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row_actions = tk.Frame(card, bg=self.color_card)
        row_actions.pack(fill=tk.X)
        self.row_actions_frame = row_actions

        self.btn_save = tk.Button(
            row_actions,
            text=t("btn_save_reminder", self.lang),
            font=(self.sys_font, 10, "bold"),
            bg="#3584E4",
            fg="#FFFFFF",
            activebackground="#1D72D6",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=7,
            command=self.save_reminder_from_form
        )
        self.btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.btn_cancel_edit = tk.Button(
            row_actions,
            text=t("btn_cancel_edit", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#EFF6FF",
            fg="#1D4ED8",
            activebackground="#DBEAFE",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.switch_to_new_reminder_mode
        )
        # Note: self.btn_cancel_edit will be packed dynamically when editing_id is active

        self.btn_save_as_preset = tk.Button(
            row_actions,
            text=t("btn_save_as_preset", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#FEF3C7",
            fg="#92400E",
            activebackground="#FDE68A",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.save_current_form_as_preset
        )
        self.btn_save_as_preset.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_clear = tk.Button(
            row_actions,
            text=t("btn_clear", self.lang),
            font=(self.sys_font, 9),
            bg="#F1F5F9",
            fg="#475569",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.clear_form
        )
        self.btn_clear.pack(side=tk.RIGHT)

    def _build_list(self, container):
        card = tk.Frame(container, bg=self.color_card, padx=16, pady=14, highlightbackground=self.color_border, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        header_row = tk.Frame(card, bg=self.color_card)
        header_row.pack(fill=tk.X, pady=(0, 8))

        self.lbl_list_count = tk.Label(header_row, text=t("table_section_title", self.lang), font=(self.sys_font, 12, "bold"), bg=self.color_card, fg=self.color_text)
        self.lbl_list_count.pack(side=tk.LEFT)

        self.btn_select_all = tk.Button(
            header_row,
            text="🔘 " + t("btn_select_all", self.lang),
            font=(self.sys_font, 8, "bold"),
            bg="#EFF6FF",
            fg="#1D4ED8",
            activebackground="#DBEAFE",
            activeforeground="#1E40AF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.toggle_select_all
        )
        self.btn_select_all.pack(side=tk.LEFT, padx=(12, 0))

        self.btn_table_new = tk.Button(
            header_row,
            text="➕ " + t("btn_new_reminder", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=3,
            command=self.switch_to_new_reminder_mode
        )
        self.btn_table_new.pack(side=tk.RIGHT, padx=(8, 0))

        self.lbl_hint = tk.Label(header_row, text=t("table_double_click_hint", self.lang), font=(self.sys_font, 8, "italic"), bg=self.color_card, fg="#64748B")
        self.lbl_hint.pack(side=tk.RIGHT)

        table_frame = tk.Frame(card, bg=self.color_card)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("time", "frequency", "color", "title", "links")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("time", text=t("col_time", self.lang))
        self.tree.heading("frequency", text=t("col_freq", self.lang))
        self.tree.heading("color", text=t("col_color", self.lang))
        self.tree.heading("title", text=t("col_title", self.lang))
        self.tree.heading("links", text=t("col_links", self.lang))

        self.tree.column("time", width=70, minwidth=60, anchor="center")
        self.tree.column("frequency", width=120, minwidth=90, anchor="w")
        self.tree.column("color", width=95, minwidth=70, anchor="center")
        self.tree.column("title", width=140, minwidth=100, anchor="w")
        self.tree.column("links", width=110, minwidth=70, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.put_selected_on_desktop())
        self.tree.bind("<Delete>", lambda e: self.delete_selected_reminder())
        self.tree.bind("<BackSpace>", lambda e: self.delete_selected_reminder())
        self.tree.bind("<Control-a>", self.toggle_select_all)
        self.tree.bind("<Control-A>", self.toggle_select_all)
        self.tree.bind("<Button-3>", self.show_tree_context_menu)

        self.tree_menu = tk.Menu(self.root, tearoff=0)

        action_bar = tk.Frame(card, bg=self.color_card)
        action_bar.pack(fill=tk.X, pady=(10, 0))

        act_left = tk.Frame(action_bar, bg=self.color_card)
        act_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_desktop = tk.Button(
            act_left,
            text=t("btn_desktop", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            activebackground="#0369A1",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=7,
            command=self.put_selected_on_desktop
        )
        self.btn_desktop.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_alarm = tk.Button(
            act_left,
            text=t("btn_test_alarm", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#D97706",
            fg="#FFFFFF",
            activebackground="#B45309",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.test_alarm_now
        )
        self.btn_alarm.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_preset_from_row = tk.Button(
            act_left,
            text=t("btn_set_as_preset", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#FEF3C7",
            fg="#92400E",
            activebackground="#FDE68A",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.set_selected_as_preset
        )
        self.btn_preset_from_row.pack(side=tk.LEFT, padx=(0, 6))

        act_right = tk.Frame(action_bar, bg=self.color_card)
        act_right.pack(side=tk.RIGHT)

        self.btn_sync = tk.Button(
            act_right,
            text=t("btn_sync", self.lang),
            font=(self.sys_font, 9),
            bg="#F1F5F9",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            padx=9,
            pady=7,
            command=self.manual_sync
        )
        self.btn_sync.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_delete = tk.Button(
            act_right,
            text=t("btn_delete", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#EF4444",
            fg="#FFFFFF",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=7,
            command=self.delete_selected_reminder
        )
        self.btn_delete.pack(side=tk.LEFT)

    def select_color(self, color_key: str):
        self.selected_color = color_key
        for k, btn in self.color_swatches.items():
            if k == color_key:
                btn.config(text="✓", bd=2)
            else:
                btn.config(text="", bd=1)
        self.lbl_selected_color_name.config(text=get_color_name(color_key, self.lang))

    def insert_formatting(self, marker: str):
        try:
            sel_start = self.txt_text.index(tk.SEL_FIRST)
            sel_end = self.txt_text.index(tk.SEL_LAST)
            selected_text = self.txt_text.get(sel_start, sel_end)
            self.txt_text.delete(sel_start, sel_end)
            self.txt_text.insert(sel_start, f"{marker}{selected_text}{marker}")
        except tk.TclError:
            cur_idx = self.txt_text.index(tk.INSERT)
            placeholder = "testo" if self.lang == "it" else "text"
            self.txt_text.insert(cur_idx, f"{marker}{placeholder}{marker}")

    def insert_bullet(self):
        cur_idx = self.txt_text.index(tk.INSERT)
        self.txt_text.insert(cur_idx, "\n• ")

    def insert_h3(self):
        cur_idx = self.txt_text.index(tk.INSERT)
        self.txt_text.insert(cur_idx, "\n### ")

    def clean_formatting(self):
        try:
            sel_start = self.txt_text.index(tk.SEL_FIRST)
            sel_end = self.txt_text.index(tk.SEL_LAST)
            txt = self.txt_text.get(sel_start, sel_end)
            cleaned = re.sub(r"(\*\*|\*|__|\=\=|###\s*)", "", txt)
            self.txt_text.delete(sel_start, sel_end)
            self.txt_text.insert(sel_start, cleaned)
        except tk.TclError:
            pass

    def check_system_status(self):
        daemon_ok = CronManager.is_daemon_service_active()
        cron_avail = CronManager.is_crontab_available()
        cron_ok = CronManager.is_cron_service_active()

        if daemon_ok and cron_ok:
            badge_text = t("status_service_active_both", self.lang)
            badge_bg = "#DCFCE7"
            badge_fg = "#15803D"
            tooltip_text = t("tooltip_service_both", self.lang)
        elif daemon_ok:
            badge_text = t("status_service_active_systemd", self.lang)
            badge_bg = "#DCFCE7"
            badge_fg = "#15803D"
            tooltip_text = t("tooltip_service_systemd", self.lang)
        elif cron_ok:
            badge_text = t("status_service_active_cron", self.lang)
            badge_bg = "#DCFCE7"
            badge_fg = "#15803D"
            tooltip_text = t("tooltip_service_cron", self.lang)
        else:
            badge_text = t("status_service_inactive", self.lang)
            badge_bg = "#FEE2E2"
            badge_fg = "#B91C1C"
            tooltip_text = t("tooltip_service_inactive", self.lang)

        self.badge_service.config(text=badge_text, bg=badge_bg, fg=badge_fg)
        if hasattr(self, "tooltip_service"):
            self.tooltip_service.set_text(tooltip_text)

    def show_service_info_dialog(self):
        """Mostra una finestra dettagliata con lo stato trasparente dei motori di notifica."""
        daemon_ok = CronManager.is_daemon_service_active()
        cron_avail = CronManager.is_crontab_available()
        cron_ok = CronManager.is_cron_service_active()

        if self.lang == "it":
            title = t("title_service_status", self.lang)
            d_status = "✓ Attivo e in esecuzione (monitora i promemoria ogni minuto)" if daemon_ok else "⚠️ Inattivo o non avviato"
            if cron_ok:
                c_status = "✓ Attivo e sincronizzato"
            elif not cron_avail:
                c_status = "○ Non installato sul sistema (non necessario, gestito dal demone)"
            else:
                c_status = "○ Inattivo (opzionale se il demone Systemd è attivo)"

            msg = (
                f"Stato dei servizi di notifica in background:\n\n"
                f"• Demone Systemd (postit-daemon.service):\n  {d_status}\n\n"
                f"• Schedulatore Crontab:\n  {c_status}\n\n"
                f"Nota: Se il demone Systemd è attivo, i tuoi promemoria scatteranno "
                f"sempre con precisione anche senza Crontab.\n\n"
                f"Vuoi risincronizzare e ricaricare i servizi adesso?"
            )
        else:
            title = t("title_service_status", self.lang)
            d_status = "✓ Active and running (monitors reminders every minute)" if daemon_ok else "⚠️ Inactive or not started"
            if cron_ok:
                c_status = "✓ Active and synchronized"
            elif not cron_avail:
                c_status = "○ Not installed on system (not required, handled by daemon)"
            else:
                c_status = "○ Inactive (optional if Systemd daemon is active)"

            msg = (
                f"Background notification services status:\n\n"
                f"• Systemd User Daemon (postit-daemon.service):\n  {d_status}\n\n"
                f"• Crontab Scheduler:\n  {c_status}\n\n"
                f"Note: If the Systemd daemon is active, your reminders will always "
                f"trigger reliably on schedule even without Crontab.\n\n"
                f"Do you want to re-synchronize and reload services now?"
            )

        if messagebox.askyesno(title, msg, parent=self.root):
            self.manual_sync()

    def update_preset_button(self):
        """Aggiorna lo stato e il testo del pulsante Preset in base al file preset.json."""
        preset = PresetStore.load()
        if preset:
            title = preset.get("title", "Preset")
            time_val = preset.get("time", "--:--")
            self.btn_preset.config(
                text=t("btn_preset_format", self.lang, title=title, time=time_val),
                bg="#FEF08A",
                fg="#854D0E",
                activebackground="#FDE047",
                activeforeground="#713F12"
            )
        else:
            self.btn_preset.config(
                text=t("btn_preset_empty", self.lang),
                bg="#F1F5F9",
                fg="#64748B",
                activebackground="#E2E8F0",
                activeforeground="#334155"
            )

    def apply_preset(self):
        """Carica il preset memorizzato oppure mostra la guida su come memorizzarne uno."""
        preset = PresetStore.load()
        if not preset:
            messagebox.showinfo(
                t("msg_no_preset_title", self.lang),
                t("msg_no_preset_body", self.lang)
            )
            return

        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, preset.get("time", "18:00"))

        raw_freq = preset.get("frequency", "")
        is_wk = any(k in raw_freq for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"])
        self.combo_freq.set(t("freq_weekdays", self.lang) if is_wk else t("freq_daily", self.lang))

        self.select_color(preset.get("color", "yellow"))

        self.entry_title.delete(0, tk.END)
        self.entry_title.insert(0, preset.get("title", ""))

        self.txt_text.delete("1.0", tk.END)
        self.txt_text.insert("1.0", preset.get("text", ""))

        links = preset.get("links", [])
        self.entry_l1_label.delete(0, tk.END)
        self.entry_l1_url.delete(0, tk.END)
        if len(links) > 0:
            self.entry_l1_label.insert(0, links[0].get("label", ""))
            self.entry_l1_url.insert(0, links[0].get("url", ""))

        self.entry_l2_label.delete(0, tk.END)
        self.entry_l2_url.delete(0, tk.END)
        if len(links) > 1:
            self.entry_l2_label.insert(0, links[1].get("label", ""))
            self.entry_l2_url.insert(0, links[1].get("url", ""))

        self.lbl_status.config(text=t("status_preset_loaded", self.lang, title=preset.get('title')))

    def save_current_form_as_preset(self):
        """Salva i dati attualmente compilati nel form come Preset Rapido."""
        time_str = self.entry_time.get().strip() or "18:00"
        title = self.entry_title.get().strip()
        if not title:
            messagebox.showwarning(t("msg_missing_title_title", self.lang), t("msg_missing_title_body", self.lang))
            return

        text = self.txt_text.get("1.0", tk.END).strip()
        frequency = self.combo_freq.get()

        links = []
        l1_label = self.entry_l1_label.get().strip()
        l1_url = self.entry_l1_url.get().strip()
        if l1_url:
            links.append({"label": l1_label or t("link1_default_label", self.lang), "url": l1_url})

        l2_label = self.entry_l2_label.get().strip()
        l2_url = self.entry_l2_url.get().strip()
        if l2_url:
            links.append({"label": l2_label or t("link2_default_label", self.lang), "url": l2_url})

        preset_data = {
            "time": time_str,
            "frequency": frequency,
            "color": self.selected_color,
            "title": title,
            "text": text,
            "links": links
        }

        if PresetStore.save(preset_data):
            self.update_preset_button()
            self.lbl_status.config(text=t("status_preset_stored", self.lang, title=title))
            messagebox.showinfo(
                t("msg_preset_saved_title", self.lang),
                t("msg_preset_saved_body", self.lang, title=title)
            )
        else:
            messagebox.showerror(t("msg_error_title", self.lang), t("msg_preset_save_error", self.lang))

    def set_selected_as_preset(self):
        """Salva il promemoria selezionato nella tabella come Preset Rapido."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(t("msg_no_selection_title", self.lang), t("msg_no_selection_preset", self.lang))
            return

        rem = ReminderStore.get_by_id(selected[0])
        if not rem:
            return

        preset_data = {
            "time": rem.get("time", "18:00"),
            "frequency": rem.get("frequency", t("freq_weekdays", self.lang)),
            "color": rem.get("color", "yellow"),
            "title": rem.get("title", t("postit_default_title", self.lang)),
            "text": rem.get("text", ""),
            "links": rem.get("links", [])
        }

        if PresetStore.save(preset_data):
            self.update_preset_button()
            self.lbl_status.config(text=t("status_preset_stored", self.lang, title=rem.get('title')))
            messagebox.showinfo(
                t("msg_preset_saved_title", self.lang),
                t("msg_preset_row_saved_body", self.lang, title=rem.get('title'))
            )
        else:
            messagebox.showerror(t("msg_error_title", self.lang), t("msg_preset_save_error", self.lang))

    def set_form_mode(self, editing: bool, title: str = ""):
        """Configura l'aspetto visivo del modulo tra creazione nuovo o modifica esistente."""
        if editing:
            self.lbl_form_section.config(text=t("form_section_edit", self.lang))
            if hasattr(self, "badge_form_mode"):
                self.badge_form_mode.config(
                    text=t("badge_edit_mode", self.lang),
                    bg="#FEF3C7",
                    fg="#92400E"
                )
            self.btn_save.config(
                text=t("btn_update_reminder", self.lang),
                bg="#16A34A",
                activebackground="#15803D"
            )
            if hasattr(self, "btn_cancel_edit") and hasattr(self, "btn_save_as_preset"):
                self.btn_cancel_edit.pack(side=tk.LEFT, padx=(0, 6), before=self.btn_save_as_preset)
        else:
            self.editing_id = None
            self.lbl_form_section.config(text=t("form_section_new", self.lang))
            if hasattr(self, "badge_form_mode"):
                self.badge_form_mode.config(
                    text=t("badge_new_mode", self.lang),
                    bg="#DCFCE7",
                    fg="#15803D"
                )
            self.btn_save.config(
                text=t("btn_save_reminder", self.lang),
                bg="#3584E4",
                activebackground="#1D72D6"
            )
            if hasattr(self, "btn_cancel_edit"):
                self.btn_cancel_edit.pack_forget()

    def switch_to_new_reminder_mode(self, event=None, clear_fields: bool = True):
        """Passa esplicitamente alla modalità di creazione di un nuovo promemoria da zero."""
        self.editing_id = None
        self.tree.selection_set([])
        if clear_fields:
            self.clear_form(silent=True)
        self.set_form_mode(editing=False)
        self.entry_title.focus_set()
        self.entry_title.select_range(0, tk.END)
        self.lbl_status.config(text=t("status_new_mode", self.lang))
        return "break"

    def clear_form(self, silent: bool = False):
        self.editing_id = None
        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, "18:00")
        self.combo_freq.set(t("freq_weekdays", self.lang))
        self.select_color("yellow")
        self.entry_title.delete(0, tk.END)
        self.entry_title.insert(0, t("default_title", self.lang))
        self.txt_text.delete("1.0", tk.END)
        self.txt_text.insert("1.0", t("default_message_text", self.lang))
        self.entry_l1_label.delete(0, tk.END)
        self.entry_l1_url.delete(0, tk.END)
        self.entry_l2_label.delete(0, tk.END)
        self.entry_l2_url.delete(0, tk.END)
        self.set_form_mode(editing=False)
        if not silent:
            self.lbl_status.config(text=t("status_form_cleared", self.lang))

    def toggle_select_all(self, event=None):
        """Seleziona o deseleziona tutti i promemoria nella tabella."""
        all_items = self.tree.get_children()
        if not all_items:
            return "break"
        current_sel = self.tree.selection()
        if len(current_sel) == len(all_items):
            self.tree.selection_set([])
            self.switch_to_new_reminder_mode(clear_fields=True)
            if hasattr(self, "btn_select_all"):
                self.btn_select_all.config(text="🔘 " + t("btn_select_all", self.lang))
            self.btn_delete.config(text=t("btn_delete", self.lang))
        else:
            self.tree.selection_set(all_items)
            self.on_tree_select(None)
            if hasattr(self, "btn_select_all"):
                self.btn_select_all.config(text="✖ " + t("btn_deselect_all", self.lang))
        return "break"

    def show_tree_context_menu(self, event):
        """Mostra il menu contestuale al click col tasto destro sulla tabella."""
        row_id = self.tree.identify_row(event.y)
        if row_id:
            if row_id not in self.tree.selection():
                self.tree.selection_set(row_id)
                self.on_tree_select(None)

        selected = self.tree.selection()
        if not selected:
            return

        self.tree_menu.delete(0, tk.END)
        count = len(selected)

        desk_lbl = f"📌 {t('btn_desktop', self.lang)} ({count})" if count > 1 else f"📌 {t('btn_desktop', self.lang)}"
        self.tree_menu.add_command(label=desk_lbl, command=self.put_selected_on_desktop)

        if count == 1:
            self.tree_menu.add_command(label=f"✏️ {t('tree_context_edit', self.lang)}", command=lambda: self.on_tree_select(None))
            self.tree_menu.add_command(label=f"👁️ {t('btn_test_alarm', self.lang)}", command=self.test_alarm_now)
            self.tree_menu.add_command(label=f"⭐ {t('btn_set_as_preset', self.lang)}", command=self.set_selected_as_preset)

        self.tree_menu.add_separator()
        self.tree_menu.add_command(label=f"➕ {t('tree_context_new', self.lang)}  [Ctrl+N]", command=self.switch_to_new_reminder_mode)
        del_lbl = f"🗑️ {t('btn_delete', self.lang)} ({count})  [Canc]" if count > 1 else f"🗑️ {t('btn_delete', self.lang)}  [Canc]"
        self.tree_menu.add_command(label=del_lbl, command=self.delete_selected_reminder)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label=f"🔘 {t('menu_select_all', self.lang)}  [Ctrl+A]", command=self.toggle_select_all)

        try:
            self.tree_menu.post(event.x_root, event.y_root)
        except Exception:
            pass

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            self.btn_delete.config(text=t("btn_delete", self.lang))
            if hasattr(self, "btn_select_all"):
                self.btn_select_all.config(text="🔘 " + t("btn_select_all", self.lang))
            return

        all_count = len(self.tree.get_children())
        if hasattr(self, "btn_select_all"):
            if len(selected) == all_count and all_count > 0:
                self.btn_select_all.config(text="✖ " + t("btn_deselect_all", self.lang))
            else:
                self.btn_select_all.config(text="🔘 " + t("btn_select_all", self.lang))

        if len(selected) > 1:
            self.btn_delete.config(text=f"🗑️ {t('btn_delete', self.lang)} ({len(selected)})")
            self.lbl_status.config(text=t("status_multiple_selected", self.lang, count=len(selected)))
            self.set_form_mode(editing=False)
            return

        self.btn_delete.config(text=t("btn_delete", self.lang))
        item_id = selected[0]
        rem = ReminderStore.get_by_id(item_id)
        if not rem:
            return

        self.editing_id = rem.get("id")
        self.set_form_mode(editing=True, title=rem.get("title", ""))

        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, rem.get("time", "18:00"))

        raw_freq = rem.get("frequency", "")
        is_wk = any(k in raw_freq for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"])
        self.combo_freq.set(t("freq_weekdays", self.lang) if is_wk else t("freq_daily", self.lang))

        self.select_color(rem.get("color", "yellow"))

        self.entry_title.delete(0, tk.END)
        self.entry_title.insert(0, rem.get("title", ""))

        self.txt_text.delete("1.0", tk.END)
        self.txt_text.insert("1.0", rem.get("text", ""))

        links = rem.get("links", [])
        self.entry_l1_label.delete(0, tk.END)
        self.entry_l1_url.delete(0, tk.END)
        if len(links) > 0:
            self.entry_l1_label.insert(0, links[0].get("label", ""))
            self.entry_l1_url.insert(0, links[0].get("url", ""))

        self.entry_l2_label.delete(0, tk.END)
        self.entry_l2_url.delete(0, tk.END)
        if len(links) > 1:
            self.entry_l2_label.insert(0, links[1].get("label", ""))
            self.entry_l2_url.insert(0, links[1].get("url", ""))

        self.lbl_status.config(text=t("status_edit_mode", self.lang, title=rem.get('title')))

    def save_reminder_from_form(self):
        time_str = self.entry_time.get().strip()
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", time_str):
            messagebox.showerror(t("msg_invalid_time_title", self.lang), t("msg_invalid_time_body", self.lang))
            return

        parts = time_str.split(":")
        time_str = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

        title = self.entry_title.get().strip()
        if not title:
            messagebox.showerror(t("msg_title_required_title", self.lang), t("msg_title_required_body", self.lang))
            return

        text = self.txt_text.get("1.0", tk.END).strip()
        frequency = self.combo_freq.get()

        links = []
        l1_label = self.entry_l1_label.get().strip()
        l1_url = self.entry_l1_url.get().strip()
        if l1_url:
            links.append({"label": l1_label or t("link1_default_label", self.lang), "url": l1_url})

        l2_label = self.entry_l2_label.get().strip()
        l2_url = self.entry_l2_url.get().strip()
        if l2_url:
            links.append({"label": l2_label or t("link2_default_label", self.lang), "url": l2_url})

        rem_id = self.editing_id or f"rem-{uuid.uuid4().hex[:8]}"
        reminder_data = {
            "id": rem_id,
            "time": time_str,
            "frequency": frequency,
            "color": self.selected_color,
            "title": title,
            "text": text,
            "links": links,
            "enabled": True
        }

        if ReminderStore.add_or_update(reminder_data):
            reminders = ReminderStore.load_all()
            try:
                CronManager.sync_reminders(reminders, lang=self.lang)
            except Exception as e:
                print(f"[Warning] Sincronizzazione crontab non riuscita (il demone monitor resta attivo): {e}")

            self.refresh_reminders_table()
            self.clear_form()
            self.check_system_status()
            self.lbl_status.config(text=t("status_reminder_saved", self.lang, title=title))
            messagebox.showinfo(
                t("msg_save_success_title", self.lang),
                t("msg_save_success_body", self.lang, title=title)
            )
        else:
            messagebox.showerror(t("msg_error_title", self.lang), t("msg_save_error", self.lang))

    def delete_selected_reminder(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(t("msg_no_selection_title", self.lang), t("msg_no_selection_delete", self.lang))
            return

        count = len(selected)
        if count == 1:
            rem = ReminderStore.get_by_id(selected[0])
            title = rem.get("title", "") if rem else ""
            confirm_msg = t("msg_delete_confirm_body", self.lang, title=title)
        else:
            confirm_msg = t("msg_delete_multiple_confirm_body", self.lang, count=count)

        if not messagebox.askyesno(t("msg_delete_confirm_title", self.lang), confirm_msg, parent=self.root):
            return

        deleted_count = 0
        for item_id in selected:
            if ReminderStore.delete_by_id(item_id):
                deleted_count += 1

        if deleted_count > 0:
            reminders = ReminderStore.load_all()
            try:
                CronManager.sync_reminders(reminders, lang=self.lang)
            except Exception as e:
                print(f"[Warning] Sincronizzazione crontab non riuscita: {e}")

            self.refresh_reminders_table()
            self.clear_form()
            self.check_system_status()
            if deleted_count > 1:
                status_txt = t("status_reminders_deleted_multiple", self.lang, count=deleted_count)
            else:
                status_txt = t("status_reminder_deleted", self.lang)
            self.lbl_status.config(text=status_txt)
        else:
            messagebox.showerror(t("msg_error_title", self.lang), t("msg_delete_error", self.lang))

    def put_selected_on_desktop(self):
        selected = self.tree.selection()
        if selected:
            rem_ids = list(selected)
        elif self.editing_id:
            rem_ids = [self.editing_id]
        else:
            reminders = ReminderStore.load_all()
            rem_ids = [reminders[0]["id"]] if reminders else ["benvenuto-01"]

        runner = str(RUNNER_SH.resolve()) if RUNNER_SH.exists() else str(Path(__file__).resolve())
        launched = 0
        for rem_id in rem_ids:
            try:
                subprocess.Popen(
                    [runner, "--desktop", "--id", rem_id],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                launched += 1
            except Exception as e:
                messagebox.showerror(t("msg_launch_error_title", self.lang), t("msg_launch_error_body", self.lang, error=e))
                break

        if launched > 1:
            self.lbl_status.config(text=t("status_multiple_desktop_launched", self.lang, count=launched))
        elif launched == 1:
            self.lbl_status.config(text=t("status_desktop_launched", self.lang))

    def test_alarm_now(self):
        selected = self.tree.selection()
        if selected:
            rem_id = selected[0]
        elif self.editing_id:
            rem_id = self.editing_id
        else:
            reminders = ReminderStore.load_all()
            rem_id = reminders[0]["id"] if reminders else "benvenuto-01"

        # Se la finestra del promemoria è già aperta, invia SIGUSR1 per portarla in allarme senza duplicarla
        if not signal_existing_reminder(rem_id, is_alarm=True):
            runner = str(RUNNER_SH.resolve()) if RUNNER_SH.exists() else str(Path(__file__).resolve())
            subprocess.Popen(
                [runner, "--popup", "--alarm", "--id", rem_id],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        self.lbl_status.config(text=t("status_alarm_tested", self.lang))

    def manual_sync(self):
        """Sincronizza e ricarica sia il demone utente systemd che crontab."""
        reminders = ReminderStore.load_all()
        cron_ok, cron_msg = False, ""
        try:
            cron_ok, cron_msg = CronManager.sync_reminders(reminders, lang=self.lang)
        except Exception as e:
            cron_msg = str(e)

        daemon_restarted = False
        if CronManager.is_daemon_service_active():
            try:
                subprocess.run(["systemctl", "--user", "restart", "postit-daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                daemon_restarted = True
            except Exception:
                pass

        self.check_system_status()

        if daemon_restarted and cron_ok:
            full_msg = t("sync_all_success", self.lang)
        elif daemon_restarted:
            full_msg = t("sync_daemon_success", self.lang)
        elif cron_ok:
            full_msg = cron_msg
        else:
            full_msg = cron_msg or t("sync_manual_done", self.lang)

        self.lbl_status.config(text=full_msg)
        messagebox.showinfo(t("msg_sync_title", self.lang), full_msg)

    def check_updates(self, manual: bool = False):
        """Controlla se ci sono nuove versioni/release su GitHub in un thread asincrono."""
        if manual:
            self.lbl_status.config(text=t("msg_checking_updates", self.lang))

        def worker():
            has_update, release_info, tag = UpdateManager.check_for_updates()

            def on_checked():
                if manual:
                    self.lbl_status.config(text=t("status_ready", self.lang))

                if has_update and release_info:
                    self.latest_release_info = release_info
                    self.latest_release_tag = tag
                    self.btn_check_update.config(
                        text=t("btn_update_available", self.lang, version=tag),
                        bg="#DCFCE7",
                        fg="#15803D"
                    )
                    self.show_update_dialog(release_info)
                elif manual:
                    messagebox.showinfo(
                        t("msg_no_updates_title", self.lang),
                        t("msg_no_updates_body", self.lang, version=APP_VERSION),
                        parent=self.root
                    )

            self.root.after(0, on_checked)

        threading.Thread(target=worker, daemon=True).start()

    def show_update_dialog(self, release_info: dict):
        """Mostra una finestra modale per l'aggiornamento con note di rilascio e 1-click update."""
        tag = release_info.get("tag_name", "v1.x.x")
        dlg = tk.Toplevel(self.root)
        dlg.title(t("msg_update_window_title", self.lang))
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg="#FFFFFF")
        apply_app_icon(dlg)

        # Calcolo dimensioni generose e centratura perfetta sullo schermo per evitare che la finestra sia piccola o tagliata
        screen_w = dlg.winfo_screenwidth()
        screen_h = dlg.winfo_screenheight()
        dlg_w = min(760, max(660, int(screen_w * 0.55)))
        dlg_h = min(600, max(520, int(screen_h * 0.65)))
        pos_x = max(20, (screen_w - dlg_w) // 2)
        pos_y = max(20, (screen_h - dlg_h) // 2 - 25)

        dlg.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")
        dlg.minsize(620, 480)

        # 1. Header fisso in alto
        hdr = tk.Frame(dlg, bg="#EFF6FF", padx=20, pady=14)
        hdr.pack(side=tk.TOP, fill=tk.X)

        lbl_h = tk.Label(hdr, text=f"🎉 {t('msg_update_header', self.lang)}", font=(self.sys_font, 11, "bold"), bg="#EFF6FF", fg="#1D4ED8")
        lbl_h.pack(anchor="w")

        info_text = f"{t('msg_current_version', self.lang)} {APP_VERSION}   ➜   {t('msg_latest_version', self.lang)} {tag}"
        lbl_v = tk.Label(hdr, text=info_text, font=(self.sys_font, 9, "bold"), bg="#EFF6FF", fg="#1E40AF")
        lbl_v.pack(anchor="w", pady=(4, 0))

        # 2. Barra inferiore fissa (pulsanti di azione e stato)
        # Nota: Viene impacchettata con side=BOTTOM prima del corpo centrale affinché
        # sia sempre garantita la sua visibilità e non venga mai schiacciata o nascosta.
        b_bar = tk.Frame(dlg, bg="#FFFFFF", padx=20, pady=12)
        b_bar.pack(side=tk.BOTTOM, fill=tk.X)

        lbl_progress = tk.Label(b_bar, text="", font=(self.sys_font, 8, "italic"), bg="#FFFFFF", fg="#0284C7")
        lbl_progress.pack(anchor="w", pady=(0, 8))

        btn_row = tk.Frame(b_bar, bg="#FFFFFF")
        btn_row.pack(fill=tk.X)

        # 3. Area centrale espandibile con scrollbar per note di rilascio
        body_frame = tk.Frame(dlg, bg="#FFFFFF", padx=20, pady=8)
        body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        lbl_notes = tk.Label(body_frame, text=t("msg_release_notes", self.lang), font=(self.sys_font, 8, "bold"), bg="#FFFFFF", fg="#475569")
        lbl_notes.pack(anchor="w", pady=(0, 6))

        txt_container = tk.Frame(body_frame, bg="#FFFFFF")
        txt_container.pack(fill=tk.BOTH, expand=True)

        scroll_notes = ttk.Scrollbar(txt_container)
        scroll_notes.pack(side=tk.RIGHT, fill=tk.Y)

        txt_notes = tk.Text(
            txt_container,
            height=8,
            font=(self.sys_font, 9),
            bg="#F8FAFC",
            relief=tk.SOLID,
            bd=1,
            wrap=tk.WORD,
            padx=12,
            pady=10,
            yscrollcommand=scroll_notes.set
        )
        txt_notes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_notes.config(command=txt_notes.yview)

        raw_body = release_info.get("body", "").strip() or "Nuovo rilascio disponibile con ottimizzazioni e miglioramenti."
        render_markdown_release_notes(txt_notes, raw_body, self.sys_font)

        def do_update():
            lbl_progress.config(text=t("msg_update_in_progress", self.lang))
            btn_upd.config(state=tk.DISABLED)
            dlg.update_idletasks()

            def bg_work():
                ok, msg = UpdateManager.perform_automatic_update(release_info)
                def on_done():
                    if ok:
                        relaunch = messagebox.askyesno(
                            t("msg_update_relaunch_confirm_title", self.lang),
                            t("msg_update_relaunch_confirm_body", self.lang, version=tag),
                            parent=dlg
                        )
                        if relaunch:
                            current_exec = Path(__file__).resolve()
                            installed_mgr = USER_HOME / ".local" / "bin" / "postit_manager.py"
                            if RUNNER_SH.exists() and current_exec == installed_mgr:
                                runner = [str(RUNNER_SH.resolve())]
                            elif RUNNER_SH.exists() and not current_exec.is_file():
                                runner = [str(RUNNER_SH.resolve())]
                            else:
                                runner = [sys.executable, str(current_exec)]
                            try:
                                subprocess.Popen(
                                    runner,
                                    start_new_session=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                            except Exception as ex:
                                print(f"[Post-it] Riavvio fallito: {ex}")
                            dlg.destroy()
                            self.root.destroy()
                            sys.exit(0)
                        else:
                            dlg.destroy()
                            self.lbl_status.config(text=t("status_updated_manual_restart", self.lang, version=tag))
                    else:
                        lbl_progress.config(text="")
                        btn_upd.config(state=tk.NORMAL)
                        messagebox.showerror(
                            t("msg_update_error_title", self.lang),
                            t("msg_update_error_body", self.lang, error=msg),
                            parent=dlg
                        )
                self.root.after(0, on_done)

            threading.Thread(target=bg_work, daemon=True).start()

        btn_upd = tk.Button(
            btn_row,
            text=t("btn_update_now", self.lang),
            font=(self.sys_font, 9, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=6,
            command=do_update
        )
        btn_upd.pack(side=tk.LEFT, padx=(0, 8))

        btn_gh = tk.Button(
            btn_row,
            text=t("btn_view_github", self.lang),
            font=(self.sys_font, 8),
            bg="#F1F5F9",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=6,
            command=lambda: webbrowser.open(release_info.get("html_url", GITHUB_RELEASES_URL))
        )
        btn_gh.pack(side=tk.LEFT, padx=(0, 8))

        btn_cancel = tk.Button(
            btn_row,
            text=t("btn_close_dialog", self.lang),
            font=(self.sys_font, 8),
            bg="#F1F5F9",
            fg="#64748B",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=6,
            command=dlg.destroy
        )
        btn_cancel.pack(side=tk.RIGHT)

    def refresh_reminders_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        reminders = ReminderStore.load_all()
        self.lbl_list_count.config(text=t("table_active_count", self.lang, count=len(reminders)))

        for rem in sorted(reminders, key=lambda x: x.get("time", "00:00")):
            rem_id = rem.get("id")
            time_val = rem.get("time", "--:--")
            is_wk = any(k in rem.get("frequency", "") for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"])
            freq_val = t("freq_short_weekdays", self.lang) if is_wk else t("freq_short_daily", self.lang)
            c_key = rem.get("color", "yellow")
            color_val = get_color_name(c_key, self.lang)
            title_val = rem.get("title", "(Senza titolo)" if self.lang == "it" else "(Untitled)")

            links = rem.get("links", [])
            valid_links = [l for l in links if l.get("url", "").strip()]
            links_str = t("links_count", self.lang, count=len(valid_links)) if valid_links else t("no_links", self.lang)

            self.tree.insert("", tk.END, iid=rem_id, values=(time_val, freq_val, color_val, title_val, links_str))

        self.root.update_idletasks()


def run_daemon():
    print("[Post-it Daemon] Monitor avviato con successo.", flush=True)
    last_triggered_minute = ""

    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            weekday = now.weekday()

            if current_time != last_triggered_minute:
                reminders = ReminderStore.load_all()
                for rem in reminders:
                    if not rem.get("enabled", True):
                        continue

                    rem_time = rem.get("time", "").strip()
                    freq = rem.get("frequency", "Lun-Ven (Giorni feriali)")

                    is_weekdays = any(k in freq for k in ["Lun-Ven", "Mon-Fri", "feriali", "Weekdays"])
                    is_day_valid = not (is_weekdays and weekday >= 5)

                    if is_day_valid and rem_time == current_time:
                        rem_id = rem.get("id")

                        # Se la finestra è già attiva (es. aperta sul desktop o già mostrata),
                        # invia segnale SIGUSR1 per portarla in allarme senza aprire duplicati
                        if signal_existing_reminder(rem_id, is_alarm=True):
                            print(f"[Post-it Daemon] Allarme inviato a finestra attiva per '{rem.get('title')}'.", flush=True)
                        else:
                            runner = str(RUNNER_SH.resolve()) if RUNNER_SH.exists() else str(Path(__file__).resolve())
                            print(f"[Post-it Daemon] Trigger orario {current_time} per '{rem.get('title')}'.", flush=True)
                            subprocess.Popen(
                                [runner, "--popup", "--alarm", "--id", rem_id],
                                start_new_session=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )

                last_triggered_minute = current_time

        except Exception as e:
            print(f"[Post-it Daemon] Errore monitor: {e}", flush=True)

        time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description="Post-it Reminders Manager")
    parser.add_argument("--popup", action="store_true", help="Avvia finestra popup in sovraimpressione")
    parser.add_argument("--desktop", action="store_true", help="Avvia finestra post-it desktop adesiva")
    parser.add_argument("--alarm", action="store_true", help="Forza la modalità allarme sonoro e sovraimpressione")
    parser.add_argument("--id", type=str, default="", help="ID del promemoria")
    parser.add_argument("--daemon", action="store_true", help="Avvia il demone monitor di background")
    parser.add_argument("--sync-cron", action="store_true", help="Sincronizza crontab")
    parser.add_argument("--list", action="store_true", help="Elenca i promemoria salvati")
    parser.add_argument("--lang", type=str, choices=["it", "en"], default="", help="Forza la lingua dell'applicazione ('it' o 'en')")
    args = parser.parse_args()

    if args.lang:
        ConfigStore.set_language(args.lang)

    ReminderStore.ensure_storage()

    if args.daemon:
        run_daemon()
        sys.exit(0)

    if args.list:
        print(json.dumps(ReminderStore.load_all(), indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.sync_cron:
        ok, msg = CronManager.sync_reminders(ReminderStore.load_all())
        print(msg)
        sys.exit(0 if ok else 1)

    if not TKINTER_AVAILABLE:
        lang = ConfigStore.get_language()
        err_msg = (
            "⚠️  Errore: Il modulo grafico 'tkinter' per Python non è installato nel sistema.\n\n"
            "Post-it Reminders richiede Tkinter per l'interfaccia grafica.\n"
            "Per installarlo esegui il comando corrispondente alla tua distribuzione:\n"
            "  • Fedora / RHEL / CentOS:       sudo dnf install -y python3-tkinter (oppure: sudo dnf5 install -y python3-tkinter)\n"
            "  • Fedora Silverblue / Atomic:   sudo rpm-ostree install python3-tkinter (oppure in Toolbox)\n"
            "  • Ubuntu / Debian / Linux Mint: sudo apt install -y python3-tk\n"
            "  • Arch Linux / Manjaro:          sudo pacman -S --needed tk\n"
            "  • openSUSE:                      sudo zypper install -y python3-tk\n"
            "  • Ambiente Conda/Mamba:          conda install -c conda-forge tk\n\n"
            "Nota: Se non hai privilegi sudo, chiedi all'amministratore di sistema di installare\n"
            "'python3-tkinter' o usa un ambiente Python utente (es. Conda o Toolbox) con Tkinter abilitato."
        ) if lang == "it" else (
            "⚠️  Error: The 'tkinter' GUI package for Python is not installed on this system.\n\n"
            "Post-it Reminders requires Tkinter for its user interface.\n"
            "To install it, run the command for your Linux distribution:\n"
            "  • Fedora / RHEL / CentOS:       sudo dnf install -y python3-tkinter (or: sudo dnf5 install -y python3-tkinter)\n"
            "  • Fedora Silverblue / Atomic:   sudo rpm-ostree install python3-tkinter (or via Toolbox)\n"
            "  • Ubuntu / Debian / Linux Mint: sudo apt install -y python3-tk\n"
            "  • Arch Linux / Manjaro:          sudo pacman -S --needed tk\n"
            "  • openSUSE:                      sudo zypper install -y python3-tk\n"
            "  • Conda/Mamba environment:       conda install -c conda-forge tk\n\n"
            "Note: If you do not have sudo privileges, ask your system administrator to install\n"
            "'python3-tkinter' or use a user-level Python environment (e.g. Conda or Toolbox) with Tkinter."
        )
        print(f"\n{err_msg}\n", file=sys.stderr)
        send_system_notification("Post-it Reminders", "Modulo 'tkinter' mancante. Installa python3-tkinter.")
        sys.exit(1)

    if args.popup or args.desktop:
        rem = None
        if args.id:
            rem = ReminderStore.get_by_id(args.id)
        if not rem:
            reminders = ReminderStore.load_all()
            rem = reminders[0] if reminders else DEFAULT_WELCOME_REMINDERS.get(ConfigStore.get_language(), DEFAULT_WELCOME_REMINDER)

        is_alarm = args.alarm or args.popup
        rem_id = rem.get("id", "default")

        # Controllo Anti-Duplicazione atomico:
        # Se la finestra per questo promemoria è già aperta, invia SIGUSR1 ed esci
        acquired, lock_path = acquire_reminder_lock(rem_id, is_alarm=is_alarm)
        if not acquired:
            sys.exit(0)

        window = PostitWindow(rem, is_alarm_mode=is_alarm, lock_file=lock_path)
        window.show()
        sys.exit(0)

    root = tk.Tk(className="postit-manager")
    configure_dialog_fonts(root)
    app = PostitManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
