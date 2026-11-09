# Personal AI Decision Hub — Architecture Handoff Kit

Version: v1.4 Research and Implementation Roadmap (November 8, 2026)

## Read in order

1. `baseline/v1.2_Requirements_Architecture_EN.md` — canonical architecture and original requirements, not implemented yet.
2. `baseline/v1.3_Multi_Agent_Organization_Research_EN.md` — proposed hierarchical agent extension and case/framework research.
3. `AI_Decision_Hub_Multi_Agent_Implementation_Roadmap_v1.4_EN.md` — new implementation path, selected architecture, gates, 30 ordered tasks and research spikes.

## Which files are editable?

The Markdown documents and `diagrams/diagram_01.mmd` … `diagram_05.mmd` are the authoritative editable sources. The Word file is a generated review edition with rendered figures and equivalent information. Word uses shorter blocks rather than wide landscape tables for the roadmap and build backlog.

The figure PNGs are review derivatives; edit `.mmd` source instead. The ZIP includes the source diagrams but does not include interim QA images or build scripts.

## First action

Review and approve milestone M0 (baseline decisions). Set up the repository, write ADRs, verify provider access, and create M1 implementation tickets. Do not begin Agent Factory or remote-code execution yet.

## Version control

A requirement change should update its ID, affected API/schema/diagram, acceptance tests, migration strategy and ADR, all within one Git pull request.
