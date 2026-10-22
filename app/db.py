"""Pedidos en SQLite (un solo archivo en DATOS_DIR)."""
import json
import sqlite3
import threading
from datetime import datetime, timezone

ESTADOS = ("pendiente_pago", "pagado", "vista_previa", "cambio", "aprobado", "entregado", "cancelado")
MIGRACIONES = ["ALTER TABLE pedidos ADD COLUMN cliente_token TEXT",
               "ALTER TABLE pedidos ADD COLUMN cambios INTEGER NOT NULL DEFAULT 0",
               "ALTER TABLE pedidos ADD COLUMN nota_cambio TEXT",
               "ALTER TABLE pedidos ADD COLUMN vista_url TEXT",
               "ALTER TABLE pedidos ADD COLUMN vista_n INTEGER NOT NULL DEFAULT 0",
               "ALTER TABLE pedidos ADD COLUMN aprobado TEXT",
               "ALTER TABLE pedidos ADD COLUMN purgado TEXT",
               "ALTER TABLE pedidos ADD COLUMN cambios_extra INTEGER NOT NULL DEFAULT 0",
               "ALTER TABLE pedidos ADD COLUMN seguimiento TEXT",
               "ALTER TABLE pedidos ADD COLUMN seguimiento_url TEXT",
               "ALTER TABLE pedidos ADD COLUMN cuadro_comprado TEXT",
               "ALTER TABLE pedidos ADD COLUMN mp_init_point TEXT",
               "ALTER TABLE pedidos ADD COLUMN pago_medio TEXT",              # mercadopago | transferencia
               "ALTER TABLE pedidos ADD COLUMN aviso_sin_pago TEXT",          # cuándo se avisó al dueño que no se pagó
               "ALTER TABLE pedidos ADD COLUMN transferencia_avisada TEXT",   # cuándo el cliente dijo que transfirió
               "ALTER TABLE pedidos ADD COLUMN canje TEXT",                   # link de un solo uso con el que se pidió
               "ALTER TABLE pedidos ADD COLUMN regalo_enviado TEXT"]          # mail de la foto de regalo (o por qué no)
