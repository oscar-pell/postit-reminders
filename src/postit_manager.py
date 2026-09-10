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
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from pathlib import Path

# Versione applicazione e coordinate repository GitHub
APP_VERSION = "1.1.3"
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

        "status_ready": "Pronto.",
        "status_data": "Dati: {filename}",

        "form_section_title": "Crea o Modifica Post-it",
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
        "table_double_click_hint": "💡 Doppio click per mettere sul desktop",
        "col_time": "Orario",
        "col_freq": "Frequenza",
        "col_color": "Colore",
        "col_title": "Titolo",
        "col_links": "Link",
        "links_count": "{count} link",
        "no_links": "—",

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
        "msg_save_success_body": "Il promemoria '{title}' è stato salvato.\nSarà attivato sia dal demone di sistema sia da Cron.",
        "msg_save_error": "Impossibile salvare il promemoria.",
        "msg_delete_confirm_title": "Conferma eliminazione",
        "msg_delete_confirm_body": "Vuoi davvero eliminare '{title}'?",
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
        "msg_update_success_body": "L'applicazione è stata aggiornata con successo alla versione {version}!\n\nRiavvia l'applicazione per utilizzare le nuove funzionalità.",
        "msg_update_error_title": "Errore Aggiornamento",
        "msg_update_error_body": "Impossibile completare l'aggiornamento automatico: {error}\n\nPuoi scaricare l'aggiornamento manualmente da GitHub.",
        "sync_all_success": "✓ Demone Systemd e Crontab sincronizzati con successo!",
        "sync_daemon_success": "✓ Demone Systemd ricaricato con successo (promemoria attivi)!",
        "sync_manual_done": "✓ Schedulatore sincronizzato.",

        "status_preset_loaded": "✓ Preset '{title}' caricato nel modulo.",
        "status_preset_stored": "⭐ Preset '{title}' memorizzato con successo!",
        "status_form_cleared": "Modulo ripulito.",
        "status_reminder_loaded": "Caricato promemoria: '{title}'",
        "status_reminder_saved": "✓ Promemoria '{title}' salvato!",
        "status_reminder_deleted": "Promemoria eliminato.",
        "status_desktop_launched": "📌 Post-it posizionato sul desktop (processo indipendente).",
        "status_alarm_tested": "🚨 Test sovraimpressione allarme inviato a schermo!",

        "postit_default_title": "Promemoria",
        "postit_pin_on": "📌 In Primo Piano",
        "postit_pin_off": "🔓 Normale (Desktop)",
        "postit_status_pinned": "Fissato sopra tutte le finestre",
        "postit_status_unpinned": "Libero (può andare sotto le finestre)",
        "postit_btn_alarm": "🚨 SOVRAIMPRESSIONE",
        "postit_alarm_banner": "🚨 È ARRIVATO L'ORARIO STABILITO! CONTROLLA I TUOI COMPITI",
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

        "status_ready": "Ready.",
        "status_data": "Data: {filename}",

        "form_section_title": "Create or Edit Post-it",
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
        "table_double_click_hint": "💡 Double-click to pin on desktop",
        "col_time": "Time",
        "col_freq": "Frequency",
        "col_color": "Color",
        "col_title": "Title",
        "col_links": "Links",
        "links_count": "{count} links",
        "no_links": "—",

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
        "msg_save_success_body": "Reminder '{title}' has been saved.\nIt will be triggered by both the background daemon and Cron.",
        "msg_save_error": "Could not save the reminder.",
        "msg_delete_confirm_title": "Confirm Deletion",
        "msg_delete_confirm_body": "Do you really want to delete '{title}'?",
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
        "msg_update_success_body": "Successfully updated to {version}!\n\nPlease restart the application to use the new features.",
        "msg_update_error_title": "Update Error",
        "msg_update_error_body": "Unable to complete automatic update: {error}\n\nYou can update manually from GitHub.",
        "sync_all_success": "✓ Systemd Daemon and Crontab successfully synchronized!",
        "sync_daemon_success": "✓ Systemd Daemon successfully reloaded (active reminders)!",
        "sync_manual_done": "✓ Scheduler synchronized.",

        "status_preset_loaded": "✓ Preset '{title}' loaded into form.",
        "status_preset_stored": "⭐ Preset '{title}' saved successfully!",
        "status_form_cleared": "Form cleared.",
        "status_reminder_loaded": "Loaded reminder: '{title}'",
        "status_reminder_saved": "✓ Reminder '{title}' saved!",
        "status_reminder_deleted": "Reminder deleted.",
        "status_desktop_launched": "📌 Sticky note placed on desktop (independent process).",
        "status_alarm_tested": "🚨 Alarm overlay test sent to screen!",

        "postit_default_title": "Reminder",
        "postit_pin_on": "📌 Always on Top",
        "postit_pin_off": "🔓 Normal (Desktop)",
        "postit_status_pinned": "Pinned above all windows",
        "postit_status_unpinned": "Desktop sticky (can go behind windows)",
        "postit_btn_alarm": "🚨 OVERLAY ALARM",
        "postit_alarm_banner": "🚨 TIME'S UP! CHECK YOUR SCHEDULED TASKS",
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
        """
        req = urllib.request.Request(
            GITHUB_API_LATEST,
            headers={
                "User-Agent": "PostitReminders-App",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    return False, None, f"HTTP {resp.status}"
                data = json.loads(resp.read().decode("utf-8"))
                latest_tag = data.get("tag_name", "").strip()
                latest_ver = UpdateManager.parse_version(latest_tag)
                current_ver = UpdateManager.parse_version(APP_VERSION)
                has_update = latest_ver > current_ver
                return has_update, data, latest_tag
        except Exception as e:
            return False, None, str(e)

    @staticmethod
    def perform_automatic_update(release_info: dict) -> tuple[bool, str]:
        """
        Scarica e installa l'ultima versione dell'applicazione.
        Tenta prima l'aggiornamento tramite git pull se presente un repository locale,
        altrimenti scarica e aggiorna i binari utente direttamente da GitHub.
        """
        tag = release_info.get("tag_name", "main")

        # 1. Tentativo con git se esiste un repository locale
        candidate_git_dirs = [
            Path(__file__).resolve().parent.parent,
            USER_HOME / "postit-reminders"
        ]
        for g_dir in candidate_git_dirs:
            if (g_dir / ".git").is_dir() and (g_dir / "install.sh").exists():
                try:
                    subprocess.run(
                        ["git", "pull", "--ff-only", "origin", "main"],
                        cwd=str(g_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=15,
                        check=True
                    )
                    subprocess.run(
                        ["bash", str(g_dir / "install.sh")],
                        cwd=str(g_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=30,
                        check=True
                    )
                    return True, f"Aggiornato con successo da repository locale ({tag})."
                except Exception:
                    pass

        # 2. Aggiornamento diretto da GitHub Raw
        try:
            raw_base = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{tag}"
            py_url = f"{raw_base}/src/postit_manager.py"
            sh_url = f"{raw_base}/src/postit-runner.sh"

            req_py = urllib.request.Request(py_url, headers={"User-Agent": "PostitReminders-App"})
            with urllib.request.urlopen(req_py, timeout=12) as resp:
                py_code = resp.read().decode("utf-8")

            req_sh = urllib.request.Request(sh_url, headers={"User-Agent": "PostitReminders-App"})
            with urllib.request.urlopen(req_sh, timeout=12) as resp:
                sh_code = resp.read().decode("utf-8")

            bin_dir = USER_HOME / ".local" / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)

            tmp_py = bin_dir / "postit_manager.py.tmp"
            tmp_py.write_text(py_code, encoding="utf-8")
            tmp_py.chmod(0o755)

            # Controllo sintassi Python prima della sostituzione
            res_test = subprocess.run([sys.executable, "-m", "py_compile", str(tmp_py)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res_test.returncode != 0:
                tmp_py.unlink(missing_ok=True)
                return False, "File scaricato non valido (errore di compilazione)."

            target_py = bin_dir / "postit_manager.py"
            tmp_py.replace(target_py)

            target_sh = bin_dir / "postit-runner.sh"
            target_sh.write_text(sh_code, encoding="utf-8")
            target_sh.chmod(0o755)

            if CronManager.is_daemon_service_active():
                try:
                    subprocess.run(["systemctl", "--user", "restart", "postit-daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

            return True, f"Aggiornato con successo alla versione {tag} in {bin_dir}."
        except Exception as e:
            return False, f"Errore durante l'aggiornamento: {e}"


def render_formatted_text(text_widget: tk.Text, raw_text: str, theme: dict):
    """Renderizza testo formattato in stile Markdown all'interno del Text widget."""
    sys_font = get_system_font_family()
    text_widget.configure(state=tk.NORMAL)
    text_widget.delete("1.0", tk.END)

    f_base = font.Font(family=sys_font, size=11)
    f_bold = font.Font(family=sys_font, size=11, weight="bold")
    f_italic = font.Font(family=sys_font, size=11, slant="italic")
    f_header = font.Font(family=sys_font, size=12, weight="bold")

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

    def __init__(self, reminder: dict, is_alarm_mode: bool = False, parent=None, lang: str = None):
        self.reminder = reminder
        self.is_alarm = is_alarm_mode
        self.parent = parent
        self.is_toplevel = parent is not None
        self.lang = lang or ConfigStore.get_language()

        self.lock_file = RUN_DIR / f"window_{self.reminder.get('id', 'default')}.active"
        try:
            self.lock_file.write_text(str(os.getpid()))
        except Exception:
            pass

        if self.is_toplevel:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk(className="postit-manager")

        color_key = self.reminder.get("color", "yellow")
        self.theme = COLOR_THEMES.get(color_key, COLOR_THEMES["yellow"])
        self.sys_font = get_system_font_family()
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
            font=(self.sys_font, 12, "bold"),
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
            padx=6,
            pady=2
        )
        self.badge_frame.pack(side=tk.RIGHT, padx=(0, 4))

        self.lbl_time = tk.Label(
            self.badge_frame,
            text=f"⏰ {time_text}",
            bg=self.theme["badge_bg"],
            fg=self.theme["badge_fg"],
            font=(self.sys_font, 9, "bold")
        )
        self.lbl_time.pack()

        sep = tk.Frame(self.main_card, bg=self.theme["border"], height=1)
        sep.pack(fill=tk.X)

        # Banner Allarme
        self.alarm_banner = tk.Frame(self.main_card, bg="#EF4444", padx=10, pady=6)
        self.lbl_alarm_banner = tk.Label(
            self.alarm_banner,
            text=t("postit_alarm_banner", self.lang),
            bg="#EF4444",
            fg="#FFFFFF",
            font=(self.sys_font, 10, "bold")
        )
        self.lbl_alarm_banner.pack()

        # 2. FOOTER
        footer_frame = tk.Frame(self.main_card, bg=self.theme["bg"], padx=16, pady=10)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_lbl = tk.Label(
            footer_frame,
            text=t("postit_press_esc", self.lang),
            bg=self.theme["bg"],
            fg="#64748B",
            font=(self.sys_font, 9, "italic")
        )
        self.status_lbl.pack(side=tk.LEFT)

        btn_done = tk.Button(
            footer_frame,
            text=t("postit_btn_done", self.lang),
            bg="#10B981",
            fg="#FFFFFF",
            activebackground="#059669",
            activeforeground="#FFFFFF",
            font=(self.sys_font, 10, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=6,
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

    def _handle_click_url(self, url: str, label: str):
        open_url(url)
        self.status_lbl.config(text=t("postit_url_opened", self.lang, label=label), fg="#2563EB")

    def close(self):
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception:
            pass

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

        style = ttk.Style()
        try:
            style.theme_use("clam")
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

        self.badge_daemon = tk.Label(
            hdr_right,
            text="● Demone: ...",
            font=(self.sys_font, 9, "bold"),
            bg="#F1F5F9",
            fg="#475569",
            padx=9,
            pady=4
        )
        self.badge_daemon.pack(side=tk.LEFT, padx=(0, 6))

        self.badge_cron = tk.Label(
            hdr_right,
            text="● Cron: ...",
            font=(self.sys_font, 9, "bold"),
            bg="#F1F5F9",
            fg="#475569",
            padx=9,
            pady=4
        )
        self.badge_cron.pack(side=tk.LEFT, padx=(0, 10))

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

        # Form
        self.lbl_form_section.config(text=t("form_section_title", self.lang))
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

        if self.editing_id:
            self.btn_save.config(text=t("btn_update_reminder", self.lang))
        else:
            self.btn_save.config(text=t("btn_save_reminder", self.lang))
        self.btn_save_as_preset.config(text=t("btn_save_as_preset", self.lang))
        self.btn_clear.config(text=t("btn_clear", self.lang))

        # List & Table
        self.lbl_hint.config(text=t("table_double_click_hint", self.lang))
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

        self.lbl_form_section = tk.Label(card, text=t("form_section_title", self.lang), font=(self.sys_font, 12, "bold"), bg=self.color_card, fg=self.color_text)
        self.lbl_form_section.pack(anchor="w", pady=(0, 8))

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

        self.lbl_hint = tk.Label(header_row, text=t("table_double_click_hint", self.lang), font=(self.sys_font, 9, "italic"), bg=self.color_card, fg="#64748B")
        self.lbl_hint.pack(side=tk.RIGHT)

        table_frame = tk.Frame(card, bg=self.color_card)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("time", "frequency", "color", "title", "links")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

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

        if daemon_ok:
            self.badge_daemon.config(text=t("daemon_active", self.lang), bg="#DCFCE7", fg="#15803D")
        else:
            self.badge_daemon.config(text=t("daemon_inactive", self.lang), bg="#FEF3C7", fg="#B45309")

        if cron_ok:
            self.badge_cron.config(text=t("cron_active", self.lang), bg="#DCFCE7", fg="#15803D")
        elif not cron_avail:
            self.badge_cron.config(text=t("cron_not_installed_badge", self.lang), bg="#F1F5F9", fg="#64748B")
        elif daemon_ok:
            self.badge_cron.config(text=t("cron_optional_badge", self.lang), bg="#F1F5F9", fg="#64748B")
        else:
            self.badge_cron.config(text=t("cron_inactive", self.lang), bg="#FEE2E2", fg="#B91C1C")

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

    def clear_form(self):
        self.editing_id = None
        self.btn_save.config(text=t("btn_save_reminder", self.lang))
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
        self.lbl_status.config(text=t("status_form_cleared", self.lang))

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        rem = ReminderStore.get_by_id(item_id)
        if not rem:
            return

        self.editing_id = rem.get("id")
        self.btn_save.config(text=t("btn_update_reminder", self.lang))

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

        self.lbl_status.config(text=t("status_reminder_loaded", self.lang, title=rem.get('title')))

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

        item_id = selected[0]
        rem = ReminderStore.get_by_id(item_id)
        title = rem.get("title", "") if rem else ""

        if not messagebox.askyesno(t("msg_delete_confirm_title", self.lang), t("msg_delete_confirm_body", self.lang, title=title)):
            return

        if ReminderStore.delete_by_id(item_id):
            reminders = ReminderStore.load_all()
            try:
                CronManager.sync_reminders(reminders, lang=self.lang)
            except Exception as e:
                print(f"[Warning] Sincronizzazione crontab non riuscita: {e}")

            self.refresh_reminders_table()
            self.clear_form()
            self.check_system_status()
            self.lbl_status.config(text=t("status_reminder_deleted", self.lang))
        else:
            messagebox.showerror(t("msg_error_title", self.lang), t("msg_delete_error", self.lang))

    def put_selected_on_desktop(self):
        selected = self.tree.selection()
        if selected:
            rem_id = selected[0]
        elif self.editing_id:
            rem_id = self.editing_id
        else:
            reminders = ReminderStore.load_all()
            rem_id = reminders[0]["id"] if reminders else "benvenuto-01"

        runner = str(RUNNER_SH.resolve()) if RUNNER_SH.exists() else str(Path(__file__).resolve())
        try:
            subprocess.Popen(
                [runner, "--desktop", "--id", rem_id],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.lbl_status.config(text=t("status_desktop_launched", self.lang))
        except Exception as e:
            messagebox.showerror(t("msg_launch_error_title", self.lang), t("msg_launch_error_body", self.lang, error=e))

    def test_alarm_now(self):
        selected = self.tree.selection()
        if selected:
            rem_id = selected[0]
        elif self.editing_id:
            rem_id = self.editing_id
        else:
            reminders = ReminderStore.load_all()
            rem_id = reminders[0]["id"] if reminders else "benvenuto-01"

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
        dlg.geometry("560x480")
        dlg.minsize(500, 420)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg="#FFFFFF")
        apply_app_icon(dlg)

        try:
            dlg.geometry("+%d+%d" % (
                self.root.winfo_rootx() + (self.root.winfo_width() - 560) // 2,
                self.root.winfo_rooty() + (self.root.winfo_height() - 480) // 2
            ))
        except Exception:
            pass

        hdr = tk.Frame(dlg, bg="#EFF6FF", padx=20, pady=16)
        hdr.pack(fill=tk.X)

        lbl_h = tk.Label(hdr, text=f"🎉 {t('msg_update_header', self.lang)}", font=(self.sys_font, 13, "bold"), bg="#EFF6FF", fg="#1D4ED8")
        lbl_h.pack(anchor="w")

        info_text = f"{t('msg_current_version', self.lang)} {APP_VERSION}   ➜   {t('msg_latest_version', self.lang)} {tag}"
        lbl_v = tk.Label(hdr, text=info_text, font=(self.sys_font, 10, "bold"), bg="#EFF6FF", fg="#1E40AF")
        lbl_v.pack(anchor="w", pady=(4, 0))

        body_frame = tk.Frame(dlg, bg="#FFFFFF", padx=20, pady=12)
        body_frame.pack(fill=tk.BOTH, expand=True)

        lbl_notes = tk.Label(body_frame, text=t("msg_release_notes", self.lang), font=(self.sys_font, 9, "bold"), bg="#FFFFFF", fg="#475569")
        lbl_notes.pack(anchor="w", pady=(0, 6))

        txt_notes = tk.Text(body_frame, font=(self.sys_font, 9), bg="#F8FAFC", relief=tk.SOLID, bd=1, wrap=tk.WORD)
        txt_notes.pack(fill=tk.BOTH, expand=True)
        raw_body = release_info.get("body", "").strip() or "Nuovo rilascio disponibile con ottimizzazioni e miglioramenti."
        txt_notes.insert("1.0", raw_body)
        txt_notes.config(state=tk.DISABLED)

        lbl_progress = tk.Label(body_frame, text="", font=(self.sys_font, 9, "italic"), bg="#FFFFFF", fg="#0284C7")
        lbl_progress.pack(anchor="w", pady=(6, 0))

        b_bar = tk.Frame(dlg, bg="#FFFFFF", padx=20, pady=14)
        b_bar.pack(fill=tk.X, side=tk.BOTTOM)

        def do_update():
            lbl_progress.config(text=t("msg_update_in_progress", self.lang))
            btn_upd.config(state=tk.DISABLED)
            dlg.update_idletasks()

            def bg_work():
                ok, msg = UpdateManager.perform_automatic_update(release_info)
                def on_done():
                    if ok:
                        messagebox.showinfo(
                            t("msg_update_success_title", self.lang),
                            t("msg_update_success_body", self.lang, version=tag),
                            parent=dlg
                        )
                        dlg.destroy()
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
            b_bar,
            text=t("btn_update_now", self.lang),
            font=(self.sys_font, 10, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=7,
            command=do_update
        )
        btn_upd.pack(side=tk.LEFT, padx=(0, 8))

        btn_gh = tk.Button(
            b_bar,
            text=t("btn_view_github", self.lang),
            font=(self.sys_font, 9),
            bg="#F1F5F9",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=7,
            command=lambda: webbrowser.open(release_info.get("html_url", GITHUB_RELEASES_URL))
        )
        btn_gh.pack(side=tk.LEFT, padx=(0, 8))

        btn_cancel = tk.Button(
            b_bar,
            text=t("btn_close_dialog", self.lang),
            font=(self.sys_font, 9),
            bg="#F1F5F9",
            fg="#64748B",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=7,
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
    print("[Post-it Daemon] Monitor avviato con successo.")
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
                        lock_file = RUN_DIR / f"window_{rem_id}.active"

                        if not lock_file.exists():
                            runner = str(RUNNER_SH.resolve()) if RUNNER_SH.exists() else str(Path(__file__).resolve())
                            print(f"[Post-it Daemon] Trigger orario {current_time} per '{rem.get('title')}'.")
                            subprocess.Popen(
                                [runner, "--popup", "--alarm", "--id", rem_id],
                                start_new_session=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )

                last_triggered_minute = current_time

        except Exception as e:
            print(f"[Post-it Daemon] Errore monitor: {e}")

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
        window = PostitWindow(rem, is_alarm_mode=is_alarm)
        window.show()
        sys.exit(0)

    root = tk.Tk(className="postit-manager")
    app = PostitManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
