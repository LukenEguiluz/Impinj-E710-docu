# FRD950 (Impinj E710) — Guía completa de implementación

Documentación para implementar el lector fijo **Faread FRD950-A8** (motor RF Impinj E710) desde cualquier lenguaje/plataforma vía **TCP**.

Validado en laboratorio el **2026-07-30** contra `192.168.1.190:6000`.

---

## 1. Resumen ejecutivo

| Ítem | Valor |
|------|--------|
| IP default típica | `192.168.1.190` |
| Puerto TCP | `6000` |
| Transporte | TCP raw (binario, no texto) |
| Protocolo host↔lector | `Len \| Adr \| Cmd \| Data[] \| CRC16_LSB \| CRC16_MSB` |
| Air interface tags | ISO 18000-6C / EPC Gen2 (este FW: `TrType=0x02` → **solo 6C**) |
| Región México peaje (IAVE/PASE/Televía) | **902–928 MHz** (US band3 en el lector) |
| Potencia máxima | **33 dBm** (`0x21`) |
| Antenas | 4 (mux por bits; inventory usa `0x80`…`0x83`) |

### Qué NO usar

- Framing `BB … 7E` (módulos M100 UART) → **sin respuesta**
- Framing `A0 Len Addr Cmd … checksum` (Serial Interface V3 / crate `e710_uhf`) → **sin respuesta**
- Inventory `0x01` **sin** Q+Session → status `0xFF` (parameter error)

---

## 2. Conexión TCP

```text
socket.connect(HOST, 6000)
TCP_NODELAY recomendado
KeepAlive recomendado (el lector cierra idle)
```

Reglas:

1. Un comando a la vez en **answer mode**.
2. En **realtime mode** el lector solo acepta: info `0x21`, set mode `0x76`, get mode params `0x77`.
3. Siempre salir de realtime (`0x76` data=`0x00`) al terminar.
4. Gap entre bytes &lt; 15 ms (en TCP no suele ser problema si envías el frame completo de una).

---

## 3. Formato de trama

### 3.1 Comando (Host → Reader)

| Campo | Bytes | Descripción |
|-------|------:|-------------|
| Len | 1 | Bytes desde Adr hasta CRC_MSB inclusive = `len(Data)+4`. Rango 4–255 |
| Adr | 1 | Dirección lector `0x00`–`0xFE`. `0xFF` = broadcast |
| Cmd | 1 | Código de comando |
| Data[] | 0–N | Parámetros |
| CRC16 LSB | 1 | CRC de `Len…último Data` |
| CRC16 MSB | 1 | |

### 3.2 Respuesta (Reader → Host)

| Campo | Bytes | Descripción |
|-------|------:|-------------|
| Len | 1 | Igual convención |
| Adr | 1 | Dirección |
| reCmd | 1 | Eco del comando (o `0xEE` en realtime) |
| Status | 1 | Resultado (ver §10) |
| Data[] | 0–N | Payload |
| CRC16 LSB/MSB | 2 | |

### 3.3 CRC-16

```text
Preset  = 0xFFFF
Poly    = 0x8408
Orden   = LSB primero en el wire
Cubre   = desde Len hasta último byte de Data (sin incluir el CRC)
```

#### Python

```python
def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if (crc & 1) else (crc >> 1)
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def build_frame(addr: int, cmd: int, data: bytes = b"") -> bytes:
    body = bytes([addr & 0xFF, cmd & 0xFF]) + data
    partial = bytes([len(body) + 2]) + body   # Len = Adr+Cmd+Data+CRC(2)
    return partial + crc16(partial)
```

#### Verificación conocida

```text
build_frame(0x00, 0x01)           → 04 00 01 DB 4B
build_frame(0x00, 0x21)           → 04 00 21 D9 6A
build_frame(0x00, 0x01, b"\x04\x00") → 06 00 01 04 00 AC 36
```

### 3.4 Parser de respuestas (pueden llegar varias tramas juntas)

