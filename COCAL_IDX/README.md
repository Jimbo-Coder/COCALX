# COCAL_IDX
A cleaned up COCAL reader for the CarpetX EinsteinToolkit


## BNS exported grids and velocity correction

This branch ports the Carpet reader changes through `COCAL` commit `c83ca53`.
Exported `bnsgrids_3D_mpt{1,2,3}.las` coordinates take precedence over grid
reconstruction. Supply all three files, or none for legacy data. Each stellar
patch uses its own surface grid and signed `xcm` orbital offset. Inconsistent
metadata and Cartesian points outside the finite grid coverage are rejected.

- `COCAL_IDX::coc2cac_bns_compact = yes` for a compactified outer export. The
  infinity sample is read but excluded from interpolation. Default: `no`.
- `COCAL_IDX::coc2cac_ecc_cor_velx` sets the velocity-correction coefficient.
  Default: `0`; the default prescription is radial.
- `COCAL_IDX::coc2cac_bns_xunit = yes` selects the xunit prescription: the
  coefficient multiplies the signed half-separation in COCAL coordinates,
  giving a constant x correction for each star. Negative coefficients give
  inward corrections. Default: `no`.

Use the prescription and coefficient from the ID generation settings; neither
is inferred from the directory name. Existing CarpetX parameter names, field
centerings, tile loops and per-rank loading are retained.

1. Use the thornlist asterx_subcycle.th to checkout the ETK + CarpetX (subcycle) + cocal_IDX, 
> ./GetComponents --root {dir} asterx_subcycle.th 

2. Obtain a 1 Layer EoS RNS from https://uofi.box.com/s/gbamn61wxuhh5iw6dxte1m1bzrgtl0al , both IDs that have K123.6 in the title should be 1 Layer. Pick between CF or WL.

3. Configure simfactory mdb files, machine.ini, .cfg, .run, .sub, sets output location. Lastly 
> ./simfactory/bin/sim setup-silent.
I use in my .bashrc " alias sim="./simfactory/bin/sim" " . 

4. GPU configurating

5. Compile with 
> ./simfactory/bin/sim {config name} --thornlist ../asterx_subcycle.th

6. Submit jobs with 
> ./simfactory/bin/sim create-submit {simname} --config {config name} --parfile {parfilepath} --queue {queue} --procs {procs} --num-threads {threads} --walltime {walltime}

7. Ensure that the parameters
cocal_IDX::coc2cac_rnstype
cocal_IDX::coc2cac_dir_path_ID
are set correctly in the .parfile, point to respective ID and have the correct type.