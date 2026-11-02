# COCAL_IDX
The COCAL initial-data reader for CarpetX, ported from the Carpet thorn
COCAL_ID ([Jimbo-Coder/COCAL](https://github.com/Jimbo-Coder/COCAL)) with the
same parameters. main has RNS, MRNS and BNS; dev adds the black-hole IDs.

## CarpetX specifics

Each grid function is evaluated at its own centring: the ADMBaseX metric,
lapse and shift at vertices, the HydroBaseX fluid and `Bvec` at cell centres,
and `Avecx/y/z` on the cell edges. There is no staggering offset and no
separate `initial_Avec`/`initial_Bvec` choice: `HydroBaseX::initial_hydro =
"Cocal"` sets the fluid and, for MRNS_WL, `Avec`
(`COCAL_IDX_read_magnetic_potential = yes`) or `Bvec` (`no`); the other is zero.

The data are read at `INITIAL` before `ODESolvers_Initial`, and the metric is
set then, with the lapse and shift where `initial_lapse` and `initial_shift`
are `"Cocal"`. The fluid is set in
`HydroBaseX_InitialData`. CarpetX enters the initial bin again for every level
it adds; the data are read once and freed at `CPINITIAL`.

## AsterX (this branch)

AsterX-Msup also sets AsterX's vector potential, so COCAL_IDX inherits AsterX
here and needs it active: `Avec_x/y/z` are HydroBaseX's `Avecx/y/z` (the same
edge centrings) and `Psi` = sqrt(det g) Aphi at the vertices, from
`src/cocal_id_set_asterx.cxx`; all zero unless MRNS_WL data give the potential.
`test/cocalx_mrns_wl_asterx` covers the handoff.

## Parameters

Parameters (`param.ccl`) are set as `COCAL_IDX::<name>`.
Parameter files for the earlier CarpetX reader rename:

| Earlier CarpetX reader | Now |
| --- | --- |
| `coc2cac_dir_path_ID` | `COCAL_IDX_PathToID` |
| `coc2cac_rnstype` | `COCAL_IDX_rnstype` |
| `coc2cac_readpot` | `COCAL_IDX_read_magnetic_potential` |
| `coc2cac_read_tabulated_eos` | `COCAL_IDX_read_tabulated_eos` |
| `coc2cac_cen_{x,y,z}{1,2}` | `COCAL_IDX_cen_{x,y,z}{1,2}` |
| `verbose` | `COCAL_IDX_verbose` |
| `coc2cac_readformat` | removed: both formats are read |

```shell
sed -i -e '/coc2cac_readformat/d' -e 's/coc2cac_dir_path_ID/COCAL_IDX_PathToID/' \
  -e 's/coc2cac_readpot/COCAL_IDX_read_magnetic_potential/' -e 's/COCAL_IDX::coc2cac_/COCAL_IDX::COCAL_IDX_/g' \
  -e 's/COCAL_IDX::verbose/COCAL_IDX::COCAL_IDX_verbose/' run.par
```

New: `COCAL_IDX_ecc_cor_velx` with `COCAL_IDX_bns_xunit` (BNS velocity
correction), and `COCAL_IDX_share_node_memory`.

## Setup

1. Check out the ETK, CarpetX and COCAL_IDX with the thornlist:
   `./GetComponents --root {dir} thornlists/asterx_subcycle.th`
2. Configure simfactory (machine, option list, run and submit scripts) and
   compile with GNU make 4 or later (`gmake` on macOS): `./simfactory/bin/sim build {config} --thornlist thornlists/asterx_subcycle.th`
3. Generate a parfile with [tools/generate_parfile.py](../tools/README.md), or
   start from an example in `par/` and set `COCAL_IDX::COCAL_IDX_PathToID` and,
   for RNS, `COCAL_IDX::COCAL_IDX_rnstype` to match the ID. Single-layer
   RNS IDs (K123.6, CF or WL) are at
   https://uofi.box.com/s/gbamn61wxuhh5iw6dxte1m1bzrgtl0al.

## How it works

Every COCAL export (RNS, MRNS, BNS) is held the same way:

- a **metric domain**: COCAL's spherical patches, one (RNS) or three (a
  binary: one per star, rotated by pi about z for the second, and the outer
  patch), with the fields psi, alpha, beta^i, K_ij/psi^4 and, for waveless
  data, h_ij;
