# 📸 Screen Multi-Shot

Captura screenshots **full-page** de una web entera en Desktop, Tablet y Mobile. Combina URLs manuales con crawling automático de todos los enlaces internos.

---

## Versiones

| Versión | Archivo | Para quién |
|---|---|---|
| **GUI** *(recomendada)* | `screenshot_gui.py` / `ScreenshotMultiShot.exe` | Uso diario, sin terminal |
| **CLI** | `screenshot_web.py` | Automatización, scripts |

---

## Instalación

**Windows**
```bash
py -m pip install -r requirements_gui.txt
py -m playwright install chromium
```

**macOS / Linux**
```bash
pip install -r requirements_gui.txt
playwright install chromium
```

> [!NOTE]
> La versión GUI instala Chromium automáticamente la primera vez que se ejecuta, sin necesidad de hacerlo manualmente.

---

## Uso

### GUI
```bash
py screenshot_gui.py
```

Dos pestañas:
- **📸 Capturar** — configura URL, crawl, dispositivos y lanza la captura
- **🖼️ Mockups** — inserta los screenshots generados en frames de iPhone, iPad o MacBook

### CLI
```bash
py screenshot_web.py
```

El script pregunta todo de forma interactiva antes de arrancar.

---

## Mockups

La pestaña **🖼️ Mockups** detecta automáticamente el área de pantalla de cada frame y compone la imagen final.

> [!IMPORTANT]
> Coloca los PNG de los dispositivos en la carpeta `mockups/` antes de usar esta función:
> ```
> mockups/
> ├── iphone.png
> ├── ipad.png
> └── macbook.png
> ```

El resultado se guarda en `mockups_output/`, organizado por dispositivo.

---

## Salida

```
screenshots/
├── desktop/     ← 1440×900 px
├── tablet/      ← 768×1024 px (retina ×2)
└── mobile/      ← 390×844 px  (retina ×3)
```

Cada PNG recibe el nombre de la ruta de la URL. La raíz `/` se guarda como `index.png`.

---

## Crawl

El crawler sigue todos los `<a href>` internos de forma recursiva. La profundidad es configurable e **independiente** para la URL base y para las URLs específicas.

> [!WARNING]
> Profundidades altas (4-5) en webs grandes pueden generar cientos de URLs y tardar mucho tiempo.

URLs excluidas automáticamente: archivos binarios (`.pdf`, `.zip`, imágenes…), `mailto:`, `tel:`, `#`, `/logout`, `/admin`.

---

## Generar .exe

```bash
build.bat
```

El ejecutable queda en `dist/ScreenshotMultiShot.exe`. Copia la carpeta `mockups/` junto al `.exe` para que funcione la pestaña de mockups.

---

## Requisitos

| | Versión mínima |
|---|---|
| Python | 3.10+ |
| playwright | 1.44+ |
| customtkinter | 5.2+ |
| Pillow | 10.0+ |
| numpy | 1.24+ |

---

## Licencia

MIT
