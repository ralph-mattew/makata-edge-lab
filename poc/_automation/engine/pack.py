"""Domain pack loader for the ideation engine.

A *pack* bundles everything domain-specific — config, prompts, knowledge
(open-problems + outcomes), calibration cases — so the engine machinery
(stages, gates, synthesis) stays reusable across domains. The engine resolves all
domain paths through a Pack; stages call `load_pack(name)` instead of reading a bare
`config.yaml`.

Layout:
  packs/<name>/pack.yaml          (was config.yaml)
  packs/<name>/prompts/*.txt      (domain prompts / slot-fills)
  packs/<name>/knowledge/         (open-problems.md, outcomes.jsonl)
  packs/<name>/calibration/       (cases.jsonl)
  scans/<name>/                   (git-ignored run outputs; auto-created)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict
import yaml

HERE = Path(__file__).resolve().parent        # .../_automation/engine
ROOT = HERE.parent                            # .../_automation
PACKS_DIR = ROOT / "packs"
DEFAULT_PACK = "edge-ai-rag"


class Pack:
    def __init__(self, name: str):
        self.name = name
        self.dir = PACKS_DIR / name
        if not self.dir.is_dir():
            raise FileNotFoundError(
                f"pack '{name}' not found at {self.dir} (available: "
                f"{', '.join(p.name for p in PACKS_DIR.iterdir() if p.is_dir())})")
        cfg_path = self.dir / "pack.yaml"
        self.config: Dict = yaml.safe_load(cfg_path.read_text()) or {}
        self.prompts_dir = self.dir / "prompts"
        self.knowledge_dir = self.dir / "knowledge"
        self.calibration_dir = self.dir / "calibration"
        self.scans_dir = ROOT / "scans" / name
        self.scans_dir.mkdir(parents=True, exist_ok=True)
        # Expose resolved paths on the config so engine modules that only receive
        # `config` (gates, knowledge) can find the active pack's files.
        self.config["_pack"] = {
            "name": name,
            "prompts": str(self.prompts_dir),
            "knowledge": str(self.knowledge_dir),
            "calibration": str(self.calibration_dir),
            "scans": str(self.scans_dir),
        }

    def wire(self):
        """Point the engine's path-resolving modules at this pack. Call once after load."""
        import _client, _knowledge
        _client.set_prompts_dir(self.prompts_dir)
        _knowledge.set_knowledge_dir(self.knowledge_dir)
        return self


def load_pack(name: str = DEFAULT_PACK) -> Pack:
    return Pack(name).wire()


def add_pack_arg(parser):
    """Standard --pack CLI flag for the stages."""
    parser.add_argument("--pack", default=DEFAULT_PACK,
                        help=f"domain pack under packs/ (default: {DEFAULT_PACK})")
    return parser
