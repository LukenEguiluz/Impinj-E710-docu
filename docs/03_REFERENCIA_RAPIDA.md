# Referencia rápida — comandos FRD950

Trama: `Len | Adr | Cmd | Data | CRC16_LSB | CRC16_MSB`  
CRC: preset `0xFFFF`, poly `0x8408`, LSB primero. Cubre `Len…Data`.

## Construir frame (Python)

```python
def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def frame(addr, cmd, data=b""):
    body = bytes([addr, cmd]) + data
    p = bytes([len(body) + 2]) + body
    return p + crc16(p)
```

Vectores: `frame(0,0x01)→04 00 01 DB 4B` · `frame(0,0x21)→04 00 21 D9 6A`

## Comandos más usados

| Hex | Nombre | Data | Notas |
|-----|--------|------|-------|
| `21` | Info | — | FW, banda, power, ants |
| `22` | Frecuencia | MaxFre MinFre | MX peaje: `F4 00` |
| `25` | Scan time | Scntm | ×100 ms |
| `2F` | Potencia | 0…33 | max `21` = 33 dBm |
| `3F` | Ant mux | bitmask | bit0=ant1; bit7=temporal |
| `66` | Ant check | 0/1 | off recomendado si RL dudoso |
| `75` | RT params | proto pause filter Q sess | ej. `00 00 00 04 01` |
| `76` | Work mode | 0/1/2 | **0=answer, 1=realtime** |
| `91` | Return loss | freq_kHz[4BE] + antIdx | prueba RF |
| `92` | Temperatura | — | |
| `94` | Power/ant | — | 4 bytes |
| `01` | Inventory | **Q Session** [T Ant Scan] | sin Q/S → `0xFF` |
| `0F` | Single inv | — | `0xFB` = no tag |

## Regiones (MaxFre, MinFre)

| Región | Data | MHz |
|--------|------|-----|
| **México peaje / US3** | `F4 00` | 902–928 |
| US | `31 80` | 902.75–927.25 |
| EU | `4E 00` | 865.1–867.9 |
| EU3 | `83 40` | 865.7–867.5 |

## Antenas

| Puerto | Mux bit (`0x3F`) | Inv code (`0x01`) |
|-------:|------------------:|------------------:|
| 1 | `0x01` / temp `0x81` | `0x80` |
| 2 | `0x02` / `0x82` | `0x81` |
| 3 | `0x04` / `0x84` | `0x82` |
| 4 | `0x08` / `0x88` | `0x83` |

## Realtime tag frame

`reCmd=0xEE` `Status=0x00` → `Ant | Len | EPC[Len] | RSSI`

## Status cortos

`00` OK · `01` inv OK · `FB` no tag · `F8` ant error · `FF` param · `FD` length · `FE` ilegal

## Flujo mínimo MX ant1

```text
76:00 → 22:F400 → 2F:21 → 66:00 → 3F:81 → 75:0000000401 → 76:01
… leer 0xEE …
76:00
```
