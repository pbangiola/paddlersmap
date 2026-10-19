# OSM retry — October 19, 2026

Another bounded retrieval round ran locally and on GitHub Actions using both existing providers. **No new launch records were promoted.** Coverage remains nine completed historical cells out of 48; 21 historical OSM source records are available for review. All 101 active curated launches retain their original coordinates and verification identities.

- Local DE pass: HTTP 502 and read timeout on the two previously unfinished central-US cells. Coffee's status endpoint was blocked by the cloud proxy (HTTP 403 tunnel denial).
- [Hosted Coffee run 39253335477](https://github.com/pbangiola/paddlersmap/actions/runs/39253335477): HTTP 500 on both cells; saved its incomplete report and review artifact.
- [Hosted DE run 39253653937](https://github.com/pbangiola/paddlersmap/actions/runs/39253653937): both parent queries timed out; subdivision was attempted. The provider returned HTTP 502 with the explicit explanation **“This Overpass API server is currently at capacity. All query workers are busy and the request queue is full.”** Retrieval stopped after two source failures. Its diagnostic bodies and incomplete report are preserved in `hosted-de-incomplete-report.json`.
- Intermediate run 39253583824 was canceled before completion while diagnostic handling was corrected; it is not evidence of successful retrieval.

The workflow uploaded raw checkpoints for a later resume; it has read-only repository permissions and never publishes partial inventories. Existing named-launch filtering was retained. No broader/fuzzy launch search or coordinate snapping occurred.

Retries now support smaller query cells, bounded request/time budgets, complete child checkpoints and public provider diagnostics. A later round can resume with `named-canoe-launches.yml` and `resume_run=39253653937` when service capacity returns. The complete-only publication safeguard deliberately kept the active inventory unchanged.
