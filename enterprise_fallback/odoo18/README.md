# Odoo Community fallback cell (development prototype)

This is a self-hosted **original Odoo Community 18.0** software track for an enterprise computer-use benchmark. The actor uses Odoo's browser GUI. Environment-owned XML-RPC seeds disposable records; a separate PostgreSQL role with `SELECT` but no `UPDATE` reads persisted state for scoring. Neither an imitation application nor an API-only actor result qualifies as a computer-use success.

The isolated local development world now has **four causal workflows** in the original Odoo Community interface:

| Workflow | Public development candidates | Source visible to actor | Target state |
| --- | ---: | --- | --- |
| Purchase RFQ reconciliation | 120 three-line RFQs across eight fault patterns | A supplier confirmation PDF attached to each Odoo RFQ | Line quantities, prices, and promised dates; preserve all other RFQs, attachment bytes, supplier, and draft state |
| Inventory replenishment | 20 SKU/location rules | A four-week demand and lead-time planning note on each Odoo product's Purchase tab | Compute and set minimum/maximum at WH/Stock; preserve other rules and product notes |
| Sales quotation reconciliation | 20 three-line quotations, with one to three quantity/price faults and a wrong customer PO reference | Synthetic customer PO PDF in the quotation's native attachment viewer | Repair customer reference and line values; preserve customer, order state, discounts, unrelated quotations and every attachment |
| CRM opportunity handoff | 20 opportunities across three target stages, three salespeople, varying revenue, closing dates and priority | Synthetic handoff PDF in the opportunity's native attachment viewer | Repair stage, assignee, forecast, close date and priority; preserve customer, original notes, unrelated opportunities and attachments |

The 120 RFQs contain 20 selection candidates and 100 **unsealed scale candidates**. They reuse the same eight fault patterns, 24 synthetic vendors, and 48 synthetic SKUs. The exact selection/scale overlap is **0 IDs, 20 vendors, 36 SKUs, and all 8 fault patterns**. They are *not* 100 independent hidden tasks, a leak-safe split, or an official final denominator. The Inventory cases use 20 different SKUs but one planning formula family. Sales and CRM are separate 20-case development pools, not extra admitted final tasks. Their customer entities overlap across families and are not hidden. The separate `train_world_candidates(world_seed)` function reproducibly generates 40 **undeployed** train-only RFQ candidate identities with zero overlap in RFQ IDs, vendor names, and SKUs against both selection and scale candidates. A future official study must instantiate entity-disjoint train/selection/final worlds for all four families, freeze a private evaluation seed and source-family split, and run fresh GUI admission on every task before any model campaign.

`proposed_clustered_split(world_seed)` is a separate **undeployed repair blueprint**: 40 train, 20 selection, and 100 evaluation-candidate RFQs; each split has its own vendor and SKU namespace, with five cases per vendor and zero ID/vendor/SKU overlap. All eight fault patterns still appear in every split. If used, the endpoint must be preregistered as **within-template generalization**; novel-template transfer requires additional independently designed task families and a different split. The generator is public and example seeds are not hidden; no output from it is a sealed final task.

The only authentic historical values in this development world are the **112 unmodified Costco/Walmart SEC companyfacts observations** attached as a separate reference excerpt on the synthetic company record. These public filing facts are not purchase orders, supplier confirmations, demand forecasts, or benchmark gold. All operational entities and documents are synthetic. The source URL and raw JSON digest remain in [`retail_excerpt.json`](../../sec_excel_factory/sources/retail_excerpt.json). We do not claim that an SEC filing or its narrative is open-licensed merely because it is publicly accessible.

## Reproduce locally

Use Python 3.10 or newer, Docker Compose, and the repository's `report` extra.

