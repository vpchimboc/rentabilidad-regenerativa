#!/usr/bin/env bash
# =============================================================================
#  Despliegue de Rentabilidad Regenerativa (Django) en Ubuntu
#  Nginx + Gunicorn (entorno virtual) + HTTPS de Let's Encrypt con renovación automática
#
#  Uso (en el servidor, como root o con sudo):
#     sudo bash /home/dvsystem/rentabilidad-regenerativa/deploy/desplegar.sh correo@dominio.com
#
#  Se puede ejecutar de nuevo para actualizar: no borra la base de datos ni el .env.
# =============================================================================
set -Eeuo pipefail

DOMINIO="delphi.dvsystemecuador.com"
IP_SERVIDOR="137.184.25.239"
USUARIO="dvsystem"
PROYECTO="/home/${USUARIO}/rentabilidad-regenerativa"
VENV="${PROYECTO}/.venv"
SERVICIO="rentabilidad"
SOCKET="/run/${SERVICIO}/gunicorn.sock"
CORREO="${1:-}"

verde() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
aviso() { printf '\033[1;33m[aviso] %s\033[0m\n' "$*"; }
falla() { printf '\033[1;31m[error] %s\033[0m\n' "$*" >&2; exit 1; }
trap 'falla "El despliegue se detuvo en la línea ${LINENO}. Revise el mensaje anterior."' ERR

# --- 0. Comprobaciones previas ----------------------------------------------
[[ $EUID -eq 0 ]] || falla "Ejecute el script con sudo."
[[ -n "$CORREO" ]] || falla "Indique un correo para Let's Encrypt: sudo bash $0 correo@dominio.com"
id "$USUARIO" &>/dev/null || falla "No existe el usuario ${USUARIO}."
[[ -f "${PROYECTO}/manage.py" ]] || falla "No encuentro ${PROYECTO}/manage.py. Suba primero el proyecto."

verde "Comprobando que el dominio apunte a este servidor"
RESUELVE="$(getent ahostsv4 "$DOMINIO" | awk 'NR==1{print $1}' || true)"
if [[ "$RESUELVE" != "$IP_SERVIDOR" ]]; then
  falla "${DOMINIO} resuelve a '${RESUELVE:-nada}' y debería resolver a ${IP_SERVIDOR}.
         Cree en su DNS un registro A: delphi -> ${IP_SERVIDOR}, espere la propagación y repita."
fi
echo "OK: ${DOMINIO} -> ${RESUELVE}"

# --- 1. Paquetes del sistema --------------------------------------------------
verde "Instalando paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx certbot python3-certbot-nginx python3-venv python3-pip sqlite3 ufw

# Django 6.1 requiere Python 3.12 o superior.
PYTHON="$(command -v python3.13 || command -v python3.12 || true)"
if [[ -z "$PYTHON" ]]; then
  aviso "No hay Python 3.12+; se instala desde el repositorio deadsnakes."
  apt-get install -y software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -y
  apt-get install -y python3.12 python3.12-venv
  PYTHON="$(command -v python3.12)"
fi
echo "Python: $($PYTHON --version)"

# --- 2. Entorno virtual y dependencias ---------------------------------------
verde "Preparando el entorno virtual"
# Un .venv copiado desde Windows no sirve en Linux: se recrea.
if [[ -d "$VENV" && ! -x "${VENV}/bin/python" ]]; then
  aviso "El .venv existente es de Windows; se reemplaza."
  rm -rf "$VENV"
fi
[[ -d "$VENV" ]] || sudo -H -u "$USUARIO" "$PYTHON" -m venv "$VENV"
sudo -H -u "$USUARIO" "${VENV}/bin/pip" install --upgrade pip
sudo -H -u "$USUARIO" "${VENV}/bin/pip" install -r "${PROYECTO}/requirements-produccion.txt"

# --- 3. Variables de entorno (.env) ------------------------------------------
verde "Configurando variables de entorno"
ENV_FILE="${PROYECTO}/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  CLAVE="$("${VENV}/bin/python" -c 'import secrets; print(secrets.token_urlsafe(50))')"
  cat > "$ENV_FILE" <<EOF
DJANGO_SECRET_KEY=${CLAVE}
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=${DOMINIO},${IP_SERVIDOR},localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMINIO}
EOF
  echo "Creado ${ENV_FILE} con una clave secreta nueva."
else
  echo "Se conserva el ${ENV_FILE} existente."
fi
chown "$USUARIO:$USUARIO" "$ENV_FILE"
chmod 600 "$ENV_FILE"

# --- 4. Base de datos y archivos estáticos -----------------------------------
verde "Migraciones y archivos estáticos"
if [[ -f "${PROYECTO}/db.sqlite3" ]]; then
  RESPALDO="${PROYECTO}/db.sqlite3.respaldo-$(date +%Y%m%d-%H%M%S)"
  cp -p "${PROYECTO}/db.sqlite3" "$RESPALDO"
  echo "Respaldo de la base: ${RESPALDO}"
fi
manage() { sudo -H -u "$USUARIO" bash -c "set -a; source '${ENV_FILE}'; set +a; cd '${PROYECTO}'; '${VENV}/bin/python' manage.py $*"; }
manage migrate --noinput
manage collectstatic --noinput
contar() { manage shell -c "'$1'" 2>/dev/null | tail -1; }