```python
def parse_frames(buf: bytes) -> list[bytes]:
    out, i = [], 0
    while i < len(buf):
        ln = buf[i]
        if ln < 4 or i + 1 + ln > len(buf):
            break
        out.append(buf[i : i + 1 + ln])
        i += 1 + ln
    return out
```

---

## 4. Configuración de región / frecuencia (`0x22`)

### 4.1 Comando

```text
Len=0x06  Adr  Cmd=0x22  MaxFre  MinFre  CRC
```

Cada byte `Fre`:

```text
bit7..bit6 = código de banda (combinado Max+Min)
bit5..bit0 = punto de frecuencia N
```

`N_max` debe ser ≥ `N_min`.

### 4.2 Tabla de bandas (bits Max7 Max6 Min7 Min6)

| Bits | Banda | Fórmula | N |
|------|-------|---------|---|
| `0 0 0 1` | Chinese band2 | `920.125 + N×0.25` | 0–19 |
| `0 0 1 0` | **US** | `902.75 + N×0.5` | 0–49 |
| `0 0 1 1` | Korea | `917.1 + N×0.2` | 0–31 |
| `0 1 0 0` | **EU** | `865.1 + N×0.2` | 0–14 |
| `0 1 1 0` | Ukraine | `868.0 + N×0.1` | 0–6 |
| `0 1 1 1` | Peru | `916.2 + N×0.9` | 0–11 |
| `1 0 0 0` | Chinese band1 | `840.125 + N×0.25` | 0–19 |
| `1 0 0 1` | EU3 | `865.7 + N×0.6` | 0–3 |
| `1 0 1 0` | Taiwan | `922.25 + N×0.5` | 0–11 |
| `1 1 0 0` | **US band3** | `902 + N×0.5` | 0–52 |

### 4.3 Presets listos

| Uso | MaxFre | MinFre | Hex Data | Rango efectivo |
|-----|--------|--------|----------|----------------|
| **México peaje (recomendado)** | `0xF4` | `0x00` | `F4 00` | **902–928 MHz** (US3, N=0..52) |
| US clásico | `0x31` | `0x80` | `31 80` | 902.75–927.25 MHz |
| EU | `0x4E` | `0x00` | `4E 00` | 865.1–867.9 MHz |
| EU3 | `0x83` | `0x40` | `83 40` | 865.7–867.5 MHz |
| China b2 | `0x13` | `0x40` | `13 40` | 920.125–924.875 MHz |

Construcción:

```python
def fre_byte(b7, b6, n):
    return ((b7 & 1) << 7) | ((b6 & 1) << 6) | (n & 0x3F)

# México / US3: Max bits (1,1), Min bits (0,0), Nmax=52, Nmin=0
maxfre = fre_byte(1, 1, 52)  # 0xF4
minfre = fre_byte(0, 0, 0)   # 0x00
frame = build_frame(0x00, 0x22, bytes([maxfre, minfre]))
```

Ejemplo TX México:

```text
06 00 22 F4 00 …CRC…
```

Verificar con `0x21`: campos `dmaxfre`/`dminfre` deben coincidir.

> Nota laboratorio: Korea (`1F C0`) fue **rechazada** (`0xFF`) en este FW. El resto de bandas listadas arriba sí se aplicaron.

---

## 5. Potencia RF (`0x2F`)

```text
05 00 2F Power CRC
```

| Power | dBm |
|------:|----:|
| `0x00`…`0x1E` | 0…30 |
| `0x21` | **33** (máximo FRD950; aceptado en pruebas) |

Ejemplo máximo:

```text
05 00 2F 21 … → status 0x00
```

Leer potencia actual:

- En `0x21` info → byte `Power`
- O `0x94` → 4 bytes (una potencia por antena), ej. `21 21 21 21`

---

## 6. Antenas

### 6.1 Multiplex (`0x3F`) — Format 1

```text
05 00 3F Ant CRC
```

`Ant` bitmask:

