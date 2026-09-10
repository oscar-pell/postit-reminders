#!/usr/bin/env python3
"""
Post-it Reminders Manager (Gestore Promemoria Desktop Avanzato)
Desktop utility universale per Linux (Ubuntu, Debian, Fedora, Arch, openSUSE, ecc.)
per la gestione di promemoria stile Post-it con finestre Always-on-Top, modalità
Post-it Desktop adesiva, richiamo orario automatico, palette colori personalizzabile,
formattazione testo ricca, Preset Rapido configurabile e doppio scheduler (Systemd + Cron).
"""

import argparse
from datetime import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, font

# Percorsi di sistema dinamici basati su standard XDG
USER_HOME = Path.home()
APP_DIR = USER_HOME / ".local" / "share" / "postit-app"
ICONS_DIR = USER_HOME / ".local" / "share" / "icons" / "hicolor"
RUN_DIR = Path(f"/run/user/{os.getuid()}/postit-app") if Path(f"/run/user/{os.getuid()}").exists() else APP_DIR / "run"
RUN_DIR.mkdir(parents=True, exist_ok=True)

REMINDERS_FILE = APP_DIR / "reminders.json"
PRESET_FILE = APP_DIR / "preset.json"
ICON_SVG = APP_DIR / "icon.svg"
ICON_PNG = APP_DIR / "icon.png"
RUNNER_SH = USER_HOME / ".local" / "bin" / "postit-runner.sh"
DESKTOP_FILE = USER_HOME / ".local" / "share" / "applications" / "postit-manager.desktop"

# Delimitatori Crontab
CRON_MARKER = "# POSTIT_APP_JOB"
CRON_BLOCK_START = "# === BEGIN POSTIT_APP_JOBS (Generato da Post-it Manager - NON MODIFICARE MANUALMENTE) ==="
CRON_BLOCK_END = "# === END POSTIT_APP_JOBS ==="

