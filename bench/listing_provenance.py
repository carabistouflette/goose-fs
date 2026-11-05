# SPDX-License-Identifier: Apache-2.0
"""Inputs shared by listing builders and their recorder."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def sources():
    paths=[ROOT/'fs.goose',ROOT/'fs.build',ROOT/'GOOSE_REVISION',*sorted((ROOT/'native').glob('*'))]
    paths += [ROOT/name for name in ('bench/listing.goose.in','bench/listing-build.py',
        'bench/listing-control-build.py','bench/listing-measure.py','bench/listing_provenance.py',
        'bench/build-baseline.py','bench/compare/provenance.py','tests/listing_fixture.py')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
