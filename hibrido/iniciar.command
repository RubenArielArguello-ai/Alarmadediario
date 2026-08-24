#!/bin/bash
# Lanzador de la Alarma de Diario híbrida.
# Se puede ejecutar con doble clic desde el Finder.

cd "$(dirname "$0")/.." || exit 1     # raíz del repo

if [ ! -d ".venv" ]; then
  echo "ERROR: no encuentro .venv en la raíz del repo."
  echo "Creá el entorno con:"
  echo "    python3 -m venv .venv"
  echo "    source .venv/bin/activate"
  echo "    pip install -r hibrido/requirements.txt"
  read -r -p "Enter para cerrar…"
  exit 1
fi

source .venv/bin/activate

if [ ! -f "hibrido/modelos/config.json" ]; then
  echo "AVISO: no encuentro los pesos de OWLv2 en hibrido/modelos/."
  echo "Bajalos con:  python hibrido/descargar_modelo.py"
  echo "Mientras tanto puedo arrancar en modo solo_color (sin modelo)."
  read -r -p "¿Arranco en solo_color? [s/N] " resp
  if [ "$resp" != "s" ] && [ "$resp" != "S" ]; then
    exit 1
  fi
  MODO="--modo solo_color"
fi

# Si quedó un server viejo colgado, lo bajamos antes de arrancar.
VIEJO=$(lsof -ti:8000 2>/dev/null)
if [ -n "$VIEJO" ]; then
  echo "Cerrando un servidor anterior (PID $VIEJO)…"
  kill -9 "$VIEJO" 2>/dev/null
  sleep 1
fi

echo "Arrancando… abrí http://localhost:8000"
echo "Para detenerlo: Ctrl+C"
echo

python hibrido/server.py $MODO

echo
read -r -p "El servidor se detuvo. Enter para cerrar…"
