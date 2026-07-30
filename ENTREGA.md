# Acta de entrega — FRD950

## 1. Objeto

Entregar documentación y código de referencia para integrar el lector UHF **FRD950-A8 (Impinj E710)** por TCP puerto **6000**, incluyendo configuración de región (México peaje), potencia, antenas, modos de inventory y cliente Python de ejemplo.

## 2. Entregables

| # | Entregable | Ubicación | Estado |
|---|------------|-----------|--------|
| 1 | Guía completa de implementación | `docs/01_IMPLEMENTACION.md` | Incluido |
| 2 | Bitácora de laboratorio / contexto | `docs/02_CONTEXTO_LAB.md` | Incluido |
| 3 | Quickstart | `docs/00_QUICKSTART.md` | Incluido |
| 4 | Referencia rápida de comandos | `docs/03_REFERENCIA_RAPIDA.md` | Incluido |
| 5 | Cliente Python `Frd950` | `src/frd950/` | Incluido / probado |
| 6 | Ejemplos de uso | `ejemplos/` | Incluido |
| 7 | README de paquete | `README.md` | Incluido |

**No incluido:** DLL del fabricante, firmware del lector, SDK Windows, capturas tcpdump crudas.

## 3. Validación en laboratorio (2026-07-30)

| Prueba | Resultado |
|--------|-----------|
| TCP `192.168.1.190:6000` | OK |
| Protocolo Len+CRC16 | OK |
| Protocolos BB…7E y A0… | Sin respuesta (descartados) |
| Región US3 902–928 (México) | OK |
| Potencia 33 dBm | OK |
| Return loss ant1 | ~14 dB (OK) |
| Return loss ant2–4 | 0 dB (cables/antenas a revisar en sitio) |
| Realtime inventory ant1 | OK — EPC `BCA002220700000000036178` |
| Cliente `frd950.client` smoke test | OK |

## 4. Dependencias

- Python ≥ 3.10 recomendado (3.9+ debería bastar)
- Solo biblioteca estándar (`socket`, `dataclasses`, …)
- Red IP hasta el lector, puerto TCP 6000 abierto

## 5. Responsabilidades del integrador en sitio

1. Asignar IP / VLAN y verificar `ping` + TCP 6000.  
2. Conectar antenas; medir return loss (`ejemplos/medir_antenas.py`).  
3. Ajustar potencia según normativa local (lab usó 33 dBm).  
4. Usar región 902–928 para tags de caseta México.  
5. Al detener la app, dejar modo answer (`0x76=0`).

## 6. Contacto / continuidad

Repositorio origen: proyecto `dohealth`.  
Paquete autocontenido: carpeta `entrega_frd950/`.
