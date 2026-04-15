import os
import ssl
import sys
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'p2p_project.settings')

from django.core.wsgi import get_wsgi_application
from network.apps import start_node

def build_ssl_context(certfile: str, keyfile: str):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context

def main():
    host = '0.0.0.0'
    port = 8000
    certfile = 'cert.pem'
    keyfile = 'key.pem'


    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    if len(sys.argv) > 3:
        certfile = sys.argv[3]
    if len(sys.argv) > 4:
        keyfile = sys.argv[4]


    if not os.path.exists(certfile) or not os.path.exists(keyfile):
        raise SystemExit(
            f'Certificate files not found: {certfile}, {keyfile}\n'
            'Generate them with openssl or mkcert before running.'
        )


    application = get_wsgi_application()


    thread = threading.Thread(target=start_node, daemon=True)
    thread.start()


    httpd = make_server(host, port, application, handler_class=WSGIRequestHandler)
    httpd.socket = build_ssl_context(certfile, keyfile).wrap_socket(httpd.socket, server_side=True)


    print(f'Serving HTTPS on https://{host}:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    main()
