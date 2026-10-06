from __future__ import annotations

from io import BytesIO
import json
import subprocess
from flask import Response, Flask, jsonify, redirect, render_template, request, send_file, url_for

from . import __version__, ais, config
from .channel_xlsx import export_channels, import_channels
from .receivers import inventory
from .runtime import runtime
from . import update_manager


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        settings = config.load(); state = runtime.status(); match = None; ais_error = None
        latest = state.get("latest") or {}
        if latest.get("atis_code") and latest.get("fresh"):
            try: match = ais.match_atis(latest["atis_code"], ais.read_ships(settings["ais_ships_url"]))
            except Exception as error: ais_error = str(error)
        return jsonify({"version":__version__,"receiver":state,"ais_match":match,"ais_error":ais_error,"settings":settings,"update":update_manager.get_status()})

    @app.get("/api/audio.pcm")
    def audio():
        try:
            value = request.args.get("after")
            after = int(value) if value is not None else None
            if after is not None and after < 0: raise ValueError()
        except ValueError:
            return jsonify({"error": "Invalid audio cursor"}), 400
        sequence, pcm = runtime.audio.read(after)
        return Response(pcm, mimetype="application/octet-stream", headers={
            "Cache-Control": "no-store", "X-Audio-Sequence": str(sequence),
            "X-Audio-Rate": "16000", "X-Receiver-Running": "1" if runtime.status()["running"] else "0",
        })

    @app.get("/api/receivers")
    def receivers(): return jsonify(inventory())

    @app.get("/api/recordings/<recording_id>.wav")
    def recording(recording_id: str):
        payload = runtime.recordings.get_wav(recording_id)
        if payload is None:
            return jsonify({"error": "Recording expired or is still in progress"}), 404
        return send_file(BytesIO(payload), mimetype="audio/wav", as_attachment=True,
                         download_name=f"marine-{recording_id[:8]}.wav", max_age=0)

    @app.get("/api/update/status")
    def update_status():
        refresh = str(request.args.get("refresh") or "").strip().lower() in {"1", "true", "yes"}
        return jsonify(update_manager.check_remote_version() if refresh else update_manager.get_status())

    @app.post("/api/update/channel")
    def update_channel():
        payload = request.get_json(silent=True) or {}
        channel = payload.get("channel")
        if channel not in ("main", "develop"):
            return jsonify({"ok": False, "error": "Choose stable (main) or beta (develop)."}), 400
        try:
            return jsonify(update_manager.set_channel(channel))
        except (RuntimeError, ValueError) as error:
            return jsonify({"ok": False, "error": str(error)}), 409

    @app.post("/api/update/install")
    def install_update():
        status = update_manager.check_remote_version()
        if status.get("check_error"):
            return jsonify({"ok": False, "error": "Update check failed: " + str(status["check_error"])}), 503
        if not status.get("update_available"):
            return jsonify({"ok": False, "error": "No update is available for the selected channel."}), 409
        if any(not item.get("complete") for item in runtime.recordings.list()):
            return jsonify({"ok": False, "error": "Wait for the current Marine recording to finish before updating."}), 409
        try:
            result = subprocess.run(["sudo", "-n", "/usr/local/sbin/ais-atis-update"],
                                    capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError) as error:
            return jsonify({"ok": False, "error": f"Could not start updater: {error}"}), 503
        try:
            payload = json.loads((result.stdout or "").strip() or "{}")
        except ValueError:
            payload = {}
        if result.returncode != 0 or not payload.get("ok"):
            message = payload.get("error") or (result.stderr or result.stdout or "Updater did not start").strip()
            return jsonify({"ok": False, "error": message}), 503
        return jsonify(payload), 202

    @app.post("/api/settings")
    def settings():
        try: saved = config.save({**config.load(), **(request.get_json(force=True) or {})})
        except ValueError as error: return jsonify({"ok":False,"error":str(error)}),400
        runtime.start(saved)
        return jsonify({"ok":True,"settings":saved})

    @app.get("/api/channels/export.xlsx")
    def export_xlsx():
        return send_file(BytesIO(export_channels(config.load())),as_attachment=True,download_name="ais-atis-channels.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.post("/api/channels/import.xlsx")
    def import_xlsx():
        upload=request.files.get("file")
        if upload is None: return jsonify({"ok":False,"error":"Select an .xlsx file"}),400
        try:
            imported=import_channels(upload.read()); current=config.load(); current.update(imported); saved=config.save(current)
            runtime.start(saved) if saved.get("receiver") else runtime.stop()
            return jsonify({"ok":True,"settings":saved})
        except ValueError as error: return jsonify({"ok":False,"error":str(error)}),400

    @app.post("/api/receiver/stop")
    def stop(): runtime.stop(); return jsonify({"ok":True})

    @app.get("/vessel/<mmsi>")
    def vessel(mmsi: str): return redirect(url_for("index", mmsi=mmsi))

    return app


def main() -> None:
    settings = config.load()
    if settings.get("receiver"):
        runtime.start(settings)
    create_app().run(host=settings["web_host"], port=settings["web_port"], threaded=True)


if __name__ == "__main__": main()
