# Manual de Programador

Este documento explica la base técnica del proyecto y está orientado a quien necesite mantenerlo, extenderlo o depurarlo.

## 1. Objetivo del proyecto

El repositorio contiene dos implementaciones de mensajería en tiempo real:

- Una versión P2P, donde los nodos se descubren, se conectan y se envían mensajes directamente.
- Una versión centralizada, donde Django Channels actúa como servidor de coordinación por WebSocket.

El núcleo más interesante del proyecto está en la versión P2P, porque combina descubrimiento de nodos, cifrado híbrido, WebSockets y HTTPS local.

## 2. Arquitectura general

En la versión P2P, el flujo principal es este:

1. Django levanta la interfaz web y expone los endpoints HTTP de la app `network`.
2. En segundo plano, `network.apps.start_node()` crea un `P2PNode` en un hilo propio con su propio `asyncio` loop.
3. El nodo anuncia su presencia por multicast UDP y también comparte su clave pública en los mensajes de estado y saludo inicial.
4. Cuando un nodo conoce a otro, guarda el `ws_url`, la `node_id` y la clave pública del peer.
5. Los mensajes se envían por WebSocket, pero el contenido viaja cifrado con RSA + AES-GCM.
6. La interfaz consulta el estado de nodos, mensajes y señales WebRTC mediante vistas HTTP.

Los archivos más relevantes para entender esta parte son [network/p2p_node.py](network/p2p_node.py), [network/crypto.py](network/crypto.py), [network/views.py](network/views.py) y [network/apps.py](network/apps.py).

## 3. Implementación de RSA y AES

La criptografía está encapsulada en `HybridCryptoBox`, en [network/crypto.py](network/crypto.py).

### 3.1 Generación y persistencia de claves

Cada nodo genera un par RSA de 2048 bits si todavía no existe uno almacenado. Las claves se guardan en disco dentro de `network/keys/` usando un nombre derivado del `node_id`.

- La clave privada se escribe en formato PEM.
- La clave pública se guarda como texto PEM para poder distribuirla fácilmente.
- Si existe la variable de entorno `P2P_RSA_PRIVATE_KEY_PASSWORD`, la clave privada queda protegida con contraseña.

Esto permite que cada nodo conserve su identidad entre ejecuciones.

### 3.2 Cifrado de un mensaje

La función `encrypt_for_peer()` aplica un esquema híbrido:

1. Se genera una clave AES aleatoria de 32 bytes.
2. Se genera un nonce de 12 bytes.
3. El texto plano se cifra con `AESGCM(aes_key)`.
4. La clave AES se cifra con la clave pública RSA del receptor usando OAEP con SHA-256.
5. El resultado se codifica en Base64 para transportarlo en JSON.

El payload final incluye:

- `algorithm`: indica que se usa `rsa-oaep+aes-gcm`.
- `encrypted_key`: la clave AES cifrada con RSA.
- `nonce`: el nonce de AES-GCM.
- `ciphertext`: el mensaje cifrado.

### 3.3 Descifrado

La función `decrypt_payload()` invierte el proceso:

1. Decodifica Base64.
2. Recupera la clave AES con la clave privada RSA.
3. Descifra el contenido con AES-GCM.

### 3.4 Por qué se usa un esquema híbrido

RSA no es eficiente para cifrar mensajes largos; por eso aquí solo cifra la clave simétrica. AES-GCM sí es rápido para el cuerpo del mensaje y además aporta autenticidad e integridad del ciphertext. En la práctica, este diseño combina la ventaja de ambos algoritmos.

## 4. Flujo extremo a extremo de un mensaje

Este es el recorrido real de un envío en la versión P2P:

1. La UI llama al endpoint `/send/` definido en [network/urls.py](network/urls.py) y atendido por `send_to()` en [network/views.py](network/views.py).
2. `send_to()` usa `asyncio.run_coroutine_threadsafe()` para ejecutar la coroutine en el loop del nodo que vive en segundo plano.
3. `P2PNode.send_to()` busca la conexión WebSocket del nodo destino.
4. Si no hay conexión, intenta abrir una nueva con `connect_to_new_peer()`.
5. Antes de enviar, recupera la clave pública del peer desde `peer_public_keys`.
6. El texto se cifra con `HybridCryptoBox.encrypt_for_peer()`.
7. Se envía un JSON con `type: secure_chat`, `from`, `to` y el payload cifrado.
8. El nodo receptor entra por `handler()` y `process_message()` en [network/p2p_node.py](network/p2p_node.py).
9. El receptor llama a `decrypt_payload()` y guarda el mensaje en memoria para la UI.

