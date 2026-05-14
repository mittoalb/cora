# Standards terms

*ISA, ISO/IEC, NIST, PROV-O, RAiD.*

- **ISA-95.** Manufacturing operations hierarchy: Enterprise / Site / Area / Unit / Assembly / Device. Used for the Asset model.
- **ISA-88.** Batch control. Basis for Track A (Method / Practice / Plan / Run).
- **ISA-106.** Continuous-process operations. Basis for Track B.
- **ISA-99 / IEC 62443.** Industrial cybersecurity. Basis for Track C: Zones, Conduits, Policies (`trust` BC).
- **ISO/IEC 42001 + NIST AI RMF.** AI governance frameworks. Inform Decision and Strategy BCs.
- **W3C PROV-O.** Provenance ontology. Borrowed at API boundaries (Activity, Entity, Agent, used, wasGeneratedBy). W3C Provenance Working Group is closed; PROV-O is frozen 2013 bedrock vocabulary, not a moving spec. Community momentum lives in downstream consumers (RO-Crate, FAIRSCAPE).
- **RAiD (ISO 23527).** Research Activity Identifier. Forward-compat field on `RunStarted`.

Watch-only (not adopted as a glossary term, see [Deferred](../stack/deferred.md)):

- **PIDINST.** RDA-WG recommendation for persistent IDs of physical instruments, layered on DataCite Schema 4.5+ via `resourceTypeGeneral=Instrument`. Adoption is thin (HZB at BESSY II is the only confirmed photon-science adopter as of 2026), so CORA treats it as a watch item rather than a standard. The Asset model reserves capacity for a publication-quality persistent ID; the minting profile (PIDINST vs raw DataCite Instrument resourceType vs other) is decided when first needed.
