# 📸 Screen Multi-Shot

Captura screenshots **full-page** de una web entera en Desktop, Tablet y Mobile. Combina URLs manuales con crawling automático de todos los enlaces internos.

---

## Descarga rápida (Windows)

> [!TIP]
> Sin Python, sin instalación. Descarga la carpeta `dist/` del repositorio y ejecuta directamente el `.exe`.

```
dist/
├── ScreenshotMultiShot.exe   ← ejecutar esto
└── mockups/
    ├── iphone.png
    ├── ipad.png
    └── macbook.png
```

La primera vez que se abra descargará Chromium automáticamente (~150 MB).

---

## Versiones

| Versión | Archivo | Para quién |
|---|---|---|
| **GUI** *(recomendada)* | `dist/ScreenshotMultiShot.exe` | Uso diario, sin terminal |
| **Script** | `screenshot_gui.py` | Desarrollo / macOS / Linux |
| **CLI** | `screenshot_web.py` | Automatización, scripts |

---

## Instalación desde código fuente

**Windows**
```bash
py -m pip install -r requirements.txt
py -m playwright install chromium
py screenshot_gui.py
```

**macOS / Linux**
```bash
pip install -r requirements.txt
playwright install chromium
python screenshot_gui.py
```

> [!NOTE]
> La versión GUI instala Chromium automáticamente la primera vez que se ejecuta, sin necesidad de hacerlo manualmente.

---

## Uso

Dos pestañas:
- **Capturar** — configura URL, crawl, dispositivos y lanza la captura
- **Mockups** — inserta los screenshots generados en frames de iPhone, iPad o MacBook

### Estructura de salida

```
screenshots/
├── desktop/     ← 1440×900 px
├── tablet/      ← 768×1024 px (retina ×2)
└── mobile/      ← 390×844 px  (retina ×3)
```

Cada PNG recibe el nombre de la ruta de la URL. La raíz `/` se guarda como `index.png`.

---

## Mockups

La pestaña **Mockups** detecta automáticamente el área de pantalla de cada frame y compone la imagen final.

> [!IMPORTANT]
> Los PNG de los dispositivos deben estar en la carpeta `mockups/` junto al `.exe` (ya incluida en `dist/`):
> ```
> mockups/
> ├── iphone.png
> ├── ipad.png
> └── macbook.png
> ```

El resultado se guarda en `mockups_output/`, organizado por dispositivo.

---

## Crawl

El crawler sigue todos los `<a href>` internos de forma recursiva. La profundidad es configurable e **independiente** para la URL base y para las URLs específicas.

> [!WARNING]
> Profundidades altas (4-5) en webs grandes pueden generar cientos de URLs y tardar mucho tiempo.

URLs excluidas automáticamente: archivos binarios (`.pdf`, `.zip`, imágenes…), `mailto:`, `tel:`, `#`, `/logout`, `/admin`.

---

## Generar .exe (desarrollo)

```bash
build.bat
```

El ejecutable queda en `dist/ScreenshotMultiShot.exe`.

---

## Requisitos (script)

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
