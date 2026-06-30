# One-Way Data Transfer Mechanism ("Data Diode") / 单向数据传输机制

Implements the contract's core security architecture (Argo Finance Skills,
Articles 2.2 / 2.3 / 3.3 / 10.4): public external intelligence may flow **into**
the internal system, but the firm's private data must **never** flow out.

> **中文摘要：** 本模块实现合同的核心安全原则——*公开情报只能"外→内"流入内部知识库，
> 内部私有数据永远不能外流*。它是**用户可选**的：可整体开关（`MIRRORQUANT_DIODE_ENABLED`），
> 并可选择传输方案（`MIRRORQUANT_DIODE_MODE` = `software` 软件单向通道 / `offline` 离线导入 /
> `physical` 物理数据二极管）。诚实声明：软件模式**不等于**物理数据二极管。

---

## Architecture

```
External public information
   → External Intelligence Machine  (staging: IntelligencePacket)
   → One-Way Transfer Gate          (mirrorquant_demo/data_diode.py)
   → Internal Knowledge Base        (knowledge_base.ingest_document)
```

Data only ever moves **external → internal**. There is no function or endpoint
anywhere that moves internal data outward — by design.

## User-selectable configuration (per deployment)

Set in `.env` (see `.env.example`). All values are read at call time, so a
restart applies changes.

| Variable | Values | Meaning |
|----------|--------|---------|
| `MIRRORQUANT_DIODE_ENABLED` | `true` (default) / `false` | Turn the whole subsystem on/off. When off, `/api/diode/ingest` and `/transfer` return **503**; `/policy` still reports `enabled: false`. |
| `MIRRORQUANT_DIODE_MODE` | `software` (default) / `offline` / `physical` | The transfer scheme (see below). |
| `MIRRORQUANT_DIODE_SOURCE_WHITELIST` | comma-separated, blank = allow-all | Restrict which sources may pass the gate. |

### Modes / 模式

- **`software`** — software-defined one-way trust channel: classification +
  source whitelist + internal-content scanning + audit. *Not equivalent to a
  physical one-way data diode; no physical link-level isolation guarantee
  (contract Art. 10.4).* 软件单向通道（默认）。
- **`offline`** — offline-media import: transfers require an explicit manual
  confirmation (`confirm=true`), modelling air-gapped offline import. 离线导入，
  需人工确认。
- **`physical`** — a physical one-way data diode is installed: hardware
  link-level isolation; the software checks remain as defence-in-depth. The
  policy reports `physical_diode_equivalent: true`. 物理数据二极管（硬件隔离）。

## How the gate works

1. **Submit** (`submit_packet`) — the External Intelligence Machine stages a
   packet. Rejected (and stored as `rejected`) if the classification is not
   `public`, or if the content matches internal/confidential markers
   (`CONFIDENTIAL`, `holdings`, `trading plan`, `内部`, `机密`, `内幕`, `持仓`, …).
   Internal data must never even enter the external machine.
2. **Transfer** (`transfer_packet`) — the one-way gate re-validates
   classification + source whitelist + content scan (defence-in-depth). In
   `offline` mode it also requires `confirm=true`. On success the packet content
   is ingested as an **internal** knowledge-base document — the only direction
   data ever flows.

Every submit / transfer / rejection is written to the audit log.

## API

| Method & path | Role | Purpose |
|---------------|------|---------|
| `GET  /api/diode/policy` | verified | Current policy: `enabled`, `mode`, whitelist, isolation guarantees, honesty note. |
| `POST /api/diode/ingest` | analyst+ | Stage a public intelligence packet. |
| `GET  /api/diode` | verified | List packets (optional `?status=staged|transferred|rejected`). |
| `POST /api/diode/packets/{id}/transfer?confirm=…` | analyst+ | One-way transfer into the internal KB. |

All analytical responses carry the standard `compliance` block.

## Security model (enforced invariants)

- ✅ Direction is **external → internal only**; no internal-egress path exists.
- ✅ Only `public`-classified content can enter or cross the gate.
- ✅ Internal/confidential markers → rejected at submit **and** at the gate.
- ✅ Optional source whitelist.
- ✅ Full audit trail (`audit_logs`).

## Honesty caveat / 诚实声明

The `software` and `offline` modes are **software-defined** controls. Per
contract Article 10.4 they are **NOT equivalent to a physical one-way data
diode** and provide no physical link-level isolation guarantee. For deployments
holding MNPI / confidential holdings, select `physical` mode with a real hardware
diode (separately procured per the contract).
