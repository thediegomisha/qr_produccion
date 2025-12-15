# 📦 Sistema de Generación y Gestión de Códigos QR

Producto orientado a la **generación, administración y validación de códigos QR**, desarrollado como una **aplicación web en Python + Streamlit**, con persistencia en **PostgreSQL** y soporte para **lectura desde dispositivos móviles**.

El sistema permite asociar información estructurada a cada QR (por ejemplo: DNI, UID, fecha de proceso), facilitando su uso en escenarios de control, registro e impresión.

---

## 🚀 Características principales

- Generación de **códigos QR únicos**
- Asociación de información estructurada a cada QR
- Visualización y administración desde interfaz web
- Preparado para **lectura desde dispositivos móviles**
- Persistencia de datos en **PostgreSQL**
- Arquitectura escalable para nuevas reglas de validación

---

## 🧱 Arquitectura general

El producto se compone de los siguientes elementos:

- **Interfaz Web (Streamlit)**  
  Panel para creación, visualización y gestión de códigos QR.

- **Backend lógico (Python)**  
  Encargado de la generación, validación y reglas de negocio del QR.

- **Base de datos (PostgreSQL)**  
  Almacenamiento de la información asociada a cada QR y su estado.

- **Dispositivo móvil / lector QR**  
  Lectura y envío del contenido QR para validación.


## 🛠️ Tecnologías utilizadas

- **Python 3.10+**
- **Streamlit** (Interfaz web)
- **PostgreSQL** (Base de datos)
- **Librerías de generación QR**
- **Git & GitHub**

---

👤 Autor

Juan Luis Diaz Aylas
Ingeniero de Sistemas Computacionales
GitHub: https://github.com/thediegomisha
