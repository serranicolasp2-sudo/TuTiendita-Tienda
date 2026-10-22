"""Publicador automático de productos y servicios en Mercado Libre vía API oficial.

Uso:
  python tienda/herramientas/publicar_ml.py listar
  python tienda/herramientas/publicar_ml.py publicar [--activar] [--id ID_PRODUCTO]
  python tienda/herramientas/publicar_ml.py activar-todas
  python tienda/herramientas/publicar_ml.py mis-publicaciones
"""
import argparse
import json
import pathlib
import sys
import httpx

BASE_DIR = pathlib.Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent / "app"))

import ml_api
from catalogo import PRODUCTOS

AVISO_ENTREGA_CUADROS = """*** IMPORTANTE SOBRE LA ENTREGA ***
Al realizar tu compra, selecciona siempre la opcion:
-> "Retiro en el domicilio del vendedor" o "Acordar con el vendedor".
El envio a tu domicilio esta 100% BONIFICADO e INCLUIDO a todo el pais.
Una vez hecha la compra, nos pasas tu direccion de entrega por el chat privado y te lo enviamos directo a tu casa sin costo adicional.
--------------------------------------------------

"""

# Definición de plantillas de publicación para Mercado Libre
PLANTILLAS = {
    # ---------------- CANCIONES PERSONALIZADAS (MLA1174: Música) ----------------
    "tc-cancion": {
        "title": "Canción Personalizada Con Tu Historia Regalo Digital MP3",
        "category_id": "MLA1174",
        "currency_id": "ARS",
        "available_quantity": 99,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://tucancion.com.ar/img/tc-avatar-1080x1080.png"},
            {"source": "https://tucancion.com.ar/img/tc-post-dedicatoria-1080x1350.png"},
            {"source": "https://tucancion.com.ar/img/tc-post-pasos-1080x1350.png"},
            {"source": "https://tucancion.com.ar/img/tc-post-ocasiones-1080x1350.png"},
            {"source": "https://tucancion.com.ar/img/portada-facebook.png"},
        ],
        "attributes": [
            {"id": "MUSIC_ARTIST_NAME", "value_name": "Tu Canción"},
            {"id": "ALBUM_NAME", "value_name": "Canción con tu historia"},
            {"id": "ALBUM_TYPE", "value_id": "4781803"},
            {"id": "FORMAT", "value_id": "2132699"},  # Digital
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "2 días"}
        ],
        "shipping": {
            "mode": "not_specified",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": """CANCIÓN PERSONALIZADA CON SU PROPIA HISTORIA · REGALO ORIGINAL

Creamos una canción única y emotiva basada en anécdotas, recuerdos y nombres reales.
Un regalo inolvidable para el Día de la Madre, cumpleaños o aniversarios.

¿QUÉ RECIBÍS?
• Archivo de audio MP3 en calidad de estudio profesional.
• Letra completa en PDF lista para imprimir o dedicar.
• Hasta 5 correcciones incluidas para que quede exactamente como querés.

¿CÓMO SE HACE?
1. Hacés la compra.
2. Nos contás por mensaje la historia, a quién va dedicada y qué estilo preferís (balada, pop, cumbia, folklore, rock, tango, acústico, etc.).
3. En menos de 48 horas te enviamos la primera versión para que la escuches y apruebes.

Entrega 100% digital e inmediata por la mensajeria privada de Mercado Libre."""
    },

    "tc-combo": {
        "title": "Canción Personalizada + Video Con Fotos Para Regalar",
        "category_id": "MLA1174",
        "currency_id": "ARS",
        "available_quantity": 99,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://tucancion.com.ar/img/tc-avatar-1080x1080.png"},
            {"source": "https://tucancion.com.ar/img/tc-post-dedicatoria-1080x1350.png"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-madera.webp"},
            {"source": "https://tucancion.com.ar/img/portada-facebook.png"},
        ],
        "attributes": [
            {"id": "MUSIC_ARTIST_NAME", "value_name": "Tu Canción"},
            {"id": "ALBUM_NAME", "value_name": "Canción y Video con Fotos"},
            {"id": "ALBUM_TYPE", "value_id": "4781803"},
            {"id": "FORMAT", "value_id": "2132699"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "3 días"}
        ],
        "shipping": {
            "mode": "not_specified",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": """COMBO COMPLETO: CANCIÓN PERSONALIZADA + VIDEO CON FOTOS

El regalo más emocionante: su canción original de fondo sincronizada con un video de sus fotos familiares (hasta 20 fotos, incluyendo hasta 3 fotos restauradas).

¿QUÉ RECIBÍS?
• Audio MP3 de la canción personalizada.
• Video musical en alta definición (MP4) con sus fotos sincronizadas.
• Hasta 3 fotos antiguas restauradas a nuevo incluidas en el video.
• Letra en PDF de regalo.

Plazo de entrega: 72 horas."""
    },

    # ---------------- FOTOS DIGITALES (MLA434385: Fotos) ----------------
    "rf-foto-1": {
        "title": "Restauración De Foto Antigua Dañada Digital Alta Calidad",
        "category_id": "MLA434385",
        "currency_id": "ARS",
        "available_quantity": 99,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-antes.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-foto-de-perfil.png"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
            {"id": "MODEL", "value_name": "Restauración Digital 1 Foto"},
            {"id": "FORMAT", "value_id": "2132699"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "1 días"}
        ],
        "shipping": {
            "mode": "not_specified",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": """RESTAURACIÓN PROFESIONAL DE 1 FOTO ANTIGUA · FORMATO DIGITAL

¿Tenés una foto familiar querida manchada, doblada, rota o desvaída?
La restauramos respetando fielmente las caras y rasgos originales.

¿QUÉ INCLUYE?
• Eliminación completa de manchas, rayas, roturas y polvo.
• Corrección de nitidez y contraste.
• Coloración opcional si la foto original es blanco y negro.
• Archivo digital en ultra alta resolución (apto para imprimir en cuadro).

¿CÓMO TRABAJAMOS?
1. Comprás la publicación.
2. Nos enviás la foto fotografiada con buena luz con el celular o escaneada.
3. En menos de 2 horas te mostramos una vista previa de cómo quedó.
4. Si te gusta, te enviamos el archivo original por el chat privado de Mercado Libre.

Entrega 100% digital sin costo de envío."""
    },

    "rf-pack-5": {
        "title": "Pack 5 Fotos Antiguas Restauradas Digital Alta Calidad",
        "category_id": "MLA434385",
        "currency_id": "ARS",
        "available_quantity": 99,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-antes.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-foto-de-perfil.png"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
            {"id": "MODEL", "value_name": "Pack 5 Fotos Digitales"},
            {"id": "FORMAT", "value_id": "2132699"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "1 días"}
        ],
        "shipping": {
            "mode": "not_specified",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": """PACK DE 5 FOTOS ANTIGUAS RESTAURADAS CON DESCUENTO

Ideal para revivir un álbum familiar o recuerdos de una época.
Restauración digital en alta definición, color opcional incluido y entrega por archivo digital."""
    },

    "rf-pack-10": {
        "title": "Pack 10 Fotos Antiguas Restauradas Retoque Digital",
        "category_id": "MLA434385",
        "currency_id": "ARS",
        "available_quantity": 99,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-antes.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-foto-de-perfil.png"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
            {"id": "MODEL", "value_name": "Pack 10 Fotos Digitales"},
            {"id": "FORMAT", "value_id": "2132699"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "2 días"}
        ],
        "shipping": {
            "mode": "not_specified",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": """PACK DE 10 FOTOS ANTIGUAS RESTAURADAS

Restauración completa para 10 fotografías familiares.
Entrega digital en alta definición."""
    },

    "rf-pack-20": {
        "title": "Pack 20 Fotos Antiguas Restauradas Retoque Digital",
        "category_id": "MLA434385",
        "currency_id": "ARS",
        "available_quantity": 99,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-antes.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-foto-de-perfil.png"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
            {"id": "MODEL", "value_name": "Pack 20 Fotos Digitales"},
            {"id": "FORMAT", "value_id": "2132699"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "3 días"}
        ],
        "shipping": {
            "mode": "not_specified",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": """PACK DE 20 FOTOS ANTIGUAS RESTAURADAS · ÁLBUM COMPLETO

La opción más económica por foto ($1.999 por foto) para recuperar toda la historia familiar."""
    },

    # ---------------- CUADROS FÍSICOS (MLA1635: Cuadros Decorativos) ----------------
    "rf-cuadro-enmarcado-20x30": {
        "title": "Cuadro Enmarcado 20x30 Con Tu Foto Restaurada Regalo",
        "category_id": "MLA1635",
        "currency_id": "ARS",
        "available_quantity": 10,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-madera.webp"},
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-negro.webp"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
            {"id": "THEME", "value_name": "Familiar / Personalizado"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "2 días"}
        ],
        "shipping": {
            "mode": "me2",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": AVISO_ENTREGA_CUADROS + """CUADRO ENMARCADO 20x30 CON TU FOTO ANTIGUA RESTAURADA

¿Tenés una foto familiar gastada, dañada o en blanco y negro?
La restauramos profesionalmente y te la entregamos lista para colgar.

¿QUÉ INCLUYE?
• Restauración digital completa de la foto (eliminación de manchas, rayas y roturas).
• Coloración opcional sin cargo si la foto es blanco y negro.
• Impresión fotográfica de alta definición.
• Marco color madera o negro (a tu elección) con vidrio protector.
• Envío a todo el país bonificado.

¿CÓMO TRABAJAMOS?
1. Comprás la publicación (seleccionando «Retiro en el domicilio del vendedor»).
2. Nos mandás la foto escaneada o fotografiada con el celular por mensaje.
3. Te enviamos una vista previa digital para que apruebes el resultado antes de enmarcar.
4. Armamos el cuadro y te lo enviamos a tu casa.

Plazo de elaboración: 48 horas."""
    },

    "rf-cuadro-enmarcado-30x40": {
        "title": "Cuadro Enmarcado 30x40 Con Tu Foto Restaurada Regalo",
        "category_id": "MLA1635",
        "currency_id": "ARS",
        "available_quantity": 10,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-madera.webp"},
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-negro.webp"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
            {"id": "THEME", "value_name": "Familiar / Personalizado"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "2 días"}
        ],
        "shipping": {
            "mode": "me2",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": AVISO_ENTREGA_CUADROS + """CUADRO ENMARCADO 30x40 CON TU FOTO ANTIGUA RESTAURADA

El tamaño ideal para fotos familiares destacadas.
Restauración digital en ultra resolución e impresión enmarcada.

¿QUÉ INCLUYE?
• Restauración digital completa de la foto (manchas, roturas, nitidez).
• Coloración opcional si la foto original es blanco y negro.
• Impresión fotográfica 30x40 a 300 dpi.
• Marco en madera natural o negro con vidrio.
• Envío incluido a todo el país.

Plazo de elaboración: 48 horas."""
    },

    "rf-cuadro-ecocuero-20x30": {
        "title": "Cuadro Bastidor Ecocuero 20x30 Con Foto Restaurada",
        "category_id": "MLA1635",
        "currency_id": "ARS",
        "available_quantity": 10,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-ecocuero.webp"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "2 días"}
        ],
        "shipping": {
            "mode": "me2",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": AVISO_ENTREGA_CUADROS + """CUADRO BASTIDOR DE ECOCUERO 20x30

Impresión texturada sobre bastidor tensado de madera, moderno y sin marco externo.
Incluye restauración fotográfica digital completa y envío bonificado a todo el país."""
    },

    "rf-cuadro-ecocuero-40x30": {
        "title": "Cuadro Bastidor Ecocuero 40x30 Con Foto Restaurada",
        "category_id": "MLA1635",
        "currency_id": "ARS",
        "available_quantity": 10,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",
        "condition": "new",
        "pictures": [
            {"source": "https://restauraciondefotos.com.ar/img/cuadro-ecocuero.webp"},
            {"source": "https://restauraciondefotos.com.ar/img/muestra-despues.jpg"},
            {"source": "https://restauraciondefotos.com.ar/img/rf-portada-facebook.png"},
        ],
        "attributes": [
            {"id": "BRAND", "value_name": "Restauración de fotos"},
        ],
        "sale_terms": [
            {"id": "MANUFACTURING_TIME", "value_name": "2 días"}
        ],
        "shipping": {
            "mode": "me2",
            "local_pick_up": True,
            "free_shipping": False
        },
        "description": AVISO_ENTREGA_CUADROS + """CUADRO BASTIDOR DE ECOCUERO 40x30 (GRANDE)

Impresión en ecocuero de alta durabilidad sobre bastidor de madera maciza.
Incluye la restauración fotográfica completa y el envío bonificado a todo el país."""
    }
}


def armar_payload(prod_id: str) -> dict:
    if prod_id not in PLANTILLAS:
        raise ValueError(f"No hay plantilla definida para {prod_id}")
    prod = PRODUCTOS[prod_id]
    p = json.loads(json.dumps(PLANTILLAS[prod_id]))
    p["price"] = prod.precio
    if "title" in p and "family_name" not in p:
        p["family_name"] = p.pop("title")
    return p


def listar():
    print(f"\n{'ID PRODUCTO':<28} | {'PRECIO':<10} | {'CATEGORÍA':<10} | {'TÍTULO ML'}")
    print("-" * 85)
    for k, v in PLANTILLAS.items():
        prod = PRODUCTOS.get(k)
        precio = f"${prod.precio:,}".replace(",", ".") if prod else "S/D"
        print(f"{k:<28} | {precio:<10} | {v['category_id']:<10} | {v['title'][:32]}")
    print()


def publicar(token: str, prod_id: str | None = None, activar: bool = False):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    a_publicar = [prod_id] if prod_id else list(PLANTILLAS.keys())

    # Consultar publicaciones activas para no duplicar
    me = ml_api.get("/users/me")
    user_id = me["id"]
    r_exist = httpx.get(
        f"{ml_api.API}/users/{user_id}/items/search",
        headers=headers,
        params={"limit": 50, "status": "active,paused"}
    )
    items_existentes = r_exist.json().get("results", [])

    for k in a_publicar:
        payload = armar_payload(k)
        desc_texto = payload.pop("description", "")
        payload["status"] = "active" if activar else "paused"

        print(f"\nPublicando '{k}' (${payload['price']}) [Estado: {payload['status']}]...")
        r = httpx.post(f"{ml_api.API}/items", headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            item = r.json()
            item_id = item.get("id")
            permalink = item.get("permalink")
            print(f"  >>> ¡PUBLICADO EXITOSAMENTE! ID: {item_id}")
            print(f"      Enlace: {permalink}")
            if desc_texto and item_id:
                rd = httpx.post(
                    f"{ml_api.API}/items/{item_id}/description",
                    headers=headers,
                    json={"plain_text": desc_texto},
                    timeout=20
                )
                if rd.status_code in (200, 201):
                    print("      Descripción cargada con éxito.")
                else:
                    print(f"      Aviso al cargar descripción: {rd.text}")
        else:
            print(f"  ERROR ({r.status_code}): {r.json().get('message', r.text)}")


def activar_todas(token: str):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    me = ml_api.get("/users/me")
    user_id = me["id"]
    r = httpx.get(
        f"{ml_api.API}/users/{user_id}/items/search",
        headers=headers,
        params={"limit": 50, "status": "paused"}
    )
    items = r.json().get("results", [])
    print(f"\nActivando {len(items)} publicaciones pausadas...")
    for item_id in items:
        ra = httpx.put(
            f"{ml_api.API}/items/{item_id}",
            headers=headers,
            json={"status": "active"},
            timeout=20
        )
        if ra.status_code in (200, 201):
            print(f"  [ACTIVA] {item_id}: https://articulo.mercadolibre.com.ar/{item_id}")
        else:
            print(f"  [ERROR] {item_id}: {ra.text}")
    print()


def mis_publicaciones(token: str):
    me = ml_api.get("/users/me")
    user_id = me["id"]
    r = httpx.get(
        f"{ml_api.API}/users/{user_id}/items/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 50, "status": "active,paused"}
    )
    if r.status_code != 200:
        sys.exit(f"Error al consultar publicaciones: {r.text}")
    items = r.json().get("results", [])
    print(f"\nPublicaciones totales de {me.get('nickname')} ({len(items)} en total):")
    for i in items:
        # consultar item
        ri = httpx.get(f"{ml_api.API}/items/{i}", headers={"Authorization": f"Bearer {token}"})
        if ri.status_code == 200:
            ji = ri.json()
            estado = ji.get("status")
            precio = ji.get("price")
            titulo = ji.get("title")
            print(f" • [{estado.upper():<6}] ${precio:<7} | {titulo[:40]} | https://articulo.mercadolibre.com.ar/{i}")
        else:
            print(f" • {i}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando")
    sub.add_parser("listar", help="Lista los productos y títulos preparados")
    
    p_pub = sub.add_parser("publicar", help="Publica en Mercado Libre")
    p_pub.add_argument("--id", help="Publica solo el producto con este ID")
    p_pub.add_argument("--activar", action="store_true", help="Publica directamente activas en lugar de pausadas")
    
    sub.add_parser("activar-todas", help="Pasa todas las publicaciones pausadas a activas")
    sub.add_parser("mis-publicaciones", help="Consulta lo publicado actualmente")

    args = parser.parse_args()
    if not args.comando or args.comando == "listar":
        listar()
        return

    tok = ml_api.token()
    if args.comando == "publicar":
        publicar(tok, args.id, args.activar)
    elif args.comando == "activar-todas":
        activar_todas(tok)
    elif args.comando == "mis-publicaciones":
        mis_publicaciones(tok)


if __name__ == "__main__":
    main()