| Bit | Significado |
|----:|-------------|
| 0 | Antena 1 enable |
| 1 | Antena 2 |
| 2 | Antena 3 |
| 3 | Antena 4 |
| 7 | `0` = guardar en flash / `1` = temporal (no persistir) |

Ejemplos:

```text
01     → solo ant1, persistente
81     → solo ant1, temporal
0F     → ants 1–4, persistente
8F     → ants 1–4, temporal
```

### 6.2 Código de antena en inventory (`0x01`)

| Antena física | Código `Ant` en inventory |
|--------------:|---------------------------:|
| 1 | `0x80` |
| 2 | `0x81` |
| 3 | `0x82` |
| 4 | `0x83` |

### 6.3 Antenna check / “sensibilidad” de detector (`0x66`, `0x6E`)

**Antenna connection check** (`0x66`):

```text
05 00 66 Enable CRC
Enable: 0x00 = off, 0x01 = on
```

Con check ON, si el cable/antena está mal → inventory puede fallar con `0xF8`.

**Umbral return loss del detector** (`0x6E`) — esto es lo más cercano a “sensibilidad” de detección de antena (no del tag):

```text
05 00 6E Param CRC
bit7=0 → leer umbral actual
bit7=1 → escribir; bit6..0 = umbral 0–20 (dB)
Default típico: 6 dB
```

Valores más altos = match de antena más estricto.

### 6.4 Medir return loss real (`0x91`) — prueba de RF

```text
09 00 91 Freq[4 BE kHz] AntIndex CRC
AntIndex: 0=ant1 … 3=ant4
Freq debe ser múltiplo de 100 o 125 kHz
```

Ejemplo 915.25 MHz, ant1:

```text
Freq = 915250 = 0x000DF6D2  (usar el valor exacto que validéis)
```

Interpretación práctica en lab:

| RL (dB) | Interpretación |
|--------:|----------------|
| ≥ ~6–10 | Antena/cable razonables, RF TX activo |
| 0 | Sospecha open/corto/desconectado |

Medido en lab @ ~915 MHz:

- Ant1 ≈ 14 dB → OK  
- Ant2/3/4 ≈ 0 dB → mal cableadas o ausentes  

---

## 7. Tiempos de inventory / filtros

### 7.1 Scan time global (`0x25`)

```text
05 00 25 Scntm CRC
Duración ≈ Scntm × 100 ms
Rango útil ~ 3…255 (manual: no poner demasiado corto)
```

También se puede pasar `ScanTime` **por comando** en inventory (ver §8).

### 7.2 Realtime pause / filter (`0x75`)

Ver §9. `FliterTime` (sic) = 0…255 segundos de dedupe por tag. `0` = reportar siempre (máxima “sensibilidad” de reporte).

### 7.3 Heartbeat realtime (`0x78`)

```text
05 00 78 Param CRC
bit7=1 escritura; bit6..0 = N → N×30 s entre heartbeats
0 = deshabilitar heartbeat
```

---

## 8. Inventory Gen2 en answer mode (`0x01`)

### 8.1 Obligatorio

Este FW **exige** al menos:

```text
Data = QValue | Session
```

Sin eso → `Status=0xFF`.

### 8.2 Parámetros

**QValue (1 byte)**

| Bits | Uso |
|------|-----|
| 7 | `1` = al final enviar paquete de estadísticas (`0x26`) |
| 6 | estrategia especial |
| 5 | Impinj FastID |
| 4 | Phase |
| 3..0 | Q (0–15). Regla: 2^Q ≈ #tags esperados |

**Session:** `0x00`=S0, `0x01`=S1, `0x02`=S2, `0x03`=S3, `0xFF`=smart  

**Opcional (los tres juntos):** `Target` (`0x00`=A / `0x01`=B) + `Ant` (`0x80`…) + `ScanTime` (×100 ms)

Mask/TID opcionales: ver manual V2.20 §8.2.1 si se necesitan.

### 8.3 Ejemplos

Inventory mínimo (Q=4, S0):

```text
06 00 01 04 00 AC 36
```

