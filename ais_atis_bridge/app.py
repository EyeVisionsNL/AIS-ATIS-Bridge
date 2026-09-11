from __future__ import annotations

from io import BytesIO
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from . import ais, config
from .channel_xlsx import export_channels, import_channels
from .receivers import inventory
from .runtime import runtime


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        settings = config.load(); state = runtime.status(); match = None; ais_error = None
        latest = state.get("latest") or {}
        if latest.get("atis_code"):
            try: match = ais.match_atis(latest["atis_code"], ais.read_ships(settings["ais_ships_url"]))
            except Exception as error: ais_error = str(error)
        return jsonify({"receiver":state,"ais_match":match,"ais_error":ais_error,"settings":settings})

    @app.get("/api/receivers")
    def receivers(): return jsonify(inventory())

    @app.post("/api/settings")
    def settings():
        saved = config.save(request.get_json(force=True) or {})
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