# Primera instalación: todos los datos salen del repositorio (la base no se versiona).
if [[ "$(contar 'from framework.models import Dimension; print(Dimension.objects.count())')" == "0" ]]; then
  verde "Base vacía: cargando datos desde el repositorio"
  manage cargar_framework                 # dimensiones, variables, 17 indicadores, cuestionario Delphi
  manage cargar_demo                      # 3 casos ilustrativos, expertos, rondas Delphi, bibliometría, PRISMA
  manage importar_emprendimientos         # 120 emprendimientos de fuentes públicas (CSV del repositorio)
  manage entrenar_rna                     # red neuronal entrenada y activa
else
  echo "La base ya tiene datos: no se recargan."
fi

# Administrador inicial si todavía no existe ninguno.
CREDENCIAL="/root/rentabilidad-admin.txt"
if [[ "$(contar 'from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).count())')" == "0" ]]; then
  CLAVE_ADMIN="$("${VENV}/bin/python" -c 'import secrets; print(secrets.token_urlsafe(14))')"
  sudo -H -u "$USUARIO" bash -c "set -a; source '${ENV_FILE}'; set +a; cd '${PROYECTO}'; \
    DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL='${CORREO}' DJANGO_SUPERUSER_PASSWORD='${CLAVE_ADMIN}' \
    '${VENV}/bin/python' manage.py createsuperuser --noinput"
  ( umask 077; printf 'URL: https://%s/cuenta/ingresar/\nUsuario: admin\nContraseña: %s\n' "$DOMINIO" "$CLAVE_ADMIN" > "$CREDENCIAL" )
  echo "Administrador creado. Credenciales guardadas en ${CREDENCIAL} (solo root puede leerlo)."
fi
manage check --deploy || aviso "Revise las advertencias de 'check --deploy' indicadas arriba."

# Permisos: Nginx (www-data) solo necesita atravesar la carpeta y leer los estáticos.
chown -R "$USUARIO:$USUARIO" "$PROYECTO"
chmod 711 "/home/${USUARIO}"
chmod 755 "$PROYECTO"
find "${PROYECTO}/staticfiles" -type d -exec chmod 755 {} \;
find "${PROYECTO}/staticfiles" -type f -exec chmod 644 {} \;
chmod 660 "${PROYECTO}/db.sqlite3" 2>/dev/null || true

# --- 5. Servicio Gunicorn (systemd) ------------------------------------------
verde "Configurando Gunicorn como servicio"
cat > "/etc/systemd/system/${SERVICIO}.service" <<EOF
[Unit]
Description=Rentabilidad Regenerativa (Gunicorn)
After=network.target

[Service]
User=${USUARIO}
Group=www-data
WorkingDirectory=${PROYECTO}
EnvironmentFile=${ENV_FILE}
RuntimeDirectory=${SERVICIO}
RuntimeDirectoryMode=0750
ExecStart=${VENV}/bin/gunicorn config.wsgi:application \\
    --bind unix:${SOCKET} --umask 007 \\
    --workers 3 --timeout 120 \\
    --access-logfile - --error-logfile -
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICIO"
systemctl restart "$SERVICIO"
sleep 2
systemctl is-active --quiet "$SERVICIO" || { journalctl -u "$SERVICIO" -n 40 --no-pager; falla "Gunicorn no arrancó."; }

# --- 6. Nginx -----------------------------------------------------------------
verde "Configurando Nginx"
cat > "/etc/nginx/sites-available/${SERVICIO}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMINIO};

    client_max_body_size 20M;

    location /static/ {
        alias ${PROYECTO}/staticfiles/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_pass http://unix:${SOCKET};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF
ln -sf "/etc/nginx/sites-available/${SERVICIO}" "/etc/nginx/sites-enabled/${SERVICIO}"
nginx -t
systemctl reload nginx

# --- 7. Cortafuegos ------------------------------------------------------------
verde "Cortafuegos"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null
ufw status | sed -n '1,8p'

# --- 8. HTTPS con Let's Encrypt -----------------------------------------------
verde "Obteniendo el certificado HTTPS"
certbot --nginx -d "$DOMINIO" --non-interactive --agree-tos -m "$CORREO" --redirect --keep-until-expiring

# Recargar Nginx cada vez que se renueve el certificado.
install -d /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/recargar-nginx.sh <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/recargar-nginx.sh

verde "Comprobando la renovación automática"
systemctl enable --now certbot.timer
systemctl list-timers certbot.timer --no-pager | sed -n '1,3p'
certbot renew --dry-run

# --- 9. Verificación final -----------------------------------------------------
verde "Verificación"
CODIGO="$(curl -s -o /dev/null -w '%{http_code}' "https://${DOMINIO}/")"
echo "https://${DOMINIO}/ -> HTTP ${CODIGO}"
[[ "$CODIGO" == "200" ]] || aviso "La página no devolvió 200. Revise: journalctl -u ${SERVICIO} -n 50"

cat <<EOF

=====================================================================
 Listo: https://${DOMINIO}
 - Servicio:      systemctl status ${SERVICIO}
 - Registros:     journalctl -u ${SERVICIO} -f
 - Certificado:   se renueva solo (certbot.timer); prueba: certbot renew --dry-run
 - Acceso admin:  sudo cat ${CREDENCIAL}   (cambie la contraseña al ingresar)
 - Otro admin:    cd ${PROYECTO} && sudo -H -u ${USUARIO} bash -c 'set -a; . ./.env; set +a; .venv/bin/python manage.py createsuperuser'
=====================================================================
EOF