# Palette Temi Colore Post-it
COLOR_THEMES = {
    "yellow": {
        "name": "Giallo Classico",
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

# Promemoria generico di benvenuto (nessun dato sensibile o personale)
DEFAULT_WELCOME_REMINDER = {
    "id": "benvenuto-01",
    "time": "18:00",
    "frequency": "Lun-Ven (Giorni feriali)",
    "title": "Benvenuto in Post-it Reminders!",
    "text": "**Questo è il tuo primo post-it:**\n• Modifica orario, frequenza e colori a tuo piacimento.\n• Inserisci collegamenti rapidi ai tuoi siti preferiti.\n• Clicca su **⭐ Salva come Preset** per memorizzare il tuo template personale e riutilizzarlo con un click!",
    "color": "yellow",
    "links": [],
    "enabled": True
}


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


def send_system_notification(title: str, message: str, urgency: str = "critical"):
    """Invia una notifica di sistema desktop cross-desktop tramite libnotify / notify-send."""
    icon_name = "postit-manager"
    clean_msg = re.sub(r"(\*\*|\*|__|\=\=|###\s*)", "", message)
    try:
        subprocess.Popen(
            ["notify-send", "-u", urgency, "-i", icon_name, "-a", "Promemoria Post-it", title, clean_msg],
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
            ReminderStore.save_all([DEFAULT_WELCOME_REMINDER])

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
    """Gestione sincronizzazione atomica con Crontab."""

    @staticmethod
    def is_cron_service_active() -> bool:
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
        res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return res.stdout
        return ""

    @staticmethod
    def sync_reminders(reminders: list) -> tuple[bool, str]:
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
            dow = "1-5" if "Lun-Ven" in freq else "*"

            cmd = f"{runner_path} --popup --alarm --id {rem['id']}"
            job_line = f"{minute} {hour} * * {dow} {cmd} {CRON_MARKER}"
            new_cron_jobs.append(job_line)

        all_lines = [l for l in filtered_lines if l.strip()]
        if new_cron_jobs:
            all_lines.append(CRON_BLOCK_START)
            all_lines.extend(new_cron_jobs)
            all_lines.append(CRON_BLOCK_END)

        new_crontab_content = "\n".join(all_lines) + ("\n" if all_lines else "")

        try:
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
            return True, f"Crontab sincronizzato con successo ({len(new_cron_jobs)} job attivi)."
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() or str(e)
            return False, f"Errore nell'aggiornamento crontab: {err}"
        except Exception as e:
            return False, f"Errore generico crontab: {e}"


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
    """Finestra Post-it autonoma con pulsanti d'azione sempre visibili e auto-sovraimpressione."""

    def __init__(self, reminder: dict, is_alarm_mode: bool = False, parent=None):
        self.reminder = reminder
        self.is_alarm = is_alarm_mode
        self.parent = parent
        self.is_toplevel = parent is not None

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
        title = self.reminder.get("title", "Post-it")
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

        title_text = self.reminder.get("title", "Promemoria")
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
            text="📌 In Primo Piano" if self.is_pinned else "🔓 Normale (Desktop)",
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
            text="🚨 È ARRIVATO L'ORARIO STABILITO! CONTROLLA I TUOI COMPITI",
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
            text="Premi Esc per chiudere",
            bg=self.theme["bg"],
            fg="#64748B",
            font=(self.sys_font, 9, "italic")
        )
        self.status_lbl.pack(side=tk.LEFT)

        btn_done = tk.Button(
            footer_frame,
            text="✓ Ho Fatto / Chiudi",
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
                text="Collegamenti Rapidi:",
                bg=self.theme["bg"],
                fg="#334155",
                font=(self.sys_font, 9, "bold"),
                anchor="w"
            )
            lbl_actions.pack(fill=tk.X, pady=(0, 6))

            for link in valid_links:
                label_txt = link.get("label", "").strip() or "Apri Collegamento"
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

        raw_text = self.reminder.get("text", "Nessun messaggio.")
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
            self.btn_pin.config(text="📌 In Primo Piano", bg="#FDE047", fg="#78350F")
            self.status_lbl.config(text="Fissato sopra tutte le finestre")
        else:
            self.btn_pin.config(text="🔓 Normale (Desktop)", bg="#FFFFFF", fg="#475569")
            self.status_lbl.config(text="Libero (può andare sotto le finestre)")

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

        self.btn_pin.config(text="🚨 SOVRAIMPRESSIONE", bg="#EF4444", fg="#FFFFFF")
        self.alarm_banner.pack(fill=tk.X, after=self.header_frame)
        self.status_lbl.config(text="⏰ È scattato l'orario del promemoria!", fg="#DC2626")

        send_system_notification(
            title=f"📌 {self.reminder.get('title', 'Promemoria')}",
            message=self.reminder.get("text", "È arrivato l'orario stabilito!"),
            urgency="critical"
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

        is_day_valid = True
        if "Lun-Ven" in freq and weekday >= 5:
            is_day_valid = False

        if is_day_valid and now_time == time_target:
            self.trigger_alarm_mode()

    def _handle_click_url(self, url: str, label: str):
        open_url(url)
        self.status_lbl.config(text=f"✓ Apertura '{label}' nel browser completata!", fg="#2563EB")

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
    """Finestra principale di gestione e configurazione promemoria con Preset dinamico."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.sys_font = get_system_font_family()
        self.root.title("Promemoria Post-it - Gestore Desktop")
        self.root.geometry("960x720")
        self.root.minsize(900, 650)

        apply_app_icon(self.root)

        self.editing_id = None
        self.selected_color = "yellow"

        self._init_styles()
        self._build_ui()
        self.refresh_reminders_table()
        self.update_preset_button()
        self.check_system_status()

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

        lbl_app_title = tk.Label(
            title_box,
            text="Promemoria Post-it",
            font=(self.sys_font, 15, "bold"),
            bg="#FFFFFF",
            fg=self.color_text
        )
        lbl_app_title.pack(anchor="w")

        lbl_app_sub = tk.Label(
            title_box,
            text="Post-it Desktop interattivi, promemoria in sovraimpressione e collegamenti rapidi",
            font=(self.sys_font, 9),
            bg="#FFFFFF",
            fg=self.color_muted
        )
        lbl_app_sub.pack(anchor="w")

        badge_box = tk.Frame(header_bar, bg="#FFFFFF")
        badge_box.pack(side=tk.RIGHT)

        self.badge_daemon = tk.Label(
            badge_box,
            text="● Demone: ...",
            font=(self.sys_font, 9, "bold"),
            bg="#F1F5F9",
            fg="#475569",
            padx=10,
            pady=4
        )
        self.badge_daemon.pack(side=tk.LEFT, padx=(0, 6))

        self.badge_cron = tk.Label(
            badge_box,
            text="● Cron: ...",
            font=(self.sys_font, 9, "bold"),
            bg="#F1F5F9",
            fg="#475569",
            padx=10,
            pady=4
        )
        self.badge_cron.pack(side=tk.LEFT)

        main_content = tk.Frame(self.root, bg=self.color_bg, padx=18, pady=14)
        main_content.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(main_content, bg=self.color_bg, width=460)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))

        right_col = tk.Frame(main_content, bg=self.color_bg)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self._build_form(left_col)
        self._build_list(right_col)

        status_bar = tk.Frame(self.root, bg="#FFFFFF", padx=18, pady=8, highlightbackground=self.color_border, highlightthickness=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = tk.Label(status_bar, text="Pronto.", font=(self.sys_font, 9), bg="#FFFFFF", fg=self.color_muted)
        self.lbl_status.pack(side=tk.LEFT)

        lbl_path = tk.Label(status_bar, text=f"Dati: {REMINDERS_FILE.name}", font=(self.sys_font, 9), bg="#FFFFFF", fg="#94A3B8")
        lbl_path.pack(side=tk.RIGHT)

    def _build_form(self, container):
        card = tk.Frame(container, bg=self.color_card, padx=16, pady=14, highlightbackground=self.color_border, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        lbl_section = tk.Label(card, text="Crea o Modifica Post-it", font=(self.sys_font, 12, "bold"), bg=self.color_card, fg=self.color_text)
        lbl_section.pack(anchor="w", pady=(0, 8))

        # PULSANTE PRESET RAPIDO DINAMICO (configurabile)
        self.btn_preset = tk.Button(
            card,
            text="⚡ Carica Preset Rapido...",
            font=(self.sys_font, 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=6,
            command=self.apply_preset
        )
        self.btn_preset.pack(fill=tk.X, pady=(0, 10))

        lbl_colors = tk.Label(card, text="Colore Sfondo Post-it:", font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        lbl_colors.pack(anchor="w")

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
            text=COLOR_THEMES[self.selected_color]["name"],
            font=(self.sys_font, 9, "italic"),
            bg=self.color_card,
            fg="#64748B"
        )
        self.lbl_selected_color_name.pack(side=tk.LEFT, padx=(8, 0))

        row_time = tk.Frame(card, bg=self.color_card)
        row_time.pack(fill=tk.X, pady=(0, 8))

        col_time = tk.Frame(row_time, bg=self.color_card)
        col_time.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        lbl_time = tk.Label(col_time, text="Orario (HH:MM):", font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        lbl_time.pack(anchor="w")

        self.entry_time = tk.Entry(col_time, font=(self.sys_font, 11), bg="#F8FAFC", relief=tk.SOLID, bd=1)
        self.entry_time.insert(0, "18:00")
        self.entry_time.pack(fill=tk.X, pady=(2, 0))

        col_freq = tk.Frame(row_time, bg=self.color_card)
        col_freq.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))

        lbl_freq = tk.Label(col_freq, text="Frequenza:", font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        lbl_freq.pack(anchor="w")

        self.combo_freq = ttk.Combobox(col_freq, values=["Lun-Ven (Giorni feriali)", "Ogni Giorno"], state="readonly", font=(self.sys_font, 10))
        self.combo_freq.set("Lun-Ven (Giorni feriali)")
        self.combo_freq.pack(fill=tk.X, pady=(2, 0))

        lbl_title = tk.Label(card, text="Titolo:", font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        lbl_title.pack(anchor="w")

        self.entry_title = tk.Entry(card, font=(self.sys_font, 10), bg="#F8FAFC", relief=tk.SOLID, bd=1)
        self.entry_title.insert(0, "Chiusura Attività")
        self.entry_title.pack(fill=tk.X, pady=(2, 8))

        lbl_toolbar = tk.Label(card, text="Testo Messaggio (Formattazione):", font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        lbl_toolbar.pack(anchor="w")

        tb_frame = tk.Frame(card, bg="#F1F5F9", padx=4, pady=3, relief=tk.SOLID, bd=1)
        tb_frame.pack(fill=tk.X, pady=(2, 0))

        btn_bold = tk.Button(tb_frame, text="G", font=(self.sys_font, 9, "bold"), width=3, relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("**"))
        btn_bold.pack(side=tk.LEFT, padx=1)

        btn_italic = tk.Button(tb_frame, text="C", font=(self.sys_font, 9, "italic"), width=3, relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("*"))
        btn_italic.pack(side=tk.LEFT, padx=1)

        btn_under = tk.Button(tb_frame, text="S", font=(self.sys_font, 9, "underline"), width=3, relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("__"))
        btn_under.pack(side=tk.LEFT, padx=1)

        btn_hl = tk.Button(tb_frame, text="🟡 Evidenzia", font=(self.sys_font, 8, "bold"), bg="#FEF08A", relief=tk.FLAT, cursor="hand2", command=lambda: self.insert_formatting("=="))
        btn_hl.pack(side=tk.LEFT, padx=3)

        btn_bullet = tk.Button(tb_frame, text="• Elenco", font=(self.sys_font, 8), relief=tk.FLAT, cursor="hand2", command=self.insert_bullet)
        btn_bullet.pack(side=tk.LEFT, padx=1)

        btn_h3 = tk.Button(tb_frame, text="Titolo H3", font=(self.sys_font, 8, "bold"), relief=tk.FLAT, cursor="hand2", command=self.insert_h3)
        btn_h3.pack(side=tk.LEFT, padx=1)

        btn_reset_fmt = tk.Button(tb_frame, text="🧹 Pulisci", font=(self.sys_font, 8), relief=tk.FLAT, cursor="hand2", command=self.clean_formatting)
        btn_reset_fmt.pack(side=tk.RIGHT, padx=1)

        self.txt_text = tk.Text(card, font=(self.sys_font, 10), bg="#F8FAFC", height=5, relief=tk.SOLID, bd=1, wrap=tk.WORD)
        self.txt_text.insert("1.0", "Ricordati di aggiornare le tue attività prima di staccare.")
        self.txt_text.pack(fill=tk.X, pady=(0, 8))

        lbl_links = tk.Label(card, text="Collegamenti Rapidi (Opzionali):", font=(self.sys_font, 9, "bold"), bg=self.color_card, fg="#475569")
        lbl_links.pack(anchor="w")

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
            text="💾 Salva Promemoria",
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

        btn_save_as_preset = tk.Button(
            row_actions,
            text="⭐ Salva come Preset",
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
        btn_save_as_preset.pack(side=tk.LEFT, padx=(0, 6))

        btn_clear = tk.Button(
            row_actions,
            text="Pulisci",
            font=(self.sys_font, 9),
            bg="#F1F5F9",
            fg="#475569",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.clear_form
        )
        btn_clear.pack(side=tk.RIGHT)

    def _build_list(self, container):
        card = tk.Frame(container, bg=self.color_card, padx=16, pady=14, highlightbackground=self.color_border, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        header_row = tk.Frame(card, bg=self.color_card)
        header_row.pack(fill=tk.X, pady=(0, 8))

        self.lbl_list_count = tk.Label(header_row, text="Elenco Promemoria", font=(self.sys_font, 12, "bold"), bg=self.color_card, fg=self.color_text)
        self.lbl_list_count.pack(side=tk.LEFT)

        lbl_hint = tk.Label(header_row, text="💡 Doppio click per mettere sul desktop", font=(self.sys_font, 9, "italic"), bg=self.color_card, fg="#64748B")
        lbl_hint.pack(side=tk.RIGHT)

        table_frame = tk.Frame(card, bg=self.color_card)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("time", "frequency", "color", "title", "links")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("time", text="Orario")
        self.tree.heading("frequency", text="Frequenza")
        self.tree.heading("color", text="Colore")
        self.tree.heading("title", text="Titolo")
        self.tree.heading("links", text="Link")

        self.tree.column("time", width=70, minwidth=60, anchor="center")
        self.tree.column("frequency", width=120, minwidth=90, anchor="w")
        self.tree.column("color", width=80, minwidth=60, anchor="center")
        self.tree.column("title", width=140, minwidth=100, anchor="w")
        self.tree.column("links", width=120, minwidth=80, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.put_selected_on_desktop())

        action_bar = tk.Frame(card, bg=self.color_card)
        action_bar.pack(fill=tk.X, pady=(10, 0))

        btn_desktop = tk.Button(
            action_bar,
            text="📌 Metti sul Desktop",
            font=(self.sys_font, 10, "bold"),
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
        btn_desktop.pack(side=tk.LEFT, padx=(0, 6))

        btn_alarm = tk.Button(
            action_bar,
            text="👁️ Testa Allarme Ora",
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
        btn_alarm.pack(side=tk.LEFT, padx=(0, 6))

        btn_preset_from_row = tk.Button(
            action_bar,
            text="⭐ Imposta come Preset",
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
        btn_preset_from_row.pack(side=tk.LEFT, padx=(0, 6))

        btn_delete = tk.Button(
            action_bar,
            text="🗑️ Elimina",
            font=(self.sys_font, 9, "bold"),
            bg="#EF4444",
            fg="#FFFFFF",
            activebackground="#DC2626",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.delete_selected_reminder
        )
        btn_delete.pack(side=tk.LEFT, padx=(0, 6))

        btn_sync = tk.Button(
            action_bar,
            text="🔄 Sincronizza",
            font=(self.sys_font, 9),
            bg="#F1F5F9",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=7,
            command=self.manual_sync
        )
        btn_sync.pack(side=tk.RIGHT)

    def select_color(self, color_key: str):
        self.selected_color = color_key
        for k, btn in self.color_swatches.items():
            if k == color_key:
                btn.config(text="✓", bd=2)
            else:
                btn.config(text="", bd=1)
        self.lbl_selected_color_name.config(text=COLOR_THEMES[color_key]["name"])

    def insert_formatting(self, marker: str):
        try:
            sel_start = self.txt_text.index(tk.SEL_FIRST)
            sel_end = self.txt_text.index(tk.SEL_LAST)
            selected_text = self.txt_text.get(sel_start, sel_end)
            self.txt_text.delete(sel_start, sel_end)
            self.txt_text.insert(sel_start, f"{marker}{selected_text}{marker}")
        except tk.TclError:
            cur_idx = self.txt_text.index(tk.INSERT)
            self.txt_text.insert(cur_idx, f"{marker}testo{marker}")

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
        cron_ok = CronManager.is_cron_service_active()

        if daemon_ok:
            self.badge_daemon.config(text="● Demone: ATTIVO", bg="#DCFCE7", fg="#15803D")
        else:
            self.badge_daemon.config(text="⚠️ Demone: INATTIVO", bg="#FEF3C7", fg="#B45309")

        if cron_ok:
            self.badge_cron.config(text="● Cron: ATTIVO", bg="#DCFCE7", fg="#15803D")
        else:
            self.badge_cron.config(text="⚠️ Cron: INATTIVO", bg="#FEE2E2", fg="#B91C1C")

    def update_preset_button(self):
        """Aggiorna lo stato e il testo del pulsante Preset in base al file preset.json."""
        preset = PresetStore.load()
        if preset:
            title = preset.get("title", "Preset")
            time_val = preset.get("time", "--:--")
            self.btn_preset.config(
                text=f"⚡ Carica Preset: {title} ({time_val})",
                bg="#FEF08A",
                fg="#854D0E",
                activebackground="#FDE047",
                activeforeground="#713F12"
            )
        else:
            self.btn_preset.config(
                text="⚡ Preset Rapido: (Nessun preset memorizzato - clicca qui per info)",
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
                "Nessun Preset Memorizzato",
                "Non hai ancora memorizzato un Preset Rapido.\n\n"
                "Come creare il tuo Preset:\n"
                "1. Compila i campi del modulo oppure seleziona un promemoria dalla tabella.\n"
                "2. Clicca sul pulsante '⭐ Salva come Preset'.\n\n"
                "I tuoi dati verranno memorizzati nel tuo profilo locale e potrai riutilizzarli al volo in qualsiasi momento!"
            )
            return

        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, preset.get("time", "18:00"))

        self.combo_freq.set(preset.get("frequency", "Lun-Ven (Giorni feriali)"))
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

        self.lbl_status.config(text=f"✓ Preset '{preset.get('title')}' caricato nel modulo.")

    def save_current_form_as_preset(self):
        """Salva i dati attualmente compilati nel form come Preset Rapido."""
        time_str = self.entry_time.get().strip() or "18:00"
        title = self.entry_title.get().strip()
        if not title:
            messagebox.showwarning("Titolo Mancante", "Inserisci almeno un titolo prima di salvare il Preset.")
            return

        text = self.txt_text.get("1.0", tk.END).strip()
        frequency = self.combo_freq.get()

        links = []
        l1_label = self.entry_l1_label.get().strip()
        l1_url = self.entry_l1_url.get().strip()
        if l1_url:
            links.append({"label": l1_label or "Link 1", "url": l1_url})

        l2_label = self.entry_l2_label.get().strip()
        l2_url = self.entry_l2_url.get().strip()
        if l2_url:
            links.append({"label": l2_label or "Link 2", "url": l2_url})

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
            self.lbl_status.config(text=f"⭐ Preset '{title}' memorizzato con successo!")
            messagebox.showinfo(
                "Preset Memorizzato",
                f"Il promemoria '{title}' è stato memorizzato come Preset Rapido!\n\n"
                "• Rimarrà salvato nel tuo sistema anche se elimini questo promemoria dalla tabella.\n"
                "• Potrai ricompilarlo all'istante ogni volta che vorrai cliccando su 'Carica Preset'."
            )
        else:
            messagebox.showerror("Errore", "Impossibile salvare il Preset.")

    def set_selected_as_preset(self):
        """Salva il promemoria selezionato nella tabella come Preset Rapido."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Nessuna selezione", "Seleziona un promemoria dalla tabella da impostare come Preset.")
            return

        rem = ReminderStore.get_by_id(selected[0])
        if not rem:
            return

        preset_data = {
            "time": rem.get("time", "18:00"),
            "frequency": rem.get("frequency", "Lun-Ven (Giorni feriali)"),
            "color": rem.get("color", "yellow"),
            "title": rem.get("title", "Promemoria"),
            "text": rem.get("text", ""),
            "links": rem.get("links", [])
        }

        if PresetStore.save(preset_data):
            self.update_preset_button()
            self.lbl_status.config(text=f"⭐ Promemoria '{rem.get('title')}' impostato come Preset!")
            messagebox.showinfo(
                "Preset Memorizzato",
                f"Il promemoria '{rem.get('title')}' è stato memorizzato come Preset Rapido!\n\n"
                "• Rimarrà salvato nel tuo sistema anche se elimini questo promemoria dalla tabella.\n"
                "• Se in futuro imposti un altro promemoria come preset, sovrascriverà questi dati."
            )
        else:
            messagebox.showerror("Errore", "Impossibile salvare il Preset.")

    def clear_form(self):
        self.editing_id = None
        self.btn_save.config(text="💾 Salva Promemoria")
        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, "18:00")
        self.combo_freq.set("Lun-Ven (Giorni feriali)")
        self.select_color("yellow")
        self.entry_title.delete(0, tk.END)
        self.entry_title.insert(0, "Chiusura Attività")
        self.txt_text.delete("1.0", tk.END)
        self.entry_l1_label.delete(0, tk.END)
        self.entry_l1_url.delete(0, tk.END)
        self.entry_l2_label.delete(0, tk.END)
        self.entry_l2_url.delete(0, tk.END)
        self.lbl_status.config(text="Modulo ripulito.")

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        rem = ReminderStore.get_by_id(item_id)
        if not rem:
            return

        self.editing_id = rem.get("id")
        self.btn_save.config(text="💾 Aggiorna Modifiche")

        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, rem.get("time", "18:00"))

        self.combo_freq.set(rem.get("frequency", "Lun-Ven (Giorni feriali)"))
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

        self.lbl_status.config(text=f"Caricato promemoria: '{rem.get('title')}'")

    def save_reminder_from_form(self):
        time_str = self.entry_time.get().strip()
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", time_str):
            messagebox.showerror("Orario non valido", "Inserisci un orario valido nel formato HH:MM (es. 18:00).")
            return

        parts = time_str.split(":")
        time_str = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

        title = self.entry_title.get().strip()
        if not title:
            messagebox.showerror("Titolo obbligatorio", "Inserisci un titolo per il promemoria.")
            return

        text = self.txt_text.get("1.0", tk.END).strip()
        frequency = self.combo_freq.get()

        links = []
        l1_label = self.entry_l1_label.get().strip()
        l1_url = self.entry_l1_url.get().strip()
        if l1_url:
            links.append({"label": l1_label or "Link 1", "url": l1_url})

        l2_label = self.entry_l2_label.get().strip()
        l2_url = self.entry_l2_url.get().strip()
        if l2_url:
            links.append({"label": l2_label or "Link 2", "url": l2_url})

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
            CronManager.sync_reminders(reminders)
            self.refresh_reminders_table()
            self.clear_form()
            self.lbl_status.config(text=f"✓ Promemoria '{title}' salvato!")
            messagebox.showinfo("Salvataggio Completato", f"Il promemoria '{title}' è stato salvato.\nSarà attivato sia dal demone di sistema sia da Cron.")
        else:
            messagebox.showerror("Errore", "Impossibile salvare il promemoria.")

    def delete_selected_reminder(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Nessuna selezione", "Seleziona un promemoria da eliminare.")
            return

        item_id = selected[0]
        rem = ReminderStore.get_by_id(item_id)
        title = rem.get("title", "questo promemoria") if rem else "questo promemoria"

        if not messagebox.askyesno("Conferma eliminazione", f"Vuoi davvero eliminare '{title}'?"):
            return

        if ReminderStore.delete_by_id(item_id):
            reminders = ReminderStore.load_all()
            CronManager.sync_reminders(reminders)
            self.refresh_reminders_table()
            self.clear_form()
            self.lbl_status.config(text="Promemoria eliminato.")
        else:
            messagebox.showerror("Errore", "Impossibile eliminare il promemoria.")

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
            self.lbl_status.config(text=f"📌 Post-it posizionato sul desktop (processo indipendente).")
        except Exception as e:
            messagebox.showerror("Errore Avvio", f"Impossibile avviare il Post-it sul desktop: {e}")

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
        self.lbl_status.config(text="🚨 Test sovraimpressione allarme inviato a schermo!")

    def manual_sync(self):
        reminders = ReminderStore.load_all()
        ok, msg = CronManager.sync_reminders(reminders)
        self.check_system_status()
        self.lbl_status.config(text=msg)
        if ok:
            messagebox.showinfo("Sincronizzazione", msg)
        else:
            messagebox.showerror("Errore", msg)

    def refresh_reminders_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        reminders = ReminderStore.load_all()
        self.lbl_list_count.config(text=f"Promemoria Attivi ({len(reminders)})")

        for rem in sorted(reminders, key=lambda x: x.get("time", "00:00")):
            rem_id = rem.get("id")
            time_val = rem.get("time", "--:--")
            freq_val = "Lun-Ven" if "Lun-Ven" in rem.get("frequency", "") else "Tutti i gg"
            c_key = rem.get("color", "yellow")
            color_val = COLOR_THEMES.get(c_key, {}).get("name", c_key)
            title_val = rem.get("title", "(Senza titolo)")

            links = rem.get("links", [])
            valid_links = [l for l in links if l.get("url", "").strip()]
            links_str = f"{len(valid_links)} link" if valid_links else "—"

            self.tree.insert("", tk.END, iid=rem_id, values=(time_val, freq_val, color_val, title_val, links_str))


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

                    is_day_valid = True
                    if "Lun-Ven" in freq and weekday >= 5:
                        is_day_valid = False

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
    args = parser.parse_args()

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

    if args.popup or args.desktop:
        rem = None
        if args.id:
            rem = ReminderStore.get_by_id(args.id)
        if not rem:
            reminders = ReminderStore.load_all()
            rem = reminders[0] if reminders else DEFAULT_WELCOME_REMINDER

        is_alarm = args.alarm or args.popup
        window = PostitWindow(rem, is_alarm_mode=is_alarm)
        window.show()
        sys.exit(0)

    root = tk.Tk(className="postit-manager")
    app = PostitManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