Antena 1, Target A, 1 s, Q=4, S1 (recomendado peaje / tags que permanecen):

```text
09 00 01 04 01 00 80 0A …CRC…
```

Con stats:

```text
09 00 01 84 01 00 80 0A …CRC…
```

### 8.4 Respuesta con tags

```text
Status ∈ {0x01 OK, 0x02 timeout, 0x03 more frames, 0x04 mem full}
Data = AntMask | Num | EPC1 | EPC2 | …
```

- `Num` = cantidad de EPCs en esta trama  
- Longitud de cada EPC = `len(resto) / Num` (si divide exacto)  
- `0x26` = trama de estadísticas: `Ant | ReadRate[2] | TotalCount[4]`

### 8.5 Single tag (`0x0F`)

```text
04 00 0F …CRC…
```

- `0xFB` = no hay tag en campo (muy útil para diagnóstico)  
- `0x01` / datos = tag visto  

---

## 9. Modo realtime (mejor práctica para “escuchar”)

### 9.1 Configurar parámetros (`0x75`)

Mínimo validado (sin máscara):

```text
Data = TagProtocol | ReadPauseTime | FliterTime | QValue | Session

TagProtocol: 0=6C, 1=6B
ReadPauseTime: 0=10ms, 1=20ms, 2=30ms, 3=50ms, 4=100ms
FliterTime: 0=sin filtro (reporta cada vez); N = N segundos dedupe
QValue: 0–15 (bit7 reserved=0)
Session: 0–3 o 0xFF
```

Ejemplo peaje / lab:

```text
05 bytes data: 00 00 00 04 01
→ 6C, pause 10ms, sin filtro, Q=4, Session S1
```

### 9.2 Activar / desactivar (`0x76`)

```text
05 00 76 Mode CRC
Mode: 0 = answer (default/control)
      1 = realtime inventory
      2 = realtime + trigger GPI1
```

**Persistente en flash.** Siempre dejar en `0` al cerrar la app.

### 9.3 Frames async (`reCmd=0xEE`)

**Tag detectado** `Status=0x00`:

```text
Data = Ant | Len | EPC[Len] | RSSI
```

Ejemplo real lab:

```text
EPC  = BCA002220700000000036178
RSSI ≈ 0x66–0x68
```

**Heartbeat** `Status=0x28` (si está habilitado):

```text
Data = PacketNo[4] | AntStatus… | TotalCount[4]
```

### 9.4 Flujo recomendado (México / antena N)

```text
1. connect TCP :6000
2. 0x76 = 0                  # asegurar answer
3. 0x22 = F4 00              # 902–928 MX
4. 0x2F = 21                 # 33 dBm
5. 0x66 = 00                 # ant-check off (o on si cables OK)
6. 0x3F = 80|bit(ant)        # solo antena deseada (temporal)
7. 0x75 = 00 00 00 04 01     # realtime 6C
8. 0x76 = 01                 # START listening
9. read socket → parse 0xEE frames
10. 0x76 = 00                # STOP (obligatorio)
```

---

## 10. Códigos de status (los usados)

| Status | Significado |
|-------:|-------------|
| `0x00` | OK |
| `0x01` | Inventory OK (tags reportados) |
| `0x02` | Inventory timeout (reporta lo ya leído) |
| `0x03` | Más tramas vienen |
| `0x04` | Memoria llena |
| `0x26` | Paquete de estadísticas |
| `0x28` | Heartbeat realtime |
| `0xF8` | Error de antena / desconectada |
| `0xF9` | Error de ejecución |
| `0xFA` | Tags vistos pero operación falló |
| `0xFB` | **No hay tag operable en campo** |
| `0xFC` | Error code del tag |
| `0xFD` | Longitud de comando incorrecta |
| `0xFE` | Comando ilegal / CRC malo |
| `0xFF` | Error de parámetros |

---

## 11. Info del lector (`0x21`)

