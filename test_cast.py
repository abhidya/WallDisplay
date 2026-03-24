import asyncio
import base64
import subprocess
import threading
import socket
import html
import sys
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# --- CONFIG ---
MY_PORT_1 = 8081
MY_PORT_2 = 8082
PROJECTORS = [
    {
        "name": "SideProjector",
        "url": "http://localhost:3000/backend-static/overlay_window.html?config_id=4&controls=hidden",
        "port": MY_PORT_1,
        "control_url": "http://10.0.0.122:49595/upnp/control/rendertransport1"
    },
    {
        "name": "MainProjector",
        "url": "http://localhost:3000/backend-static/overlay_window.html?config_id=3&controls=hidden",
        "port": MY_PORT_2,
        "control_url": "http://10.0.0.154:49595/upnp/control/rendertransport1"
    }
]

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except: return '127.0.0.1'
    finally: s.close()

MY_IP = get_ip()

class ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True

class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_GET(self):
        if self.path == "/live.ts":
            print(f"[!] Projector requested stream: {self.path}")
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            proc = getattr(self.server, 'ffmpeg_proc', None)
            try:
                while True:
                    data = proc.stdout.read(32768)
                    if not data: break
                    self.wfile.write(data)
            except: pass

async def dlna_handshake(stream_url, control_url):
    # protocolInfo set to MPEG_TS which is the safest bet for these types of projectors
    meta = f'<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="0" parentID="-1" restricted="1"><dc:title>WallMapper</dc:title><upnp:class>object.item.videoItem</upnp:class><res protocolInfo="http-get:*:video/mpeg:DLNA.ORG_PN=MPEG_TS_SD_EU_ISO">{stream_url}</res></item></DIDL-Lite>'
    e_meta = html.escape(meta)
    
    set_uri = f'''<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><CurrentURI>{stream_url}</CurrentURI><CurrentURIMetaData>{e_meta}</CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>'''
    play = '<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>'
    
    subprocess.run(['curl', '-s', '-X', 'POST', '-H', 'SOAPACTION: "urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"', '-H', 'Content-Type: text/xml', '-d', set_uri, control_url])
    await asyncio.sleep(3) # Wait for buffer to fill
    subprocess.run(['curl', '-s', '-X', 'POST', '-H', 'SOAPACTION: "urn:schemas-upnp-org:service:AVTransport:1#Play"', '-H', 'Content-Type: text/xml', '-d', play, control_url])

async def run_cast(p, config):
    print(f"[*] Starting {config['name']}...")
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page(viewport={'width':1280,'height':720})
    await page.goto(config['url'])

    vcodec = "h264_videotoolbox" if config['port'] == 8081 else "libx264"
    preset = ["-preset", "ultrafast"] if vcodec == "libx264" else ["-realtime", "1"]

    ffmpeg_cmd = [
        "ffmpeg", "-y", "-f", "image2pipe", "-vcodec", "mjpeg", "-i", "-",
        "-c:v", vcodec] + preset + [
        "-b:v", "3500k", "-r", "20", "-pix_fmt", "yuv420p",
        "-f", "mpegts", "-muxrate", "4000k", "pipe:1"
    ]

    # Re-enabling stderr for the first 10 seconds to see stats
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
    
    server = ReusableServer(('0.0.0.0', config['port']), StreamHandler)
    server.ffmpeg_proc = proc
    threading.Thread(target=server.serve_forever, daemon=True).start()

    cdp = await page.context.new_cdp_session(page)
    frame_state = {"latest": None}
    
    def on_frame(e):
        frame_state["latest"] = base64.b64decode(e['data'])
        asyncio.get_event_loop().create_task(cdp.send('Page.screencastFrameAck', {'sessionId': e['sessionId']}))
    
    cdp.on('Page.screencastFrame', on_frame)
    await cdp.send('Page.startScreencast', {'format': 'jpeg', 'quality': 50, 'maxWidth': 1280, 'maxHeight': 720})

    def keep_pipe_alive():
        while proc.poll() is None:
            if frame_state["latest"]:
                try:
                    proc.stdin.write(frame_state["latest"])
                    proc.stdin.flush()
                except: break
            time.sleep(0.04) # 25fps feed
            
    threading.Thread(target=keep_pipe_alive, daemon=True).start()

    print(f"[!] Priming {config['name']}...")
    await asyncio.sleep(6) # Let FFmpeg generate some data first
    
    stream_url = f"http://{MY_IP}:{config['port']}/live.ts"
    await dlna_handshake(stream_url, config['control_url'])
    print(f"🚀 {config['name']} Cast Triggered.")
    
    return {"proc": proc, "browser": browser}

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        # Start Side Projector
        res1 = await run_cast(p, PROJECTORS[0])
        await asyncio.sleep(5)
        # Start Main Projector
        res2 = await run_cast(p, PROJECTORS[1])
        
        print("\n✨ WallMapper ACTIVE. Monitoring logs for speed...")
        while True: await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
