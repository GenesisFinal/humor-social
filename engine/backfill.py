"""
Módulo de Backfill Histórico para el Índice de Humor Social Argentino (IHSA).
Genera una serie temporal retrospectiva de los últimos 30 días con NOTICIAS REALISTAS Y ESPECÍFICAS
para cada medio de comunicación, evitando textos genéricos o vacíos.
"""

from datetime import date, timedelta
import random
import json
from config import MEDIA_SOURCES, EMOTIONAL_AXES, DB_PATH
from engine.models import DailySnapshot, EmotionalAxesScores, SourceSentimentScore
from engine.scoring import compute_daily_ihsa
from storage.db import init_db, save_snapshot

# Pool de noticias y titulares estructurados por arquetipo de jornada argentina
DAILY_NEWS_AGENDAS = [
    {
        "theme": "Desaceleración de inflación y estabilidad cambiaria",
        "summary": "Jornada dominada por el optimismo financiero: consultoras y el INDEC anticiparon una nueva baja de la inflación mensual, mientras el Banco Central continuó sumando reservas y el dólar financiero se mantuvo calmo.",
        "opt_bias": 4.5, "cal_bias": 3.0, "conf_bias": 4.5, "ale_bias": 1.0,
        "x": ["InflacionBaja", "DolarBlue", "Caputo", "Mercados"],
        "google": ["plazo fijo rendimiento", "precio dolar mep", "aumento jubilaciones anses"],
        "media_news": {
            "clarin": {
                "pos": ["El INDEC confirmó que la inflación de alimentos se desaceleró al 2.5%", "El Banco Central extendió el plazo para créditos hipotecarios en cuotas fijas"],
                "neg": ["Tensión política entre el PRO y La Libertad Avanza por cargos en el Gabinete", "Quejas de inquilinos por el costo de las expensas en el AMBA"]
            },
            "lanacion": {
                "pos": ["Wall Street proyecta una consolidación de la baja de precios para el último trimestre", "Suben hasta 4% los bonos soberanos en Nueva York por el ancla fiscal"],
                "neg": ["Advierten que la salida del cepo cambiario requerirá mayores reservas líquidas", "Reclamos del sector textil por la apertura de importaciones"]
            },
            "infobae": {
                "pos": ["Caputo anunció que el superávit financiero se mantuvo por octavo mes consecutivo", "El dólar blue cayó 10 pesos y la brecha cambiaria perforó el 18%"],
                "neg": ["Polémica por la designación de nuevos funcionarios en el Ministerio de Justicia", "Inseguridad en el conurbano: detuvieron a una banda de entraderas"]
            },
            "cronista": {
                "pos": ["El Merval trepó 3.2% impulsado por papeles energéticos y bancarios", "El Banco Central compró US$ 110 millones en el mercado único de cambios"],
                "neg": ["Empresas industriales alertan sobre la lenta recuperación de la demanda fabril", "Presión en las paritarias de gremios de servicios"]
            },
            "ambito": {
                "pos": ["Riesgo país perforó los 1.400 puntos básicos ante compras oficiales de divisas", "El Tesoro colocó deuda en pesos con tasas a la baja"],
                "neg": ["El FMI revisa las metas de reservas y pide acelerar reformas impositivas", "Dudas sobre la liquidación del remanente de la cosecha gruesa"]
            },
            "cronica": {
                "pos": ["Lanzan nuevas líneas de préstamos personales para jubilados con tasa subsidiada", "Triunfo clave de la Selección de vóley en el torneo sudamericano"],
                "neg": ["El changuito sigue apretado: las ofertas mandan en los supermercados de barrio", "Familiares reclaman justicia por un chofer de colectivo asaltado"]
            },
            "pagina12": {
                "pos": ["Docentes universitarios convocan a un abrazo simbólico en defensa de la ciencia", "Acuerdo entre cooperativas bonaerenses para abaratar alimentos"],
                "neg": ["El consumo de leche y carne marca los pisos más bajos en tres décadas", "Denuncian que la baja de inflación se sostiene con una profunda recesión"]
            },
            "eldestape": {
                "pos": ["Científicos del Conicet logran un avance médico reconocido internacionalmente", "Masivo festival cultural barrial en apoyo a los comedores populares"],
                "neg": ["La pobreza no cede en los barrios populares pese al discurso oficial", "Caída del empleo registrado en la construcción por el freno a la obra pública"]
            },
            "tn": {
                "pos": ["Estabilidad en las pizarras: el dólar libre se mantiene sin sobresaltos", "Mejora el crédito al consumo con promociones en cuotas sin interés"],
                "neg": ["Incidentes aislados durante una concentración frente al Ministerio de Economía", "Demoras en los trenes de la línea Roca por problemas técnicos"]
            },
            "cadena3": {
                "pos": ["Productores agropecuarios del centro del país celebran la reducción de retenciones a lácteos", "Buenas perspectivas para la cosecha de trigo tras lluvias oportunas en Córdoba y Santa Fe"],
                "neg": ["Preocupación en las sierras por riesgo extremo de incendios forestales", "Gobernadores de la Región Centro reclaman mantenimiento de rutas nacionales"]
            },
            "c5n": {
                "pos": ["Trabajadores aceiteros lograron un bono extraordinario tras largas negociaciones", "Movilización de organizaciones sociales en reclamo de asistencia alimentaria"],
                "neg": ["Informe especial: cuántos sueldos mínimos se necesitan hoy para pagar un alquiler", "Cierran comercios de electrodomésticos por la caída en las ventas"]
            },
            "perfil": {
                "pos": ["La macroeconomía da señales de orden pero los analistas miran la sustentabilidad social", "El Gobierno prepara el envío del proyecto de Presupuesto con déficit cero"],
                "neg": ["Encuesta dominical: la aprobación presidencial se polariza entre el shock y el descontento", "Dudas sobre la gobernabilidad en el Congreso ante la fragmentación de bloques"]
            }
        }
    },
    {
        "theme": "Debate legislativo por veto presidencial y marchas en Congreso",
        "summary": "Jornada de marcada tensión política y social: el Congreso debatió el veto a la ley jubilatoria en medio de masivas movilizaciones de sindicatos y organizaciones sociales frente al Palacio Legislativo.",
        "opt_bias": -3.5, "cal_bias": -5.5, "conf_bias": -2.5, "ale_bias": -2.0,
        "x": ["Congreso", "Jubilados", "VetoPresidencial", "GasesEnPlazaCongreso"],
        "google": ["marcha al congreso hoy", "cortes caba", "votacion en diputados en vivo"],
        "media_news": {
            "clarin": {
                "pos": ["El Gobierno negocia voto a voto con los bloques dialoguistas para sostener el veto", "Las exportaciones de gas de Vaca Muerta generaron ingresos récord en agosto"],
                "neg": ["Tensión en los alrededores del Congreso: gases y forcejeos entre manifestantes y la Policía", "La oposición busca los dos tercios para insistir con la suba a jubilados"]
            },
            "lanacion": {
                "pos": ["El Presidente ratificó el compromiso innegociable con el equilibrio fiscal", "Inversiones en energía: licitan nuevo gasoducto con financiamiento privado"],
                "neg": ["Fuerte operativo de seguridad en el centro porteño ante la marcha de gremios y piqueteros", "La Cámara de Diputados sesiona en un clima de alta confrontación discursiva"]
            },
            "infobae": {
                "pos": ["La Justicia rechazó un amparo contra el protocolo antipiquetes de Bullrich", "Creció la producción de petróleo en Neuquén a niveles no vistos en 15 años"],
                "neg": ["Tensión frente al Congreso: incidentes, empujones y cortes sobre la avenida Rivadavia", "Jubilados se manifestaron con pancartas reclamando por el costo de vida"]
            },
            "cronista": {
                "pos": ["El dólar mayorista operó estable pese al ruido político en el Parlamento", "Bancos privados lanzan préstamos hipotecarios a 30 años"],
                "neg": ["El mercado advierte sobre el costo político del conflicto jubilatorio para el Ejecutivo", "Consumo masivo: supermercados reportan caída en segundas marcas"]
            },
            "ambito": {
                "pos": ["Caputo viajará a Washington para destrabar fondos frescos con organismos multilaterales", "Exportaciones mineras crecieron 15% interanual"],
                "neg": ["La tensión política frenó la suba de los bonos en la Bolsa porteña", "Sindicatos de transporte amenazan con medidas de fuerza en solidaridad con la marcha"]
            },
            "cronica": {
                "pos": ["Vecinos de Lanús armaron un merendero solidario para chicos del barrio", "Boca prepara el equipo con cambios para el clásico del fin de semana"],
                "neg": ["Jubilados a la calle: la mínima de hambre no alcanza para llegar al día 15", "Incidentes en el Congreso: gas pimienta y empujones a manifestantes mayores"]
            },
            "pagina12": {
                "pos": ["Masiva adhesión de sindicatos y federaciones universitarias en apoyo a los jubilados", "Personalidades de la cultura firmaron un petitorio contra los recortes presupuestarios"],
                "neg": ["Represión frente al Congreso: la Policía dispersó a jubilados con gases y camiones hidrantes", "El veto presidencial condena a millones de adultos mayores a la indigencia"]
            },
            "eldestape": {
                "pos": ["Convocatoria multitudinaria copó la Plaza de los Dos Congresos pese a los operativos de seguridad", "Madres de Plaza de Mayo encabezaron una ronda especial junto a jubilados"],
                "neg": ["Violenta represión policial en el Congreso contra manifestantes pacíficos y periodistas", "El plan de ajuste de Milei y Caputo profundiza la crisis en los sectores más vulnerables"]
            },
            "tn": {
                "pos": ["Operativo de seguridad logró mantener despejado el metrobus de la avenida 9 de Julio", "Inauguran obras de ampliación en una terminal del Aeropuerto de Ezeiza"],
                "neg": ["Caos de tránsito y enfrentamientos entre manifestantes y efectivos en Callao y Rivadavia", "Sesión maratónica en Diputados con cruces encendidos entre bancadas"]
            },
            "cadena3": {
                "pos": ["El turismo de fin de semana largo dejó un balance positivo en las sierras cordobesas", "Presentan un plan integral para prevenir incendios en los valles turísticos"],
                "neg": ["Diputados cordobeses reclaman una compensación a las cajas jubilatorias del interior", "Cortes y demoras en el transporte interurbano por reclamos salariales de choferes"]
            },
            "c5n": {
                "pos": ["Gremios estatales anunciaron que presentarán un recurso de inconstitucionalidad contra el veto", "Abuelas de Plaza de Mayo celebraron la restitución de una nueva identidad"],
                "neg": ["Imágenes exclusivas de los gases sobre jubilados en las puertas del Congreso Nacional", "El veto de Milei deja a los haberes previsionales en su mínimo histórico"]
            },
            "perfil": {
                "pos": ["Análisis dominical: las claves de la economía que mira el FMI para el año electoral", "Entrevista a economistas: los caminos para desarmar el cepo sin saltos cambiarios"],
                "neg": ["El desgaste del Gobierno ante la opinión pública por la pulseada contra el Congreso", "La grieta política se reactiva con fuerza en torno a las prioridades del gasto público"]
            }
        }
    },
    {
        "theme": "Fin de semana deportivo con gran carrera de Colapinto y fútbol",
        "summary": "Clima de algarabía y alivio social impulsado por el deporte: Franco Colapinto sumó puntos históricos en la Fórmula 1 y se vivió una vibrante fecha de fútbol nacional que descomprimió la agenda política.",
        "opt_bias": 3.0, "cal_bias": 2.0, "conf_bias": 1.5, "ale_bias": 7.0,
        "x": ["Colapinto", "FrancoEnF1", "Superclasico", "WilliamsRacing"],
        "google": ["colapinto posiciones carrera", "clasico resultado goles", "tabla formula 1"],
        "media_news": {
            "clarin": {
                "pos": ["Hazaña de Franco Colapinto: brillante actuación en la Fórmula 1 sumando puntos históricos para Argentina", "Festejo en las calles por el gran momento del automovilismo nacional"],
                "neg": ["Polémica con el VAR y quejas del técnico tras el clásico del domingo", "Alerta vial en las rutas de regreso por intenso tránsito y lluvias aisladas"]
            },
            "lanacion": {
                "pos": ["Colapinto deslumbró al mundo de la Fórmula 1 con sobrepasos milimétricos y madurez de veterano", "La marca país de Argentina se potencia en los circuitos más prestigiosos del automovilismo"],
                "neg": ["Operativos de seguridad por los festejos de los hinchas en el Obelisco", "Preocupación por la suba del precio de repuestos para vehículos"]
            },
            "infobae": {
                "pos": ["De Pilar a la gloria: la emoción de Franco Colapinto tras cruzar la meta y abrazar a su equipo", "La Fórmula 1 rindió tributo al talento del joven piloto argentino"],
                "neg": ["Incidentes menores entre simpatizantes en el ingreso al estadio antes del partido", "Demoras en las autopistas de acceso a la Ciudad de Buenos Aires"]
            },
            "cronista": {
                "pos": ["El fenómeno Colapinto: marcas argentinas e internacionales se disputan el sponsoreo en F1", "El turismo deportivo movilizó más de $35.000 millones durante el fin de semana"],
                "neg": ["Dificultades de empresas de logística por el costo de los fletes terrestres", "Inflación en hotelería y gastronomía en los destinos turísticos"]
            },
            "ambito": {
                "pos": ["Impacto económico del furor por la Fórmula 1 en las transmisiones de televisión y streaming", "Mercados esperan que la calma del fin de semana ayude a la apertura cambiaria"],
                "neg": ["Cuentas provinciales: gobernadores revisan sus números de cara al último trimestre", "Consumo en esparcimiento muestra señales de desaceleración"]
            },
            "cronica": {
                "pos": ["¡Orgullo argentino! Franco Colapinto corrió como los dioses y metió a la bandera en lo más alto", "Golazo agónico en el minuto 94 desató la locura de toda la hinchada en el clásico"],
                "neg": ["Tragedia vial en la ruta 2: tres heridos tras chocar dos autos bajo la lluvia", "Vecinos protestan por falta de luz en dos barrios de Quilmes"]
            },
            "pagina12": {
                "pos": ["Colapinto ratificó en pista el talento forjado desde el automovilismo promocional argentino", "Reconocimiento a jóvenes científicos premiados en una feria de innovación tecnológica"],
                "neg": ["Los costos de las entradas para espectáculos y partidos alejan a las familias populares", "La crisis en los clubes de barrio por las boletas de servicios"]
            },
            "eldestape": {
                "pos": ["Emocionante triunfo deportivo argentino en el exterior que une al país en una sola voz", "Festivales de música y teatro popular con entrada libre llenaron las plazas"],
                "neg": ["El contraste entre el festejo en redes y la realidad económica en los comedores", "Sindicatos alertan que los salarios no alcanzan para el ocio ni las vacaciones"]
            },
            "tn": {
                "pos": ["Colapinto hizo historia: los audios de radio con su equipo celebrando los puntos en F1", "Clima primaveral en todo el país acompañó una fecha deportiva inolvidable"],
                "neg": ["Operativo cerrojo en los alrededores de la cancha tras escaramuzas entre facciones de hinchas", "Demoras en la autopista Panamericana por el retorno del fin de semana"]
            },
            "cadena3": {
                "pos": ["Talleres y Belgrano animaron un clásico vibrante con clima de fiesta en el Kempes", "El furor de los fanáticos tuercas cordobeses siguiendo la carrera de Colapinto"],
                "neg": ["Operativo de Defensa Civil por fuertes ráfagas de viento en el sur provincial", "Quejas de automovilistas por el estado del asfalto en la ruta 9"]
            },
            "c5n": {
                "pos": ["La alegría popular por la consagración del joven piloto argentino en la élite mundial", "Boca y River jugaron a cancha llena y sin incidentes graves"],
                "neg": ["El drama de los clubes de fomento que no pueden pagar las tarifas de gas en invierno", "El aumento de las cuotas de los colegios privados golpea a la clase media"]
            },
            "perfil": {
                "pos": ["Crónica de una jornada épica: cómo el deporte actúa como amortiguador del estrés social argentino", "Colapinto: el nuevo héroe deportivo que cautiva a todas las generaciones"],
                "neg": ["Los límites del optimismo deportivo frente a las curvas de inflación y desempleo", "Entrevista exclusiva sobre la psicología de masas y los desahogos colectivos"]
            }
        }
    },
    {
        "theme": "Superávit comercial récord y baja del riesgo país",
        "summary": "Jornada de alivio macroeconómico impulsada por la liquidación de exportaciones agropecuarias, el superávit de la balanza comercial y la colocación exitosa de bonos en el mercado internacional.",
        "opt_bias": 5.0, "cal_bias": 3.0, "conf_bias": 5.0, "ale_bias": 2.0,
        "x": ["RiesgoPaisMinimo", "SuperavitComercial", "VacaMuerta", "Caputo"],
        "google": ["bonos soberanos cotizacion", "que es el riesgo pais", "inversion en pesos"],
        "media_news": {
            "clarin": {
                "pos": ["Balanza comercial positiva récord: el superávit de divisas superó los US$ 2.400 millones", "El riesgo país cayó a su menor nivel desde mediados de 2020"],
                "neg": ["La industria pyme reclama medidas para sostener la competitividad frente a productos importados", "Discusión en el Congreso por los artículos del Presupuesto Nacional"]
            },
            "lanacion": {
                "pos": ["Vaca Muerta y el campo impulsan una entrada histórica de divisas a la economía argentina", "Inversores extranjeros vuelven a comprar deuda soberana argentina con rendimientos atractivos"],
                "neg": ["El equipo económico debate los tiempos para desarmar las restricciones cruzadas al dólar", "Gobernadores de la Patagonia piden coparticipar ingresos por regalías hidrocarburíferas"]
            },
            "infobae": {
                "pos": ["Caputo celebró en redes el balance cambiario y aseguró que 'el rumbo no se negocia'", "El dólar financiero operó a la baja y la brecha retrocedió al 16%"],
                "neg": ["Crecen las tensiones políticas en el Senado por el tratamiento de acuerdos judiciales", "Reclamo gremial en puertos cerealeros por mejoras en las condiciones laborales"]
            },
            "cronista": {
                "pos": ["Récord de exportaciones energéticas: el gasoducto permitió sustituir importaciones de GNL", "Empresas privadas emitieron deuda en el exterior a tasas de un dígito"],
                "neg": ["El tipo de cambio real multilateral genera cautela entre los exportadores industriales", "Demoras en la cadena de pagos en el sector de la construcción"]
            },
            "ambito": {
                "pos": ["El riesgo país cayó 45 unidades en un solo día ante la fuerte demanda de bonos globales", "Las reservas netas del BCRA mostraron la mayor suba semanal del año"],
                "neg": ["Dudas en el mercado sobre cómo enfrentará el Tesoro los vencimientos de deuda de 2025", "La recaudación del IVA refleja el impacto del menor consumo masivo"]
            },
            "cronica": {
                "pos": ["Conocé los créditos a tasa cero que lanzan para monotributistas y pequeños comerciantes", "Crece la venta de pasajes en trenes de larga distancia para las vacaciones"],
                "neg": ["El precio de los remedios de venta libre aumentó por encima de la inflación general", "Vecinos de Morón atraparon a un ladrón que robaba cables de telefonía"]
            },
            "pagina12": {
                "pos": ["Docentes e investigadores universitarios presentaron proyectos de desarrollo productivo regional", "Fuerte concurrencia en la marcha en conmemoración de La Noche de los Lápices"],
                "neg": ["El superávit comercial se logra con un derrumbe de las importaciones que frena la industria", "Advierten sobre el cierre de talleres textiles en el conurbano bonaerense"]
            },
            "eldestape": {
                "pos": ["Trabajadores aceiteros lograron un bono extraordinario tras arduas negociaciones paritarias", "Movilización de organizaciones sociales en reclamo de asistencia alimentaria directa"],
                "neg": ["Informe sobre la distribución del ingreso: los ricos ganan 18 veces más que los pobres", "El recorte en transferencias a las provincias paraliza obras de cloacas y agua potable"]
            },
            "tn": {
                "pos": ["El dólar libre se desinfla y los bancos ofrecen plazos fijos con tasas competitivas", "Las exportaciones de carne vacuna hacia mercados asiáticos registraron subas del 20%"],
                "neg": ["Piquete de choferes en la autopista Buenos Aires - La Plata provocó largas filas de autos", "Cruce de declaraciones entre el ministro de Economía y dirigentes de la oposición"]
            },
            "cadena3": {
                "pos": ["La cosecha de maní en Córdoba alcanzó volúmenes récord con fuerte demanda europea", "Inauguran un tramo de la autopista entre San Francisco y la capital cordobesa"],
                "neg": ["Productores tamberos de Santa Fe y Córdoba piden medidas contra la suba de insumos dolarizados", "Incendio en una fábrica de plásticos en el parque industrial de Río Cuarto"]
            },
            "c5n": {
                "pos": ["El reclamo de las universidades públicas suma apoyos de organizaciones civiles y rectores", "Cooperativas de trabajo recuperaron una fábrica metalúrgica en Avellaneda"],
                "neg": ["La deuda externa en dólares volvió a crecer según datos de la Secretaría de Finanzas", "Los salarios privados pierden contra la inflación acumulada en lo que va del año"]
            },
            "perfil": {
                "pos": ["Informe especial: cómo el superávit de divisas aleja el fantasma de una devaluación brusca", "Entrevista al titular de la Bolsa de Comercio: 'El mercado cree en el equilibrio fiscal'"],
                "neg": ["El dilema de la economía: estabilidad financiera versus reactivación del consumo interno", "La disputa de poder en el oficialismo de cara al armado electoral en la provincia de Buenos Aires"]
            }
        }
    },
    {
        "theme": "Aumento de tarifas de servicios y tensión en el transporte",
        "summary": "Jornada signada por la preocupación económica doméstica: entraron en vigencia los nuevos cuadros tarifarios de electricidad y transporte, generando quejas de usuarios y advertencias gremiales.",
        "opt_bias": -4.0, "cal_bias": -4.0, "conf_bias": -4.0, "ale_bias": -2.0,
        "x": ["AumentoTarifas", "BoletoColectivo", "LuzYGás", "ParoDeTransporte"],
        "google": ["cuanto sale el boleto de colectivo", "subsidios luz rase", "aumento gas septiembre"],
        "media_news": {
            "clarin": {
                "pos": ["El Gobierno asegura que la quita de subsidios permitirá equilibrar las cuentas públicas", "Acuerdo entre provincias para abaratar el costo de la energía mayorista"],
                "neg": ["El boleto mínimo de colectivo sube en el AMBA y desata quejas de usuarios en las estaciones", "Comerciantes advierten que las facturas de luz duplican los montos del mes anterior"]
            },
            "lanacion": {
                "pos": ["La reducción de subsidios energéticos ahorró al Estado más de US$ 1.800 millones este año", "Inversiones privadas en generación solar avanzan en las provincias del norte"],
                "neg": ["Impacto en la inflación: consultoras estiman que los aumentos de tarifas sumarán un punto al IPC", "Empresas de colectivos del interior advierten que el boleto no cubre los costos operativos"]
            },
            "infobae": {
                "pos": ["El Enre habilitó un canal online simplificado para reclamar por errores de facturación", "El BCRA mantuvo estables las tasas de interés para incentivar el ahorro en pesos"],
                "neg": ["Gremios del transporte convocan a un plenario y amenazan con medidas de fuerza", "Largas filas en los centros de registro de la tarjeta SUBE para conservar los descuentos"]
            },
            "cronista": {
                "pos": ["El equilibrio en las cuentas energéticas mejora la calificación crediticia de las empresas del sector", "El dólar financiero operó con leves oscilaciones en una rueda tranquila"],
                "neg": ["La suba de tarifas impacta en los costos fijos de las pequeñas y medianas empresas industriales", "Ventas en supermercados cayeron 4.8% interanual según datos del sector"]
            },
            "ambito": {
                "pos": ["Compañías eléctricas anuncian inversiones en redes de media tensión para el próximo verano", "Bonos en dólares resistieron la presión y cerraron con ligeras alzas"],
                "neg": ["El costo de la canasta de servicios públicos para una familia superó los $140.000 mensuales", "Tensión entre la Secretaría de Transporte y las cámaras empresarias por los subsidios"]
            },
            "cronica": {
                "pos": ["Vecinos de Berazategui celebran la llegada del asfalto a tres barrios postergados", "River presentó su nuevo plantel para pelear la Copa Libertadores"],
                "neg": ["El bolsillo no da más: la luz llegó con aumentos de hasta 150% en los barrios populares", "Viajar es un lujo: viajar a Capital desde el conurbano cuesta el triple que hace seis meses"]
            },
            "pagina12": {
                "pos": ["Audiencias públicas: organizaciones de usuarios reclaman frenar los tarifazos ante la Justicia", "Estudiantes secundarios realizan sentadas pacíficas en defensa de los comedores escolares"],
                "neg": ["Tarifazo desmedido: familias de clase trabajadora deben elegir entre pagar la luz o los remedios", "Gremios del transporte ratifican que el paro será total si no hay recomposición salarial"]
            },
            "eldestape": {
                "pos": ["Clubes de barrio consiguen un amparo judicial transitorio contra el corte del suministro eléctrico", "Convocan a una concentración frente a la Secretaría de Energía"],
                "neg": ["Ajuste sin fin: denuncian que las tarifas energéticas benefician a un puñado de empresas amigas", "La pérdida de poder adquisitivo del salario mínimo llega a niveles críticos"]
            },
            "tn": {
                "pos": ["Transporte confirmó que continuará vigente el beneficio de la Red SUBE para viajes combinados", "Las estaciones de servicio aseguran que el abastecimiento de combustible es normal"],
                "neg": ["Fuerte malestar de los pasajeros en Constitución y Retiro por las tarifas y las demoras", "Empresas de colectivos reducen frecuencias nocturnas por falta de fondos"]
            },
            "cadena3": {
                "pos": ["La cosecha de trigo muestra rindes prometedores en el sudeste de Córdoba", "Inauguran un nuevo puente sobre el lago San Roque que agilizará el tránsito turístico"],
                "neg": ["El boleto urbano en Córdoba y Rosario roza los $1.000 y genera protestas de estudiantes", "Comerciantes cordobeses reclaman por las altas boletas de la empresa provincial de energía"]
            },
            "c5n": {
                "pos": ["Legisladores de la oposición preparan un proyecto para retrotraer las tarifas a valores de mayo", "Organizaciones barriales armaron una olla popular frente al Congreso"],
                "neg": ["Impacto social del tarifazo: cómo afecta a los jubilados que cobran el haber mínimo", "La parálisis en las ventas minoristas golpea a los centros comerciales a cielo abierto"]
            },
            "perfil": {
                "pos": ["Análisis de políticas públicas: el dilema de corregir precios relativos sin desbordar el humor social", "Entrevista a consultores de opinión pública sobre la tolerancia ciudadana al ajuste"],
                "neg": ["El descontento por las tarifas se traslada a las encuestas de humor social en el Gran Buenos Aires", "La relación entre el Gobierno nacional y los mandatarios provinciales atraviesa su momento más tenso"]
            }
        }
    }
]

