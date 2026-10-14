"""Interfaz gráfica del simulador, hecha con CustomTkinter.

Es una capa fina sobre simulador.servicio, el mismo que usa la CLI. Las
consultas a las APIs corren en un hilo aparte para que la ventana no se
congele, y el resultado vuelve al hilo de la interfaz a través de una cola.
"""

from __future__ import annotations

import queue
import threading
from datetime import date
from typing import Callable, Iterable

try:
    import customtkinter as ctk
except ImportError as error:  # pragma: no cover
    raise SystemExit(
        'Falta customtkinter. Instalalo con: pip install -e ".[gui]"'
    ) from error

from simulador import servicio
from simulador.formato import MESES
from simulador.interfaz import vistas
from simulador.interfaz.entradas import parsear_entero, parsear_numero
from simulador.servicio import ErrorSimulador

# (modo claro, modo oscuro)
TONOS = {
    "positivo": ("#1a7f37", "#3fb950"),
    "negativo": ("#cf222e", "#ff7b72"),
    "suave": ("gray35", "gray65"),
}


def _tono(tono: str) -> dict:
    return {"text_color": TONOS[tono]} if tono in TONOS else {}


def _texto_de_error(error: Exception) -> str:
    if isinstance(error, ErrorSimulador):
        return str(error)
    return f"Ocurrió un error inesperado: {error}"


class Ejecutor:
    """Corre funciones lentas en un hilo y entrega el resultado en el hilo de la interfaz."""

    def __init__(self, ventana: ctk.CTk) -> None:
        self._ventana = ventana
        self._cola: queue.Queue = queue.Queue()
        self._ventana.after(100, self._revisar)

    def correr(
        self,
        funcion: Callable[[], object],
        al_terminar: Callable[[object], None],
        al_fallar: Callable[[Exception], None],
    ) -> None:
        def trabajo() -> None:
            try:
                resultado = funcion()
            except Exception as error:  # se muestra en pantalla, no se pierde
                self._cola.put((al_fallar, error))
            else:
                self._cola.put((al_terminar, resultado))

        threading.Thread(target=trabajo, daemon=True).start()

    def _revisar(self) -> None:
        try:
            while True:
                callback, valor = self._cola.get_nowait()
                callback(valor)
        except queue.Empty:
            pass
        self._ventana.after(100, self._revisar)


# --- piezas de dibujo ---------------------------------------------------------

def _campo(parent, columna: int, etiqueta: str, valor: str, ancho: int = 150, fila: int = 0):
    marco = ctk.CTkFrame(parent, fg_color="transparent")
    marco.grid(row=fila, column=columna, padx=(0, 14), pady=(0, 6), sticky="w")
    ctk.CTkLabel(marco, text=etiqueta, anchor="w").grid(row=0, column=0, sticky="w")
    entrada = ctk.CTkEntry(marco, width=ancho)
    entrada.insert(0, valor)
    entrada.grid(row=1, column=0, sticky="w")
    return entrada


def _limpiar(marco) -> None:
    for widget in marco.winfo_children():
        widget.destroy()


def _linea(marco, texto: str, negrita: bool = False, tono: str = "normal", tamanio: int | None = None) -> None:
    opciones = {}
    if negrita:
        opciones["weight"] = "bold"
    if tamanio:
        opciones["size"] = tamanio
    ctk.CTkLabel(
        marco,
        text=texto,
        wraplength=720,
        justify="left",
        anchor="w",
        font=ctk.CTkFont(**opciones) if opciones else None,
        **_tono(tono),
    ).pack(anchor="w", padx=8, pady=3)


def _mensaje(marco, texto: str, tono: str = "normal") -> None:
    _limpiar(marco)
    _linea(marco, texto, tono=tono)


def _seccion(marco):
    seccion = ctk.CTkFrame(marco, fg_color="transparent")
    seccion.pack(fill="x", anchor="w", pady=4)
    return seccion


