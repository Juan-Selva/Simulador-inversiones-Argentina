"""Formas de comprar dólares en Argentina y lo que cuesta cada una.

Es un módulo de dominio: no usa la red. Contiene las reglas impositivas y de
acceso de cada canal, tal como se relevaron en REGLAS_RELEVADAS, y las cuentas
para pasar de un precio de lista a lo que realmente se paga por dólar.

Las alícuotas y restricciones son normas que cambian: si alguna deja de
valer, se corrige acá y en ningún otro lado.
"""

from __future__ import annotations

from dataclasses import dataclass

REGLAS_RELEVADAS = "13/10/2026"


@dataclass(frozen=True)
class Cargo:
    """Un impuesto o costo que se suma al precio de lista, como proporción del monto en pesos."""

    nombre: str
    tasa: float  # 0.30 = 30 %


@dataclass(frozen=True)
class Canal:
    clave: str
    nombre: str
    casa: str  # clave de la cotización en la fuente de datos (DolarAPI)
    cargos: tuple[Cargo, ...] = ()
    notas: tuple[str, ...] = ()
    para_ahorrar: bool = True  # False si no sirve para tener dólares (solo para pagar)
    con_broker: bool = False  # True si el canal pasa por un broker que cobra comisión


PERCEPCION_TARJETA = Cargo("Percepción 30 % a cuenta de Ganancias / Bienes Personales (RG 5617)", 0.30)

_NOTA_90_DIAS = (
    "Si comprás dólar oficial, durante los 90 días siguientes no podés operar MEP ni CCL "
    "(Com. A 8336 del BCRA, mantenida por la A 8361)."
)
_NOTA_FONDEO = (
    "Fondear al broker desde una cuenta bancaria puede pagar el impuesto a los débitos y créditos "
    "(alícuota general: 0,6 %); no está incluido en el precio."
)

CANALES: tuple[Canal, ...] = (
    Canal(
        clave="oficial",
        nombre="Dólar oficial (banco)",
        casa="oficial",
        notas=(
            "Se compra por home banking o app del banco, sin cupo mensual desde abril de 2025.",
            "La percepción del 30 % se eliminó para la compra de dólar ahorro (RG 5672 de ARCA): no hay impuestos.",
            _NOTA_90_DIAS,
            "El banco no suele cobrar comisión explícita: su ganancia está en la diferencia entre compra y venta.",
        ),
    ),
    Canal(
        clave="mep",
        nombre="Dólar MEP (bolsa)",
        casa="bolsa",
        con_broker=True,
        notas=(
            "Se compra con un broker (cuenta comitente) usando un bono que cotiza en pesos y en dólares. Sin cupo.",
            "Los dólares se acreditan entre el mismo día y 2 días hábiles, según el broker.",
            "Los brokers cobran una comisión (referencia: entre 0 % y 0,5 %). Podés indicarla en la comisión del broker.",
            _NOTA_FONDEO,
            _NOTA_90_DIAS,
        ),
    ),
    Canal(
        clave="ccl",
        nombre="Dólar CCL",
        casa="contadoconliqui",
        con_broker=True,
        notas=(
            "Contado con liquidación. Como el MEP, pero los dólares quedan en una cuenta en el exterior. Cotiza por encima del MEP.",
            "Sin cupo. Se acredita en 24 a 48 horas, según el broker.",
            _NOTA_FONDEO,
            _NOTA_90_DIAS,
        ),
    ),
    Canal(
        clave="blue",
        nombre="Dólar blue (efectivo)",
        casa="blue",
        notas=(
            "Mercado informal: se opera solo en efectivo.",
            "No paga impuestos en la operación, pero tampoco da comprobante ni respaldo legal.",
            "Las ofertas de blue por transferencia o con tarjeta suelen ser estafas.",
        ),
    ),
    Canal(
        clave="cripto",
        nombre="Dólar cripto (USDT)",
        casa="cripto",
        notas=(
            "Se compra USDT, un dólar digital, en un exchange. El precio de referencia ya incluye "
            "la diferencia entre compra y venta del exchange.",
            "Sin cupo. Según lo relevado, no le aplica la restricción de 90 días.",
            "Una transferencia por la red TRON cuesta menos de USD 1.",
        ),
    ),
    Canal(
        clave="tarjeta",
        nombre="Dólar tarjeta (exterior)",
        casa="oficial",
        cargos=(PERCEPCION_TARJETA,),
        para_ahorrar=False,
        notas=(
            "No sirve para ahorrar: es lo que cuesta pagar en dólares con tarjeta "
            "(compras en el exterior, servicios digitales, turismo).",
            "La percepción es un adelanto de impuestos: se recupera en la declaración jurada de Ganancias o "
            "Bienes Personales (o por SiRADIG), pero llega tarde y pierde valor con la inflación.",
            "Se evita pagando el resumen con dólares comprados antes al oficial.",
            "En enero de 2026 circularon notas que anunciaban su eliminación; fuentes posteriores y la "
            "cotización de referencia indican que sigue vigente. Confirmalo con tu banco.",
        ),
    ),
)


def cargos_del_canal(canal: Canal, comision_broker: float = 0.0) -> tuple[Cargo, ...]:
    """Cargos del canal más la comisión del broker (en proporción: 0.005 = 0,5 %) si corresponde."""
    if canal.con_broker and comision_broker > 0:
        return canal.cargos + (Cargo("Comisión del broker", comision_broker),)
    return canal.cargos


def precio_efectivo(precio: float, cargos: tuple[Cargo, ...] = ()) -> float:
    """Pesos que se pagan por cada dólar: el precio de lista más los cargos sobre el monto en pesos."""
    if precio <= 0:
        raise ValueError("El precio debe ser mayor que cero")
    return precio * (1 + sum(cargo.tasa for cargo in cargos))


def dolares_obtenidos(pesos: float, precio_por_dolar: float) -> float:
    """Dólares que se consiguen con `pesos` a `precio_por_dolar` pesos por dólar (cargos ya incluidos)."""
    if pesos <= 0:
        raise ValueError("Los pesos deben ser mayores que cero")
    if precio_por_dolar <= 0:
        raise ValueError("El precio debe ser mayor que cero")
    return pesos / precio_por_dolar