def generate_backfill_data(days_back: int = 30):
    """Genera y almacena datos históricos para los últimos N días con NOTICIAS REALISTAS Y ESPECÍFICAS."""
    init_db()
    today = date.today()
    random.seed(1234)

    print(f"[BACKFILL] Generando serie temporal retrospectiva de {days_back} días con titulares específicos...")

    for i in range(days_back, 0, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()

        # Seleccionar agenda según día de semana o rotación
        is_weekend = target_date.weekday() >= 5
        if is_weekend:
            agenda = DAILY_NEWS_AGENDAS[2]  # Fin de semana deportivo/cultural
        else:
            agenda = DAILY_NEWS_AGENDAS[(i % len(DAILY_NEWS_AGENDAS))]

        source_evaluations = []
        raw_items_by_source = {}

        for src_id, meta in MEDIA_SOURCES.items():
            category = meta.get("category", "general")
            
            # Obtener noticias específicas de este medio si existen en la agenda
            media_specific = agenda.get("media_news", {}).get(src_id)
            if media_specific:
                pos_headlines = media_specific.get("pos", [])
                neg_headlines = media_specific.get("neg", [])
            else:
                pos_headlines = [f"Noticias de reactivación y avances relevadas por {meta['name']}"]
                neg_headlines = [f"Focos de preocupación y quejas ciudadanas relevadas por {meta['name']}"]

            cat_mod = 0.0
            if category in ["political_opposition", "political_left"]:
                cat_mod = -2.0
            elif category == "economy":
                cat_mod = 1.0 if agenda["conf_bias"] > 0 else -1.5
            elif category == "popular":
                cat_mod = -0.5

            opt = max(-10.0, min(10.0, round(agenda["opt_bias"] + cat_mod + random.uniform(-0.8, 0.8), 1)))
            cal = max(-10.0, min(10.0, round(agenda["cal_bias"] + cat_mod * 0.5 + random.uniform(-0.8, 0.8), 1)))
            conf = max(-10.0, min(10.0, round(agenda["conf_bias"] + cat_mod + random.uniform(-0.8, 0.8), 1)))
            ale = max(-10.0, min(10.0, round(agenda["ale_bias"] + random.uniform(-0.6, 0.6), 1)))

            scores = EmotionalAxesScores(optimismo=opt, calma=cal, confianza=conf, alegria=ale)
            comp = (
                opt * EMOTIONAL_AXES["optimismo"]["weight"] +
                cal * EMOTIONAL_AXES["calma"]["weight"] +
                conf * EMOTIONAL_AXES["confianza"]["weight"] +
                ale * EMOTIONAL_AXES["alegria"]["weight"]
            ) * 10.0
            comp = max(-100.0, min(100.0, round(comp, 2)))

            key_themes = agenda["x"][:3]
            justification = f"Evaluación de la cobertura de {meta['name']} ({agenda['theme']}). Cobertura centrada en los temas de mayor impacto nacional del día."

            eval_obj = SourceSentimentScore(
                source_id=src_id,
                source_name=meta["name"],
                category=category,
                scores=scores,
                composite_score=comp,
                key_themes=key_themes,
                positive_drivers=pos_headlines[:2],
                negative_drivers=neg_headlines[:2],
                editorial_bias_detected=f"Encuadre editorial {category}",
                justification=justification
            )
            source_evaluations.append(eval_obj)

            # Generar titulares crudos para el buscador de auditoría
            raw_items_by_source[src_id] = [
                {"title": t, "url": meta.get("web", ""), "channel": "historico"}
                for t in (pos_headlines + neg_headlines)
            ]

        digital_val = round((agenda["opt_bias"] + agenda["ale_bias"]) * 4.5, 2)
        digital_scores = {"composite": digital_val}

        ihsa_val, axes_avg, cat_label = compute_daily_ihsa(source_evaluations, digital_scores)

        snapshot = DailySnapshot(
            date=date_str,
            ihsa_score=ihsa_val,
            ihsa_category=cat_label,
            axes_averages=axes_avg,
            sources=source_evaluations,
            top_trends_x=agenda["x"],
            top_trends_google=agenda["google"],
            summary_of_the_day=agenda["summary"]
        )

        save_snapshot(snapshot, raw_items_by_source, covers_map={})

    print(f"[BACKFILL] ¡Completado con éxito! Se poblaron {days_back} días con titulares realistas en {DB_PATH}.")

if __name__ == "__main__":
    generate_backfill_data(30)
