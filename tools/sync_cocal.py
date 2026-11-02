#!/usr/bin/env python3
"""Keep COCAL_IDX's reader the same as COCAL_ID's (Jimbo-Coder/COCAL).

    tools/sync_cocal.py <COCAL checkout>          copy the shared files here
    tools/sync_cocal.py <COCAL checkout> --check  only report differences

The shared files are COCAL_ID's reader source (src/ except the driver's
cocal_id_grid.F90 and make.code.defn) and the fixture data
(test/test_InitialData); param.ccl is COCAL_ID's for ADMBaseX/HydroBaseX.
Everything else here (cocal_id_grid.F90, cocal_id_set_data.cxx, the other ccl
files, fixtures and examples) is CarpetX's own.
"""
import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

DRIVER = {"cocal_id_grid.F90", "make.code.defn"}


def carpetx_param(text):
    """COCAL_ID's param.ccl for CarpetX: ADMBaseX/HydroBaseX, and no staggering
    offset or separate initial_Avec/Bvec/Aphi (each variable is evaluated at its
    own centring; initial_hydro = "Cocal" sets them all)."""
    text = text.replace("# Parameter definitions for thorn COCAL_ID\n",
                        "# Parameter definitions for thorn COCAL_IDX: COCAL_ID's (tools/sync_cocal.py).\n", 1)
    text = text.replace("shares: ADMBase\n", "shares: ADMBaseX\n").replace("shares: HydroBase\n", "shares: HydroBaseX\n")
    for keyword in ("initial_Bvec", "initial_Avec", "initial_Aphi"):
        text = re.sub(r"EXTENDS keyword %s\n\{\n[^}]*\}\n\n" % keyword, "", text)
    return re.sub(r'CCTK_BOOLEAN COCAL_ID_offset_AvecAphi[^\n]*\n\{\n\} "[^"]*"\n\n', "", text)


def shared(cocal):
    """(source, destination) pairs, and the expected param.ccl text."""
    src, here = cocal / "COCAL_ID", Path(__file__).resolve().parent.parent / "COCAL_IDX"
    pairs = [(p, here / "src" / p.relative_to(src / "src"))
             for p in sorted((src / "src").rglob("*")) if p.is_file() and p.name not in DRIVER]
    data = src / "test" / "test_InitialData"
    pairs += [(p, here / "test" / "test_InitialData" / p.relative_to(data))
              for p in sorted(data.rglob("*")) if p.is_file()]
    return here, pairs, carpetx_param((src / "param.ccl").read_text())


def stale(here, pairs):
    """Shared-tree files here that COCAL_ID no longer has."""
    expected = {dst for _, dst in pairs}
    trees = [here / "src", here / "test" / "test_InitialData"]
    return [p for tree in trees for p in sorted(tree.rglob("*"))
            if p.is_file() and p not in expected and not (tree.name == "src" and p.parent == tree and
                                                           (p.name in DRIVER or p.suffix == ".cxx"))]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cocal", type=Path, help="a Jimbo-Coder/COCAL checkout")
    parser.add_argument("--check", action="store_true", help="report differences, change nothing")
    args = parser.parse_args()
    here, pairs, param = shared(args.cocal.resolve())
    different = [dst for src, dst in pairs if not dst.is_file() or not filecmp.cmp(src, dst, shallow=False)]
    param_path = here / "param.ccl"
    if not param_path.is_file() or param_path.read_text() != param:
        different.append(param_path)
    extra = stale(here, pairs)
    if args.check:
        for path in different:
            print("differs:", path.relative_to(here.parent))
        for path in extra:
            print("not in COCAL_ID:", path.relative_to(here.parent))
        sys.exit(1 if different or extra else 0)
    for src, dst in pairs:
        if dst in different:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    param_path.write_text(param)
    for path in extra:
        path.unlink()
    print(f"{len(different)} files updated, {len(extra)} removed")


if __name__ == "__main__":
    main()
