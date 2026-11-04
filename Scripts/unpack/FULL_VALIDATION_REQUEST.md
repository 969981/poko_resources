# Full M0/M1/M2 execution request

This tracked marker requests a one-time `[full-unpack]` push run in GitHub Actions for branch `2.0.1_unpack`. The full runner must verify available disk before restoring all archived assets. Raw game payloads must remain private to the runner and not be uploaded as artifacts. If disk is insufficient, the pipeline should fail explicitly and the report should record the required capacity.
