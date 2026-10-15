import json

from simulador import instantanea


def _texto(foto):
    return "\n".join(foto.texto)


def test_comparacion_guarda_cotizaciones_uva_y_porcentajes_del_momento(servicio_con_datos):
    c = servicio_con_datos.comparar_estrategias(1_000_000, 35, 6)
    foto = instantanea.de_comparacion(1_000_000, 35, 6, c)

    assert foto.tipo == instantanea.COMPARACION
    assert foto.parametros == {"capital": 1_000_000, "tna": 35, "meses": 6}
    texto = _texto(foto)
    assert "$ 1.010,00" in texto and "$ 1.590,00" in texto  # blue a la compra y a la venta
    assert "UVA (cierre de mes): 1.000,00" in texto and "1.194,05" in texto
    assert "Inflación acumulada del período: 19,41 %." in texto
    assert "Plazo fijo UVA: nominal 19,41 %" in texto
    assert "Mejor en términos reales: Dólar blue." in texto
    assert "Dólar blue al simular: compra" in texto
    assert foto.datos["mejor"] == "Dólar blue"
    assert foto.datos["precio_compra"] == 1010.0


def test_comparacion_sin_uva_no_inventa_la_linea(servicio_con_datos):
    c = servicio_con_datos.comparar_estrategias(1_000_000, 35, 2)
    texto = _texto(instantanea.de_comparacion(1_000_000, 35, 2, c))
    assert "UVA (cierre" not in texto
    assert "90 días" in texto


def test_plazo_fijo_con_inflacion_real_y_con_inflacion_fija(servicio_con_datos):
    sim = servicio_con_datos.calcular_plazo_fijo(1_000_000, 35, 6, None, True)
    real = instantanea.de_plazo_fijo(1_000_000, 35, 6, None, True, sim)
    assert "Inflación real del INDEC: febrero de 2026 a julio de 2026." in _texto(real)
    assert "renovando cada 30 días" in _texto(real)
    assert real.parametros["inflacion_mensual"] is None

    sim = servicio_con_datos.calcular_plazo_fijo(1_000_000, 35, 6, 3.5, False)
    fija = instantanea.de_plazo_fijo(1_000_000, 35, 6, 3.5, False, sim)
    assert "Inflación mensual constante ingresada a mano: 3,50 %." in _texto(fija)
    assert "sin renovar" in _texto(fija)


def test_compra_de_dolares_guarda_cada_opcion_con_sus_cargos(servicio_con_datos):
    c = servicio_con_datos.comprar_dolares(1_000_000, 0.3)
    foto = instantanea.de_compra_dolares(0.3, c)
    texto = _texto(foto)
    assert foto.parametros == {"pesos": 1_000_000, "comision_broker": 0.3}
    assert "comisión del broker 0,30 %" in texto
    assert "Se suma:" in texto
    assert "Normas e impuestos relevados al 13/10/2026" in texto
    assert foto.datos["mas_barata"] == c.mas_barata.clave
    assert len(foto.datos["opciones"]) == len(c.opciones)


def test_contado_o_cuotas_con_y_sin_descuento(servicio_con_datos):
    c = servicio_con_datos.comparar_contado_y_cuotas(120_000, 6, 35, 10, 2.0)
    foto = instantanea.de_contado_cuotas(120_000, 6, 35, 10, 2.0, c)
    texto = _texto(foto)
    assert "Cuotas: 6 de $ 20.000,00" in texto
    assert "(10,00 % de descuento)" in texto
    assert "Resultado con tu plazo fijo:" in texto
    assert foto.parametros["descuento"] == 10

    c = servicio_con_datos.comparar_contado_y_cuotas(120_000, 6, 35, 0, 2.0)
    assert "sin descuento" in _texto(instantanea.de_contado_cuotas(120_000, 6, 35, 0, 2.0, c))


def test_los_datos_crudos_entran_en_json(servicio_con_datos):
    c = servicio_con_datos.comparar_estrategias(1_000_000, 35, 6)
    foto = instantanea.de_comparacion(1_000_000, 35, 6, c)
    assert json.loads(json.dumps(foto.datos)) == foto.datos  # fechas y tuplas ya convertidas
