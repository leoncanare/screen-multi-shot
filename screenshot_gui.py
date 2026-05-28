#!/usr/bin/env python3
"""
screenshot_gui.py
=================
Interfaz gráfica de Screenshot Multi-Shot.
Pestañas: Capturar · Mockups

Dependencias:
    py -m pip install playwright customtkinter Pillow numpy

Generar .exe:
    build.bat

Mockups (colocar en carpeta mockups/):
    mockups/iphone.png
    mockups/ipad.png
    mockups/macbook.png
"""

import queue
import re
import sys
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urljoin, urlparse

import customtkinter as ctk
import icons as ic

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Tema ──────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Constantes captura ────────────────────────────────────────────
PAGE_TIMEOUT    = 30_000
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

# ── Constantes mockup ─────────────────────────────────────────────
MOCKUP_CONFIG = {
    "mobile":  {"file": "iphone.png",  "viewport_w": 390,  "viewport_h": 844},
    "tablet":  {"file": "ipad.png",    "viewport_w": 768,  "viewport_h": 1024},
    "desktop": {"file": "macbook.png", "viewport_w": 1440, "viewport_h": 900},
}


def get_base_dir() -> Path:
    """Carpeta del .exe (frozen) o del script (desarrollo)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_mockups_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "mockups"
    return Path(__file__).parent / "mockups"


# ─────────────────────────────────────────────────────────────────
#  HELPERS CAPTURA
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
    if parsed.netloc != urlparse(base).netloc:
        return None
    return parsed._replace(fragment="").geturl()


def url_to_filename(url: str) -> str:
    path = urlparse(url).path.strip("/") or "index"
    safe = re.sub(r"[^\w\-]", "_", path)
    return re.sub(r"_+", "_", safe).strip("_") or "index"


# ─────────────────────────────────────────────────────────────────
#  WORKER CAPTURA
# ─────────────────────────────────────────────────────────────────

def _crawl(base_url, max_depth, page, log_fn, stop_event):
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
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
            for link in links:
                norm = normalize_url(link, base_url)
                if norm and norm not in visited:
                    to_visit.append((norm, depth + 1))
        except Exception as e:
            log_fn(f"   ⚠️  {url}: {e}")
    return found


def _screenshot(page, url, filepath, log_fn):
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
                            clearInterval(t); window.scrollTo(0,0); resolve();
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


def capture_worker(cfg, q, stop_event):
    def log(msg):           q.put(("log", msg))
    def progress(v, lbl=""): q.put(("progress", v, lbl))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        q.put(("error", "Playwright no instalado."))
        return

    base_url = cfg["base_url"].rstrip("/")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            all_urls = [base_url + "/"]

            if cfg["do_crawl_base"]:
                log(f"🔍 Crawling base: {base_url}  (prof. {cfg['depth_base']})")
                progress(0, "Crawling URL base...")
                ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
                page = ctx.new_page()
                for u in _crawl(base_url, cfg["depth_base"], page, log, stop_event):
                    if u not in all_urls:
                        all_urls.append(u)
                page.close(); ctx.close()

            for rel in cfg["manual_urls"]:
                full = rel if rel.startswith(("http://", "https://")) \
                       else urljoin(base_url + "/", rel.lstrip("/"))
                if full not in all_urls:
                    all_urls.append(full)

            if cfg["do_crawl_specific"] and cfg["manual_urls"]:
                ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
                page = ctx.new_page()
                for rel in cfg["manual_urls"]:
                    if stop_event.is_set():
                        break
                    spec = rel if rel.startswith(("http://", "https://")) \
                           else urljoin(base_url + "/", rel.lstrip("/"))
                    log(f"🔍 Crawling específica: {spec}  (prof. {cfg['depth_specific']})")
                    for u in _crawl(spec, cfg["depth_specific"], page, log, stop_event):
                        if u not in all_urls:
                            all_urls.append(u)
                page.close(); ctx.close()

            if stop_event.is_set():
                q.put(("done", False)); browser.close(); return

            log(f"\n📋 Total URLs: {len(all_urls)}")
            for u in all_urls:
                log(f"   • {u}")

            total_tasks = len(all_urls) * len(cfg["devices"])
            done_tasks  = 0
            ok_count    = 0

            for device_name in cfg["devices"]:
                if stop_event.is_set():
                    break
                dcfg = DEVICES[device_name]
                log(f"\n{'═'*50}\n  📱 {device_name.upper()} — "
                    f"{dcfg['viewport']['width']}×{dcfg['viewport']['height']}\n{'═'*50}")
                ctx  = browser.new_context(
                    viewport=dcfg["viewport"],
                    device_scale_factor=dcfg["device_scale_factor"],
                    user_agent=dcfg["user_agent"],
                )
                page = ctx.new_page()
                for i, url in enumerate(all_urls, 1):
                    if stop_event.is_set():
                        break
                    filepath = cfg["output_dir"] / device_name / f"{url_to_filename(url)}.png"
                    log(f"  [{i:02d}/{len(all_urls):02d}] {url}")
                    if _screenshot(page, url, filepath, log):
                        ok_count += 1
                        log(f"         ✅ {filepath.name}")
                    done_tasks += 1
                    progress(done_tasks / total_tasks, f"{device_name} — {i}/{len(all_urls)}")
                page.close(); ctx.close()

            browser.close()
            if stop_event.is_set():
                log("\n⛔ Cancelado."); q.put(("done", False))
            else:
                log(f"\n{'═'*50}\n  🎉 COMPLETADO  ✅ {ok_count} OK\n  📁 {cfg['output_dir'].resolve()}\n{'═'*50}")
                q.put(("done", True))
    except Exception as e:
        q.put(("error", str(e)))


# ─────────────────────────────────────────────────────────────────
#  MOCKUP COMPOSITOR
# ─────────────────────────────────────────────────────────────────

def detect_screen_area(img_path: Path):
    """
    Detecta el área de pantalla blanca dentro del mockup usando BFS desde
    las esquinas para distinguir fondo de la zona de pantalla.
    Devuelve (left, top, right, bottom) o None.
    """
    try:
        import numpy as np
        arr = np.array(Image.open(img_path).convert("RGB"))
        h, w = arr.shape[:2]

        # Máscara de píxeles blancos (todos los canales > 240)
        white = np.all(arr > 240, axis=2)

        # BFS desde las 4 esquinas para marcar el fondo blanco
        visited = np.zeros((h, w), dtype=bool)
        q = deque()
        for r, c in [(0, 0), (0, w-1), (h-1, 0), (h-1, w-1)]:
            if white[r, c] and not visited[r, c]:
                visited[r, c] = True
                q.append((r, c))
        while q:
            r, c = q.popleft()
            for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
                nr, nc = r+dr, c+dc
                if 0 <= nr < h and 0 <= nc < w and white[nr, nc] and not visited[nr, nc]:
                    visited[nr, nc] = True
                    q.append((nr, nc))

        # Pantalla = blanco que NO es fondo
        screen = white & ~visited
        if not screen.any():
            return None

        rows = np.where(screen.any(axis=1))[0]
        cols = np.where(screen.any(axis=0))[0]
        return (int(cols[0]), int(rows[0]), int(cols[-1]+1), int(rows[-1]+1))
    except Exception:
        return None


def apply_mockup(screenshot_path: Path, mockup_path: Path, screen_bbox, output_path: Path) -> bool:
    """
    Inserta el screenshot en el mockup:
    1. Recorta al ratio del viewport (above the fold)
    2. Redimensiona al área de pantalla del mockup
    3. Pega el screenshot
    4. Re-aplica los píxeles oscuros del frame encima (notch, biseles, botones)
    """
    try:
        import numpy as np
        sx, sy, ex, ey = screen_bbox
        screen_w, screen_h = ex - sx, ey - sy

        mockup     = Image.open(mockup_path).convert("RGB")
        screenshot = Image.open(screenshot_path).convert("RGB")
        shot_w, shot_h = screenshot.size

        # Recortar al aspect ratio del área de pantalla en el mockup
        crop_h = min(int(shot_w * screen_h / screen_w), shot_h)
        resized = screenshot.crop((0, 0, shot_w, crop_h)).resize(
            (screen_w, screen_h), Image.LANCZOS
        )

        mockup_arr = np.array(mockup)
        result_arr = mockup_arr.copy()

        # Pegar screenshot en el área de pantalla
        result_arr[sy:ey, sx:ex] = np.array(resized)

        # Re-aplicar píxeles oscuros del frame (notch, bordes redondeados, botones)
        region = mockup_arr[sy:ey, sx:ex]
        is_frame = np.any(region < 200, axis=2)
        result_arr[sy:ey, sx:ex] = np.where(
            is_frame[:, :, np.newaxis], region, result_arr[sy:ey, sx:ex]
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(result_arr).save(output_path)
        return True
    except Exception as e:
        return False


def mockup_worker(cfg, q, stop_event):
    def log(msg):            q.put(("log", msg))
    def progress(v, lbl=""): q.put(("progress", v, lbl))

    if not PIL_AVAILABLE:
        q.put(("error", "Pillow no instalado. Ejecuta: py -m pip install Pillow numpy"))
        return

    screenshots_dir = cfg["screenshots_dir"]
    output_dir      = cfg["output_dir"]
    devices         = cfg["devices"]
    mockups_dir     = cfg["mockups_dir"]

    # Detectar área de pantalla en cada mockup
    screen_areas = {}
    for device in devices:
        mockup_file = mockups_dir / MOCKUP_CONFIG[device]["file"]
        if not mockup_file.exists():
            q.put(("error", f"Falta el archivo: mockups/{MOCKUP_CONFIG[device]['file']}"))
            return
        log(f"🔍 Analizando {mockup_file.name}...")
        bbox = detect_screen_area(mockup_file)
        if bbox is None:
            q.put(("error", f"No se pudo detectar la pantalla en {mockup_file.name}"))
            return
        screen_areas[device] = bbox
        log(f"   ✅ Pantalla detectada: {bbox[0]},{bbox[1]} → {bbox[2]},{bbox[3]}")

    # Recopilar tareas
    tasks = []
    for device in devices:
        folder = screenshots_dir / device
        if folder.exists():
            for png in sorted(folder.glob("*.png")):
                tasks.append((device, png))
        else:
            log(f"⚠️  Carpeta no encontrada: {folder}")

    if not tasks:
        log("⚠️  No se encontraron screenshots.")
        q.put(("done", False))
        return

    log(f"\n📋 {len(tasks)} mockups a generar\n")
    ok_count = 0

    for i, (device, png_path) in enumerate(tasks, 1):
        if stop_event.is_set():
            break
        mockup_path = mockups_dir / MOCKUP_CONFIG[device]["file"]
        out_path    = output_dir / device / png_path.name

        log(f"  [{i:02d}/{len(tasks):02d}] {device}/{png_path.name}")
        if apply_mockup(png_path, mockup_path, screen_areas[device], out_path):
            ok_count += 1
            log(f"         ✅ guardado")
        else:
            log(f"         ❌ error al procesar")

        progress(i / len(tasks), f"{device} — {png_path.stem}")

    if stop_event.is_set():
        log("\n⛔ Cancelado.")
        q.put(("done", False))
    else:
        log(f"\n🎉 COMPLETADO — {ok_count}/{len(tasks)} OK")
        log(f"📁 {output_dir.resolve()}")
        q.put(("done", True))


# ─────────────────────────────────────────────────────────────────
#  DIÁLOGO INSTALACIÓN CHROMIUM
# ─────────────────────────────────────────────────────────────────

class ChromiumInstallerDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Instalando Chromium")
        self.geometry("520x370")
        self.resizable(False, False)
        self.grab_set(); self.lift(); self.focus_force()
        self.success = False

        ctk.CTkLabel(self, text="Descargando Chromium",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(22, 4))
        ctk.CTkLabel(self,
                     text="Chromium es necesario para capturar los screenshots.\n"
                          "La descarga puede tardar unos minutos (~150 MB).",
                     font=ctk.CTkFont(size=13), text_color="gray70").pack(pady=(0, 14))

        self._bar = ctk.CTkProgressBar(self, width=460, mode="indeterminate")
        self._bar.pack(pady=(0, 10))
        self._bar.start()

        self._log = ctk.CTkTextbox(self, width=460, height=155,
                                    font=ctk.CTkFont(size=11, family="Courier"))
        self._log.pack(pady=(0, 12))
        self._log.configure(state="disabled")

        self._status = ctk.CTkLabel(self, text="Descargando...", text_color="gray70")
        self._status.pack()

        threading.Thread(target=self._run_install, daemon=True).start()

    def _append(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _run_install(self):
        try:
            # En un .exe compilado con PyInstaller, sys.executable apunta al propio
            # .exe, no a Python. Usamos 'py' del PATH para evitar el bucle infinito.
            if getattr(sys, "frozen", False):
                import shutil
                python = shutil.which("py") or shutil.which("python")
                if not python:
                    self.after(0, self._append,
                               "❌ No se encontró Python en el PATH.\n"
                               "Ejecuta manualmente:\n  py -m playwright install chromium")
                    self.after(0, self._finish, False)
                    return
            else:
                python = sys.executable

            proc = subprocess.Popen(
                [python, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                if line.strip():
                    self.after(0, self._append, line.rstrip())
            proc.wait()
            self.after(0, self._finish, proc.returncode == 0)
        except Exception:
            self.after(0, self._finish, False)

    def _finish(self, ok):
        self._bar.stop()
        self.success = ok
        if ok:
            self._status.configure(text="✅ Chromium instalado.", text_color="green")
            self.after(1800, self.destroy)
        else:
            self._status.configure(text="❌ Error en la instalación.", text_color="red")
            ctk.CTkButton(self, text="Cerrar", command=self.destroy).pack(pady=6)


# ─────────────────────────────────────────────────────────────────
#  APP PRINCIPAL
# ─────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Screenshot Multi-Shot")
        self.geometry("740x900")
        self.minsize(640, 740)

        # Estado captura
        self._cap_queue = queue.Queue()
        self._cap_stop  = threading.Event()
        self._spec_urls: list[str] = []

        # Estado mockup
        self._mock_queue    = queue.Queue()
        self._mock_stop     = threading.Event()
        self._mock_dev_info = {}

        self._build_ui()
        self.after(400, self._check_chromium)

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Cabecera
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(14, 6))
        ctk.CTkLabel(header, text="Screenshot Multi-Shot",
                     font=ctk.CTkFont(size=21, weight="bold")).pack(side="left")
        ctk.CTkOptionMenu(header, values=["dark", "light", "system"], width=105,
                          command=lambda m: ctk.set_appearance_mode(m)).pack(side="right")

        # Tabs
        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        cap_frame  = self._tabs.add("Capturar")
        mock_frame = self._tabs.add("Mockups")

        self._build_capture_tab(cap_frame)
        self._build_mockup_tab(mock_frame)

    # ── Tab Capturar ──────────────────────────────────────────────

    def _build_capture_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=2, pady=(4, 0))

        self._build_base_section(scroll)
        self._sep(scroll)
        self._build_specific_section(scroll)
        self._sep(scroll)
        self._build_devices_section(scroll)
        self._sep(scroll)
        self._build_output_section(scroll)

        # Progreso
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.pack(fill="x", padx=2, pady=(6, 0))
        self._cap_prog_label = ctk.CTkLabel(pf, text="", text_color="gray70")
        self._cap_prog_label.pack(anchor="w")
        self._cap_prog_bar = ctk.CTkProgressBar(pf, height=12)
        self._cap_prog_bar.pack(fill="x", pady=(2, 6))
        self._cap_prog_bar.set(0)

        # Log
        self._cap_log = ctk.CTkTextbox(parent, height=145,
                                        font=ctk.CTkFont(size=11, family="Courier"))
        self._cap_log.pack(fill="x", padx=2, pady=(0, 6))
        self._cap_log.configure(state="disabled")

        # Botones
        br = ctk.CTkFrame(parent, fg_color="transparent")
        br.pack(fill="x", padx=2, pady=(0, 6))
        self._cap_btn_start = ctk.CTkButton(
            br, text="  Iniciar captura", image=ic.get("rocket-launch", 20), compound="left",
            font=ctk.CTkFont(size=15, weight="bold"), height=46,
            command=self._start_capture)
        self._cap_btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._cap_btn_cancel = ctk.CTkButton(
            br, text="  Cancelar", image=ic.get("x-circle", 20), compound="left",
            font=ctk.CTkFont(size=15), height=46,
            fg_color="gray30", hover_color="gray20", state="disabled",
            command=self._cancel_capture)
        self._cap_btn_cancel.pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _sep(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color="gray25").pack(fill="x", pady=10)

    def _build_base_section(self, p):
        ctk.CTkLabel(p, text="  URL Base", image=ic.get("globe-alt", 16), compound="left",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        self._base_url = ctk.StringVar()
        ctk.CTkEntry(p, placeholder_text="https://midominio.com",
                     textvariable=self._base_url, height=36).pack(fill="x", pady=(4, 8))
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self._crawl_base = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row, text="Auto-crawl", variable=self._crawl_base).pack(side="left")
        ctk.CTkLabel(row, text="Profundidad:", text_color="gray70").pack(side="left", padx=(20, 5))
        self._depth_base = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(row, values=["1","2","3","4","5"],
                          variable=self._depth_base, width=72).pack(side="left")

    def _build_specific_section(self, p):
        ctk.CTkLabel(p, text="URLs Específicas",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(p, text="Se capturan siempre, independientemente del crawl.",
                     text_color="gray60", font=ctk.CTkFont(size=12)).pack(anchor="w")

        add_row = ctk.CTkFrame(p, fg_color="transparent")
        add_row.pack(fill="x", pady=(6, 4))
        self._spec_entry = ctk.CTkEntry(add_row, placeholder_text="/ruta  o  https://...", height=34)
        self._spec_entry.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._spec_entry.bind("<Return>", lambda _: self._add_spec())
        ctk.CTkButton(add_row, text=" Añadir", image=ic.get("plus", 14), compound="left",
                      width=92, height=34, command=self._add_spec).pack(side="left")

        self._spec_list_frame = ctk.CTkFrame(p, fg_color="gray17", corner_radius=8)
        self._spec_list_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._spec_list_frame, text="(ninguna URL añadida)",
                     text_color="gray50", font=ctk.CTkFont(size=12)).pack(pady=8)

        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self._crawl_specific = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text="Crawl en específicas",
                        variable=self._crawl_specific).pack(side="left")
        ctk.CTkLabel(row, text="Profundidad:", text_color="gray70").pack(side="left", padx=(20, 5))
        self._depth_specific = ctk.StringVar(value="2")
        ctk.CTkOptionMenu(row, values=["1","2","3","4","5"],
                          variable=self._depth_specific, width=72).pack(side="left")

    def _build_devices_section(self, p):
        ctk.CTkLabel(p, text="  Dispositivos", image=ic.get("device-phone-mobile", 16),
                     compound="left", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        self._dev_desktop = ctk.BooleanVar(value=True)
        self._dev_tablet  = ctk.BooleanVar(value=True)
        self._dev_mobile  = ctk.BooleanVar(value=True)
        _dev_icons = {"Desktop": "computer-desktop", "Tablet": "device-tablet", "Mobile": "device-phone-mobile"}
        for var, label, sub in [
            (self._dev_desktop, "Desktop", "1440 × 900"),
            (self._dev_tablet,  "Tablet",  "768 × 1024"),
            (self._dev_mobile,  "Mobile",  "390 × 844"),
        ]:
            card = ctk.CTkFrame(row, fg_color="gray17", corner_radius=8)
            card.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkLabel(card, text="", image=ic.get(_dev_icons[label], 22)).pack(pady=(10, 0))
            ctk.CTkCheckBox(card, text=label, variable=var,
                            font=ctk.CTkFont(size=13, weight="bold")).pack(padx=14, pady=(4, 2))
            ctk.CTkLabel(card, text=sub, text_color="gray60",
                         font=ctk.CTkFont(size=11)).pack(padx=14, pady=(0, 10))

    def _build_output_section(self, p):
        ctk.CTkLabel(p, text="  Carpeta de salida", image=ic.get("folder", 16),
                     compound="left", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        self._output_dir = ctk.StringVar(value=str(get_base_dir() / "screenshots"))
        ctk.CTkEntry(row, textvariable=self._output_dir, height=34).pack(
            side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(row, text=" Explorar", image=ic.get("folder-open", 16), compound="left",
                      width=105, height=34, command=self._pick_output).pack(side="left")

    def _pick_output(self):
        folder = filedialog.askdirectory(title="Carpeta de salida")
        if folder:
            self._output_dir.set(folder)

    def _add_spec(self):
        url = self._spec_entry.get().strip()
        if not url or url in self._spec_urls:
            return
        self._spec_urls.append(url)
        self._spec_entry.delete(0, "end")
        self._refresh_spec_list()

    def _remove_spec(self, url):
        self._spec_urls.remove(url)
        self._refresh_spec_list()

    def _refresh_spec_list(self):
        for w in self._spec_list_frame.winfo_children():
            w.destroy()
        if not self._spec_urls:
            ctk.CTkLabel(self._spec_list_frame, text="(ninguna URL añadida)",
                         text_color="gray50", font=ctk.CTkFont(size=12)).pack(pady=8)
            return
        for url in self._spec_urls:
            row = ctk.CTkFrame(self._spec_list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=url, anchor="w").pack(side="left", expand=True, fill="x")
            ctk.CTkButton(row, text="", image=ic.get("x-mark", 14), width=28, height=24,
                          fg_color="gray30", hover_color="#c0392b",
                          command=lambda u=url: self._remove_spec(u)).pack(side="right")

    # ── Tab Mockups ───────────────────────────────────────────────

    def _build_mockup_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=2, pady=(4, 0))

        # Carpeta de screenshots
        ctk.CTkLabel(scroll, text="  Carpeta de screenshots",
                     image=ic.get("folder-open", 16), compound="left",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", pady=(4, 8))
        self._mock_src = ctk.StringVar(value=str(get_base_dir() / "screenshots"))
        ctk.CTkEntry(row, textvariable=self._mock_src, height=34).pack(
            side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(row, text=" Explorar", image=ic.get("folder-open", 16), compound="left",
                      width=100, height=34, command=self._pick_mock_src).pack(side="left")
        ctk.CTkButton(row, text=" Escanear", image=ic.get("arrow-path", 16), compound="left",
                      width=100, height=34, command=self._scan_mockups, fg_color="gray30",
                      hover_color="gray20").pack(side="left", padx=(8, 0))

        # Carpeta de mockups PNG
        self._sep(scroll)
        ctk.CTkLabel(scroll, text="  Carpeta de mockups PNG",
                     image=ic.get("folder", 16), compound="left",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(scroll,
                     text="Carpeta que contiene  iphone.png · ipad.png · macbook.png",
                     text_color="gray60", font=ctk.CTkFont(size=12)).pack(anchor="w")
        row_m = ctk.CTkFrame(scroll, fg_color="transparent")
        row_m.pack(fill="x", pady=(4, 0))
        self._mock_frames_dir = ctk.StringVar(value=str(get_mockups_dir()))
        ctk.CTkEntry(row_m, textvariable=self._mock_frames_dir, height=34).pack(
            side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(row_m, text=" Explorar", image=ic.get("folder-open", 16), compound="left",
                      width=100, height=34, command=self._pick_mock_frames_dir).pack(side="left")

        # Tarjetas de dispositivo
        self._sep(scroll)
        ctk.CTkLabel(scroll, text="  Dispositivos", image=ic.get("device-phone-mobile", 16),
                     compound="left", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        cards = ctk.CTkFrame(scroll, fg_color="transparent")
        cards.pack(fill="x", pady=(8, 0))

        _mock_dev_icons = {
            "mobile": "device-phone-mobile",
            "tablet": "device-tablet",
            "desktop": "computer-desktop",
        }
        for device, label, mockup_file in [
            ("mobile",  "Mobile",  "iphone.png"),
            ("tablet",  "Tablet",  "ipad.png"),
            ("desktop", "Desktop", "macbook.png"),
        ]:
            card = ctk.CTkFrame(cards, fg_color="gray17", corner_radius=8)
            card.pack(side="left", expand=True, fill="x", padx=4)

            var = ctk.BooleanVar(value=True)
            ctk.CTkLabel(card, text="", image=ic.get(_mock_dev_icons[device], 22)).pack(pady=(10, 0))
            ctk.CTkCheckBox(card, text=label, variable=var,
                            font=ctk.CTkFont(size=13, weight="bold")).pack(padx=14, pady=(4, 4))

            shots_lbl = ctk.CTkLabel(card, text="—", text_color="gray50",
                                      font=ctk.CTkFont(size=11))
            shots_lbl.pack(padx=14, pady=2)

            mock_lbl = ctk.CTkLabel(card, text=mockup_file, text_color="gray50",
                                     font=ctk.CTkFont(size=10))
            mock_lbl.pack(padx=14, pady=(0, 12))

            self._mock_dev_info[device] = {
                "var": var, "shots_lbl": shots_lbl,
                "mock_lbl": mock_lbl, "file": mockup_file,
            }

        # Carpeta de salida
        self._sep(scroll)
        ctk.CTkLabel(scroll, text="  Carpeta de salida", image=ic.get("folder", 16),
                     compound="left", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", pady=(4, 0))
        self._mock_out = ctk.StringVar(value=str(get_base_dir() / "mockups_output"))
        ctk.CTkEntry(row2, textvariable=self._mock_out, height=34).pack(
            side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(row2, text=" Explorar", image=ic.get("folder-open", 16), compound="left",
                      width=100, height=34, command=self._pick_mock_out).pack(side="left")

        # Progreso
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.pack(fill="x", padx=2, pady=(6, 0))
        self._mock_prog_label = ctk.CTkLabel(pf, text="", text_color="gray70")
        self._mock_prog_label.pack(anchor="w")
        self._mock_prog_bar = ctk.CTkProgressBar(pf, height=12)
        self._mock_prog_bar.pack(fill="x", pady=(2, 6))
        self._mock_prog_bar.set(0)

        # Log
        self._mock_log = ctk.CTkTextbox(parent, height=130,
                                         font=ctk.CTkFont(size=11, family="Courier"))
        self._mock_log.pack(fill="x", padx=2, pady=(0, 6))
        self._mock_log.configure(state="disabled")

        # Botones
        br = ctk.CTkFrame(parent, fg_color="transparent")
        br.pack(fill="x", padx=2, pady=(0, 6))
        self._mock_btn_start = ctk.CTkButton(
            br, text="  Generar Mockups", image=ic.get("sparkles", 20), compound="left",
            font=ctk.CTkFont(size=15, weight="bold"), height=46,
            command=self._start_mockups)
        self._mock_btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._mock_btn_cancel = ctk.CTkButton(
            br, text="  Cancelar", image=ic.get("x-circle", 20), compound="left",
            font=ctk.CTkFont(size=15), height=46,
            fg_color="gray30", hover_color="gray20", state="disabled",
            command=self._cancel_mockups)
        self._mock_btn_cancel.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.after(700, self._scan_mockups)

    def _pick_mock_src(self):
        folder = filedialog.askdirectory(title="Carpeta de screenshots")
        if folder:
            self._mock_src.set(folder)
            self._scan_mockups()

    def _pick_mock_frames_dir(self):
        folder = filedialog.askdirectory(title="Carpeta con los PNG de mockups")
        if folder:
            self._mock_frames_dir.set(folder)
            self._scan_mockups()

    def _pick_mock_out(self):
        folder = filedialog.askdirectory(title="Carpeta de salida para mockups")
        if folder:
            self._mock_out.set(folder)

    def _scan_mockups(self):
        src         = Path(self._mock_src.get())
        mockups_dir = Path(self._mock_frames_dir.get())
        for device, info in self._mock_dev_info.items():
            # Contar screenshots disponibles
            folder = src / device
            if folder.exists():
                count = len(list(folder.glob("*.png")))
                color = "gray70" if count > 0 else "orange"
                info["shots_lbl"].configure(
                    text=f"{count} screenshot{'s' if count != 1 else ''}",
                    text_color=color,
                )
            else:
                info["shots_lbl"].configure(text="carpeta no encontrada", text_color="orange")

            # Verificar archivo de mockup
            mock_path = mockups_dir / info["file"]
            if mock_path.exists():
                info["mock_lbl"].configure(text=f"✅ {info['file']}", text_color="#2ecc71")
            else:
                info["mock_lbl"].configure(
                    text=f"❌ {info['file']} (falta en mockups/)", text_color="#e74c3c")

    # ── Chromium ──────────────────────────────────────────────────

    def _check_chromium(self):
        def _check():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    b = p.chromium.launch(headless=True,
                                         args=["--no-sandbox", "--disable-dev-shm-usage"])
                    b.close()
                ok = True
            except Exception:
                ok = False
            self.after(0, self._on_chromium_result, ok)

        self._cap_prog_label.configure(text="Comprobando Chromium...")
        threading.Thread(target=_check, daemon=True).start()

    def _on_chromium_result(self, ok):
        self._cap_prog_label.configure(text="")
        if not ok:
            dlg = ChromiumInstallerDialog(self)
            self.wait_window(dlg)
            if not dlg.success:
                messagebox.showerror("Error",
                    "No se pudo instalar Chromium.\n"
                    "Ejecuta manualmente:\n\npy -m playwright install chromium")

    # ── Inicio/cancelación captura ────────────────────────────────

    def _start_capture(self):
        base_url = self._base_url.get().strip()
        if not base_url:
            messagebox.showwarning("URL requerida", "Introduce la URL base de tu web.")
            return
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url

        devices = [n for n, v in [("desktop", self._dev_desktop),
                                   ("tablet",  self._dev_tablet),
                                   ("mobile",  self._dev_mobile)] if v.get()]
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
        self._reset_log(self._cap_log)
        self._cap_prog_bar.set(0)
        self._cap_prog_label.configure(text="Iniciando...")
        self._cap_btn_start.configure(state="disabled")
        self._cap_btn_cancel.configure(state="normal")
        self._cap_stop.clear()
        threading.Thread(target=capture_worker,
                         args=(cfg, self._cap_queue, self._cap_stop),
                         daemon=True).start()
        self._poll_capture()

    def _cancel_capture(self):
        self._cap_stop.set()
        self._cap_btn_cancel.configure(state="disabled")
        self._cap_prog_label.configure(text="Cancelando...")

    def _poll_capture(self):
        try:
            while True:
                msg = self._cap_queue.get_nowait()
                if msg[0] == "log":
                    self._append_log(self._cap_log, msg[1])
                elif msg[0] == "progress":
                    self._cap_prog_bar.set(msg[1])
                    if len(msg) > 2:
                        self._cap_prog_label.configure(
                            text=f"{int(msg[1]*100)}%  —  {msg[2]}")
                elif msg[0] in ("done", "error"):
                    self._cap_btn_start.configure(state="normal")
                    self._cap_btn_cancel.configure(state="disabled")
                    if msg[0] == "done" and msg[1]:
                        self._cap_prog_bar.set(1)
                        self._cap_prog_label.configure(text="✅ Completado")
                        out = self._output_dir.get()
                        messagebox.showinfo("✅ Completado",
                            f"Screenshots guardados en:\n{out}")
                        self._mock_src.set(out)
                        self._scan_mockups()
                    elif msg[0] == "error":
                        messagebox.showerror("Error", msg[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_capture)

    # ── Inicio/cancelación mockups ────────────────────────────────

    def _start_mockups(self):
        if not PIL_AVAILABLE:
            messagebox.showerror("Pillow no instalado",
                "Ejecuta:\n\npy -m pip install Pillow numpy")
            return

        devices = [d for d, info in self._mock_dev_info.items() if info["var"].get()]
        if not devices:
            messagebox.showwarning("Sin dispositivos", "Selecciona al menos un dispositivo.")
            return

        cfg = {
            "screenshots_dir": Path(self._mock_src.get()),
            "mockups_dir":     Path(self._mock_frames_dir.get()),
            "devices":         devices,
            "output_dir":      Path(self._mock_out.get() or "mockups_output"),
        }
        self._reset_log(self._mock_log)
        self._mock_prog_bar.set(0)
        self._mock_prog_label.configure(text="Iniciando...")
        self._mock_btn_start.configure(state="disabled")
        self._mock_btn_cancel.configure(state="normal")
        self._mock_stop.clear()
        threading.Thread(target=mockup_worker,
                         args=(cfg, self._mock_queue, self._mock_stop),
                         daemon=True).start()
        self._poll_mockups()

    def _cancel_mockups(self):
        self._mock_stop.set()
        self._mock_btn_cancel.configure(state="disabled")
        self._mock_prog_label.configure(text="Cancelando...")

    def _poll_mockups(self):
        try:
            while True:
                msg = self._mock_queue.get_nowait()
                if msg[0] == "log":
                    self._append_log(self._mock_log, msg[1])
                elif msg[0] == "progress":
                    self._mock_prog_bar.set(msg[1])
                    if len(msg) > 2:
                        self._mock_prog_label.configure(
                            text=f"{int(msg[1]*100)}%  —  {msg[2]}")
                elif msg[0] in ("done", "error"):
                    self._mock_btn_start.configure(state="normal")
                    self._mock_btn_cancel.configure(state="disabled")
                    if msg[0] == "done" and msg[1]:
                        self._mock_prog_bar.set(1)
                        self._mock_prog_label.configure(text="✅ Completado")
                        messagebox.showinfo("✅ Completado",
                            f"Mockups guardados en:\n{self._mock_out.get()}")
                    elif msg[0] == "error":
                        self._mock_prog_label.configure(text="❌ Error")
                        messagebox.showerror("Error", msg[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_mockups)

    # ── Helpers log ───────────────────────────────────────────────

    def _reset_log(self, box):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.configure(state="disabled")

    def _append_log(self, box, text):
        box.configure(state="normal")
        box.insert("end", text + "\n")
        box.see("end")
        box.configure(state="disabled")


# ─────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
