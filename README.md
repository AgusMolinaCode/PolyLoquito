# Polymarket FastLoop Trader

Bot de trading automatizado para mercados rápidos de Polymarket (5min y 15min) que utiliza momentum de precio desde Binance como señal de trading.

## Características

- **Mercados soportados**: BTC Up/Down (5min y 15min), extensible a ETH y SOL
- **Señal**: Momentum de precio desde Binance (BTCUSDT, ETHUSDT, SOLUSDT)
- **Cálculo de EV**: Considera el fee del 10% de Polymarket en fast markets
- **Control de presupuesto**: Límites diarios/semanales configurables
- **Logging completo**: Logs a archivo y consola
- **Health checks**: Endpoint para monitoreo
- **Deploy en Railway**: Configuración lista para producción

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Binance   │────▶│     Bot     │────▶│ Polymarket  │
│   API       │     │  (Python)   │     │   CLOB API  │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │   Railway   │
                     │   (Cloud)   │
                     └─────────────┘
```

## Estructura del Proyecto

```
polymarket-bot/
├── main.py              # Código principal del bot
├── health_server.py     # Servidor HTTP para health checks
├── requirements.txt     # Dependencias Python
├── Procfile            # Configuración de Railway
├── runtime.txt         # Versión de Python
├── railway.json        # Configuración de deploy
├── Dockerfile          # Contenedor Docker (opcional)
├── .env.example        # Ejemplo de variables de entorno
└── README.md           # Este archivo
```

## Instalación Local

### 1. Clonar y configurar

```bash
git clone <tu-repo>
cd polymarket-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Ejecutar

```bash
# Dry run (sin trades reales)
python main.py --once

# Ver estado
python main.py --status

# Trading real (local)
python main.py --once --live

# Modo servidor (loop continuo)
python main.py --live
```

## Deploy en Railway

### Paso 1: Crear cuenta y proyecto

