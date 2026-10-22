/*
 * tienda.js: cliente de la API de la tienda (Tu Canción · Restauración de fotos).
 * Lo escribió Claude. Antigravity: incluilo tal cual con <script src="../tienda.js" defer></script> y no lo modifiques;
 * si necesitás algo distinto, pedilo. Contrato completo en tienda/docs/CONTRATO-API.md.
 *
 * Uso mínimo en un formulario de compra:
 *   <form data-tienda-form> … campos con los nombres del contrato … <button type="submit">Pagar</button>
 *     <p data-tienda-error hidden></p> <progress data-tienda-progreso hidden></progress> </form>
 * El script lo intercepta, valida, sube y redirige a Mercado Pago.
 *
 * En gracias.html:
 *   <div data-tienda-gracias></div>  → muestra el estado del pedido (lee ?pedido=TC-0001) y se actualiza solo.
 */
(function () {
  "use strict";
  var API = (window.TIENDA_API || "/tutienditaia/api").replace(/\/$/, "");

  function pedirJSON(metodo, ruta) {
    return fetch(API + ruta, { method: metodo, headers: { Accept: "application/json" } }).then(function (r) {
      return r.json().then(function (d) { if (!r.ok) throw d; return d; });
    });
  }

  function catalogo(marca) { return pedirJSON("GET", "/catalogo" + (marca ? "?marca=" + marca : "")); }

  // ---- Precios vigentes en toda la página ----
  // Cualquier elemento con data-precio="<producto>" muestra el precio del servidor (el número escrito en el HTML es
  // solo el valor de arranque). Con data-por-foto="N" muestra el precio dividido N (packs). Así un cambio de precio
  // (a mano desde la centralita o del vigilante) se ve en todos lados y la página nunca muestra algo distinto de lo
  // que se cobra.
  var precios = null;
  function formatear(n) { return "$" + Math.round(n).toLocaleString("es-AR"); }
  function precio(id) { return precios && precios[id] != null ? precios[id] : null; }
  function pintarPrecios(raiz) {
    if (!precios) return;
    (raiz || document).querySelectorAll("[data-precio]").forEach(function (el) {
      var p = precio(el.getAttribute("data-precio"));
      if (p == null) return;
      var n = Number(el.getAttribute("data-por-foto") || 1);
      el.textContent = formatear(p / n);
    });
  }
  catalogo().then(function (c) {
    precios = {};
    (c.productos || []).forEach(function (p) { precios[p.id] = p.precio; });
    pintarPrecios();
  }).catch(function () { /* sin conexión: quedan los valores de arranque */ });
  function estado(pedido) { return pedirJSON("GET", "/pedidos/" + encodeURIComponent(pedido) + "/estado"); }

  // ---- UTM / Origen del pedido (Tarea 18) ----
  (function () {
    try {
      var q = new URLSearchParams(window.location.search);
      var src = q.get("utm_source");
      var med = q.get("utm_medium");
      var cam = q.get("utm_campaign");
      var cnt = q.get("utm_content");
      if (src || med || cam || cnt) {
        var utm = {};
        if (src) utm.source = src;
        if (med) utm.medium = med;
        if (cam) utm.campaign = cam;
        if (cnt) utm.content = cnt;
        sessionStorage.setItem("tutienditaia_utm", JSON.stringify(utm));
      }
    } catch (e) {
      // sessionStorage puede fallar en navegación privada
    }
  })();

  function obtenerOrigen() {
    try {
      var raw = sessionStorage.getItem("tutienditaia_utm");
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return null;
  }

  // ---- Píxel de Meta (Tarea 18, opcional: solo si se define window.META_PIXEL_ID) ----
  var pixelId = window.META_PIXEL_ID || "1402632028570089";
  if (pixelId && typeof window.fbq !== "function") {
    !function(f,b,e,v,n,t,s)
    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', pixelId);
    fbq('track', 'PageView');
    fbq('track', 'ViewContent');
  }

  function pixelTrack(evento, datos, idEvento) {
    if (typeof window.fbq === "function") {
      try {
        // idEvento: Meta descarta un evento repetido con el mismo id (una compra se cuenta una vez)
        if (idEvento) window.fbq('track', evento, datos || {}, { eventID: idEvento });
        else if (datos) window.fbq('track', evento, datos);
        else window.fbq('track', evento);
      } catch (e) {}
    }
  }

  function enviar(form, alProgreso) {
    return new Promise(function (resolver, rechazar) {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", API + "/pedidos");
      xhr.responseType = "json";
      xhr.upload.onprogress = function (e) { if (e.lengthComputable && alProgreso) alProgreso(e.loaded / e.total); };
      xhr.onload = function () {
        var d = xhr.response || {};
        if (xhr.status === 201) resolver(d);
        else rechazar(d.error ? d : { error: "No pudimos tomar el pedido (" + xhr.status + "). Probá de nuevo o escribinos por WhatsApp." });
      };
      xhr.onerror = function () { rechazar({ error: "Se cortó la conexión. Revisá internet y probá de nuevo." }); };
      var fd = new FormData(form);
      var origen = obtenerOrigen();
      if (origen) {
        fd.append("origen", JSON.stringify(origen));
      }
      xhr.send(fd);
    });
  }

  function marcarError(form, err) {
    form.querySelectorAll("[aria-invalid]").forEach(function (el) { el.removeAttribute("aria-invalid"); });
    var caja = form.querySelector("[data-tienda-error]");
    if (caja) { caja.textContent = err.error; caja.hidden = false; caja.setAttribute("role", "alert"); }
    if (err.campo) {
      var campo = form.querySelector('[name="' + err.campo + '"]');
      if (campo) { campo.setAttribute("aria-invalid", "true"); campo.focus(); }
    }
  }

  // ---- Mail: formato y errores de tipeo (13/10: entró uno terminado en "@gmail.col" y los avisos rebotaron).
  // El servidor revisa lo mismo y además que el dominio reciba correo (app/correo.py: mantener las listas iguales).
  var FORMATO_MAIL = /^[a-z0-9._%+\-]+@([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+[a-z]{2,}$/i;
  var DOMINIOS = ["gmail.com", "hotmail.com", "hotmail.com.ar", "hotmail.es", "outlook.com", "outlook.com.ar", "outlook.es",
    "yahoo.com", "yahoo.com.ar", "yahoo.es", "live.com", "live.com.ar", "icloud.com", "me.com", "msn.com",
    "fibertel.com.ar", "speedy.com.ar", "arnet.com.ar", "protonmail.com", "proton.me", "googlemail.com",
    "mail.com", "ymail.com", "aol.com", "gmx.com"];
  var TERMINACIONES_MAL = ["col", "con", "cpm", "cmo", "ocm", "vom", "xom", "comm", "coom", "cim", "clm", "om", "cm"];

  function distancia(a, b) {
    var d = [], i, j;
    for (i = 0; i <= a.length; i++) d[i] = [i];
    for (j = 0; j <= b.length; j++) d[0][j] = j;
    for (i = 1; i <= a.length; i++) {
      for (j = 1; j <= b.length; j++) {
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
    }
    return d[a.length][b.length];
  }

  function sugerirMail(mail) {
    var at = mail.lastIndexOf("@");
    if (at < 1) return "";
    var usuario = mail.slice(0, at), dominio = mail.slice(at + 1).toLowerCase();
    if (DOMINIOS.indexOf(dominio) >= 0) return "";
    var mejor = "", menor = 99;
    DOMINIOS.forEach(function (d) { var n = distancia(dominio, d); if (n < menor) { menor = n; mejor = d; } });
    if (menor <= (mejor.length <= 7 ? 1 : 2)) return usuario + "@" + mejor;
    if (dominio.split(".")[0] === "gmail") return usuario + "@gmail.com";
    var partes = dominio.split("."), fin = partes.pop();
    if (TERMINACIONES_MAL.indexOf(fin) >= 0 && partes.length) return usuario + "@" + partes.join(".") + ".com";
    return "";
  }

  function prepararMail(form) {
    var campo = form.querySelector('input[name="email"]');
    if (!campo) return;
    var revisado = document.createElement("input");      // "No, está bien así": el servidor no vuelve a preguntar
    revisado.type = "hidden"; revisado.name = "email_revisado";
    form.appendChild(revisado);
    var aviso = document.createElement("div");
    aviso.className = "tienda-mail-aviso"; aviso.hidden = true; aviso.setAttribute("role", "status");
    aviso.style.cssText = "margin-top:8px;font-size:15px;line-height:1.4";
    campo.insertAdjacentElement("afterend", aviso);
    var BOTON = "min-height:44px;margin:8px 8px 0 0;padding:0 14px;border-radius:6px;font:inherit;font-weight:700;cursor:pointer;";

    function boton(texto, estilo, alTocar) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = texto; b.style.cssText = BOTON + estilo;
      b.addEventListener("click", alTocar);
      return b;
    }

    function revisar(mostrarAviso) {
      var mail = campo.value.trim(), error = "", sugerencia = "";
      if (mail && !FORMATO_MAIL.test(mail)) error = "Revisá el mail: tiene que ser como nombre@gmail.com, sin espacios.";
      else if (mail && revisado.value !== "si") sugerencia = sugerirMail(mail);
      campo.setCustomValidity(error || (sugerencia ? "¿Quisiste decir " + sugerencia + "? Elegí una opción abajo del mail." : ""));
      if (mostrarAviso || !aviso.hidden) {
        aviso.innerHTML = "";
        aviso.hidden = !error && !sugerencia;
        if (error) {
          var e = document.createElement("p");
          e.style.cssText = "margin:0;color:#B42318;font-weight:700";
          e.textContent = error;
          aviso.appendChild(e);
        } else if (sugerencia) {
          var p = document.createElement("p"), fuerte = document.createElement("strong");
          p.style.margin = "0";
          fuerte.textContent = sugerencia;
          p.appendChild(document.createTextNode("¿Quisiste decir "));
          p.appendChild(fuerte);
          p.appendChild(document.createTextNode("?"));
          aviso.appendChild(p);
          aviso.appendChild(boton("Sí, corregir", "border:0;background:#1A1712;color:#fff;", function () {
            campo.value = sugerencia; revisado.value = ""; revisar(true); campo.focus();
          }));
          aviso.appendChild(boton("No, está bien así", "border:2px solid currentColor;background:transparent;color:inherit;", function () {
            revisado.value = "si"; revisar(true); campo.focus();
          }));
        }
      }
      return !error && !sugerencia;
    }
    campo.addEventListener("input", function () { revisado.value = ""; revisar(false); });
    campo.addEventListener("change", function () { revisar(true); });
    campo.addEventListener("invalid", function () { revisar(true); });
  }

  function prepararFormulario(form) {
    prepararMail(form);
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var boton = form.querySelector('[type="submit"]');
      var barra = form.querySelector("[data-tienda-progreso]");
      var caja = form.querySelector("[data-tienda-error]");
      if (caja) caja.hidden = true;
      if (boton) { boton.disabled = true; boton.dataset.texto = boton.textContent; boton.textContent = "Enviando…"; }
      if (barra) { barra.hidden = false; barra.value = 0; barra.max = 1; }
      if (!form.dataset.canje) pixelTrack('InitiateCheckout');
      enviar(form, function (p) { if (barra) barra.value = p; })
        .then(function (d) {
          if (d.pagado) {     // link de un solo uso: no se cobra, va directo a la página del pedido
            window.location.href = "gracias.html?pedido=" + encodeURIComponent(d.pedido);
            return;
          }
          if (boton) boton.textContent = "Te llevamos a Mercado Pago…";
          window.location.href = d.init_point;
        })
        .catch(function (err) {
          marcarError(form, err);
          if (boton) { boton.disabled = false; boton.textContent = boton.dataset.texto; }
          if (barra) barra.hidden = true;
        });
    });
  }

  var TEXTOS = {
    pendiente_pago: "Estamos esperando la confirmación de Mercado Pago. Si pagaste en efectivo, puede tardar unas horas.",
    pagado: "¡Listo! Recibimos el pago. Te mandamos un mail con los próximos pasos y te escribimos por WhatsApp: las fotos, en menos de 2 horas; las canciones, en menos de 48.",
    entregado: "Este pedido ya fue entregado. Revisá tu mail.",
    cancelado: "Este pedido se canceló o venció sin pago. Si fue un error, escribinos por WhatsApp."
  };
  var TEXTOS_CANJE = {
    regalo: "¡Listo! Recibimos tu pedido de regalo. Te mandamos un mail y en menos de 2 horas te escribimos por WhatsApp con la vista previa.",
    mercadolibre: "¡Listo! Recibimos los datos de tu compra de Mercado Libre. Te mandamos un mail y te escribimos por WhatsApp con la vista previa."
  };
  var TEXTO_FALLIDO ="El pago con Mercado Pago no se completó. Tu pedido sigue guardado: abajo podés volver a intentar o pagar por transferencia.";
  var TEXTO_TRANSFERENCIA = "Recibimos tu aviso de transferencia. Apenas confirmemos el comprobante te llega un mail y tu pedido entra en producción.";

  // Lo que Mercado Pago agrega a la dirección de vuelta: collection_status / status = approved, pending, rejected o null (canceló)
  function pagoFallido(q) {
    var malos = ["null", "rejected", "failure", "cancelled"];
    return q.get("pago") === "fallido" || malos.indexOf(q.get("collection_status")) !== -1 || malos.indexOf(q.get("status")) !== -1;
  }
  function pagoAprobadoEnMP(q) { return q.get("collection_status") === "approved" || q.get("status") === "approved"; }

  function copiar(texto, boton) {
    var listo = function () { var t = boton.textContent; boton.textContent = "¡Copiado!"; setTimeout(function () { boton.textContent = t; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).then(listo, function () {});
    else { var a = document.createElement("textarea"); a.value = texto; document.body.appendChild(a); a.select();
           try { document.execCommand("copy"); listo(); } catch (e) { /* sin portapapeles */ } a.remove(); }
  }

  // "¿No pudiste realizar la compra?": reintentar con Mercado Pago o pagar por transferencia y mandar el comprobante
  function alternativaDePago(el, d) {
    var caja = document.querySelector("[data-tienda-alternativa]");
    if (caja) return caja;
    caja = document.createElement("section");
    caja.className = "tienda-alternativa";
    caja.setAttribute("data-tienda-alternativa", "");
    var h = document.createElement("h2"); h.textContent = "¿No pudiste realizar la compra?";
    var p = document.createElement("p");
    p.textContent = "Volvé a intentar o realizá una transferencia a la siguiente cuenta y mandanos tu comprobante por WhatsApp:";
    caja.appendChild(h); caja.appendChild(p);

    var reintentar = document.createElement("button");
    reintentar.type = "button"; reintentar.className = "tienda-reintentar";
    reintentar.textContent = "Volver a intentar con Mercado Pago";
    reintentar.addEventListener("click", function () {
      reintentar.disabled = true; reintentar.textContent = "Te llevamos a Mercado Pago…";
      pedirJSON("GET", "/pedidos/" + encodeURIComponent(d.pedido) + "/pagar")
        .then(function (r) { window.location.href = r.init_point; })
        .catch(function (err) {
          reintentar.disabled = false; reintentar.textContent = "Volver a intentar con Mercado Pago";
          alert((err && err.error) || "No pudimos abrir Mercado Pago. Probá de nuevo o pagá por transferencia.");
        });
    });
    caja.appendChild(reintentar);

    catalogo().then(function (c) {
      var t = c.transferencia || {};
      if (!t.alias && !t.cbu) return;
      var lista = document.createElement("dl"); lista.className = "tienda-transferencia";
      [["Alias", t.alias, true], ["CBU", t.cbu, true], ["Monto", formatear(d.precio), false], ["Pedido", d.pedido, false]]
        .forEach(function (fila) {
          if (!fila[1]) return;
          var div = document.createElement("div");
          var dt = document.createElement("dt"); dt.textContent = fila[0];
          var dd = document.createElement("dd");
          var valor = document.createElement("span"); valor.textContent = fila[1]; dd.appendChild(valor);
          if (fila[2]) {
            var b = document.createElement("button"); b.type = "button"; b.className = "tienda-copiar"; b.textContent = "Copiar";
            b.addEventListener("click", function () { copiar(fila[1], b); });
            dd.appendChild(b);
          }
          div.appendChild(dt); div.appendChild(dd); lista.appendChild(div);
        });
      caja.appendChild(lista);
      var nota = document.createElement("p"); nota.className = "tienda-nota";
      nota.textContent = "Transferí el monto exacto y mandanos el comprobante con el número de pedido. Cuando lo confirmamos, tu pedido entra en producción.";
      caja.appendChild(nota);
      if (c.whatsapp) {
        var w = document.createElement("a");
        w.className = "btn-whatsapp"; w.target = "_blank"; w.rel = "noopener";
        w.href = "https://wa.me/" + c.whatsapp + "?text=" + encodeURIComponent(
          "Hola, pagué por transferencia el pedido " + d.pedido + " (" + formatear(d.precio) + "). Te mando el comprobante.");
        w.textContent = "Mandar el comprobante por WhatsApp";
        w.addEventListener("click", function () {
          // te avisa al celular que este pedido se paga por transferencia (una sola vez por pedido)
          fetch(API + "/pedidos/" + encodeURIComponent(d.pedido) + "/transferencia", { method: "POST", keepalive: true })
            .then(function () { var m = el.querySelector("p:last-child"); if (m) m.textContent = TEXTO_TRANSFERENCIA; })
            .catch(function () {});
        });
        caja.appendChild(w);
      }
    }).catch(function () { /* sin catálogo: queda solo el reintento */ });

    el.parentNode.insertBefore(caja, el.nextSibling);
    return caja;
  }

  function prepararGracias(el) {
    var q = new URLSearchParams(location.search);
    var pedido = q.get("pedido");
    if (!pedido) { el.textContent = "No encontramos el número de pedido."; return; }
    var fallido = pagoFallido(q), aprobadoEnMP = pagoAprobadoEnMP(q);
    if (fallido) el.textContent = TEXTO_FALLIDO;
    var inicio = Date.now();
    var intentos = 0;
    var purchaseTrackeado = false;
    (function consultar() {
      estado(pedido).then(function (d) {
        el.dataset.estado = d.estado;
        el.innerHTML = "";
        var t = document.createElement("p"); t.textContent = "Pedido " + d.pedido + " · " + d.producto;
        var m = document.createElement("p");
        var texto = TEXTOS[d.estado] || d.estado;
        if (d.estado === "pendiente_pago" && d.transferencia_avisada) texto = TEXTO_TRANSFERENCIA;
        else if (d.estado === "pendiente_pago" && fallido) texto = TEXTO_FALLIDO;
        else if (d.estado === "pagado" && TEXTOS_CANJE[d.pago_medio]) texto = TEXTOS_CANJE[d.pago_medio];
        m.textContent = texto;
        el.appendChild(t); el.appendChild(m);
        // Si no se pagó, las otras formas: enseguida si Mercado Pago avisó que falló o se canceló; si no, a los 15 s
        // (con el pago aprobado en MP, solo si después de 2 minutos el servidor todavía no lo confirmó)
        var caja = document.querySelector("[data-tienda-alternativa]");
        if (d.estado !== "pendiente_pago") { if (caja) caja.remove(); }
        else if (fallido || d.transferencia_avisada || (!aprobadoEnMP && Date.now() - inicio > 15000) || intentos >= 40) {
          alternativaDePago(el, d);
        }
        // Compra: solo con el pago confirmado por el servidor y una sola vez por pedido (recargar no la repite)
        var cobrado = ["pagado", "vista_previa", "cambio", "aprobado", "entregado"].indexOf(d.estado) !== -1;
        // los regalos y las compras de Mercado Libre no son ventas de la web: no se reportan al píxel
        if (cobrado && !purchaseTrackeado && typeof d.precio === "number" && d.precio > 0 && !TEXTOS_CANJE[d.pago_medio]) {
          purchaseTrackeado = true;
          var clave = "tutienditaia_compra_" + d.pedido, yaReportada = false;
          try { yaReportada = localStorage.getItem(clave) === "1"; localStorage.setItem(clave, "1"); } catch (e) { /* privado */ }
          if (!yaReportada) pixelTrack('Purchase', { value: d.precio, currency: "ARS" }, "compra-" + d.pedido);
        }
        if (d.estado === "pendiente_pago" && intentos++ < 40) setTimeout(consultar, 3000);
      }).catch(function () { el.textContent = "No pudimos consultar el pedido " + pedido + ". Escribinos por WhatsApp."; });
    })();
  }

  // ---- Link de un solo uso (?canje=…): el mismo formulario, con el producto fijo y sin pago ----
  // Lo usan la foto de regalo (mail a los 30 min sin pago) y las compras hechas en Mercado Libre.
  function avisoCanje(form, texto, error) {
    var caja = document.createElement("div");
    caja.setAttribute("role", error ? "alert" : "status");
    caja.style.cssText = "margin:0 0 20px;padding:14px 16px;border-radius:8px;font-weight:700;font-size:17px;line-height:1.4;" +
      (error ? "background:#FFEBEE;border:2px solid #C62828;color:#7F1D1D;" : "background:#E8F5E9;border:2px solid #2E7D32;color:#1B4D1F;");
    caja.textContent = texto;
    form.insertBefore(caja, form.firstChild);
    return caja;
  }

  function prepararCanje(token) {
    var form = document.querySelector("form[data-tienda-form]");
    if (!form) return;
    pedirJSON("GET", "/canje/" + encodeURIComponent(token)).then(function (c) {
      var tarjeta = document.querySelector('[data-prod-id="' + c.producto + '"]');
      if (c.estado !== "valido") {
        avisoCanje(form, c.estado === "usado" ? "Este link ya se usó. Si tenés alguna duda, escribinos por WhatsApp."
                                              : "Este link venció. Escribinos por WhatsApp y lo resolvemos.", true);
        form.scrollIntoView({ block: "start" });
        return;
      }
      // el producto del link, como si se tocara su tarjeta; las otras opciones no se muestran
      if (tarjeta) tarjeta.click();
      document.querySelectorAll("[data-prod-id]").forEach(function (t) { if (t !== tarjeta) t.style.display = "none"; });
      var campo = form.querySelector('[name="producto"]');
      if (campo) campo.value = c.producto;
      var oculto = document.createElement("input");
      oculto.type = "hidden"; oculto.name = "canje"; oculto.value = token;
      form.appendChild(oculto);
      form.dataset.canje = c.tipo;
      var regalo = c.tipo === "regalo";
      document.querySelectorAll('[id$="-producto-resumen"]').forEach(function (r) {
        r.textContent = c.nombre + (regalo ? " — de regalo" : " — ya pagado en Mercado Libre");
      });
      form.querySelectorAll('.boton-mp, [type="submit"]').forEach(function (b) {
        b.textContent = regalo ? "Pedir mi foto de regalo" : "Enviar mi pedido";
      });
      form.querySelectorAll(".texto-mp").forEach(function (t) {
        t.textContent = regalo ? "Es un regalo: no se cobra nada." : "Ya lo pagaste en Mercado Libre: no se cobra de nuevo.";
      });
      avisoCanje(form, regalo
        ? "🎁 Tu foto de regalo: completá el formulario y mandanos la foto. No se cobra nada."
        : "Ya pagaste en Mercado Libre: completá el formulario y mandanos los datos. No se cobra de nuevo.");
      form.scrollIntoView({ block: "start" });
    }).catch(function () {
      avisoCanje(form, "Este link no existe. Escribinos por WhatsApp y lo resolvemos.", true);
    });
  }

  window.Tienda = { API: API, catalogo: catalogo, estado: estado, enviar: enviar,
                    precio: precio, formatear: formatear, pintarPrecios: pintarPrecios };
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-tienda-form]").forEach(prepararFormulario);
    document.querySelectorAll("[data-tienda-gracias]").forEach(prepararGracias);
    var canje = new URLSearchParams(location.search).get("canje");
    if (canje) prepararCanje(canje);
  });
})();
