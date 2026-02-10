## SONACIP Plugins

Questa cartella contiene **plugin esterni** caricati automaticamente da SONACIP.

### Struttura

Ogni plugin vive in una sottocartella:

```
plugins/<plugin_id>/
  plugin.py          # obbligatorio: deve esporre register(app)
  plugin.json        # opzionale: metadata
  templates/         # opzionale
  static/            # opzionale
```

`plugin_id` deve contenere solo lettere/numeri/`_`/`-` (es. `hello_world`).

### Esempio minimo

`plugins/hello_world/plugin.py`:

```python
from flask import jsonify

def register(app):
    @app.get("/plugins/hello_world/ping")
    def hello_world_ping():
        return jsonify({"ok": True})
```

### Enable/Disable

- **Allowlist**: `PLUGINS_ALLOWLIST="hello_world,altro_plugin"`
- **Blocklist**: `PLUGINS_BLOCKLIST="broken_plugin"`
- **Folder**: `PLUGINS_FOLDER="/opt/sonacip/plugins"`

Se `PLUGINS_ALLOWLIST` è valorizzata, verranno caricati **solo** i plugin presenti nella lista.
