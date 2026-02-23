# Quick Start Guide

Guía rápida para poner en marcha el bot en menos de 10 minutos.

## 1. Preparar tu Wallet de Polymarket

### Si no tienes wallet:
1. Ve a [polymarket.com](https://polymarket.com)
2. Conecta tu wallet (MetaMask recomendado)
3. Deposita USDC en Polygon
4. Obtén tu clave privada:
   - MetaMask: ⋮ → Detalles de la cuenta → Exportar clave privada

### Si ya tienes wallet:
Asegúrate de tener:
- [ ] Clave privada (0x...)
- [ ] USDC en red Polygon
- [ ] Un poco de MATIC para gas (0.1 MATIC es suficiente)

## 2. Deploy en Railway (5 minutos)

### Opción A: Deploy desde GitHub (Recomendado)

1. **Sube el código a GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/polymarket-bot.git
   git push -u origin main
   ```

2. **En Railway:**
   - Ve a [railway.app](https://railway.app)
   - New Project → Deploy from GitHub repo
   - Selecciona tu repo

3. **Configurar variables:**
   - Ve a la pestaña "Variables"
   - Agrega cada variable (ver abajo)

### Opción B: Deploy manual

1. Ve a [railway.app](https://railway.app)
2. New Project → Empty Project
3. New → Upload code → Selecciona la carpeta del bot
4. Configura las variables

## 3. Variables de Entorno

En Railway, agrega estas variables:

```
POLYMARKET_PRIVATE_KEY=0x...        # TU CLAVE PRIVADA (secreto!)
LIVE=true                           # Activar trading real
MAX_POSITION=3.0                    # Máximo por trade
MAX_TOTAL_SPEND=20.0                # Límite total
ASSETS=BTC                          # Assets a tradear
RUN_INTERVAL=60                     # Segundos entre ciclos
LOG_LEVEL=INFO                      # Nivel de logs
```

**IMPORTANTE:** Haz clic en el ícono del ojo junto a `POLYMARKET_PRIVATE_KEY` para marcarla como secreto.

## 4. Verificar que Funciona

### Ver logs:
1. En Railway, ve a tu servicio
2. Pestaña "Logs"
3. Deberías ver:
   ```
   🚀 Iniciando ciclo | Modo: LIVE
   💰 Presupuesto: $0.00/$20.00 | Disponible: $20.00
   📈 Obteniendo señales para: BTC
   ```

### Ver estado:
```bash
# En Railway CLI (opcional)
railway logs
```

## 5. Primer Trade

El bot operará automáticamente cuando:
- [x] Haya un mercado BTC Up/Down activo
- [x] El momentum de BTC sea > 0.5%
- [x] El EV sea positivo después del fee del 10%

**No operará inmediatamente** si no hay buenas oportunidades. ¡Esto es normal!

## 6. Monitoreo

### Ver trades realizados:
En Railway Logs busca:
```
✅ Trade ejecutado: 0x...
```

### Ver presupuesto:
El bot muestra en cada ciclo:
```
💰 Presupuesto: $X.XX/$20.00 | Disponible: $X.XX
```

## Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| "POLYMARKET_PRIVATE_KEY no configurada" | Verifica que la variable esté en Railway |
| "Sin mercados activos" | Los fast markets no están disponibles 24/7, espera |
| "EV negativo" | El fee del 10% está destruyendo la ventaja, espera mejor momento |
| Bot no inicia | Ve a "Deployments" y haz clic en "Redeploy" |

## Próximos Pasos

- [ ] Agregar ETH y SOL: cambiar `ASSETS=BTC,ETH,SOL`
- [ ] Ajustar `MAX_POSITION` según tu capital
- [ ] Configurar alertas en Railway (Settings → Notifications)
- [ ] Revisar logs diariamente los primeros días

## Comandos Útiles

```bash
# Ver estado local (si tienes Railway CLI)
railway logs

# Pausar bot
# En Railway: Settings → Service → Stop

# Reiniciar
# En Railway: Deployments → Redeploy
```

## Soporte

Si tienes problemas:
1. Revisa los logs en Railway
2. Verifica que tu wallet tenga USDC y MATIC
3. Asegúrate de que `LIVE=true` esté configurado
4. Prueba con `LIVE=false` primero para ver que todo funciona

---

**¡Listo! Tu bot debería estar operando.** Recuerda monitorear los primeros trades para asegurarte de que todo funciona correctamente.
