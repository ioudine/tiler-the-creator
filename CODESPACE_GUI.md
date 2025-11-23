# Running the GUI inside GitHub Codespaces

This project includes helper scripts to run the Tkinter GUI (`tiler_gui.py`) inside
a Codespace by creating a virtual X server and exposing it via noVNC.

Files
- `run_gui_codespace.sh` — starts Xvfb, a lightweight window manager, `x11vnc`, and
  `websockify`/noVNC then runs `tiler_gui.py`. The script records background PIDs to
  `/tmp/tiler_gui_pids.txt` and logs websockify output to `/tmp/websockify.log`.
- `stop_gui_codespace.sh` — stops the services started by `run_gui_codespace.sh` and
  cleans temporary files.

Quick start (Codespaces terminal)
1. Start the GUI stack (keeps `tiler_gui.py` in the foreground):
   ```bash
   bash run_gui_codespace.sh
   ```
   The script will install minimal system packages (best-effort), clone noVNC/websockify
   if missing, start services and then run the GUI.

2. Open the forwarded port in Codespaces UI (Ports panel):
   - Find the port (default `6080`) and click `Open in Browser`.
   - Keep the port private unless you intentionally want to share access.

3. When finished, stop services:
   ```bash
   bash stop_gui_codespace.sh
   ```

Security & configuration
- The script supports environment variables to control behavior:
  - `RFB_PORT` (default `5900`) — VNC TCP port.
  - `WEB_PORT` (default `6080`) — noVNC/websockify HTTP port.
  - `DISPLAY_NUM` (default `:99`) — X display.
  - `USE_VNC_PASS` (default `1`) — set to `0` to run x11vnc without password (not recommended).
  - `VNC_PASS_FILE` — path to the VNC passwd file; the script generates a random one if needed.
  - `USE_TLS` (default `0`) — set to `1` to enable TLS for websockify (self-signed cert is generated if none provided).
  - `CERT_FILE` / `KEY_FILE` — paths to TLS cert and key when using `USE_TLS=1`.

- Recommendations:
  - Keep the Codespaces port private. Use Codespaces `Open in Browser` or an SSH tunnel.
  - Use `USE_VNC_PASS=1` so a password is required to connect.
  - Enable TLS (`USE_TLS=1`) if you must make the port public; for production use valid certs.
  - Do not commit generated passwords or keys into the repository.

Troubleshooting
- If you see "Address already in use", another process is listening on `5900` or `6080`.
  Use:
  ```bash
  ss -ltnp | egrep ':5900|:6080' || true
  pkill -f websockify || true
  pkill -f x11vnc || true
  ```
- If noVNC page shows errors, check websockify log:
  ```bash
  tail -n 200 /tmp/websockify.log
  ```

Notes
- The provided setup is intended for short-term development/testing inside Codespaces.
  For long-term or shared deployments, consider converting the tool to a web application
  or placing the web-facing proxy behind a managed HTTPS endpoint with authentication.
