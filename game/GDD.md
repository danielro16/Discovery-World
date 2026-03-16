# 🎮 Discovery World — Game Design Document
### Miami Beach Edition | v0.1

---

## 1. Concepto

**Discovery World** es un juego de exploración isométrico 2D donde los jugadores recorren ciudades reales, descubren negocios y contribuyen datos verificados sobre ellos — todo mientras se divierten, suben de nivel y compiten.

**Pitch:** "Google Maps + GTA Vice City + Duolingo = Discovery World"

**Plataforma:** Web (mobile-first, PWA)
**Engine:** PixiJS (isométrico 2D con efecto de profundidad)
**Primer mapa:** Miami Beach, FL

---

## 2. Core Game Loop

```
EXPLORAR → DESCUBRIR → VERIFICAR → RECOMPENSAR → REPETIR
```

1. **Explorar** — El jugador camina por Miami Beach en vista isométrica
2. **Descubrir** — Se acerca a un negocio real, se activa interacción
3. **Verificar** — Responde micro-preguntas sobre el negocio (1-3 por visita)
4. **Recompensar** — Gana XP, monedas, desbloquea zonas/items
5. **Repetir** — Nuevos negocios, misiones diarias, eventos

---

## 3. Mapa — Miami Beach

### Zonas (desbloqueables por nivel)

| Zona | Nivel | Tipo de negocios | Vibe |
|------|-------|-------------------|------|
| **Ocean Drive** | 1 (inicio) | Restaurantes, bares, hoteles art deco | Neon, nightlife |
| **Lincoln Road** | 3 | Tiendas, galerías, cafés | Shopping, cultura |
| **Española Way** | 5 | Restaurantes latinos, boutiques | Bohemio, colorido |
| **Collins Avenue** | 8 | Hoteles luxury, spas, clubs | Premium, exclusivo |
| **South Pointe** | 12 | Seafood, parques, marina | Relax, familiar |
| **North Beach** | 15 | Local gems, hidden spots | Auténtico, residencial |

### Estilo visual
- Vista isométrica con tiles en diamante
- Paleta: neón (cyan, magenta, amarillo) sobre fondos oscuros/atardecer
- Edificios art deco con volumen (caras laterales visibles)
- Palmeras, arena, agua animada
- Ciclo día/noche que afecta la estética

---

## 4. Jugador (Avatar)

- **Personalización básica:** color de pelo, ropa, accesorios (desbloqueables)
- **Movimiento:** click-to-move o joystick virtual (mobile)
- **Inventario:** items coleccionables de negocios visitados
- **Stats:**
  - 🏆 **Nivel** — sube al ganar XP
  - 💰 **Coins** — moneda del juego (ganas verificando)
  - ⚡ **Energía** — se gasta al verificar (recarga con tiempo o coins)
  - 🔥 **Streak** — días consecutivos jugando

---

## 5. Sistema de Negocios

### Cada negocio en el mapa tiene:
- **Sprite único** según categoría (restaurante, hotel, tienda, bar, etc.)
- **Estado de datos:** completo ✅ | parcial 🟡 | vacío 🔴
- **Nivel de confianza:** basado en cuántas verificaciones tiene

### Interacción con negocio:
1. Jugador se acerca → aparece burbuja con nombre + categoría
2. Toca el negocio → se abre panel de interacción
3. Ve info existente + preguntas pendientes

### Micro-preguntas (el core de recolección):
```
"¿Este restaurante tiene terraza?"        [Sí] [No] [No sé]
"¿Rango de precios?"                      [$] [$$] [$$$] [$$$$]
"¿Aceptan reservaciones?"                 [Sí] [No] [No sé]
"¿Tiene happy hour?"                      [Sí] [No] [No sé]
"¿WiFi gratis?"                           [Sí] [No] [No sé]
"¿Pet friendly?"                          [Sí] [No] [No sé]
"Sube una foto del lugar"                 [📷 Cámara]
```

Cada respuesta = **+10-50 XP** + **+5-20 coins**
Subir foto = **+100 XP** (verificada por AI)

---

## 6. Gamificación

