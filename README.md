# Literature Radar Website

Public, cumulative literature browser for rectenna, passive backscatter temperature sensing, polarization robustness, multiport/DC-combining energy harvesting, and related RF topics.

Website: https://zhangxiaoming12138.github.io/research-literature-radar-site/

## Data architecture

This repository is a **publication target**, not an independent literature-discovery pipeline. The authoritative private `research-literature-radar` workflow performs multi-source discovery, deduplication, current-profile relevance scoring, feedback application, and privacy-safe export. Only the generated public artifacts are pushed here.

This avoids the previous split-brain design where the public repository independently queried OpenAlex and assigned new records `score=0 / 自动发现`, causing the public site to drift away from the private radar's relevance semantics.

`.github/workflows/update.yml` now validates schema integrity, UTF-8 rendering, deduplication, and the privacy boundary. It no longer mutates `papers.json` from a second search pipeline.

## Privacy boundary

The repository contains only public bibliographic metadata and derived relevance/ranking fields. It must not contain private conversations, local file paths, downloaded or institutionally authorized PDFs/SI, credentials, or institutional-access state.

Journal ranking fields are published only when a verified local cache provides a source and year. Missing JCR/中科院 data remains `N/A`; it is never inferred from memory.
