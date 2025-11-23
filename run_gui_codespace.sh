#!/usr/bin/env bash
set -euo pipefail

# run_gui_codespace.sh
# Starts a headless X server, minimal window manager, x11vnc and websockify/noVNC
# Optional environment variables:
#  RFB_PORT (default 5900), WEB_PORT (default 6080)
#  DISPLAY_NUM (default :99), SCREEN_RES (default 1280x800x24)
#  USE_VNC_PASS (1 to enable password generation/use, 0 to allow -nopw)
#  VNC_PASS_FILE (path to an existing passwd file)
#  USE_TLS (1 to generate/use TLS certs for websockify, 0 to disable)
#  CERT_FILE / KEY_FILE (paths to TLS cert/key if USE_TLS=1)
# PIDs are recorded to /tmp/tiler_gui_pids.txt by default.

RFB_PORT="${RFB_PORT:-5900}"
WEB_PORT="${WEB_PORT:-6080}"
DISPLAY_NUM="${DISPLAY_NUM:-:99}"
SCREEN_RES="${SCREEN_RES:-1280x800x24}"
TMPDIR="${TMPDIR:-/tmp/tiler-vnc}"
PIDS_FILE="${PIDS_FILE:-/tmp/tiler_gui_pids.txt}"
USE_VNC_PASS="${USE_VNC_PASS:-1}"
VNC_PASS_FILE="${VNC_PASS_FILE:-$TMPDIR/passwd}"
VNC_PASS_PLAINTEXT="${VNC_PASS_PLAINTEXT:-$TMPDIR/vnc_pass.txt}"
USE_TLS="${USE_TLS:-0}"
CERT_FILE="${CERT_FILE:-$TMPDIR/cert.pem}"
KEY_FILE="${KEY_FILE:-$TMPDIR/key.pem}"

mkdir -p "$TMPDIR"
cd "$(dirname "$0")"

# install minimal packages if missing (best-effort)
sudo apt update || true
sudo apt install -y xvfb x11vnc fluxbox wget git python3-tk openssl || true
python3 -m pip install --user pillow || true

# prepare noVNC/websockify in temporary directory (do not leave copies in the repo)
NOVNC_DIR="$TMPDIR/noVNC"
WEBSOCKIFY_DIR="$NOVNC_DIR/utils/websockify"
if [ ! -d "$NOVNC_DIR" ]; then
	echo "Cloning noVNC into $NOVNC_DIR"
	git clone --depth 1 https://github.com/novnc/noVNC.git "$NOVNC_DIR"
fi
if [ ! -d "$WEBSOCKIFY_DIR" ]; then
	echo "Cloning websockify into $WEBSOCKIFY_DIR"
	git clone --depth 1 https://github.com/novnc/websockify.git "$WEBSOCKIFY_DIR"
fi

# clear old PID file and start fresh
rm -f "$PIDS_FILE"
touch "$PIDS_FILE"

echo "Starting Xvfb on $DISPLAY_NUM"
Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN_RES" &
echo $! >> "$PIDS_FILE"

export DISPLAY="$DISPLAY_NUM"

echo "Starting fluxbox"
fluxbox &
echo $! >> "$PIDS_FILE"

# prepare x11vnc command (with password if requested)
if [ "${USE_VNC_PASS}" -ne 0 ]; then
	# Always generate a fresh random password for the session and store both
	# the x11vnc hashed passwd and a plain-text helper file for convenience.
	echo "Generating VNC password (hashed + plain) in $TMPDIR"
	PW=$(openssl rand -base64 12)
	x11vnc -storepasswd "$PW" "$VNC_PASS_FILE"
	# write plain text password for convenience (restricted permissions)
	printf '%s' "$PW" > "$VNC_PASS_PLAINTEXT"
	chmod 600 "$VNC_PASS_PLAINTEXT"
	echo "Wrote hashed password to $VNC_PASS_FILE and plain text helper to $VNC_PASS_PLAINTEXT"
	X11VNC_CMD=(x11vnc -display "$DISPLAY_NUM" -rfbauth "$VNC_PASS_FILE" -forever -shared -rfbport "$RFB_PORT")
else
	X11VNC_CMD=(x11vnc -display "$DISPLAY_NUM" -nopw -forever -shared -rfbport "$RFB_PORT")
fi

echo "Starting x11vnc"
"${X11VNC_CMD[@]}" &
echo $! >> "$PIDS_FILE"

# prepare websockify args (serve bundled noVNC files)
WEBSOCK_ARGS=(--web "$NOVNC_DIR")
if [ "${USE_TLS}" -ne 0 ]; then
	if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
		echo "Generating self-signed cert/key at $CERT_FILE and $KEY_FILE"
		openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
			-keyout "$KEY_FILE" -out "$CERT_FILE" -subj "/CN=localhost"
	fi
	WEBSOCK_ARGS+=(--cert "$CERT_FILE" --key "$KEY_FILE" --ssl-only)
fi

echo "Starting websockify (noVNC) on port $WEB_PORT -> localhost:$RFB_PORT"
nohup env PYTHONPATH="$WEBSOCKIFY_DIR" \
	python3 -m websockify "$WEB_PORT" "localhost:$RFB_PORT" "${WEBSOCK_ARGS[@]}" \
	> /tmp/websockify.log 2>&1 &
echo $! >> "$PIDS_FILE"

echo "Services started. PIDs saved to $PIDS_FILE"
echo "Open Codespaces port $WEB_PORT (prefer keeping it private) and visit the noVNC page."

# finally run the GUI in the foreground so the script stays attached
export DISPLAY="$DISPLAY_NUM"
python3 tiler_gui.py

echo "tiler_gui.py exited. (GUI session ended)"
#!/usr/bin/env bash
set -e
# install minimal packages (run once)
sudo apt update
sudo apt install -y xvfb x11vnc fluxbox wget git python3-tk
python3 -m pip install --user pillow

# prepare noVNC if not present
cd "$(dirname "$0")"
[ -d noVNC ] || git clone https://github.com/novnc/noVNC.git --depth 1
[ -d noVNC/utils/websockify ] || git clone https://github.com/novnc/websockify.git --depth 1 noVNC/utils/websockify

# start services
Xvfb :99 -screen 0 1280x800x24 &
export DISPLAY=:99
fluxbox &
x11vnc -display :99 -nopw -forever -shared -listen 0.0.0.0 -rfbport 5900 &
# Start websockify and serve the noVNC static files. Use the local websockify package
# by setting PYTHONPATH so the module does not need to be installed system-wide.
nohup env PYTHONPATH="$(pwd)/noVNC/utils/websockify" \
	python3 -m websockify 6080 localhost:5900 --web "$(pwd)/noVNC" \
	> /tmp/websockify.log 2>&1 &

# run the GUI
export DISPLAY=:99
python3 tiler_gui.py