def _clave_valor(marco, filas) -> None:
    seccion = _seccion(marco)
    for i, (etiqueta, celda) in enumerate(filas):
        ctk.CTkLabel(seccion, text=etiqueta, anchor="w").grid(
            row=i, column=0, padx=(8, 32), pady=2, sticky="w"
        )
        ctk.CTkLabel(
            seccion,
            text=celda.texto,
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
            **_tono(celda.tono),
        ).grid(row=i, column=1, pady=2, sticky="w")


def _tabla(marco, cabecera: list[str], filas) -> None:
    seccion = _seccion(marco)
    for j, titulo in enumerate(cabecera):
        ctk.CTkLabel(
            seccion, text=titulo, anchor="w", font=ctk.CTkFont(weight="bold"), **_tono("suave")
        ).grid(row=0, column=j, padx=(8, 28), pady=(2, 6), sticky="w")
    for i, fila in enumerate(filas, start=1):
        for j, celda in enumerate(fila):
            ctk.CTkLabel(seccion, text=celda.texto, anchor="w", **_tono(celda.tono)).grid(
                row=i, column=j, padx=(8, 28), pady=2, sticky="w"
            )


# --- ventana ------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Simulador de inversiones")
        self.geometry("940x740")
        self.minsize(820, 660)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._ejecutor = Ejecutor(self)
        self._construir_cabecera()

        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=1, column=0, padx=16, pady=(8, 16), sticky="nsew")
        for nombre in ("Comparar", "Plazo fijo", "Comprar dólares", "Inflación"):
            self._tabs.add(nombre)
        self._construir_tab_comparar()
        self._construir_tab_plazo_fijo()
        self._construir_tab_comprar()
        self._construir_tab_inflacion()
        self._tabs.set("Comparar")

        self._actualizar_blue()

    # -- utilidades comunes

    def _cargando(self, botones: Iterable, resultado) -> None:
        for boton in botones:
            boton.configure(state="disabled")
        _mensaje(resultado, "Consultando datos...", tono="suave")

    def _terminar(self, botones: Iterable) -> None:
        for boton in botones:
            boton.configure(state="normal")

    def _fallar(self, botones: Iterable, resultado, error: Exception) -> None:
        self._terminar(botones)
        _mensaje(resultado, _texto_de_error(error), tono="negativo")

    def _lanzar(self, botones, resultado, consulta, al_terminar) -> None:
        """Muestra 'consultando', corre la consulta en segundo plano y dibuja el resultado."""
        botones = tuple(botones)
        self._cargando(botones, resultado)

        def terminado(valor) -> None:
            self._terminar(botones)
            _limpiar(resultado)
            al_terminar(valor)

        self._ejecutor.correr(consulta, terminado, lambda e: self._fallar(botones, resultado, e))

    # -- cabecera con el dólar blue de hoy

    def _construir_cabecera(self) -> None:
        cabecera = ctk.CTkFrame(self, corner_radius=12)
        cabecera.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        cabecera.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cabecera, text="Simulador de inversiones", font=ctk.CTkFont(size=22, weight="bold"), anchor="w"
        ).grid(row=0, column=0, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkLabel(
            cabecera,
            text="Plazo fijo y dólar blue contra la inflación real del INDEC",
            anchor="w",
            **_tono("suave"),
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        blue = ctk.CTkFrame(cabecera, fg_color="transparent")
        blue.grid(row=0, column=1, rowspan=2, padx=16, pady=8, sticky="e")
        ctk.CTkLabel(blue, text="Dólar blue", font=ctk.CTkFont(weight="bold"), anchor="e").grid(
            row=0, column=0, sticky="e"
        )
        self._blue_valores = ctk.CTkLabel(blue, text="Cargando...", font=ctk.CTkFont(size=16), anchor="e")
        self._blue_valores.grid(row=1, column=0, sticky="e")
        self._blue_detalle = ctk.CTkLabel(blue, text="", anchor="e", **_tono("suave"))
        self._blue_detalle.grid(row=2, column=0, sticky="e")
        self._blue_boton = ctk.CTkButton(blue, text="Actualizar", width=90, command=self._actualizar_blue)
        self._blue_boton.grid(row=0, column=1, rowspan=3, padx=(14, 0))

    def _actualizar_blue(self) -> None:
        self._blue_boton.configure(state="disabled")
        self._blue_valores.configure(text="Cargando...")
        self._blue_detalle.configure(text="")

        def listo(dolar) -> None:
            valores, detalle = vistas.tarjeta_blue(dolar)
            self._blue_valores.configure(text=valores)
            self._blue_detalle.configure(text=detalle)
            self._blue_boton.configure(state="normal")

        def fallo(error: Exception) -> None:
            self._blue_valores.configure(text="No disponible")
            self._blue_detalle.configure(text=_texto_de_error(error)[:80])
            self._blue_boton.configure(state="normal")

        self._ejecutor.correr(servicio.dolar_hoy, listo, fallo)

    # -- pestaña Comparar

    def _construir_tab_comparar(self) -> None:
        tab = self._tabs.tab("Comparar")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            tab,
            text="Compará un plazo fijo contra comprar dólar blue en los últimos meses con inflación publicada.",
            wraplength=780,
            justify="left",
            anchor="w",
            **_tono("suave"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        formulario = ctk.CTkFrame(tab, fg_color="transparent")
        formulario.grid(row=1, column=0, sticky="w", pady=(0, 8))
        self._cmp_capital = _campo(formulario, 0, "Capital ($)", "1.000.000")
        self._cmp_tna = _campo(formulario, 1, "TNA del plazo fijo (%)", "35")
        self._cmp_meses = _campo(formulario, 2, "Meses", "6", ancho=80)
        self._cmp_boton = ctk.CTkButton(formulario, text="Comparar", command=self._comparar)
        self._cmp_boton.grid(row=0, column=3, pady=(0, 6), sticky="s")

        self._cmp_resultado = ctk.CTkScrollableFrame(tab)
        self._cmp_resultado.grid(row=2, column=0, sticky="nsew")

    def _comparar(self) -> None:
        try:
            capital = parsear_numero(self._cmp_capital.get())
            tna = parsear_numero(self._cmp_tna.get())
            meses = parsear_entero(self._cmp_meses.get())
        except ValueError as error:
            _mensaje(self._cmp_resultado, str(error), tono="negativo")
            return
        self._lanzar(
            [self._cmp_boton],
            self._cmp_resultado,
            lambda: servicio.comparar_estrategias(capital, tna, meses),
            self._mostrar_comparacion,
        )

    def _mostrar_comparacion(self, c) -> None:
        marco = self._cmp_resultado
        for linea in vistas.resumen_comparacion(c):
            _linea(marco, linea)
        _tabla(marco, vistas.CABECERA_COMPARACION, vistas.filas_comparacion(c))
        _linea(marco, vistas.veredicto(c), negrita=True, tamanio=16)
        valores, detalle = vistas.tarjeta_blue(c.blue_hoy)
        _linea(marco, f"Dólar blue: {valores} ({detalle.lower()})")
        aviso = vistas.aviso_blue(c.blue_hoy)
        if aviso:
            _linea(marco, aviso, tono="suave")
        _linea(marco, "Resultado histórico: no predice rendimientos futuros.", tono="suave")

    # -- pestaña Plazo fijo

    def _construir_tab_plazo_fijo(self) -> None:
        tab = self._tabs.tab("Plazo fijo")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        formulario = ctk.CTkFrame(tab, fg_color="transparent")
        formulario.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._pf_capital = _campo(formulario, 0, "Capital ($)", "1.000.000")
        self._pf_tna = _campo(formulario, 1, "TNA (%)", "35", ancho=100)
        self._pf_meses = _campo(formulario, 2, "Meses", "6", ancho=80)

        modo = ctk.CTkFrame(formulario, fg_color="transparent")
        modo.grid(row=1, column=0, padx=(0, 14), sticky="w")
        ctk.CTkLabel(modo, text="Inflación", anchor="w").grid(row=0, column=0, sticky="w")
        self._pf_modo = ctk.CTkOptionMenu(
            modo, values=["Real del INDEC", "Mensual fija"], command=self._cambiar_modo_inflacion, width=150
        )
        self._pf_modo.grid(row=1, column=0, sticky="w")

        self._pf_inflacion = _campo(formulario, 1, "Inflación mensual (%)", "3,5", ancho=100, fila=1)
        self._pf_inflacion.configure(state="disabled")

        self._pf_renovar = ctk.CTkCheckBox(formulario, text="Renovar cada 30 días")
        self._pf_renovar.select()
        self._pf_renovar.grid(row=1, column=2, padx=(0, 14), sticky="w")

        self._pf_boton = ctk.CTkButton(formulario, text="Calcular", command=self._calcular_plazo_fijo)
        self._pf_boton.grid(row=1, column=3, sticky="w")

        self._pf_resultado = ctk.CTkScrollableFrame(tab)
        self._pf_resultado.grid(row=1, column=0, sticky="nsew")

    def _cambiar_modo_inflacion(self, modo: str) -> None:
        self._pf_inflacion.configure(state="normal" if modo == "Mensual fija" else "disabled")

    def _calcular_plazo_fijo(self) -> None:
        try:
            capital = parsear_numero(self._pf_capital.get())
            tna = parsear_numero(self._pf_tna.get())
            meses = parsear_entero(self._pf_meses.get())
            inflacion = (
                parsear_numero(self._pf_inflacion.get()) if self._pf_modo.get() == "Mensual fija" else None
            )
        except ValueError as error:
            _mensaje(self._pf_resultado, str(error), tono="negativo")
            return
        renovar = bool(self._pf_renovar.get())
        self._lanzar(
            [self._pf_boton],
            self._pf_resultado,
            lambda: servicio.calcular_plazo_fijo(capital, tna, meses, inflacion, renovar),
            self._mostrar_plazo_fijo,
        )

    def _mostrar_plazo_fijo(self, sim) -> None:
        marco = self._pf_resultado
        _linea(marco, vistas.periodo_plazo_fijo(sim), tono="suave")
        _clave_valor(marco, vistas.filas_plazo_fijo(sim))

    # -- pestaña Comprar dólares

    def _construir_tab_comprar(self) -> None:
        tab = self._tabs.tab("Comprar dólares")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            tab,
            text="Las formas de comprar dólares en Argentina: cotización, impuestos y cuántos dólares conseguís.",
            wraplength=780,
            justify="left",
            anchor="w",
            **_tono("suave"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        formulario = ctk.CTkFrame(tab, fg_color="transparent")
        formulario.grid(row=1, column=0, sticky="w", pady=(0, 8))
        self._cd_pesos = _campo(formulario, 0, "Monto en pesos ($)", "1.000.000")
        self._cd_comision = _campo(formulario, 1, "Comisión del broker MEP/CCL (%)", "0", ancho=100)
        self._cd_boton = ctk.CTkButton(formulario, text="Comparar opciones", command=self._comprar_dolares)
        self._cd_boton.grid(row=0, column=2, pady=(0, 6), sticky="s")

        self._cd_resultado = ctk.CTkScrollableFrame(tab)
        self._cd_resultado.grid(row=2, column=0, sticky="nsew")

    def _comprar_dolares(self) -> None:
        try:
            pesos = parsear_numero(self._cd_pesos.get())
            comision = parsear_numero(self._cd_comision.get())
        except ValueError as error:
            _mensaje(self._cd_resultado, str(error), tono="negativo")
            return
        self._lanzar(
            [self._cd_boton],
            self._cd_resultado,
            lambda: servicio.comprar_dolares(pesos, comision),
            self._mostrar_compra,
        )

    def _mostrar_compra(self, c) -> None:
        marco = self._cd_resultado
        _linea(marco, vistas.resumen_compra(c), negrita=True, tamanio=15)
        _tabla(marco, vistas.CABECERA_COMPRA, vistas.filas_compra(c))
        for opcion in c.opciones:
            _linea(marco, opcion.nombre, negrita=True)
            for texto in vistas.detalle_compra(opcion):
                _linea(marco, f"•  {texto}", tono="suave")
        for texto in vistas.pie_compra(c):
            _linea(marco, texto, tono="suave")

    # -- pestaña Inflación

    def _construir_tab_inflacion(self) -> None:
        tab = self._tabs.tab("Inflación")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        contenido = ctk.CTkScrollableFrame(tab)
        contenido.grid(row=0, column=0, sticky="nsew")
        contenido.grid_columnconfigure(0, weight=1)

        # Un mes puntual
        ctk.CTkLabel(contenido, text="Inflación de un mes", font=ctk.CTkFont(size=16, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        form_mes = ctk.CTkFrame(contenido, fg_color="transparent")
        form_mes.grid(row=1, column=0, sticky="w")
        self._inf_anio = _campo(form_mes, 0, "Año", str(date.today().year), ancho=90)

        marco_mes = ctk.CTkFrame(form_mes, fg_color="transparent")
        marco_mes.grid(row=0, column=1, padx=(0, 14), pady=(0, 6), sticky="w")
        ctk.CTkLabel(marco_mes, text="Mes", anchor="w").grid(row=0, column=0, sticky="w")
        self._inf_mes = ctk.CTkOptionMenu(marco_mes, values=[m.capitalize() for m in MESES], width=140)
        self._inf_mes.grid(row=1, column=0, sticky="w")

        self._inf_boton_mes = ctk.CTkButton(form_mes, text="Consultar", command=self._consultar_mes)
        self._inf_boton_mes.grid(row=0, column=2, pady=(0, 6), sticky="s")

        self._inf_resultado_mes = ctk.CTkFrame(contenido, fg_color="transparent")
        self._inf_resultado_mes.grid(row=2, column=0, sticky="ew", pady=(0, 16))

        # Últimos meses
        ctk.CTkLabel(contenido, text="Últimos meses", font=ctk.CTkFont(size=16, weight="bold"), anchor="w").grid(
            row=3, column=0, sticky="w", pady=(0, 6)
        )
        form_meses = ctk.CTkFrame(contenido, fg_color="transparent")
        form_meses.grid(row=4, column=0, sticky="w")
        self._inf_cantidad = _campo(form_meses, 0, "Cantidad de meses", "12", ancho=90)
        self._inf_boton_meses = ctk.CTkButton(form_meses, text="Ver", command=self._ver_ultimos_meses)
        self._inf_boton_meses.grid(row=0, column=1, pady=(0, 6), sticky="s")

        self._inf_resultado_meses = ctk.CTkFrame(contenido, fg_color="transparent")
        self._inf_resultado_meses.grid(row=5, column=0, sticky="ew")

    def _consultar_mes(self) -> None:
        try:
            anio = parsear_entero(self._inf_anio.get())
        except ValueError as error:
            _mensaje(self._inf_resultado_mes, str(error), tono="negativo")
            return
        mes = MESES.index(self._inf_mes.get().lower()) + 1
        self._lanzar(
            [self._inf_boton_mes],
            self._inf_resultado_mes,
            lambda: servicio.consultar_inflacion_mes(anio, mes),
            self._mostrar_mes,
        )

    def _mostrar_mes(self, r) -> None:
        marco = self._inf_resultado_mes
        if r.aviso:
            _linea(marco, r.aviso, tono="suave")
        _clave_valor(marco, vistas.filas_inflacion_mes(r))

    def _ver_ultimos_meses(self) -> None:
        try:
            cantidad = parsear_entero(self._inf_cantidad.get())
        except ValueError as error:
            _mensaje(self._inf_resultado_meses, str(error), tono="negativo")
            return
        self._lanzar(
            [self._inf_boton_meses],
            self._inf_resultado_meses,
            lambda: servicio.inflacion_ultimos_meses(cantidad),
            self._mostrar_ultimos_meses,
        )

    def _mostrar_ultimos_meses(self, datos) -> None:
        _tabla(self._inf_resultado_meses, ["Mes", "Inflación"], vistas.filas_inflacion_meses(datos))


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
