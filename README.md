# Mensajer-a-Web

Este proyecto, desarrollado en el marco de la asignatura Sistemas Distribuidos, consiste en la implementación de dos aplicaciones web de mensajería en tiempo real, cada una basada en un modelo de comunicación distinto.

La primera aplicación sigue un enfoque peer-to-peer (P2P), en el cual los clientes se comunican directamente entre sí sin la intermediación de un servidor central para el intercambio de mensajes. Este modelo permite explorar conceptos como descentralización, gestión de conexiones directas y sincronización entre nodos.

La segunda aplicación implementa un modelo cliente-servidor centralizado, donde todas las comunicaciones se gestionan a través de un servidor que actúa como intermediario entre los clientes. Este enfoque facilita el control, la escalabilidad y la administración de las conexiones.

Ambas soluciones han sido desarrolladas utilizando el lenguaje de programación Python y el framework web Django, incorporando tecnologías de comunicación en tiempo real mediante WebSockets, lo que permite una interacción eficiente y bidireccional entre los usuarios.

El objetivo principal del proyecto es analizar, comparar y comprender las ventajas, limitaciones y casos de uso de cada arquitectura dentro del contexto de sistemas distribuidos.

Para una explicación técnica más detallada del proyecto, revisa el manual de programador en [MANUAL_DESARROLLADOR.md](MANUAL_DESARROLLADOR.md).