1. Ve a [railway.app](https://railway.app) y crea una cuenta
2. Crea un nuevo proyecto
3. Selecciona "Deploy from GitHub repo" o sube los archivos directamente

### Paso 2: Configurar variables de entorno

En el dashboard de Railway, ve a "Variables" y agrega:

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `POLYMARKET_PRIVATE_KEY` | `0x...` | Tu clave privada de Polygon |
| `LIVE` | `true` | Activa trading real |
| `MAX_POSITION` | `3.0` | Máximo por trade (USD) |
| `MAX_TOTAL_SPEND` | `20.0` | Límite total de gasto (USD) |
| `ASSETS` | `BTC` | Assets a tradear (BTC,ETH,SOL) |
| `RUN_INTERVAL` | `60` | Segundos entre ciclos |
| `LOG_LEVEL` | `INFO` | Nivel de logs |

**IMPORTANTE**: Marca `POLYMARKET_PRIVATE_KEY` como secreto (botón del ojo).

### Paso 3: Configurar deploy

Railway detectará automáticamente el `Procfile`. El bot se ejecutará como worker.

### Paso 4: Monitorear

Ve a la pestaña "Deploys" para ver los logs en tiempo real.

## Variables de Entorno

### Requeridas

| Variable | Descripción |
|----------|-------------|
| `POLYMARKET_PRIVATE_KEY` | Clave privada de tu wallet Polygon (0x...) |

### Opcionales

| Variable | Default | Descripción |
|----------|---------|-------------|
| `LIVE` | `false` | `true` para trades reales |
| `MAX_POSITION` | `3.0` | Máximo USD por trade |
| `MAX_TOTAL_SPEND` | `20.0` | Límite total de gasto |
| `ASSETS` | `BTC` | Assets separados por coma |
| `RUN_INTERVAL` | `60` | Segundos entre ciclos |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |

## Cómo Funciona

### 1. Ciclo de Trading

```
┌─────────────────┐
│  Iniciar Ciclo  │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Obtener señales │◀── Binance API (BTCUSDT 1m candles)
│ de precio       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Buscar mercados │◀── Polymarket Gamma API
│ activos         │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Calcular EV     │◀── Considera fee del 10%
└────────┬────────┘
         ▼
┌─────────────────┐
│ ¿EV > 0?        │
└────────┬────────┘
    Sí /   \ No
    ▼       ▼
┌──────┐  ┌──────────┐
│Trade │  │ Esperar  │
│      │  │ próximo  │
└──────┘  │ ciclo    │
          └──────────┘
```

### 2. Cálculo de Expected Value (EV)

```
EV = (Prob_acierto × Ganancia_neta) - (Prob_falla × Monto_invertido)

Donde:
  Ganancia_neta = (1 - Precio_token) × (1 - Fee)
  Fee = 10% (Polymarket fast markets)

Si EV <= 0 → No se opera (el fee destruye la ventaja)
```

### 3. Filtros de Señal

- **Momentum mínimo**: 0.5% de movimiento en 5 minutos
- **Volumen**: Ratio > 0.5x del promedio
- **Tiempo restante**: > 60 segundos para expiración
- **Precio del token**: < 0.95 (evitar comprar caro)

## Comandos CLI

```bash
# Un solo ciclo (dry run)
python main.py --once

# Un solo ciclo (live)
python main.py --once --live

# Modo servidor (loop continuo)
python main.py --live

# Ver estado y presupuesto
python main.py --status

# Resetear presupuesto
python main.py --reset

# Health check (JSON)
python main.py --health
```

## Monitoreo

### Logs

Los logs se guardan en `/app/data/bot.log` y se muestran en consola.

En Railway: Ve a la pestaña "Logs" del servicio.

### Estado

```bash
python main.py --status
```

Salida:
```
💰 PRESUPUESTO
   Gastado:    $12.50
   Límite:     $20.00
   Disponible: $7.50

📊 ESTADO
   Status:     running
   Iniciado:   2024-01-15T10:30:00+00:00
   Última run: 2024-01-15T14:25:00+00:00
   Trades:     4
   Assets:     BTC
```

### Health Check

```bash
python main.py --health
```

Salida:
```json
{
  "status": "running",
  "last_run": "2024-01-15T14:25:00+00:00",
  "total_spent": 12.50,
  "max_spend": 20.00,
  "trades_count": 4
}
```

## Ejemplo de Output

```
============================================================
🚀 Iniciando ciclo | Modo: LIVE
💰 Presupuesto: $12.50/$20.00 | Disponible: $7.50
📈 Obteniendo señales para: BTC
  BTC: +0.823% | UP | Vol: 1.45x
  📊 3 mercados encontrados
  🎯 Bitcoin Up or Down - February 15, 5:30AM-5:35AM ET...
     ⏱ 185s | Ventana: 5m
     ✅ EV=+0.0234 | Prob=54.1% (BE=52.3%) | YES@0.480 | Fee=10%
     💵 Trade: $3.00 en YES
     ✅ Trade ejecutado: 0xabc123...
     💰 Acumulado: $15.50/$20.00
✅ Ciclo completado | Trades: 1
============================================================
⏳ Esperando 60s...
```

## Extensión a Otros Assets

Para agregar ETH y SOL:

1. Editar variable de entorno:
```
ASSETS=BTC,ETH,SOL
```

2. El bot automáticamente:
   - Busca mercados "ETH Up or Down" y "SOL Up or Down"
   - Obtiene señales de ETHUSDT y SOLUSDT desde Binance
   - Opera cada asset de forma independiente

## Seguridad

- **Nunca compartas tu `POLYMARKET_PRIVATE_KEY`**
- En Railway, siempre marca la clave privada como secreto
- Usa una wallet dedicada solo para el bot
- Configura límites de presupuesto conservadores
- Monitorea los logs regularmente

## Troubleshooting

### "POLYMARKET_PRIVATE_KEY no configurada"

Verifica que la variable de entorno esté configurada correctamente en Railway.

### "Sin mercados activos"

Los mercados fast de BTC no están disponibles 24/7. Verifica en Polymarket directamente.

### "EV negativo"

El fee del 10% está destruyendo tu ventaja. Aumenta el umbral de momentum o espera mejores oportunidades.

### "Rate limit exceeded"

El bot hace requests cada 60 segundos por defecto. Si necesitas más frecuencia, considera usar proxies o aumentar el intervalo.

## Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agregar feature'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## Licencia

MIT License - ver LICENSE para detalles.

## Disclaimer

**Este bot es solo para fines educativos. El trading conlleva riesgos significativos de pérdida. No somos responsables de pérdidas financieras. Usa bajo tu propio riesgo.**

Los fast markets de Polymarket tienen un fee del 10%. Asegúrate de que tu estrategia tenga suficiente edge para superar este costo.
