# FRD950 / Impinj E710 — Estado de integración TCP

Documento para retomar el contexto: qué se intentó, qué protocolo funciona, y por qué aún no hay lecturas de tags.

## Hardware

- **Lector:** Faread FRD950-A8 (fixed reader, motor RF Impinj E710)
- **IP / puerto:** `192.168.1.190:6000` (TCP)
- **Antenas:** 4 puertos; trabajo hecho sobre todo en **antena 1**
- **Host de prueba:** Mac en `192.168.1.100`, interfaz `en5`
- **Fecha pruebas:** 2026-07-30

## Hallazgo principal: protocolo correcto

**No** es el framing `BB … 7E` (M100/módulo UART).  
**No** es el framing `A0 Len Addr Cmd … checksum` (Serial Interface V3 / e710_uhf crate).

**Sí** es el protocolo chino clásico de lectores fijos:

```
Len | Adr | Cmd | Data[] | LSB-CRC16 | MSB-CRC16
```

- `Len` = cantidad de bytes desde `Adr` hasta `MSB-CRC16` inclusive (= `len(Data) + 4`)
- `Adr` default `0x00` (broadcast `0xFF` también responde en info)
- CRC-16: preset `0xFFFF`, poly `0x8408`, resultado **LSB primero**
- Manual de referencia: *UHF RFID Reader Series User Manual V2.20* (mismo dialecto que DL920 / clones puerto 6000)

### CRC (Python)

```python
def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def frame(addr: int, cmd: int, data: bytes = b"") -> bytes:
    body = bytes([addr, cmd]) + data
    partial = bytes([len(body) + 2]) + body
    return partial + crc16(partial)
```

### Comandos que SÍ responden

| Cmd | Uso | Notas |
|-----|-----|--------|
| `0x21` | Get reader information | OK |
| `0x22` | Set frequency band / points | OK (Korea rechazada) |
| `0x25` | Set inventory scan time | OK |
| `0x2F` | Set RF power | Acepta hasta **33 dBm** (`0x21`) |
| `0x3F` | Antenna multiplexing | OK |
| `0x66` | Antenna check on/off | OK |
| `0x01` | Inventory | **Requiere al menos Q + Session**; bare `04 00 01 …` → status `0xFF` (parameter error) |
| `0x75` / `0x76` | Realtime params / work mode | OK (answer=0, realtime=1) |
| `0x91` | Measure return loss | Necesita freq(kHz, 4B BE) + ant index |
| `0x92` | Temperature | OK |
| `0x4C` | Serial number | OK |
| `0x94` | Power per antenna | Devuelve `21 21 21 21` a 33 dBm |

### Inventory mínimo que funciona

```text
TX: 06 00 01 04 00 AC 36
    Len=06 Adr=00 Cmd=01 Q=04 Session=00 CRC
RX tipico sin tags: 07 00 01 01 01 00 …
    status=0x01 (inventory OK), Ant=0x01, Num=0
```

Con Target + Ant + ScanTime (los tres juntos):

```text
09 00 01 04 00 00 80 14 …   # Q=4 S0 Target=A Ant1=0x80 ScanTime=0x14 (2s)
```

Códigos Ant en inventory: `0x80`=ant1 … `0x83`=ant4.

### Info del lector (ejemplo)

```text
RX: 11 00 21 00 02 08 75 02 31 80 …
Data: Version=2.8, Type=0x75, TrType=0x02 (ISO18000-6C),
      dmaxfre/dminfre = banda US puntos 0–49 → 902.75–927.25 MHz,
      Power, Scntm, Ant, …, CheckAnt
```

## Qué se descartó

1. Frames `BB 00 03/04/22/27 … 7E` (incluso con checksum M100 correcto) → **sin respuesta**
2. Frames `A0 03 FF 72 …` (firmware E710 V3) → **sin respuesta**
3. Inventory sin parámetros → **parameter error (`0xFF`)**
4. Work-mode “answer” del blog DL920 (`0x0A 00 35 …`) → **command length error (`0xFD`)** en este FW (el set mode correcto es `0x76`)

## Evidencia de que el RF / stack sí trabaja

- TCP conecta y ACK de datos siempre.
- Potencia sube y se refleja en `0x21` / `0x94`: **33 dBm**.
- `0x91` return loss en **antena 1 @ 915 MHz ≈ 14 dB** → camino RF vivo + antena presente.
- Antenas **2, 3, 4 → return loss 0 dB** → muy probable cable/antena mal o desconectada.
- Temperatura sube durante inventory (p.ej. 29 → 31 °C).
- Inventory/realtime completan con status OK, no `0xF8` (antenna error) en ant1.

## Problema pendiente: 0 tags

En antena 1, a 33 dBm, en:

- answer-mode inventory continuo
- realtime mode (`0x76=1`, Q=4, Session S1, pause 10 ms)
- 1 minuto por antena (4 antenas)
- bandas: **US, EU, EU3, China1, China2, Taiwan, US3** (~25 s c/u en ant1)

→ **siempre `Num=0` / ningún frame `0xEE` con EPC**.

Korea no la aceptó el lector (`0xFF`).

Al final se restauró banda **US** y work mode **answer**.

## Scripts en el repo

- `frd950_probe.py` — sondas de protocolo / comandos
- `frd950_listen.py` — 60 s realtime por antena

## Cómo seguir (recomendaciones)

1. **Físico ant1:** tag UHF Gen2 pegado / a &lt;30 cm de la antena correcta del puerto 1; confirmar cono de polarización.
2. **Cables ant2–4:** RL=0 dB; no esperar lecturas ahí hasta arreglar RF.
3. Confirmar que los tags son **EPC C1G2** y no solo HF/NFC.
4. Si hay demo del fabricante (DLL / Windows), capturar con `tcpdump` el inventory que sí lea y comparar bytes.
5. Probar `0x18` (inventory con buffer) + `0x72`/`0x74` por si el FW reporta distinto en buffer mode.
6. No insistir en protocolos BB/A0: este equipo habla Len+CRC16 V2.x.

## Snippet rápido “¿está vivo?”

```python
# info
print(frame(0x00, 0x21).hex(" "))
# inventory ant1 Q=4 Session=1 Target=A ScanTime=1s
print(frame(0x00, 0x01, bytes([0x04, 0x01, 0x00, 0x80, 0x0A])).hex(" "))
```

Status útiles: `0x00` OK, `0x01` inventory OK, `0xFB` no tag (en algunos flujos), `0xF8` antenna error, `0xFF` parameter error, `0xFD` length error.

## Actualización (mismo día, lectura exitosa)

Con banda **México peaje US3 902–928 MHz**, ant1 @ 33 dBm, realtime:

```text
EPC: BCA002220700000000036178
RSSI ≈ 0x66–0x68
```

Documentación completa de implementación: [`01_IMPLEMENTACION.md`](01_IMPLEMENTACION.md)  
Cliente Python reutilizable: [`../src/frd950/client.py`](../src/frd950/client.py)

## Conclusión en una frase

El FRD950 en `:6000` habla **Len+CRC16**; región peaje MX **902–928**; protocol stack OK; la lectura depende de tener un Gen2 en el campo de una antena con RF sano.
