#!/usr/bin/env bash
# =============================================================================
#  Actualización de Rentabilidad Regenerativa desde git
#  Descarga los cambios nuevos y los aplica sin reinstalar el servidor.
#
#  Uso (en el servidor):
#     sudo bash /home/dvsystem/rentabilidad-regenerativa/deploy/actualizar.sh
#     sudo bash .../actualizar.sh --forzar     # reaplica aunque no haya commits nuevos
#
#  Requisito: haber ejecutado antes deploy/desplegar.sh (instalación inicial).
# =============================================================================
set -Eeuo pipefail

USUARIO="dvsystem"
PROYECTO="/home/${USUARIO}/rentabilidad-regenerativa"
VENV="${PROYECTO}/.venv"
ENV_FILE="${PROYECTO}/.env"
SERVICIO="rentabilidad"
DOMINIO="delphi.dvsystemecuador.com"
RAMA="main"
FORZAR="${1:-}"

verde() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
aviso() { printf '\033[1;33m[aviso] %s\033[0m\n' "$*"; }
falla() { printf '\033[1;31m[error] %s\033[0m\n' "$*" >&2; exit 1; }
trap 'falla "La actualización se detuvo en la línea ${LINENO}. El sitio sigue con la versión anterior en ejecución."' ERR

como_usuario() { sudo -H -u "$USUARIO" "$@"; }
git_p() { como_usuario git -C "$PROYECTO" "$@"; }
manage() { como_usuario bash -c "set -a; source '${ENV_FILE}'; set +a; cd '${PROYECTO}'; '${VENV}/bin/python' manage.py $*"; }

# --- Comprobaciones ------------------------------------------------------------
[[ $EUID -eq 0 ]] || falla "Ejecute con sudo."
[[ -d "${PROYECTO}/.git" ]] || falla "${PROYECTO} no es un clon de git."
[[ -x "${VENV}/bin/python" && -f "$ENV_FILE" ]] || falla "Falta la instalación inicial: ejecute primero deploy/desplegar.sh."
systemctl cat "$SERVICIO" &>/dev/null || falla "No existe el servicio ${SERVICIO}: ejecute primero deploy/desplegar.sh."

# Cambios hechos a mano en el servidor bloquearían el pull (o se perderían).
if [[ -n "$(git_p status --porcelain --untracked-files=no)" ]]; then
  git_p status --short --untracked-files=no
  falla "Hay archivos modificados en el servidor. Revise o descarte con: sudo -u ${USUARIO} git -C ${PROYECTO} checkout -- ."
fi

# --- 1. Descargar cambios --------------------------------------------------------
verde "Buscando cambios en git (rama ${RAMA})"
git_p fetch --quiet origin "$RAMA"
ANTES="$(git_p rev-parse HEAD)"
REMOTO="$(git_p rev-parse "origin/${RAMA}")"

if [[ "$ANTES" == "$REMOTO" && "$FORZAR" != "--forzar" ]]; then
  echo "El servidor ya está en la última versión ($(git_p log -1 --format='%h · %s'))."
  echo "Para reaplicar de todos modos: sudo bash $0 --forzar"
  exit 0
fi

echo "Cambios que se aplicarán:"
git_p log --oneline "${ANTES}..${REMOTO}" || true
git_p merge --ff-only --quiet "origin/${RAMA}"
CAMBIADOS="$(git_p diff --name-only "$ANTES" HEAD)"

# --- 2. Dependencias (solo si cambiaron) -----------------------------------------
if grep -qE '^requirements' <<<"$CAMBIADOS" || [[ "$FORZAR" == "--forzar" ]]; then
  verde "Actualizando dependencias"
  como_usuario "${VENV}/bin/pip" install --quiet -r "${PROYECTO}/requirements-produccion.txt"
else
  echo "Dependencias sin cambios."
fi

# --- 3. Base de datos -------------------------------------------------------------
verde "Respaldo y migraciones"
if [[ -f "${PROYECTO}/db.sqlite3" ]]; then
  RESPALDO="${PROYECTO}/db.sqlite3.respaldo-$(date +%Y%m%d-%H%M%S)"
  cp -p "${PROYECTO}/db.sqlite3" "$RESPALDO"
  echo "Respaldo: ${RESPALDO}"
  # Conserva solo los 10 respaldos más recientes.
  ls -1t "${PROYECTO}"/db.sqlite3.respaldo-* 2>/dev/null | tail -n +11 | xargs -r rm -f
fi
manage migrate --noinput
# Catálogo FRR: idempotente; conserva referencias, pesos y estados ajustados por la investigación.
manage cargar_framework

# Si cambió el dataset público, se reimporta (actualiza sin duplicar).
if grep -q '^emprendimientos/datos/emprendimientos_ecuador.csv' <<<"$CAMBIADOS"; then
  verde "El dataset de emprendimientos cambió: reimportando"
  manage importar_emprendimientos
  manage limpiar_datos --aplicar
  manage calcular_referencias --aplicar
fi

# --- 4. Archivos estáticos ---------------------------------------------------------
verde "Archivos estáticos"
manage collectstatic --noinput
find "${PROYECTO}/staticfiles" -type d -exec chmod 755 {} \;
find "${PROYECTO}/staticfiles" -type f -exec chmod 644 {} \;

# --- 5. Comprobación y reinicio ------------------------------------------------------
verde "Comprobando y reiniciando"
manage check
systemctl restart "$SERVICIO"
sleep 2
if ! systemctl is-active --quiet "$SERVICIO"; then
  journalctl -u "$SERVICIO" -n 40 --no-pager
  aviso "Gunicorn no arrancó. Para volver a la versión anterior:"
  echo "  sudo -u ${USUARIO} git -C ${PROYECTO} reset --hard ${ANTES} && sudo systemctl restart ${SERVICIO}"
  [[ -n "${RESPALDO:-}" ]] && echo "  (y si la migración dañó datos: cp ${RESPALDO} ${PROYECTO}/db.sqlite3)"
  exit 1
fi

CODIGO="$(curl -s -o /dev/null -w '%{http_code}' "https://${DOMINIO}/" || echo 000)"
echo "https://${DOMINIO}/ -> HTTP ${CODIGO}"
[[ "$CODIGO" == "200" ]] || aviso "La página no respondió 200. Revise: journalctl -u ${SERVICIO} -n 50"

verde "Actualizado a $(git_p log -1 --format='%h · %s')"
echo "Volver atrás si fuera necesario: sudo -u ${USUARIO} git -C ${PROYECTO} reset --hard ${ANTES:0:7} && sudo systemctl restart ${SERVICIO}"