- a **matter domain**: the fluid on its own grid, surface fitted (r/rs) as on
  COCAL's fluid grids.

At each Cactus point the metric is evaluated, the ID's matter is composed with
that same metric (the Eulerian velocity uses alpha and beta^i at the point),
and each grid function takes the values at its own points. The readers differ
only where the export formats differ.

The shift is ADMBaseX's contravariant beta^i. Waveless exports (RNS_WL,
MRNS_WL, BHT) store the covariant shift of the conformal metric, which the
reader raises with gt^ij; conformally flat exports need no raising.

| File | Contents |
| --- | --- |
| `src/COCAL_ID_master.F90` | Cactus entry points: read, free |
| `src/cocal_id_grid.F90` | the values at one point, for the CarpetX loops |
| `src/cocal_id_set_data.cxx` | the CarpetX loops, one per centring |
| `src/cocal_id_state.f90` | metric layout, the state at a point, EOS |
| `src/cocal_id_domain.f90` | patches, spline fit, patch blending |
| `src/cocal_id_spline.f90` | the C2 tensor-product spline |
| `src/cocal_id_eval.f90` | the state at a point, for every ID |
| `src/cocal_id_{rns,bns}.F90` | one reader per export format |
| `src/cocal_id_node_shared.*` | node-shared memory |
| `src/Cocal/` | COCAL's own routines, as exported by PCOCAL |

## Interpolation

Every field, metric and matter, is a C2 tensor-product cubic spline on its
patch: clamped in r, periodic B-splines in theta (continued over the poles)
and phi, with COCAL's fourth-order accuracy and no slope jumps at the nodes,
which the constraints would otherwise turn into errors growing like 1/h.
Grids starting at r=0 are fitted along whole diameters; the metric's centre
value is replaced by the even extrapolation of its neighbours, removing an
offset in COCAL's exports. The three patches of a binary are blended with C2
weights across their whole usable overlap, and star-patch nodes inside the
companion excision are first filled from the companion. Where an export has
no usable overlap, the reader warns and keeps a hard patch switch there.
Export files are never modified, and grids must have increasing radii and
uniform angles.

Where a matter field's angular data are not smooth, the spline rings and
COCAL's local 4-point Lagrange interpolation does not, so there the field
blends smoothly to Lagrange in angle (the radial spline is kept). The main
case is COCAL's exported velocity-potential gradients near the poles
(`dvep_x/y`): COCAL's second-order angular differences leave them a finite
cos(2 phi) part up to the single-valued pole row. Rough nodes are found per
field from the spline coefficients: a fourth difference in theta or phi much
larger than the neighbouring second differences, and isolated, so a smooth
but under-resolved field is never marked. Smooth fields, and every field on
grids with fewer than 24 angular nodes, keep the spline. Metric fields keep
it everywhere: the constraints take its second derivatives, and their rough
spots are the binary patch seams, where Lagrange does not help.

Matter is the spline of COCAL's Emden function on its surface-fitted grid.
As in COCAL, values at or below the vacuum threshold are vacuum.

## Node-shared storage

Node-shared arrays use the `COCAL_IDX_share_node_memory` control. It defaults
to `yes`: each node's leader reads the export straight into the fields it
fits, and the spline coefficients are shared by the node's ranks. Set it to
`no` for private per-rank copies. If shared windows cannot be created at
startup the reader warns and uses private copies; a later shared allocation
failure aborts. Open MPI on Anvil needs
`OMPI_MCA_osc=sm,ucx`.

## BNS exports

Patch grids are regenerated from each patch's `rnspar_mpt*.dat`. The
coordinate map requires equal `radi` and a shared midpoint, which are checked.
Matter belongs to one star, chosen by the midplane.

### BNS velocity correction

For exports generated with the `xunit` prescription, set
`COCAL_IDX::COCAL_IDX_bns_xunit = yes`. This multiplies `COCAL_IDX_ecc_cor_velx`
by the signed half-separation in COCAL coordinates, adding a constant x term
to each star's corotating shift; negative values give inward corrections.
The default is the radial prescription; use the prescription and coefficient
the ID was generated with.

### BNS orbital offsets

The fluid constants record in `bnsflu_3D_mpt{1,2}.las` contains
`ome, ber, radi, xcm, zcm`; missing fields are read as zero. A nonzero `zcm`
tilts the orbital rotation used for the fluid velocity.
