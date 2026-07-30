# Entrega FRD950 — Integración lector UHF (Impinj E710)

**Paquete de entrega** para implementar y operar el lector fijo Faread **FRD950-A8** vía TCP.

| Campo | Valor |
|-------|--------|
| Fecha | 2026-07-30 |
| Equipo validado | FRD950-A8 @ `192.168.1.190:6000` |
| Protocolo host | Len + Adr + Cmd + Data + CRC16 |
| Caso de uso | Lectura tags ISO 18000-6C / peaje México (IAVE, PASE, Televía) |
| Lenguaje de referencia | Python 3.10+ (solo stdlib) |

---

## Contenido de la carpeta

```text
entrega_frd950/
├── README.md                 ← este archivo (índice de entrega)
├── ENTREGA.md                ← checklist / qué se entrega y qué se validó
├── requirements.txt          ← sin dependencias externas
├── docs/
│   ├── 00_QUICKSTART.md      ← arranque en 5 minutos
│   ├── 01_IMPLEMENTACION.md  ← guía completa (protocolo, región, potencia, antenas…)
│   ├── 02_CONTEXTO_LAB.md    ← bitácora de laboratorio / lo que NO funciona
│   └── 03_REFERENCIA_RAPIDA.md
├── src/frd950/
│   ├── __init__.py
│   └── client.py             ← cliente TCP reutilizable
└── ejemplos/
    ├── leer_antena1.py
    ├── medir_antenas.py
    └── inventario_answer.py
```

---

## Cómo usar el cliente

```bash
cd entrega_frd950
PYTHONPATH=src python3 ejemplos/leer_antena1.py --host 192.168.1.190
```

O:

```bash
PYTHONPATH=src python3 -m frd950.client --host 192.168.1.190 --ant 1 --power 33 --seconds 20
```

```python
import sys
sys.path.insert(0, "src")
from frd950 import Frd950

with Frd950("192.168.1.190") as r:
    r.configure_mexico_toll(power_dbm=33, antennas=[1])
    for t in r.listen_realtime(seconds=30):
        print(t.epc, t.rssi, t.count)
```

---

## Lectura por dónde empezar

1. **Operador / integrador rápido** → [`docs/00_QUICKSTART.md`](docs/00_QUICKSTART.md)
2. **Desarrollador (cualquier lenguaje)** → [`docs/01_IMPLEMENTACION.md`](docs/01_IMPLEMENTACION.md)
3. **Cheatsheet comandos** → [`docs/03_REFERENCIA_RAPIDA.md`](docs/03_REFERENCIA_RAPIDA.md)
4. **Contexto de por qué se eligió este protocolo** → [`docs/02_CONTEXTO_LAB.md`](docs/02_CONTEXTO_LAB.md)

---

## Parámetros clave (México peaje)

| Parámetro | Valor |
|-----------|--------|
| TCP | `IP:6000` |
| Región | US band3 → **902–928 MHz** (`MaxFre=0xF4`, `MinFre=0x00`) |
| Potencia | hasta **33 dBm** |
| Protocolo aire | ISO 18000-6C (EPC Gen2) |
| Modo lectura continuo | Realtime (`0x76=1`) tras `0x75` |
| Antena de prueba OK | Puerto 1 (return loss ~14 dB en lab) |

Tag leído en laboratorio:

```text
EPC: BCA002220700000000036178
```

---

## Licencia / uso

Código y documentación generados para DoHealth / integración interna del lector. Adaptar IP, potencia y antenas al sitio de instalación.