En resumen, el camino de extremo a extremo es: interfaz web -> vista Django -> loop asíncrono del nodo -> WebSocket -> descifrado en el peer -> almacenamiento local del mensaje.

## 5. Descubrimiento y conexión entre nodos

La conexión P2P no depende de un servidor central para el intercambio de mensajes. El descubrimiento se hace de dos formas:

- Multicast UDP: `udp_broadcast()` anuncia el nodo cada pocos segundos.
- WebSocket: `connect_to_new_peer()` abre la conexión directa y `_send_hello()` intercambia `node_id`, `hostname` y clave pública.

Además, `send_status()` mantiene un pulso periódico con información del nodo, y `known_nodes` concentra los peers detectados por la red o por WebSocket.

## 6. HTTPS local con Mkcert

El script [run_https.py](run_https.py) monta la aplicación Django dentro de un servidor WSGI simple y después envuelve el socket con TLS usando `ssl.SSLContext`.

### 6.1 Qué hace el script

- Carga la aplicación Django con `get_wsgi_application()`.
- Crea el servidor HTTP con `wsgiref.simple_server.make_server()`.
- Convierte ese servidor en HTTPS cargando `cert.pem` y `key.pem`.
- Arranca el nodo P2P en un hilo daemon para que quede activo junto con la web.

### 6.2 Cómo se usa Mkcert

Mkcert se usa para generar un certificado local confiable por el navegador durante desarrollo. La idea es crear un certificado para `localhost` o para la IP/host que estés usando y pasar esos archivos al script.

Flujo recomendado:

1. Instalar y confiar en la CA local de Mkcert.
2. Generar el certificado para el host que vas a abrir en el navegador.
3. Ejecutar `run_https.py` indicando el host, el puerto, el archivo del certificado y la clave privada.

Ejemplo conceptual:

```bash
python run_https.py 0.0.0.0 8000 cert.pem key.pem
```

Si el certificado no existe, el script aborta con un error explícito y sugiere usar `openssl` o `mkcert` antes de arrancar.

### 6.3 Por qué es importante

HTTPS evita problemas del navegador con contexto inseguro y permite probar el proyecto en condiciones más cercanas a despliegue real, especialmente si luego se integra WebRTC o APIs que exigen origen seguro.

## 7. Librerías usadas

### Dependencias externas

- Django: framework principal para vistas, URLs, plantillas y arranque de la aplicación.
- websockets: cliente/servidor WebSocket usado por la capa P2P y por el cliente centralizado.
- cryptography: implementa RSA, OAEP, SHA-256 y AES-GCM.
- channels: habilita consumidores WebSocket en la versión centralizada.
- daphne: servidor ASGI usado por Django Channels.

### Módulos estándar de Python

- asyncio: coordinación de corutinas y comunicación con el loop del nodo.
- json: serialización de los mensajes que viajan por red.
- socket: multicast UDP, hostname e IP local.
- ssl: capa HTTPS de desarrollo.
- threading: ejecución del nodo en segundo plano.
- base64: transporte textual de bytes cifrados dentro de JSON.
- pathlib: rutas de archivos de claves y base de datos.
- dataclasses: estructura simple para las rutas de claves.
- random: simulación de carga del nodo.
- struct: armado del membership para multicast.
- os y re: variables de entorno y sanitización del `node_id`.

## 8. Versión centralizada

El directorio [centralizado/](centralizado/) contiene una implementación distinta basada en Django Channels:

- `centralizado/websocket_chat/asgi.py` configura el router ASGI.
- `centralizado/chat/consumers.py` maneja chat general, privado y por grupos.
- `centralizado/client.py` es un cliente WebSocket de ejemplo para probar el servidor.

Esta rama no usa el esquema híbrido RSA + AES del P2P; su interés está en la coordinación central con WebSockets.

## 9. Puntos a tener en cuenta al modificar el proyecto

- Si cambias el formato de los mensajes, debes actualizar tanto `process_message()` como la vista que los dispara.
- Si cambias la forma de guardar claves, revisa también la ruta de `network/keys/` y los tests de [network/tests.py](network/tests.py).
- Si quieres endurecer seguridad, el siguiente paso lógico es autenticar nodos y firmar o validar mejor el intercambio inicial de claves.

## 10. Resumen corto

El proyecto combina Django como capa web, WebSockets como transporte en tiempo real y criptografía híbrida para proteger el contenido de los mensajes. La conexión extremo a extremo se consigue con descubrimiento de peers, enlace directo por WebSocket y cifrado RSA + AES-GCM antes del envío.