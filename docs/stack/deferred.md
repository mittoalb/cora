# Deferred

*Picks held until a real consumer demands them. Each has a trigger.*

| Pick | Candidates | Trigger |
| --- | --- | --- |
| Streaming bus | NATS JetStream vs in-process | First cross-BC saga |
| Cache | Redis vs in-process | First read pattern that needs it |
| Search index | Meilisearch vs Postgres FTS | First user-facing search query |
| File / blob storage | filesystem vs S3-compatible (MinIO, R2, S3) | First non-local Dataset volume |
| Container orchestration | Helm, Argo CD | First non-local deployment |
| Authz engine | SpiceDB vs OpenFGA | First non-Cedar authz rule |
| Snapshot store | In-events vs sidecar table | Fold-on-read becomes a measurable bottleneck |
| Outbox | Table-based vs NOTIFY-only | First cross-process consumer needing at-least-once |
| Background scheduler | in-process (current) vs APScheduler vs Temporal | First job that needs to outlive a process |
| LLM provider + embedding | OpenAI vs Anthropic vs local (Ollama) | Reasoning generation lands (today only stored) |
| Backup / PITR | pgBackRest vs WAL-G vs managed | First non-local deployment |
| Secrets management | Vault, cloud, sealed-secrets | First non-local deployment |
| TLS / load balancer | nginx vs Caddy vs cloud LB | Deployment chooses its proxy |
| Docs site generator | mkdocs, Docusaurus | If docs outgrow GitHub's renderer |
| Versioning / release | hatch + setuptools_scm vs custom | First external consumer of the API or library |
| Asset persistent ID profile | PIDINST profile vs raw DataCite Schema 4.6 `Instrument` resourceType vs ePIC Handle | First Asset that needs publication-quality cross-facility identity (paper citation, cross-facility share). PIDINST adoption is thin (HZB at BESSY II is the only confirmed photon-science adopter as of 2026); CORA + APS would be peer #2. |
| Release-hygiene bundle | CycloneDX SBOM (Syft) + Sigstore (PyPI Trusted Publishing or cosign on containers) + SLSA L1-L2 (GitHub Actions native attestations) + in-toto attestation envelope (cross-trust egress) | CORA's release / distribution surface decided (PyPI wheel? container image? source-only?) |
| Experiment-bundle format | RO-Crate 1.2 (Process Run Crate / Workflow Run Crate profile) vs raw HDF5 + sidecar metadata | First external publishing of an experiment bundle (Zenodo, institutional repository, MAX IV data portal) |
