"""
Rapid7 Project Sonar - Forward DNS CNAME dataset processor.

Downloads and processes the monthly Rapid7 Sonar FDNS CNAME dataset.
Filters records where the CNAME target matches Salesforce infrastructure patterns.

Dataset URL: https://opendata.rapid7.com/
Files are compressed (gzip) and can be multi-GB. Processes in streaming fashion.
"""

import gzip
import json
import os
from pathlib import Path

import httpx
import structlog

from src.discovery.base import BaseDiscoverySource, DiscoveryResult, is_salesforce_cname

logger = structlog.get_logger(__name__)

SONAR_INDEX_URL = "https://opendata.rapid7.com/fdns/2024-09-16-1726459581-fdns_cname.json.gz"


class Rapid7SonarSource(BaseDiscoverySource):
    """
    Rapid7 Project Sonar dataset processor.
    Downloads the FDNS CNAME dataset and filters for Salesforce targets.
    Processes data in a streaming fashion to handle multi-GB files.
    """

    source_name = "rapid7"

    def __init__(self, data_dir: str = "/data/rapid7") -> None:
        super().__init__()
        self.data_dir = Path(data_dir)

    async def discover(self, target_cname_patterns: list[str]) -> list[DiscoveryResult]:
        """
        Process any .json.gz files found in the data directory.
        Files should be pre-downloaded from https://opendata.rapid7.com/
        """
        results: list[DiscoveryResult] = []

        if not self.data_dir.exists():
            self.log.warning("rapid7.data_dir_not_found", data_dir=str(self.data_dir))
            return results

        gz_files = list(self.data_dir.glob("*.json.gz"))
        if not gz_files:
            self.log.warning("rapid7.no_data_files", data_dir=str(self.data_dir))
            return results

        for gz_file in gz_files:
            self.log.info("rapid7.processing_file", file=gz_file.name)
            try:
                file_results = self._process_file(gz_file)
                results.extend(file_results)
            except Exception as e:
                self.log.error("rapid7.file_processing_failed", file=gz_file.name, error=str(e))

        seen = set()
        unique_results = []
        for r in results:
            if r.domain not in seen:
                seen.add(r.domain)
                unique_results.append(r)

        self.log.info("rapid7.discovery_complete", total=len(unique_results))
        return unique_results

    def _process_file(self, gz_file: Path) -> list[DiscoveryResult]:
        """Stream-process a gzip-compressed NDJSON file."""
        results: list[DiscoveryResult] = []

        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                try:
                    record = json.loads(line.strip())
                    # Sonar format: {"name": "domain.com", "type": "cname", "value": "target.com"}
                    if record.get("type") != "cname":
                        continue

                    domain = record.get("name", "").rstrip(".").lower()
                    cname_target = record.get("value", "").rstrip(".").lower()

                    if not domain or not cname_target:
                        continue

                    if is_salesforce_cname(cname_target):
                        results.append(
                            DiscoveryResult(
                                domain=domain,
                                cname_target=cname_target,
                                source=self.source_name,
                                metadata={"sonar_file": gz_file.name},
                            )
                        )

                    if line_num % 1_000_000 == 0 and line_num > 0:
                        self.log.info(
                            "rapid7.progress",
                            lines_processed=line_num,
                            matches=len(results),
                        )

                except (json.JSONDecodeError, KeyError):
                    continue

        return results
