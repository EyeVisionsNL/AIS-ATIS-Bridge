from __future__ import annotations
import socket, subprocess, tempfile, threading, time
from typing import Any
import numpy as np
from .atis import SAMPLE_RATE_HZ, decode_samples
from .audio import LiveAudio

class ReceiverRuntime:
    def __init__(self)->None:
        self.audio=LiveAudio()
        self._lock=threading.RLock(); self._thread=None; self._process=None; self._stop=threading.Event()
        self._latest=None; self._error=None; self._started=None; self._packets=0
    def start(self,settings:dict[str,Any])->None:
        self.stop()
        if not settings.get("receiver"): raise ValueError("Select a second RTL-SDR first")
        self._stop.clear(); self._error=None; self._started=time.time(); self._packets=0
        self._thread=threading.Thread(target=self._run,args=(dict(settings),),daemon=True,name="atis-receiver"); self._thread.start()
    def stop(self)->None:
        self._stop.set()
        with self._lock: process=self._process
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: process.kill()
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=3)
        with self._lock: self._process=None
        self.audio.clear()
    @staticmethod
    def render_airband_config(settings:dict[str,Any])->str:
        channels=settings["channels"]
        if settings["tuning_mode"]=="fixed": channels=[next(x for x in channels if x["id"]==settings["selected_channel_id"])]
        else: channels=[x for x in channels if x["scan_enabled"]]
        gain=-1.0 if settings["gain_mode"]=="auto" else float(settings["gain_db"])
        squelch = f"squelch_threshold = {int(settings.get('squelch_threshold_dbfs', -47))};" if settings.get("squelch_mode", "auto")=="manual" else "squelch_snr_threshold = 4.0;"
        frequencies=", ".join(f"{x['frequency_mhz']:.6f}" for x in channels); labels=", ".join('"'+x["label"].replace('"',"")+'"' for x in channels)
        return f'''log_scan_activity = true;
devices:
({{
  type = "rtlsdr";
  serial = "{settings['receiver']}";
  gain = {gain:.1f};
  correction = {settings['ppm']};
  mode = "scan";
  channels:
  ({{
    modulation = "nfm";
    freqs = ( {frequencies} );
    labels = ( {labels} );
    {squelch}
    outputs: ({{ type = "udp_stream"; dest_address = "127.0.0.1"; dest_port = 49555; continuous = true; }});
  }});
}});
'''
    def _run(self,settings:dict[str,Any])->None:
        try:
            with tempfile.NamedTemporaryFile("w",suffix=".conf") as cfg, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server:
                cfg.write(self.render_airband_config(settings)); cfg.flush(); server.bind(("127.0.0.1",49555)); server.settimeout(1)
                # -F keeps rtl_airband in the foreground without the textual
                # waterfall.  -e only disables syslog and still daemonizes,
                # which makes the parent look stopped and escapes our control.
                process=subprocess.Popen(["rtl_airband","-F","-c",cfg.name],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                with self._lock: self._process=process
                buffer=np.empty(0,dtype=np.float32); last_scan=0.0
                while not self._stop.is_set() and process.poll() is None:
                    try: raw=server.recv(65536)
                    except socket.timeout: continue
                    usable=len(raw)-(len(raw)%4)
                    if not usable: continue
                    samples=np.frombuffer(raw[:usable],dtype="<f4"); self.audio.publish(samples); buffer=np.concatenate((buffer,samples))[-SAMPLE_RATE_HZ:]
                    with self._lock: self._packets+=1
                    if len(buffer)>=SAMPLE_RATE_HZ and time.monotonic()-last_scan>=.25:
                        last_scan=time.monotonic(); decoded=decode_samples(buffer)
                        if decoded:
                            with self._lock: self._latest={**decoded[-1],"received_epoch":time.time()}
                if process.poll() not in (None,0) and not self._stop.is_set():
                    message=process.stderr.read().decode("utf-8","replace")[-500:] if process.stderr else "rtl_airband stopped"; raise RuntimeError(message.strip())
        except Exception as error:
            with self._lock: self._error=str(error)
    def status(self)->dict[str,Any]:
        with self._lock:
            latest=dict(self._latest) if self._latest else None; running=bool(self._process and self._process.poll() is None); error=self._error; packets=self._packets
        if latest:
            age=max(0.0,time.time()-latest.pop("received_epoch")); latest.update(age_seconds=round(age,1),fresh=age<=120)
        return {"running":running,"state":"DECODED" if latest and latest["fresh"] else ("SCANNING" if running else "STOPPED"),"latest":latest,"error":error,"started_epoch":self._started,"packets_received":packets}
runtime=ReceiverRuntime()
