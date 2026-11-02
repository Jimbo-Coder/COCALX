# COCALX tools

[generate_parfile.py](generate_parfile.py) writes a CarpetX + AsterX + Z4c
parfile and a JSON record for a COCAL RNS or BNS ID with one polytrope. It is
one script using only the Python standard library.

Runs are entries of `configs` near the top of the script:

```python
configs = [
    {"name": "bns-local", "id_dir": "/path/to/SP_K123.6_000", "profile": "local"},
]
```

```sh
python tools/generate_parfile.py 0           # configs[0]
python tools/generate_parfile.py /path/to/ID # an ID with the semiprod defaults
```

The output is `<name>.par` and `<name>.json` in the current directory;
existing files are kept unless `--force` is given.

## Settings

| Key | Meaning |
| --- | --- |
| `profile` | `"local"` (small, short) or `"semiprod"` (default) |
| `grid` | `finest_dx`, `levels`, `domain`, `star_margin`, `star_padding`, `common_levels`, `movement_cells` |
| `run` | `iterations`, `final_time`, `dtfac`, `out_every`, `out3d_every`, `walltime_hours`, `checkpoint_hours` |
| `gauge` | `eta`, default `1/M_ADM` |
| `compact`, `xunit`, `ecc_cor_velx`, `ecc_cor_velz` | BNS: as the ID was generated (per-star velocities as two-element lists) |
| `active_thorns` | replaces `default_thorns` for the run |

The grid is sized from the stars' exported radii: a stack of BoxInBox regions
about each star (and, for BNS semiprod, shared central levels), on a base grid
of whole 8-cell blocks. The ID uses COCAL's polytrope and the evolution an
ideal gas of the same Gamma, since AsterX needs a temperature.

Tabulated and piecewise-polytropic EOS (EOSX cannot yet set the first segment
bound, 0), MRNS (AsterX-Msup) and black-hole IDs are refused; start those from
the examples in `COCAL_IDX/par`.
