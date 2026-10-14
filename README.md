# Simulador de inversiones

Simulador en Python que compara estrategias de inversión (plazo fijo y dólar blue) contra la inflación argentina, para ver el rendimiento real y no solo el nominal. Usa datos reales: IPC del INDEC (datos.gob.ar) y dólar blue (ArgentinaDatos).

## Estructura

```
src/simulador/
  dominio/     funciones puras: estrategias, ajuste por inflación y reglas de compra de dólares (sin red ni DB)
  ingesta/     descarga y caché de series (IPC de datos.gob.ar, dólares de ArgentinaDatos y DolarAPI)
  servicio.py  casos de uso: combinan ingesta y dominio; los usan la CLI y las interfaces
  formato.py   formato de pesos, porcentajes y meses en español
  cli.py       interfaz de línea de comandos (Typer)
  interfaz/    interfaz gráfica (CustomTkinter): app.py dibuja, vistas.py y entradas.py son lógica testeable
tests/         tests con pytest, sin depender de la red
```

La lógica vive en el dominio y en el servicio, así que la CLI y cualquier interfaz gráfica son capas finas que comparten el mismo código.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -e ".[gui,dev]"
```

Si solo querés la línea de comandos alcanza con `pip install -e .`; el extra `gui` agrega CustomTkinter.

## Uso

```bash
# Inflación mensual real de los últimos 12 meses
simulador inflacion --meses 12

# Inflación del mes pasado (si el INDEC todavía no la publicó, muestra el último mes disponible)
simulador inflacion-mes

# Inflación de un mes puntual, con la variación interanual
simulador inflacion-mes --anio 2025 --mes 3

# Valor del dólar blue de hoy
simulador dolar

# Plazo fijo contra la inflación real de los últimos 6 meses
simulador plazo-fijo --capital 1000000 --tna 35 --meses 6

# Plazo fijo contra una inflación mensual constante
simulador plazo-fijo --capital 1000000 --tna 35 --meses 6 --inflacion-mensual 3.5

# Plazo fijo, dólar blue y plazo fijo UVA (ajustado por inflación, desde 3 meses) en los últimos 6 meses;
# muestra también el blue de hoy
simulador comparar --capital 1000000 --tna 35 --meses 6

# Formas de comprar dólares hoy, con impuestos y cuántos dólares conseguís
simulador comprar-dolares --pesos 1000000

# Lo mismo, sumando la comisión de tu broker para MEP y CCL (en porcentaje)
simulador comprar-dolares --pesos 1000000 --comision-broker 0.3

# ¿Contado o cuotas sin interés? (el descuento es opcional)
simulador contado-o-cuotas --precio 120000 --cuotas 6 --tna 35 --descuento 10

