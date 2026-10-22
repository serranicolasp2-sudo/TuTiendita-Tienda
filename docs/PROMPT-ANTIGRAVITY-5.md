# Tarea 5 para Antigravity: retención de datos (30 días)

Claude ya hizo y probó el cambio. **No modifiques el código.**

Qué cambia:
- Después del pago, el servidor borra su copia de las fotos apenas las sube a Drive.
- 30 días después de la entrega, la carpeta del pedido en Drive va a la papelera.
- El mail de entrega avisa que el link dura 30 días.

```bash
# 1. Copiá RegalosIA/tienda/app/ y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#    Resultado esperado mientras los precios de prueba estén en $500: "4 failed, 14 passed".
#    Las 4 que fallan son test_entrega, test_conciliacion_encuentra_pago_sin_webhook,
#    test_revision_foto_un_cambio_y_aprobacion y test_cancion_tiene_cinco_cambios: simulan pagos a precio real.
#    Cualquier otra falla: frená y anotala.

# 2. Reiniciar
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
```

Anotá al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 5 hecha", la salida de pytest y la de `is-active`. No toques el `.env`. No hagas pedidos de prueba.

**Recordatorio para el lanzamiento (D-20):** volver `rf-foto-1` a $5.000 y `tc-cancion` a $27.000 en `app/catalogo.py` y en las webs. Con eso pasan las 18 pruebas.
