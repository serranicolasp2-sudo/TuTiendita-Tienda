"""Revisión del mail que escribe el cliente (13/10: entró uno terminado en "@gmail.col" y los avisos rebotaron).

tienda.js hace lo mismo en el navegador (formato y "¿Quisiste decir…?"; mantener las listas iguales). Acá además se
consulta el DNS: si el dominio no existe o no recibe correo, el pedido no se toma. Si el DNS no contesta, se acepta:
no se frena una venta por un problema de red.
"""
import functools
import re

FORMATO = re.compile(r"^[a-z0-9._%+\-]+@([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+[a-z]{2,}$", re.I)
DOMINIOS = ("gmail.com", "hotmail.com", "hotmail.com.ar", "hotmail.es", "outlook.com", "outlook.com.ar", "outlook.es",
            "yahoo.com", "yahoo.com.ar", "yahoo.es", "live.com", "live.com.ar", "icloud.com", "me.com", "msn.com",
            "fibertel.com.ar", "speedy.com.ar", "arnet.com.ar", "protonmail.com", "proton.me", "googlemail.com",
            "mail.com", "ymail.com", "aol.com", "gmx.com")
TERMINACIONES_MAL = ("col", "con", "cpm", "cmo", "ocm", "vom", "xom", "comm", "coom", "cim", "clm", "om", "cm")


def distancia(a: str, b: str) -> int:
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        nueva = [i]
        for j, cb in enumerate(b, 1):
            nueva.append(min(fila[j] + 1, nueva[j - 1] + 1, fila[j - 1] + (ca != cb)))
        fila = nueva
    return fila[-1]


def sugerencia(mail: str) -> str:
    """El mail corregido si parece un error de tipeo en un proveedor conocido (gmail.col → gmail.com), o ""."""
    usuario, _, dominio = mail.rpartition("@")
    dominio = dominio.lower()
    if not usuario or dominio in DOMINIOS:
        return ""
    mejor = min(DOMINIOS, key=lambda d: distancia(dominio, d))
    if distancia(dominio, mejor) <= (1 if len(mejor) <= 7 else 2):
        return f"{usuario}@{mejor}"
    if dominio.split(".")[0] == "gmail":
        return f"{usuario}@gmail.com"
    base, _, fin = dominio.rpartition(".")
    if fin in TERMINACIONES_MAL and base:
        return f"{usuario}@{base}.com"
    return ""


@functools.lru_cache(maxsize=1024)
def recibe_correo(dominio: str) -> bool:
    """False solo si el DNS dice que el dominio no existe o que no recibe mails."""
    try:
        import dns.resolver
    except ImportError:            # sin dnspython instalado se salta esta parte
        return True
    r = dns.resolver.Resolver()
    r.lifetime = 4
    try:
        mx = r.resolve(dominio, "MX")
        return not all(str(x.exchange) == "." for x in mx)          # "MX 0 ." = no recibe correo (RFC 7505)
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        try:
            r.resolve(dominio, "A")
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return False
        except Exception:
            return True
    except Exception:
        return True


def problema(mail: str, revisado: bool = False) -> str:
    """Qué está mal en el mail, para mostrarle al cliente, o "" si está bien. revisado: ya dijo "está bien así"."""
    if not FORMATO.match(mail):
        return "Revisá el mail: tiene que ser como nombre@gmail.com, sin espacios."
    s = sugerencia(mail)
    if s and not revisado:
        return f"¿Quisiste decir {s}? Revisá cómo escribiste el mail."
    dominio = mail.rpartition("@")[2].lower()
    if not recibe_correo(dominio):
        return f"Ese mail no puede recibir correos: «{dominio}» no existe. Revisá cómo lo escribiste."
    return ""