```text
TX: 04 00 21 D9 6A
RX Data (status 0x00):
  Version[2]  Type  Tr_Type  dmaxfre  dminfre  Power  Scntm  Ant  Res  Res  CheckAnt
```

`Tr_Type`:

- bit1=1 → soporta 18000-6C  
- bit0=1 → soporta 18000-6B  

Lab: `Tr_Type=0x02` → **solo 6C**.

Otros útiles:

| Cmd | Función |
|-----|---------|
| `0x4C` | Serial number |
| `0x92` | Temperatura (`PlusMinus`, `Temp`) |
| `0x94` | Potencia por antena |
| `0x77` | Leer params work/realtime mode |
| `0x18` | Inventory a buffer |
| `0x73`/`0x74`/`0x72` | Clear / count / get buffer |

---

## 12. RSSI (referencia)

El byte RSSI en realtime es un índice; tablas del manufacturer mapean ~`0x62`≈−31 dBm … `0x1F`≈−98 dBm. En práctica: **mayor hex ≈ señal más fuerte** en muchas tablas de estos lectores. Valores lab del tag peaje: `0x65`–`0x68`.

---

## 13. Ejemplo mínimo extremo a extremo (Python)

Ver módulo: [`../src/frd950/client.py`](../src/frd950/client.py)

```python
from frd950 import Frd950

with Frd950("192.168.1.190", 6000) as r:
    r.configure_mexico_toll(power_dbm=33, antennas=[1])
    tags = r.listen_realtime(seconds=30, q=4, session=1, filter_time=0)
    for t in tags:
        print(t.epc, t.rssi, t.count)
```

Tag leído en lab:

```text
EPC: BCA002220700000000036178
```

---

## 14. Checklist de puesta en marcha en otro sitio

1. Misma VLAN/IP; ping + TCP `6000`.  
2. `0x21` responde → protocolo OK.  
3. `0x22` región correcta (MX=`F4 00`).  
4. `0x2F` potencia (probar 20…33 dBm).  
5. `0x91` return loss por puerto → detectar antenas muertas.  
6. `0x3F` habilitar solo antenas con RL sano.  
7. Realtime `0x75`+`0x76=1` y parsear `0xEE`.  
8. Si `0xFB` / 0 tags: acercar tag Gen2, revisar polarización / vidrio metalizado.  
9. Al salir: `0x76=0`.

---

## 15. Referencias

- *UHF RFID Reader Series User Manual V2.20* (protocolo Len+CRC16)  
- Norma peaje México: air interface **ISO 18000-6C @ 902–928 MHz** (IAVE/PASE/Televía Gen2; 6B legacy discontinuado)  
- Hardware: Faread FRD950-A8 / Impinj E710  
- En este paquete: `src/frd950/`, `ejemplos/`, `docs/02_CONTEXTO_LAB.md`

---

## 16. Mapa rápido de comandos implementados

| Cmd | Hex | Data | Persistente |
|-----|-----|------|-------------|
| Info | `21` | — | — |
| Set freq | `22` | MaxFre MinFre | sí |
| Set addr | `24` | Adr | sí |
| Set scan time | `25` | Scntm | sí |
| Set power | `2F` | Power | sí |
| Beep/LED | `33` | … | — |
| Ant mux | `3F` | Ant | bit7 |
| Beep enable | `40` | … | — |
| Serial | `4C` | — | — |
| Ant check | `66` | 0/1 | — |
| RL threshold | `6E` | flags+dB | sí |
| Buffer get/clear/count | `72`/`73`/`74` | … | — |
| RT params | `75` | ver §9 | — |
| Work mode | `76` | 0/1/2 | **sí** |
| Get mode | `77` | — | — |
| Heartbeat | `78` | … | — |
| Measure RL | `91` | freq+ant | — |
| Temp | `92` | — | — |
| Stop inv | `93` | — | — |
| Power/ant | `94` | — | — |
| Inventory 6C | `01` | Q Session [Target Ant Scan] | — |
| Single 6C | `0F` | — | — |
| Inventory 6B | `50` | — | — |
