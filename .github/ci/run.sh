#!/bin/bash
# Build a minimal Cactus with CarpetX (cocalx.th, ubuntu.cfg) with this
# repository as the COCALX arrangement, and run the COCAL_IDX fixture tests.
# Also used by hand:
#   [JOBS=n] [OPTIONS=optionlist] .github/ci/run.sh [work directory, default ./cactus-ci]
# Needs git, gcc, g++, gfortran, make, cmake, perl, python3, OpenMPI, zlib and
# HDF5.
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
ci=$repo/.github/ci
work=$(mkdir -p "${1:-cactus-ci}" && cd "${1:-cactus-ci}" && pwd)
cd "$work"

# A cached checkout is updated to the current development branches; make then
# recompiles only what changed.
if [ ! -d Cactus/src ]; then
  curl -fsSL -o GetComponents https://raw.githubusercontent.com/gridaphobe/CRL/master/GetComponents
  chmod +x GetComponents
  ./GetComponents --parallel "$ci/cocalx.th"
else
  ./GetComponents --update --parallel "$ci/cocalx.th"
fi
ln -sfn "$repo" Cactus/arrangements/COCALX
{ grep -E '^[A-Za-z]+/[A-Za-z0-9_]+' "$ci/cocalx.th"; echo COCALX/COCAL_IDX; } > ThornList

cd Cactus
[ -d configs/cocalx ] || make -j"${JOBS:-$(nproc)}" cocalx-config options="${OPTIONS:-$ci/ubuntu.cfg}" THORNLIST="$work/ThornList" PROMPT=no
# A cached build may still list reader files that were since removed.
rm -rf configs/cocalx/build/COCAL_IDX
make cocalx -j"${JOBS:-$(nproc)}"

# One process per fixture (test.ccl); MPI one-sided windows over shared memory.
export OMPI_MCA_osc=sm OMPI_MCA_rmaps_base_oversubscribe=1
CCTK_TESTSUITE_RUN_TESTS=COCAL_IDX make cocalx-testsuite PROMPT=no | tee "$work/testsuite.log"
expected=$(ls "$repo"/COCAL_IDX/test/*.par | wc -l)
passed=$(sed -n 's/.*Number of tests passed *-> *\([0-9]*\).*/\1/p' "$work/testsuite.log" | tail -1)
if [ "${passed:-0}" != "$expected" ]; then
  echo "COCAL_IDX fixtures: ${passed:-0} of $expected passed" >&2
  cat TEST/cocalx/COCAL_IDX/*.diffs 2>/dev/null | head -100 >&2 || true
  exit 1
fi
echo "COCAL_IDX fixtures: $passed of $expected passed"
