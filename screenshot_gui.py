#!/usr/bin/env python3
"""
screenshot_gui.py
=================
Interfaz gráfica de Screenshot Multi-Shot.
Auto-instala Chromium de Playwright la primera vez que se ejecuta.

Dependencias:
    py -m pip install playwright customtkinter

Generar .exe:
    build.bat
"""

import queue
import re
import sys
import subprocess
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urljoin, urlparse

import customtkinter as ctk

# ── Tema ──────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Constantes ────────────────────────────────────────────────────
PAGE_TIMEOUT   = 30_000
WAIT_AFTER_LOAD = 1.5

EXCLUDE_PATTERNS = [
    r"\.(pdf|zip|png|jpg|jpeg|gif|svg|ico|webp|mp4|mp3|woff|woff2|ttf|eot)$",
    r"^mailto:", r"^tel:", r"^javascript:", r"#", r"/logout", r"/admin",
]

DEVICES = {
    "desktop": {
        "viewport": {"width": 1440, "height": 900},
        "device_scale_factor": 1,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    },
    "tablet": {
        "viewport": {"width": 768, "height": 1024},
        "device_scale_factor": 2,
        "user_agent": (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
    "mobile": {
        "viewport": {"width": 390, "height": 844},
        "device_scale_factor": 3,
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
}


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def normalize_url(url: str, base: str):
    url = url.strip()
    if not url:
        return None
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return None
    full = urljoin(base, url)
    parsed = urlparse(full)
    base_parsed = urlparse(base)
    if parsed.netloc != base_parsed.netloc:
        return None
    return parsed._replace(fragment="").geturl()


def url_to_filename(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        path = "index"
    safe = re.sub(r"[^\w\-]", "_", path)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "index"


# ─────────────────────────────────────────────────────────────────
#  WORKER (hilo de captura)
# ─────────────────────────────────────────────────────────────────

def _crawl(base_url: str, max_depth: int, page, log_fn, stop_event) -> list:
    visited, found = set(), []
    to_visit = [(base_url, 0)]

    while to_visit:
        if stop_event.is_set():
            break
        url, depth = to_visit.pop(0)
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        found.append(url)
        log_fn(f"   [depth={depth}] {url}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            time.sleep(0.3)
            links = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(el => el.getAttribute('href'))"
            )
            for link in links:
                norm = normalize_url(link, base_url)
                if norm and norm not in visited:
                    to_visit.append((norm, depth + 1))
        except Exception as e:
            log_fn(f"   ⚠️  {url}: {e}")
    return found


def _screenshot(page, url: str, filepath: Path, log_fn) -> bool:
    try:
        page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        time.sleep(WAIT_AFTER_LOAD)
        page.evaluate("""
            async () => {
                await new Promise(resolve => {
                    let total = 0;
                    const dist = 300;
                    const t = setInterval(() => {
                        window.scrollBy(0, dist);
                        total += dist;
                        if (total >= document.body.scrollHeight) {
                            clearInterval(t);
                            window.scrollTo(0, 0);
                            resolve();
                        }
                    }, 80);
                });
            }
        """)
        time.sleep(0.5)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(filepath), full_page=True)
        return True
    except Exception as e:
        log_fn(f"      ❌ {e}")
        return False


def worker(cfg: dict, q: queue.Queue, stop_event: threading.Event):
    """Ejecuta el crawl y los screenshots en un hilo separado."""

    def log(msg):      q.put(("log", msg))
    def progress(v, label=""): q.put(("progress", v, label))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        q.put(("error", "Playwright no instalado."))
        return

    base_url          = cfg["base_url"].rstrip("/")
    manual_urls       = cfg["manual_urls"]
    do_crawl_base     = cfg["do_crawl_base"]
    depth_base        = cfg["depth_base"]
    do_crawl_specific = cfg["do_crawl_specific"]
    depth_specific    = cfg["depth_specific"]
    devices           = cfg["devices"]
    output_dir        = cfg["output_dir"]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            # ── Fase 1: construir lista de URLs ───────────────────
            all_urls = [base_url + "/"]

            if do_crawl_base:
                log(f"🔍 Crawling base: {base_url}  (prof. {depth_base})")
                progress(0.0, "Crawling URL base...")
                ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
                page = ctx.new_page()
                for u in _crawl(base_url, depth_base, page, log, stop_event):
                    if u not in all_urls:
                        all_urls.append(u)
                page.close(); ctx.close()

            # Añadir URLs manuales
            for rel in manual_urls:
                full = rel if rel.startswith(("http://", "https://")) \
                       else urljoin(base_url + "/", rel.lstrip("/"))
                if full not in all_urls:
                    all_urls.append(full)

            # Crawl desde específicas (profundidad independiente)
            if do_crawl_specific and manual_urls:
                ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
                page = ctx.new_page()
                for rel in manual_urls:
                    if stop_event.is_set():
                        break
                    spec = rel if rel.startswith(("http://", "https://")) \
                           else urljoin(base_url + "/", rel.lstrip("/"))
                    log(f"🔍 Crawling específica: {spec}  (prof. {depth_specific})")
                    for u in _crawl(spec, depth_specific, page, log, stop_event):
                        if u not in all_urls:
                            all_urls.append(u)
                page.close(); ctx.close()

            if stop_event.is_set():
                log("⛔ Cancelado.")
                q.put(("done", False))
                browser.close()
                return

            log(f"\n📋 Total URLs: {len(all_urls)}")
            for u in all_urls:
                log(f"   • {u}")

            # ── Fase 2: screenshots ───────────────────────────────
            total_tasks = len(all_urls) * len(devices)
            done_tasks  = 0
            ok_count    = 0
            fail_count  = 0

            for device_name in devices:
                if stop_event.is_set():
                    break
                dcfg = DEVICES[device_name]
                log(f"\n{'═'*50}")
                log(f"  📱 {device_name.upper()} — {dcfg['viewport']['width']}×{dcfg['viewport']['height']}")
                log(f"{'═'*50}")

                ctx  = browser.new_context(
                    viewport=dcfg["viewport"],
                    device_scale_factor=dcfg["device_scale_factor"],
                    user_agent=dcfg["user_agent"],
                )
                page = ctx.new_page()

                for i, url in enumerate(all_urls, 1):
                    if stop_event.is_set():
                        break
                    filepath = output_dir / device_name / f"{url_to_filename(url)}.png"
                    log(f"  [{i:02d}/{len(all_urls):02d}] {url}")
                    if _screenshot(page, url, filepath, log):
                        ok_count += 1
                        log(f"         ✅ {filepath.name}")
                    else:
                        fail_count += 1
                    done_tasks += 1
                    progress(done_tasks / total_tasks, f"{device_name} — {i}/{len(all_urls)}")

                page.close(); ctx.close()

            browser.close()

            if stop_event.is_set():
                log("\n⛔ Cancelado por el usuario.")
                q.put(("done", False))
            else:
                log(f"\n{'═'*50}")
                log(f"  🎉 COMPLETADO  ✅ {ok_count} OK  ❌ {fail_count} errores")
                log(f"  📁 {output_dir.resolve()}")
                log(f"{'═'*50}")
                q.put(("done", True))

    except Exception as e:
        q.put(("error", str(e)))


# ─────────────────────────────────────────────────────────────────
#  DIÁLOGO DE INSTALACIÓN DE CHROMIUM
# ─────────────────────────────────────────────────────────────────

class ChromiumInstallerDialog(ctk.CTkToplevel):
    """Se muestra si Chromium no está instalado. Lo descarga automáticamente."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Instalando Chromium")
        self.geometry("520x370")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.success = False

        ctk.CTkLabel(
            self, text="🌐 Descargando Chromium",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(22, 4))

        ctk.CTkLabel(
            self,
            text="Chromium es necesario para capturar los screenshots.\n"
                 "La descarga puede tardar unos minutos (~150 MB).",
            font=ctk.CTkFont(size=13),
            text_color="gray70",
        ).pack(pady=(0, 14))

        self._bar = ctk.CTkProgressBar(self, width=460, mode="indeterminate")
        self._bar.pack(pady=(0, 10))
        self._bar.start()

        self._log = ctk.CTkTextbox(
            self, width=460, height=155,
            font=ctk.CTkFont(size=11, family="Courier"),
        )
        self._log.pack(pady=(0, 12))
        self._log.configure(state="disabled")

        self._status = ctk.CTkLabel(self, text="Descargando...", text_color="gray70")
        self._status.pack()

        threading.Thread(target=self._run_install, daemon=True).start()

    def _append(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _run_install(self):
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.after(0, self._append, line)
            proc.wait()
            self.after(0, self._finish, proc.returncode == 0)
        except Exception as e:
            self.after(0, self._finish, False)

    def _finish(self, ok: bool):
        self._bar.stop()
        self.success = ok
        if ok:
            self._status.configure(text="✅ Chromium instalado correctamente.", text_color="green")
            self.after(1800, self.destroy)
        else:
            self._status.configure(text="❌ Error en la instalación.", text_color="red")
            ctk.CTkButton(self, text="Cerrar", command=self.destroy).pack(pady=6)


# ─────────────────────────────────────────────────────────────────
#  VENTANA PRINCIPAL
# ─────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Screenshot Multi-Shot")
        self.geometry("720x880")
        self.minsize(620, 720)

        self._queue      = queue.Queue()
        self._stop_event = threading.Event()
        self._spec_urls: list[str] = []

        self._build_ui()
        self.after(400, self._check_chromium)

    # ── Construcción de la UI ─────────────────────────────────────

    def _build_ui(self):
        # ── Cabecera ──────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(14, 0))

        ctk.CTkLabel(
            header, text="🖥️  Screenshot Multi-Shot  📱",
            font=ctk.CTkFont(size=21, weight="bold"),
        ).pack(side="left")

        ctk.CTkOptionMenu(
            header, values=["dark", "light", "system"], width=105,
            command=lambda m: ctk.set_appearance_mode(m),
        ).pack(side="right")

        # ── Área scrollable de configuración ─────────────────────
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self._build_base_section(scroll)
        self._sep(scroll)
        self._build_specific_section(scroll)
        self._sep(scroll)
        self._build_devices_section(scroll)
        self._sep(scroll)
        self._build_output_section(scroll)

        # ── Progreso ──────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.pack(fill="x", padx=20, pady=(0, 4))

        self._prog_label = ctk.CTkLabel(prog_frame, text="", text_color="gray70")
        self._prog_label.pack(anchor="w")

        self._prog_bar = ctk.CTkProgressBar(prog_frame, height=12)
        self._prog_bar.pack(fill="x", pady=(2, 6))
        self._prog_bar.set(0)

        # ── Log ───────────────────────────────────────────────────
        self._log_box = ctk.CTkTextbox(
            self, height=155,
            font=ctk.CTkFont(size=11, family="Courier"),
        )
        self._log_box.pack(fill="x", padx=20, pady=(0, 6))
        self._log_box.configure(state="disabled")

        # ── Botones ───────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        self._btn_start = ctk.CTkButton(
            btn_row, text="🚀  Iniciar captura",
            font=ctk.CTkFont(size=15, weight="bold"), height=46,
            command=self._start,
        )
        self._btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._btn_cancel = ctk.CTkButton(
            btn_row, text="⛔  Cancelar",
            font=ctk.CTkFont(size=15), height=46,
            fg_color="gray30", hover_color="gray20", state="disabled",
            command=self._cancel,
        )
        self._btn_cancel.pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _sep(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color="gray25").pack(fill="x", pady=10)

    # ── Sección URL Base ──────────────────────────────────────────

    def _build_base_section(self, p):
        ctk.CTkLabel(p, text="🌐  URL Base",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        self._base_url = ctk.StringVar()
        ctk.CTkEntry(
            p, placeholder_text="https://midominio.com",
            textvariable=self._base_url, height=36,
        ).pack(fill="x", pady=(4, 8))

        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")

        self._crawl_base = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row, text="Auto-crawl", variable=self._crawl_base).pack(side="left")

        ctk.CTkLabel(row, text="Profundidad:", text_color="gray70").pack(side="left", padx=(20, 5))
        self._depth_base = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(row, values=["1","2","3","4","5"],
                          variable=self._depth_base, width=72).pack(side="left")

    # ── Sección URLs Específicas ──────────────────────────────────

    def _build_specific_section(self, p):
        ctk.CTkLabel(p, text="📋  URLs Específicas",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            p, text="Se capturan siempre, independientemente del crawl.",
            text_color="gray60", font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        add_row = ctk.CTkFrame(p, fg_color="transparent")
        add_row.pack(fill="x", pady=(6, 4))

        self._spec_entry = ctk.CTkEntry(
            add_row, placeholder_text="/ruta  o  https://...", height=34,
        )
        self._spec_entry.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._spec_entry.bind("<Return>", lambda _: self._add_spec())

        ctk.CTkButton(add_row, text="+ Añadir", width=92, height=34,
                      command=self._add_spec).pack(side="left")

        # Lista de URLs específicas
        self._spec_list_frame = ctk.CTkFrame(p, fg_color="gray17", corner_radius=8)
        self._spec_list_frame.pack(fill="x", pady=(0, 8))
        self._spec_empty = ctk.CTkLabel(
            self._spec_list_frame,
            text="(ninguna URL añadida)", text_color="gray50",
            font=ctk.CTkFont(size=12),
        )
        self._spec_empty.pack(pady=8)

        # Opciones de crawl para específicas
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")

        self._crawl_specific = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text="Crawl en específicas",
                        variable=self._crawl_specific).pack(side="left")

        ctk.CTkLabel(row, text="Profundidad:", text_color="gray70").pack(side="left", padx=(20, 5))
        self._depth_specific = ctk.StringVar(value="2")
        ctk.CTkOptionMenu(row, values=["1","2","3","4","5"],
                          variable=self._depth_specific, width=72).pack(side="left")

    def _add_spec(self):
        url = self._spec_entry.get().strip()
        if not url or url in self._spec_urls:
            return
        self._spec_urls.append(url)
        self._spec_entry.delete(0, "end")
        self._refresh_spec_list()

    def _remove_spec(self, url: str):
        self._spec_urls.remove(url)
        self._refresh_spec_list()

    def _refresh_spec_list(self):
        for w in self._spec_list_frame.winfo_children():
            w.destroy()
        if not self._spec_urls:
            ctk.CTkLabel(
                self._spec_list_frame,
                text="(ninguna URL añadida)", text_color="gray50",
                font=ctk.CTkFont(size=12),
            ).pack(pady=8)
            return
        for url in self._spec_urls:
            row = ctk.CTkFrame(self._spec_list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=url, anchor="w").pack(side="left", expand=True, fill="x")
            ctk.CTkButton(
                row, text="✕", width=28, height=24,
                fg_color="gray30", hover_color="#c0392b",
                command=lambda u=url: self._remove_spec(u),
            ).pack(side="right")

    # ── Sección Dispositivos ──────────────────────────────────────

    def _build_devices_section(self, p):
        ctk.CTkLabel(p, text="📱  Dispositivos",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))

        self._dev_desktop = ctk.BooleanVar(value=True)
        self._dev_tablet  = ctk.BooleanVar(value=True)
        self._dev_mobile  = ctk.BooleanVar(value=True)

        for var, emoji, label, sub in [
            (self._dev_desktop, "🖥", "Desktop",  "1440 × 900"),
            (self._dev_tablet,  "📟", "Tablet",   "768 × 1024"),
            (self._dev_mobile,  "📱", "Mobile",   "390 × 844"),
        ]:
            card = ctk.CTkFrame(row, fg_color="gray17", corner_radius=8)
            card.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkCheckBox(
                card, text=f"{emoji}  {label}", variable=var,
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(padx=14, pady=(12, 2))
            ctk.CTkLabel(card, text=sub, text_color="gray60",
                         font=ctk.CTkFont(size=11)).pack(padx=14, pady=(0, 12))

    # ── Sección Carpeta de salida ─────────────────────────────────

    def _build_output_section(self, p):
        ctk.CTkLabel(p, text="📁  Carpeta de salida",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))

        self._output_dir = ctk.StringVar(value="screenshots")
        ctk.CTkEntry(row, textvariable=self._output_dir, height=34).pack(
            side="left", expand=True, fill="x", padx=(0, 8)
        )
        ctk.CTkButton(row, text="📂 Explorar", width=105, height=34,
                      command=self._pick_folder).pack(side="left")

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Selecciona carpeta de salida")
        if folder:
            self._output_dir.set(folder)

    # ── Comprobación de Chromium al arrancar ──────────────────────

    def _check_chromium(self):
        def _check():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--no-sandbox", "--disable-dev-shm-usage"],
                    )
                    browser.close()
                ok = True
            except Exception:
                ok = False
            self.after(0, self._on_chromium_result, ok)

        self._prog_label.configure(text="Comprobando Chromium...")
        threading.Thread(target=_check, daemon=True).start()

    def _on_chromium_result(self, ok: bool):
        self._prog_label.configure(text="")
        if not ok:
            dlg = ChromiumInstallerDialog(self)
            self.wait_window(dlg)
            if not dlg.success:
                messagebox.showerror(
                    "Error",
                    "No se pudo instalar Chromium.\n"
                    "Ejecuta manualmente:\n\n"
                    "py -m playwright install chromium",
                )

    # ── Inicio de captura ─────────────────────────────────────────

    def _start(self):
        base_url = self._base_url.get().strip()
        if not base_url:
            messagebox.showwarning("URL requerida", "Introduce la URL base de tu web.")
            return
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url

        devices = [
            name for name, var in [
                ("desktop", self._dev_desktop),
                ("tablet",  self._dev_tablet),
                ("mobile",  self._dev_mobile),
            ] if var.get()
        ]
        if not devices:
            messagebox.showwarning("Sin dispositivos", "Selecciona al menos un dispositivo.")
            return

        cfg = {
            "base_url":          base_url,
            "manual_urls":       list(self._spec_urls),
            "do_crawl_base":     self._crawl_base.get(),
            "depth_base":        int(self._depth_base.get()),
            "do_crawl_specific": self._crawl_specific.get(),
            "depth_specific":    int(self._depth_specific.get()),
            "devices":           devices,
            "output_dir":        Path(self._output_dir.get() or "screenshots"),
        }

        # Reset UI
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._prog_bar.set(0)
        self._prog_label.configure(text="Iniciando...")
        self._btn_start.configure(state="disabled")
        self._btn_cancel.configure(state="normal")
        self._stop_event.clear()

        threading.Thread(
            target=worker,
            args=(cfg, self._queue, self._stop_event),
            daemon=True,
        ).start()
        self._poll()

    def _cancel(self):
        self._stop_event.set()
        self._btn_cancel.configure(state="disabled")
        self._prog_label.configure(text="Cancelando...")

    # ── Polling de la cola de mensajes ────────────────────────────

    def _poll(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]

                if kind == "log":
                    self._log_box.configure(state="normal")
                    self._log_box.insert("end", msg[1] + "\n")
                    self._log_box.see("end")
                    self._log_box.configure(state="disabled")

                elif kind == "progress":
                    self._prog_bar.set(msg[1])
                    if len(msg) > 2:
                        self._prog_label.configure(
                            text=f"{int(msg[1]*100)}%  —  {msg[2]}"
                        )

                elif kind in ("done", "error"):
                    self._btn_start.configure(state="normal")
                    self._btn_cancel.configure(state="disabled")
                    if kind == "done" and msg[1]:
                        self._prog_bar.set(1)
                        self._prog_label.configure(text="✅ Completado")
                        messagebox.showinfo(
                            "✅ Completado",
                            f"Screenshots guardados en:\n{self._output_dir.get()}",
                        )
                    elif kind == "error":
                        self._prog_label.configure(text="❌ Error")
                        messagebox.showerror("Error", msg[1])
                    return  # Detener el polling

        except queue.Empty:
            pass

        self.after(100, self._poll)


# ─────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
