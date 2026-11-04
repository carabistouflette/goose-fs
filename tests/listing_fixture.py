# SPDX-License-Identifier: Apache-2.0
"""Deterministic legal filenames with an exact packed directory byte count."""
def names_for_bytes(size):
    if size in (1,2) or not 0 <= size <= 1048576: raise ValueError("unrepresentable packed size")
    count,remainder=divmod(size,257)
    names=[f'entry-{i:04d}'.encode().ljust(255,b'x') for i in range(count)]
    if remainder in (1,2): names[-1]=names[-1][:-3]; remainder+=3
    if remainder: names.append(b'q'*(remainder-2))
    assert sum(len(n)+2 for n in names)==size
    return names