The [`compose.yaml`](compose.yaml) pins Odoo and PostgreSQL by OCI digest. Docker Compose publishes the Odoo GUI on loopback only (`8078` by default); PostgreSQL has no host port. Odoo's database manager is disabled with `--no-database-list`, confirmed by the page's disabled banner. `bootstrap.py` checks that its loopback port is unoccupied before creating credentials, creates a private mode-0600 `.env`, rotates Odoo's temporary default admin password, installs Community modules, seeds all four workflows, creates a read-only SQL role, freezes a scoped baseline, and checkpoints **both** PostgreSQL and Odoo's physical filestore. `ODOO_PROJECT` and `ODOO_PORT` may select an isolated worker at first bootstrap. Readiness requires a responding Odoo XML-RPC version endpoint; an unrelated service's login page is insufficient. It does not use a cloud account or paid service.

```bash
python3 -m pip install -e '.[report,browser]'
python3 enterprise_fallback/odoo18/bootstrap.py
python3 enterprise_fallback/odoo18/verify.py score ELPO-0005
python3 enterprise_fallback/odoo18/verify.py score ELRP-0001
python3 enterprise_fallback/odoo18/verify.py score ELSQ-0001
python3 enterprise_fallback/odoo18/verify.py score ELCRM-0001
python3 enterprise_fallback/odoo18/reset.py restore
python3 enterprise_fallback/odoo18/gui_controls.py
python3 -m unittest tests/test_odoo_fallback_factory.py -v
```

Fresh cases should start from `reset.py restore`. `gui_controls.py` itself cold-restores the local worker before and after its Sales and CRM controls, so run it only against a disposable benchmark worker. `sweep_development.py --family all` similarly restores between every unsealed Sales/CRM case; the observed 40/40 [per-case receipt](../../docs/evidence/odoo-community-development-gui-sweep-2026-09-25.json) is an environment-solvability check, not official task admission. `verify.py score <case>` must run only after actor GUI work and must use the evaluator's private gold and frozen snapshot in ignored `private/`. It compares protected attachment store paths and physical source bytes while allowing Odoo to generate unrelated runtime cache files. The original four GUI-positive cases and two wrong-object controls in the [earlier evidence note](../../docs/evidence/odoo-community-fallback-2026-09-25.md), plus the new controls in the [four-family evidence note](../../docs/evidence/odoo-community-four-family-gate-2026-09-25.md), remain development checks; none has an official final identity. The baseline checkpoint should never be published because it contains local credentials and evaluator material. A production worker must receive a distinct `ODOO_PROJECT`, port, private checkpoint, and sealed gold. The current bootstrap is deliberately one-shot for one local worker.

## Next workflow contracts

1. **Purchase receipt against PO:** seed confirmed POs, incoming stock pickings, partial receipts, lot numbers, and backorders. The actor reconciles received quantities and lot IDs in the Inventory GUI. A read-only verifier checks `stock_picking`, `stock_move`, and `stock_move_line`, plus untouched RFQs and valuation effects; reset restores database, filestore, and worker session. This family is designed, **not implemented or admitted**.
2. **Vendor bill variance and credit:** seed an Odoo vendor bill, confirmed receipt, and supplier credit memo with mixed tax/currency cases. The actor repairs bill lines and credit allocation in the Invoicing GUI. A read-only verifier checks `account_move`/`account_move_line`, reconciliation and tax totals, and no unrelated postings. Company accounting setup and independent GUI controls are **pending**.
3. **Approval and permissions:** seed buyer, inventory, and finance roles with separate actor sessions; submit a purchase request for approval without granting extra privileges. The verifier reads business state and `res_users`/group memberships, and reset includes all profiles and sessions. This is **design only** and requires a security review before use.

Odoo 18.0's [source license is LGPLv3](https://github.com/odoo/odoo/blob/18.0/LICENSE), its [official container image](https://hub.docker.com/_/odoo) is maintained by Odoo, and PostgreSQL is distributed under the [PostgreSQL License](https://www.postgresql.org/about/licence/). The [Odoo deployment documentation](https://www.odoo.com/documentation/18.0/administration/on_premise/deploy.html) describes database-manager restrictions. The [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) supplies the historical reference observations; the operational fixture is original EnvLoop synthetic data.
