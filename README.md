# Literature Radar Website

Public, cumulative literature browser for rectenna, passive backscatter temperature sensing, polarization robustness, multiport/DC-combining energy harvesting, and related RF topics.

Website: https://zhangxiaoming12138.github.io/research-literature-radar-site/

The repository contains only public bibliographic metadata. It does not contain private conversations, local file paths, downloaded/authorized PDFs or SI, credentials, or institutional-access state.

`papers.json` was initially seeded from the private multi-source radar history. `.github/workflows/update.yml` then runs every day at 08:20 Asia/Shanghai and incrementally merges recent OpenAlex matches. The workflow can also be triggered manually with a larger `days` window for historical backfill.
