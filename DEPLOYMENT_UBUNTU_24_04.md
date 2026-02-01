## Deployment SONACIP — Ubuntu 24.04 (VPS)

Obiettivo: **clone/unzip → install → run** con deployment automatico (**systemd + nginx + HTTPS**) e senza interventi manuali post-installazione.

### Installazione automatica (consigliata)

Su Ubuntu 24.04, dall’interno della directory del repo:

```bash
sudo ./sonacip_install.sh
```

Opzioni (tutte automatiche):
- **HTTPS Let’s Encrypt** (consigliato):

```bash
export SONACIP_DOMAIN="tuodominio.it"
export SONACIP_LETSENCRYPT_EMAIL="tuamail@tuodominio.it"
sudo ./sonacip_install.sh
```

- **Redis opzionale** (cache + rate limit persistente):

```bash
export SONACIP_ENABLE_REDIS=true
sudo ./sonacip_install.sh
```

- **UFW opzionale**:

```bash
export SONACIP_ENABLE_UFW=true
sudo ./sonacip_install.sh
```

Note:
- Se non imposti `SONACIP_DOMAIN`+`SONACIP_LETSENCRYPT_EMAIL`, viene configurato HTTPS con certificato self‑signed.
- L’installer esegue automaticamente: venv, deps, migrazioni (`manage.py db upgrade`), seed (`manage.py seed`), systemd, nginx, healthcheck, backup timer, logrotate.

### Smoke test (manuale)

```bash
cd /opt/sonacip
sudo -u sonacip ./venv/bin/python -c "import wsgi; print('wsgi import ok')"
sudo -u sonacip ./venv/bin/gunicorn --version
```

