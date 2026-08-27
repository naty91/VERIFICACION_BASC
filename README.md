# CENASE BASC Proveedores – v2.0

Aplicación Streamlit para la gestión de asociados de negocio/proveedores de CENASE.

## Funciones principales
- Carga individual y masiva de proveedores desde Excel/CSV.
- Normalización y deduplicación por RUC.
- Expediente digital por proveedor.
- Matriz de criticidad BASC.
- Registro de verificaciones: SRI, Supercias, Función Judicial, Fiscalía, listas, adverse media, permisos, referencias y BASC.
- Croquis/fotografía de ubicación.
- Checklist BASC de 40 controles.
- Evaluación ponderada sobre 100 puntos.
- Decisión y responsables de verificación/aprobación.
- Estados: nuevo, en verificación, aprobado, condicionado, bloqueado e inactivo.
- Evidencias digitales con huella SHA-256.
- Planes de acción/no conformidades.
- Histórico de evaluaciones.
- Alertas por vencimiento/próxima reevaluación.
- PDFs individuales y expediente BASC completo.
- ZIP por proveedor y ZIP masivo.
- Reporte maestro Excel.
- Respaldo/restauración de la sesión en ZIP.
- Login opcional mediante Streamlit Secrets.

## Publicar en Streamlit Community Cloud
1. Cree un repositorio en GitHub.
2. Suba todos los archivos de esta carpeta (no suba un `secrets.toml` real).
3. En Streamlit Community Cloud cree una app apuntando a `app.py`.
4. Configure los Secrets de la app con:

```toml
[auth]
username = "cenase"
password = "SU_CLAVE_SEGURA"
```

5. Reinicie la app.

## Seguridad de información
Streamlit Community Cloud no debe considerarse el repositorio documental definitivo de CENASE. Use el botón **Respaldo completo** y conserve los expedientes/evidencias en el repositorio corporativo. Para persistencia multiusuario permanente, conecte posteriormente una base de datos y almacenamiento privado.

## Archivos de referencia incluidos
- Acuerdo_Proveedores_CENASE.xlsx
- REPORTE DE PROVEEDORES 2026.xlsx
- REGISTRO DE VERIFICACION DE ASOCIADOS DE NEGOCIO.xlsx
- REQUISISTOS.xlsx

La app no declara automáticamente que una fuente externa está conforme. El resultado debe registrarse con evidencia por el responsable que efectivamente realizó la consulta.