_lock = threading.Lock()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS contadores (marca TEXT PRIMARY KEY, ultimo INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pedidos (
  id TEXT PRIMARY KEY,
  marca TEXT NOT NULL,
  producto TEXT NOT NULL,
  precio INTEGER NOT NULL,
  estado TEXT NOT NULL,
  creado TEXT NOT NULL,
  pagado TEXT,
  entregado TEXT,
  nombre TEXT NOT NULL,
  email TEXT NOT NULL,
  whatsapp TEXT NOT NULL,
  datos TEXT NOT NULL,
  archivos TEXT NOT NULL DEFAULT '[]',
  mp_preferencia TEXT,
  mp_pago TEXT,
  drive_carpeta TEXT,
  drive_url TEXT,
  entrega_url TEXT,
  error TEXT,
  cambios_extra INTEGER NOT NULL DEFAULT 0,
  seguimiento TEXT,
  seguimiento_url TEXT,
  cuadro_comprado TEXT
);
CREATE TABLE IF NOT EXISTS fechas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pedido TEXT NOT NULL,
  creado TEXT NOT NULL,
  nombre TEXT NOT NULL,
  email TEXT NOT NULL,
  whatsapp TEXT NOT NULL,
  marca TEXT NOT NULL,
  para_quien TEXT NOT NULL,
  vinculo TEXT,
  tipo TEXT NOT NULL,
  otra TEXT,
  dia INTEGER NOT NULL,
  mes INTEGER NOT NULL,
  permiso_en TEXT NOT NULL,
  permiso_texto TEXT NOT NULL,
  baja_token TEXT NOT NULL UNIQUE,
  baja_en TEXT,
  ultimo_aviso_anio INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fechas_baja_token ON fechas(baja_token);
CREATE TABLE IF NOT EXISTS canjes (
  token TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,          -- regalo | mercadolibre
  producto TEXT NOT NULL,
  creado TEXT NOT NULL,
  vence TEXT NOT NULL,
  email TEXT,                  -- regalo: a quién se le dio (un regalo por mail y por WhatsApp)
  whatsapp TEXT,
  origen TEXT,                 -- regalo: el pedido que no se pagó · mercadolibre: el número de orden
  usado TEXT,
  pedido TEXT                  -- el pedido que se hizo con el link
);

"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Base:
    def __init__(self, ruta):
        self.ruta = str(ruta)
        with self._con() as c:
            c.executescript(ESQUEMA)
            for sql in MIGRACIONES:
                try:
                    c.execute(sql)
                except sqlite3.OperationalError:
                    pass  # la columna ya existe

    def _con(self):
        c = sqlite3.connect(self.ruta, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def nuevo_id(self, marca: str) -> str:
        with _lock, self._con() as c:
            fila = c.execute("SELECT ultimo FROM contadores WHERE marca=?", (marca,)).fetchone()
            n = (fila["ultimo"] if fila else 0) + 1
            c.execute("INSERT INTO contadores(marca, ultimo) VALUES(?, ?) "
                      "ON CONFLICT(marca) DO UPDATE SET ultimo=excluded.ultimo", (marca, n))
        return f"{marca.upper()}-{n:04d}"

    def crear(self, **campos) -> dict:
        campos = {**campos, "estado": "pendiente_pago", "creado": ahora()}
        campos["datos"] = json.dumps(campos.get("datos", {}), ensure_ascii=False)
        campos["archivos"] = json.dumps(campos.get("archivos", []), ensure_ascii=False)
        cols = ", ".join(campos)
        with self._con() as c:
            c.execute(f"INSERT INTO pedidos({cols}) VALUES({', '.join('?' * len(campos))})", tuple(campos.values()))
        return self.obtener(campos["id"])

    def actualizar(self, pid: str, **campos):
        if not campos:
            return
        sets = ", ".join(f"{k}=?" for k in campos)
        with self._con() as c:
            c.execute(f"UPDATE pedidos SET {sets} WHERE id=?", (*campos.values(), pid))

    def marcar_pagado(self, pid: str, pago_id: str) -> bool:
        """Pasa a pagado una sola vez (evita procesar dos veces el mismo aviso)."""
        with _lock, self._con() as c:
            cur = c.execute("UPDATE pedidos SET estado='pagado', pagado=?, mp_pago=?, pago_medio='mercadopago' "
                            "WHERE id=? AND estado='pendiente_pago'", (ahora(), str(pago_id), pid))
            return cur.rowcount == 1

    def marcar_pagado_transferencia(self, pid: str) -> bool:
        """El dueño vio el comprobante y aprueba: pasa a pagado sin pago de MP (mp_pago queda vacío, así los cobros
        y la comisión real de MP no lo cuentan). Una sola vez, y solo si el pedido sigue esperando el pago."""
        with _lock, self._con() as c:
            cur = c.execute("UPDATE pedidos SET estado='pagado', pagado=?, pago_medio='transferencia' "
                            "WHERE id=? AND estado='pendiente_pago'", (ahora(), pid))
            return cur.rowcount == 1

    def marcar_pagado_canje(self, pid: str, medio: str) -> bool:
        """Pedido hecho con un link de un solo uso (regalo o compra de Mercado Libre): ya está pago."""
        with _lock, self._con() as c:
            cur = c.execute("UPDATE pedidos SET estado='pagado', pagado=?, pago_medio=? "
                            "WHERE id=? AND estado='pendiente_pago'", (ahora(), medio, pid))
            return cur.rowcount == 1

    # ---- links de un solo uso (formulario sin pago) ----
    def crear_canje(self, **campos) -> dict:
        campos = {**campos, "creado": ahora()}
        cols = ", ".join(campos)
        with self._con() as c:
            c.execute(f"INSERT INTO canjes({cols}) VALUES({', '.join('?' * len(campos))})", tuple(campos.values()))
        return self.obtener_canje(campos["token"])

    def obtener_canje(self, token: str) -> dict | None:
        with self._con() as c:
            fila = c.execute("SELECT * FROM canjes WHERE token=?", (token,)).fetchone()
        return dict(fila) if fila else None

    def usar_canje(self, token: str, pid: str) -> bool:
        """Se usa una sola vez: el primero que lo usa se lo queda."""
        with _lock, self._con() as c:
            cur = c.execute("UPDATE canjes SET usado=?, pedido=? WHERE token=? AND usado IS NULL", (ahora(), pid, token))
            return cur.rowcount == 1

    def regalo_dado(self, email: str, whatsapp: str) -> bool:
        """¿Ya se le dio una foto de regalo a este mail o a este WhatsApp?"""
        with self._con() as c:
            fila = c.execute("SELECT 1 FROM canjes WHERE tipo='regalo' AND (lower(email)=lower(?) OR whatsapp=?) LIMIT 1",
                             (email or "", whatsapp or "")).fetchone()
        return fila is not None

    def canje_de_orden(self, tipo: str, origen: str) -> dict | None:
        with self._con() as c:
            fila = c.execute("SELECT * FROM canjes WHERE tipo=? AND origen=? ORDER BY creado DESC LIMIT 1",
                             (tipo, origen)).fetchone()
        return dict(fila) if fila else None

    def interesados(self) -> list[dict]:
        """Quienes empezaron un pedido y no lo pagaron (pendiente o cancelado), uno por mail, el más reciente.
        No incluye a quien después compró con el mismo mail."""
        with self._con() as c:
            filas = [dict(r) for r in c.execute(
                "SELECT id, marca, producto, precio, estado, creado, nombre, email, whatsapp, error, "
                "transferencia_avisada FROM pedidos ORDER BY creado DESC")]
        compraron = {f["email"].lower() for f in filas if f["estado"] not in ("pendiente_pago", "cancelado")}
        vistos, lista = set(), []
        for f in filas:
            mail = f["email"].lower()
            if f["estado"] not in ("pendiente_pago", "cancelado") or mail in compraron or mail in vistos:
                continue
            vistos.add(mail)
            lista.append({"pedido": f["id"], "marca": f["marca"], "producto": f["producto"], "precio": f["precio"],
                          "estado": f["estado"], "creado": f["creado"], "nombre": f["nombre"], "email": f["email"],
                          "whatsapp": f["whatsapp"], "motivo": f["error"] or "",
                          "transferencia_avisada": f["transferencia_avisada"]})
        return lista

    def obtener(self, pid: str) -> dict | None:
        with self._con() as c:
            fila = c.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()
        if not fila:
            return None
        d = dict(fila)
        d["datos"] = json.loads(d["datos"])
        d["archivos"] = json.loads(d["archivos"])
        return d

    def listar(self, estado: str | None = None, limite: int = 200) -> list[dict]:
        sql, args = "SELECT id FROM pedidos", ()
        if estado:
            sql, args = sql + " WHERE estado=?", (estado,)
        with self._con() as c:
            ids = [r["id"] for r in c.execute(sql + " ORDER BY creado DESC LIMIT ?", (*args, limite))]
        return [self.obtener(i) for i in ids]

    def guardar_fecha(self, **campos) -> dict:
        campos = {**campos, "creado": ahora()}
        cols = ", ".join(campos)
        with self._con() as c:
            cur = c.execute(f"INSERT INTO fechas({cols}) VALUES({', '.join('?' * len(campos))})", tuple(campos.values()))
            fid = cur.lastrowid
            fila = c.execute("SELECT * FROM fechas WHERE id=?", (fid,)).fetchone()
            return dict(fila)

    def obtener_fecha_por_token(self, token: str) -> dict | None:
        with self._con() as c:
            fila = c.execute("SELECT * FROM fechas WHERE baja_token=?", (token,)).fetchone()
            return dict(fila) if fila else None

    def dar_baja_fecha(self, token: str) -> bool:
        with self._con() as c:
            cur = c.execute("UPDATE fechas SET baja_en=? WHERE baja_token=? AND baja_en IS NULL", (ahora(), token))
            return cur.rowcount > 0

    def listar_fechas(self, solo_activas: bool = True) -> list[dict]:
        sql = "SELECT * FROM fechas"
        if solo_activas:
            sql += " WHERE baja_en IS NULL AND permiso_en IS NOT NULL"
        sql += " ORDER BY mes ASC, dia ASC, id ASC"
        with self._con() as c:
            return [dict(r) for r in c.execute(sql)]

    def marcar_aviso_fecha(self, fid: int, anio: int):
        with self._con() as c:
            c.execute("UPDATE fechas SET ultimo_aviso_anio=? WHERE id=?", (anio, fid))

