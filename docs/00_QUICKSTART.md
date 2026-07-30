# Quickstart FRD950 (5 minutos)

## 1. Red

```bash
ping 192.168.1.190
nc -vz 192.168.1.190 6000
```

## 2. Lectura antena 1 (México peaje)

Desde la raíz de `entrega_frd950`:

```bash
PYTHONPATH=src python3 ejemplos/leer_antena1.py --host 192.168.1.190 --seconds 30
```

Esperado: líneas con EPC hex (ej. `BCA002220700000000036178`).

## 3. Si no lee tags

```bash
PYTHONPATH=src python3 ejemplos/medir_antenas.py --host 192.168.1.190
```

- Antena con return loss **≈ 0 dB** → cable/antena mal.  
- Return loss alto y aún 0 tags → acercar tag Gen2 / revisar orientación.

## 4. Preset que usa el ejemplo

| Paso | Comando | Valor |
|------|---------|-------|
| Modo | `0x76` | answer `0` luego realtime `1` |
| Región | `0x22` | `F4 00` (902–928 MHz) |
| Potencia | `0x2F` | `21` (33 dBm) |
| Antena | `0x3F` | solo ant1 |
| Ant-check | `0x66` | off |
| RT params | `0x75` | 6C, Q=4, Session S1 |

Detalle completo: [`01_IMPLEMENTACION.md`](01_IMPLEMENTACION.md).
