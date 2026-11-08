"""Local CPU embedding endpoint; differs from the authors' OpenAI embedding backend."""
import json, os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
ONNXMiniLM_L6_V2.DOWNLOAD_PATH = Path(__file__).resolve().parents[1] / "models" / "all-MiniLM-L6-v2"
lock=Lock()
model=ONNXMiniLM_L6_V2(preferred_providers=['CPUExecutionProvider'])
model(['warmup'])
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok","model":"all-MiniLM-L6-v2","dimension":384}')
    def do_POST(self):
        try:
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            inputs=payload['input']; inputs=[inputs] if isinstance(inputs,str) else inputs
            if not all(isinstance(t,str) for t in inputs): raise ValueError('Text inputs required; set check_embedding_ctx_length=False')
            with lock: vectors=model(inputs)
            result={'object':'list','model':'all-MiniLM-L6-v2','data':[{'object':'embedding','index':i,'embedding':v.tolist()} for i,v in enumerate(vectors)],'usage':{'prompt_tokens':0,'total_tokens':0}}
            body=json.dumps(result).encode(); self.send_response(200)
        except Exception as e:
            body=json.dumps({'error':str(e)}).encode(); self.send_response(400)
        self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
ThreadingHTTPServer(('127.0.0.1',8001),Handler).serve_forever()