# Lo mismo, con una inflación mensual propia en lugar de la del INDEC
simulador contado-o-cuotas --precio 120000 --cuotas 6 --tna 35 --descuento 10 --inflacion-mensual 3
```

## Interfaz gráfica

```bash
simulador-gui
# o, sin reinstalar el proyecto:
python -m simulador.interfaz.app
```

Tiene cinco pestañas (Comparar, Plazo fijo, Comprar dólares, Contado o cuotas, Inflación) y muestra arriba el dólar blue de hoy, con un botón para actualizarlo. Las consultas a las APIs corren en segundo plano, así que la ventana no se congela. Los números se pueden escribir como `1.000.000` o `35,5`.

Arriba a la izquierda hay un selector de tema con dos íconos, sol (modo claro) y luna (modo oscuro). La primera vez la ventana sigue el modo de tu sistema operativo; después se recuerda tu elección entre sesiones en `~/.config/simulador-inversiones/preferencias.json`.

## Tests

```bash
pytest
```

## Cómo se calcula el dólar

Las simulaciones usan el historial diario del dólar blue de ArgentinaDatos. Se compra al precio de venta del mercado en el último día disponible del mes anterior al primer mes simulado y se vende al precio de compra del mercado en el último día disponible del último mes, así que la diferencia entre ambos precios (el spread) queda incluida. No se modelan comisiones ni impuestos, y los resultados son históricos: no predicen rendimientos futuros.

El valor que se muestra como "dólar blue de hoy" viene de DolarAPI, que informa cuándo se actualizó por última vez; ese horario se muestra junto al precio. Ambas son APIs comunitarias, no oficiales, y las que probé (ArgentinaDatos, DolarAPI y Bluelytics) actualizan con retraso: pueden no reflejar un movimiento del mercado ocurrido hace pocas horas. Si DolarAPI falla, se usa el último registro del historial y se avisa que no informa la hora.

El INDEC publica la inflación con casi un mes de retraso, por eso las simulaciones llegan hasta el último mes publicado y no hasta hoy.

## Comprar dólares

La pestaña (y el comando `comprar-dolares`) compara, para un monto en pesos, las formas de comprar dólares en Argentina: cotización, impuestos y cargos, dólares que conseguís y cuánto más cara es cada una frente a la más barata. Cada opción también explica sus condiciones (cupos, plazos, restricciones).

| Opción | Cotización usada | Impuestos y cargos |
| --- | --- | --- |
| Dólar oficial (banco) | oficial, venta | ninguno (la percepción del 30 % se eliminó en abril de 2025, RG 5672) |
| Dólar MEP | bolsa, venta | comisión del broker (la ingresás vos) |
| Dólar CCL | contado con liquidación, venta | comisión del broker (la ingresás vos) |
| Dólar blue | blue, venta | ninguno, pero es un mercado informal |
| Dólar cripto (USDT) | cripto, venta | ninguno; el margen del exchange ya está en el precio |
| Dólar tarjeta | oficial, venta | percepción del 30 % a cuenta de Ganancias / Bienes Personales (RG 5617) |

El dólar tarjeta se muestra aparte de la comparación de ahorro: sirve para saber cuánto cuesta pagar en dólares con tarjeta, no para tener dólares.

Qué no está en el precio: el impuesto a los débitos y créditos (alícuota general del 0,6 %) que puede aplicar al fondear un broker desde una cuenta bancaria, y las comisiones de cada banco o broker. Además, quien compra dólar oficial queda 90 días sin poder operar MEP ni CCL (Comunicación "A" 8336 del BCRA, mantenida por la "A" 8361).

Las reglas impositivas están en `dominio/compra_dolares.py`, con la fecha en que se relevaron (`REGLAS_RELEVADAS`). Son normas que cambian: conviene verificarlas con tu banco, broker o contador antes de operar. Las cotizaciones vienen de DolarAPI y cada una muestra cuándo se actualizó. Sobre el dólar tarjeta hubo información cruzada en enero de 2026 (algunas notas anunciaron su eliminación); las fuentes posteriores y la propia cotización de referencia indican que el 30 % sigue vigente.

Fuentes de las normas: [ARCA, RG 5672 vía Ámbito](https://www.ambito.com/economia/dolar-ahorro-arca-oficializo-el-fin-la-percepcion-del-30-n6134275), [El Cronista sobre el dólar tarjeta](https://www.cronista.com/economia-politica/por-que-no-se-elimino-el-dolar-tarjeta-cuanto-recaudo-arca-en-lo-que-va-de-2026/), [Infobae sobre la Com. A 8336](https://www.infobae.com/economia/2025/09/29/nuevas-trabas-del-bcra-como-se-puede-comprar-dolar-oficial-y-mep-a-partir-de-hoy/), [AFCOMEX sobre la Com. A 8361](https://afcomex.com.ar/resumen-tecnico-comunicacion-a-8361-bcra/), [Rivet](https://rivet.fi/blog/como-comprar-dolares-argentina) y [dolar.net.ar](https://www.dolar.net.ar/2026/05/todo-lo-que-tenes-que-saber-sobre-la-compra.html).

## Contado o cuotas

Calcula si conviene pagar un producto de contado (con un descuento opcional) o en cuotas sin interés. Las cuotas con interés no se contemplan.

La idea: pagar en cuotas te deja la plata en el bolsillo un tiempo más, y eso vale algo si tu plata rinde. Entonces se calcula cuánto valen hoy las cuotas, descontadas a lo que rinde tu plata (valor presente), y se compara con el precio de contado. Si las cuotas valen menos que el contado, convienen las cuotas; si valen más, conviene el contado.

- **Plazo fijo:** es la comparación principal. Usa la TNA que ingreses, con la misma cuenta que el resto del simulador (TNA × 30/365 por mes).
- **Inflación:** segunda lectura, para plata que solo mantiene su valor. Usa la inflación mensual que ingreses o, si la dejás vacía, la del último mes publicado por el INDEC (si no se puede descargar, se omite).
- **Crédito implícito:** con descuento, también muestra a qué tasa mensual (y TNA) equivale renunciar al descuento. Si tu plata rinde más que eso, convienen las cuotas.
- **Sin descuento**, las cuotas sin interés siempre convienen: pagás lo mismo, pero más tarde.

Supuestos: la primera cuota se paga a los 30 días y las demás una por mes, todas de igual monto, y no se consideran comisiones ni intereses por pagar tarde el resumen de la tarjeta. La inflación del último mes es solo una referencia: la futura puede ser distinta.

## Estado y próximos pasos

- [x] Plazo fijo (simple y renovado) con comparación contra inflación
- [x] Inflación real del INDEC (IPC nacional) con caché de 24 h, por mes e interanual
- [x] Estrategia dólar blue (compra y venta reales) y comando `comparar` contra plazo fijo
- [x] Dólar blue de hoy en los resultados que involucran dólares
- [x] Interfaz gráfica (CustomTkinter) con modo claro y oscuro
- [x] Comprar dólares: oficial, MEP, CCL, blue, cripto y tarjeta, con impuestos
- [x] Contado o cuotas sin interés, con descuento opcional
- [x] Estrategia UVA / CER (plazo fijo UVA dentro de `comparar`)
- [ ] Persistencia en SQLite