### 6.1 Misiones diarias
- "Descubre 3 restaurantes en Ocean Drive" → 200 XP
- "Verifica 10 datos de cualquier negocio" → 150 XP
- "Encuentra un negocio con happy hour" → 100 XP

### 6.2 Achievements
- 🏅 "Primer paso" — Verifica tu primer negocio
- 🗺️ "Explorador" — Visita 50 negocios
- 📸 "Fotógrafo" — Sube 20 fotos verificadas
- 🔥 "En llamas" — 7 días de streak
- 👑 "Rey de Ocean Drive" — Verifica el 80% de negocios en la zona

### 6.3 Leaderboard
- Por zona (quién verificó más en Ocean Drive)
- Por ciudad (ranking general Miami Beach)
- Por semana (reset semanal para que nuevos puedan competir)

### 6.4 Recompensas
- **Coins** → comprar skins, accesorios, items decorativos
- **Badges** → mostrar en perfil
- **Descuentos reales** → (futuro) negocios ofrecen cupones a top verificadores

---

## 7. Datos recolectados por interacción

Cada micro-tarea alimenta el pipeline de datos:

| Campo | Tipo | Fuente en juego |
|-------|------|-----------------|
| nombre | string | Pre-cargado / corrección del jugador |
| categoría | enum | Pre-cargado / corrección |
| dirección | string | Del mapa |
| horarios | struct | Pregunta al jugador |
| rango_precio | enum | Pregunta ($/$$/$$$) |
| tiene_terraza | bool | Pregunta sí/no |
| wifi_gratis | bool | Pregunta sí/no |
| pet_friendly | bool | Pregunta sí/no |
| happy_hour | bool | Pregunta sí/no |
| acepta_reservas | bool | Pregunta sí/no |
| fotos | array[url] | Upload del jugador |
| sigue_abierto | bool | Pregunta sí/no |
| rating_jugador | 1-5 | Calificación post-visita |

### Verificación cruzada:
- Misma pregunta a **3 jugadores diferentes**
- Si 2/3 coinciden → dato confirmado ✅
- Si no hay consenso → se marca para review

---

## 8. Stack técnico

```
Frontend:        PixiJS + pixi-viewport (canvas 2D acelerado por GPU)
UI overlay:      HTML/CSS sobre el canvas (paneles, menús)
Tiles engine:    Custom isometric tile renderer
State:           Zustand o vanilla store
Backend:         Supabase (auth, DB, storage, realtime)
Mapa base:       OpenStreetMap data → convertido a tiles isométricos
Assets:          AI-generated sprites (Midjourney/Stable Diffusion)
Audio:           Howler.js (synthwave/vaporwave ambient)
Deploy:          Vercel (PWA)
```

---

## 9. MVP — Fase 1 (4-6 semanas)

### Incluye:
- [x] Mapa isométrico de Ocean Drive (1 zona)
- [x] 20-30 negocios reales pre-cargados
- [x] Avatar básico con movimiento
- [x] Sistema de micro-preguntas (5 tipos)
- [x] XP + Coins + Nivel
- [x] Leaderboard simple
- [x] Auth con Supabase
- [x] Mobile responsive (PWA)

### No incluye (fase 2+):
- [ ] Más zonas de Miami Beach
- [ ] Fotos verificadas por AI
- [ ] Descuentos/cupones reales
- [ ] Multiplayer en tiempo real
- [ ] Otras ciudades
- [ ] Ciclo día/noche
- [ ] Audio/música

---

## 10. Monetización (futuro)

1. **Freemium** — Energía gratis limitada, compra más con $
2. **Negocios pagan** — Para aparecer destacados en el juego
3. **Datos** — El directorio verificado tiene valor comercial
4. **Cupones** — Comisión por redención de descuentos

---

## 11. Métricas de éxito

| Métrica | Target MVP |
|---------|-----------|
| DAU | 500+ |
| Datos verificados/día | 2,000+ |
| Retención D7 | 30%+ |
| Negocios con datos completos | 80% de Ocean Drive |
| Avg. session time | 8+ minutos |
