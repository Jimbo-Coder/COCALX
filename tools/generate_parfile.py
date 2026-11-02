#!/usr/bin/env python3
"""Generate a CarpetX + AsterX + Z4c parfile for COCAL_IDX from a COCAL RNS or BNS ID directory."""

import argparse
from collections import namedtuple
import hashlib
import json
import math
from pathlib import Path
import re

# Thorns of the generated parfile; a configuration can supply its own active_thorns.
default_thorns = [
    "ADMBaseX", "AsterAnalysis", "AsterMasks", "AsterSeeds", "AsterX", "BoxInBox",
    "CarpetX", "CarpetXRegrid", "Con2PrimFactory", "CoordinatesX", "COCAL_IDX",
    "EOSX", "HydroBaseX", "IOUtil", "NewRadX", "ODESolvers", "QuasiLocalMeasures",
    "ReconX", "SphericalSurface", "TGRtensor", "TimerReport", "TmunuBaseX",
    "VolumeIntegrals_GRMHDX", "VolumeIntegrals_vacuumX", "Z4c",
]


# RUN CONFIGURATIONS: edit here, then run `python tools/generate_parfile.py 0`.
# Add entries for your own runs; keep the committed example generic.
# See tools/README.md for the available settings.
configs = [
    {
        "name": "example",
        "id_dir": "/path/to/ID",
        "profile": "semiprod",       # "local" or "semiprod"
        "grid": {},                  # e.g. {"finest_dx": 0.125, "levels": 8}
        "run": {},                   # e.g. {"iterations": 16, "out_every": 8}
    },
]


# Implementation below; the user settings end above.
# These also determine the conservative nesting allowance in resolve_grid().
GHOST_SIZE = 3
RK_STAGES = 4
G_CGS, C_CGS, MSUN_CGS = 6.67428e-8, 2.99792458e10, 1.98892e33
DENSITY_UNIT = (G_CGS / C_CGS**2)**3 * MSUN_CGS**2  # g/cm^3 -> G = c = Msol = 1
PROLONGATION_ORDER = 5
MIN_DISTANCE = 4

# Matter limits for every ID, scaled by the ID's peak rest-mass density: the atmosphere
# far below any fluid, the ceiling well above a merger remnant or collapsing core
# (BNS SP_K123.6: 7.3e-13 and 0.022, the validated 1e-12 and 0.02).
ATMOSPHERE_FRACTION = 1e-9
CEILING_FACTOR = 30


def matter_limits(data):
    peak = data["peak_density"]
    return dict(atmosphere=ATMOSPHERE_FRACTION * peak, ceiling=CEILING_FACTOR * peak)


def quoted(value):
    value = str(value)
    if any(char in value for char in ('"', "\n", "\r", "$", "@")):
        raise ValueError(f"Unsupported character in parfile string: {value!r}")
    return f'"{value}"'


def real(value):
    if not math.isfinite(value):
        raise ValueError("Numeric settings must be finite")
    return f"{value:.16g}"


def array(values):
    return "[" + ", ".join(real(value) for value in values) + "]"


def variables(*rows):
    return '"\n  ' + '\n  '.join(rows) + '\n"'


def resolve_grid(data, overrides, local):
    """Build surface-sized stellar stacks and shared parents, then fit the domain.

    All widths are coordinate half-widths. Grid spacings double outward; box
    widths approximately double, with extra room where numerical nesting needs it.
    The outer domain never sets an inner box's size.
    """
    bns = data["kind"] == "bns"
    centers = data["centers"]
    radii = data["max_coordinate_star_radii"]

    # 1. Apply user overrides to the profile defaults.
    default_levels = 4 if local else (8 if bns else 6)
    grid = {
        "finest_dx": 0.5 if local else 0.125,
        "levels": default_levels,
        "domain": None,
        "star_margin": 0.20,
        "star_padding": 0.0,
        "common_levels": None,
        "movement_cells": 2.0,
    }
    unknown = overrides.keys() - grid.keys()
    if unknown:
        raise ValueError("Unknown grid settings: " + ", ".join(sorted(unknown)))
    grid.update(overrides)

    dx = grid["finest_dx"]
    levels = grid["levels"]
    if type(levels) is not int or not 2 <= levels <= 10:
        raise ValueError("grid levels must be an integer in 2..10, including the base level")
    for name in ("finest_dx", "movement_cells", "star_margin", "star_padding"):
        value = grid[name]
        positive = name in ("finest_dx", "movement_cells")
        if (type(value) not in (int, float) or not math.isfinite(value)
                or value < 0 or (positive and value == 0)):
            bound = "positive" if positive else "nonnegative"
            raise ValueError(f"grid {name} must be a {bound} finite number")
    coarse_dx = dx * 2**(levels - 1)

    def aligned(width, spacing):
        return math.ceil(width / (2 * spacing)) * (2 * spacing)

    def nesting_margin(parent_dx):
        # CarpetRegrid2 nests the buffered fine region plus its ghosts, then
        # adds min_distance and the prolongation stencil on the parent grid.
        # Two further parent cells allow for coordinate rounding and snapping.
        fine_support = RK_STAGES * GHOST_SIZE * (parent_dx / 2)
        coarse_support = (MIN_DISTANCE + PROLONGATION_ORDER // 2 + 2) * parent_dx
        return fine_support + coarse_support

    # 2. Cover the surface allowance after tracking lag and centre rounding.
    # The local profile keeps a minimum half-width for the small fixtures.
    tracking_margin = grid["movement_cells"] * dx if bns else 0.0
    rounding_margin = dx / 2 if bns else 0.0
    fine = []
    for radius in radii:
        allowance = max(grid["star_margin"] * radius, grid["star_padding"])
        half_width = aligned(radius + allowance + tracking_margin + rounding_margin, dx)
        fine.append(max(12 if local else 0, half_width))

    star_boxes = []
    for radius in fine:
        boxes = [radius]
        for level in range(levels - 2, 0, -1):
            parent_dx = dx * 2**(levels - 1 - level)
            parent = max(2 * boxes[0], boxes[0] + nesting_margin(parent_dx))
            boxes.insert(0, aligned(parent, parent_dx))
        star_boxes.append(boxes)

    # 3. Use shared outer boxes once the stellar boxes substantially overlap.
    # Keep at least the finest level star-centred. The overlap must cover half
    # the smaller box's x-width; a mere first touch is a poor handoff to a cube.
    separation = abs(centers[1] - centers[0]) if bns else 0
    # Only for the diagnostic spheres, not the grid.
    wide = bns and separation > 8 * max(radii)
    common_levels = grid["common_levels"]
    if common_levels is not None:
        if not bns or local:
            raise ValueError("common_levels applies only to semiprod BNS grids")
        if type(common_levels) is not int or not 1 <= common_levels <= levels:
            raise ValueError("common_levels must be in 1..levels, including the base level")
    elif bns and not local:
        common_levels = 1  # base level only, if no shared refined parent fits
        for level in range(levels - 2, 0, -1):
            widths = [boxes[level - 1] for boxes in star_boxes]
            lower = max(x - width for x, width in zip(centers, widths))
            upper = min(x + width for x, width in zip(centers, widths))
            if upper - lower >= min(widths):
                common_levels = level + 1
                break
    else:
        common_levels = 0

    common_boxes = []
    if bns and not local:
        # Inactive central radii follow the stellar size, for a later collapse.
        common_boxes = [max(boxes[level - 1] for boxes in star_boxes)
                        for level in range(1, levels)]
        for level in range(levels - 2, 0, -1):
            parent_dx = dx * 2**(levels - 1 - level)
            child_extent = common_boxes[level]
            if level < common_levels:
                # Support the next-finer union. Same-level stellar requests may
                # extend beyond this central box; BoxInBox takes their union.
                child_extent = max(child_extent, max(
                    abs(x) + boxes[level] for x, boxes in zip(centers, star_boxes)))
            required = child_extent + nesting_margin(parent_dx)
            common_boxes[level - 1] = aligned(
                max(common_boxes[level - 1], required), parent_dx)

    # 4. Fit the stacks inside the domain, leaving room for boundary stencils.
    boundary_clearance = nesting_margin(coarse_dx)
    stack_extent = [
        max(abs(x) + boxes[0] for x, boxes in zip(centers, star_boxes)),
        max(boxes[0] for boxes in star_boxes),
        max(boxes[0] for boxes in star_boxes),
    ]
    if common_levels > 1:
        stack_extent = [max(extent, common_boxes[0]) for extent in stack_extent]
    domain = grid["domain"]
    if domain is None:
        if local:
            domain = [max(64, extent + boundary_clearance) for extent in stack_extent]
        else:
            stellar_extent = max(abs(x) + r for x, r in zip(centers, radii))
            half_width = max(
                1536 if bns else 384,
                4 * stellar_extent,
                max(stack_extent) + boundary_clearance,
            )
            domain = [half_width] * 3

        # Eight coarse cells give the domain convenient divisibility.
        domain_unit = 8 * coarse_dx
        domain = [math.ceil(width / domain_unit) * domain_unit for width in domain]

    if not isinstance(domain, (list, tuple)) or len(domain) != 3:
        raise ValueError("domain needs three positive half-widths aligned to coarse cells")
    for width in domain:
        if type(width) not in (int, float) or not math.isfinite(width) or width <= 0:
            raise ValueError("domain needs three positive half-widths aligned to coarse cells")
        coarse_cells = width / coarse_dx
        if not math.isclose(coarse_cells, round(coarse_cells)):
            raise ValueError("domain half-widths must align to coarse cells")

    if any(width - extent < boundary_clearance
           for width, extent in zip(domain, stack_extent)):
        raise ValueError(
            f"Refinement stacks need {boundary_clearance / coarse_dx:g} coarse cells of boundary clearance; "
            "enlarge domain or reduce levels/surface padding"
        )

    # 5. CoM and density searches must contain their star, but not its companion.
    region = []
    for half_width, radius in zip(fine, radii):
        search_radius = half_width + 1
        if bns:
            search_radius = min(search_radius, separation / 2 - dx)
        if search_radius <= radius:
            raise ValueError("Stellar diagnostic spheres must enclose their star without reaching the companion")
        region.append(search_radius)

    grid.update(
        domain=list(domain),
        common_levels=common_levels,
        coarse_dx=coarse_dx,
        wide=wide,
        fine_box_radii=fine,
        star_boxes=star_boxes,
        common_boxes=common_boxes,
        tracking_radii=region,
    )
    return grid


def settings(id_dir, overrides=None):
    """Apply one run's overrides; grid and run defaults come from its profile."""
    values = {
        "name": None,
        "profile": "semiprod",
        "compact": False,
        "xunit": False,
        "ecc_cor_velx": 0.0,
        "ecc_cor_velz": 0.0,
        "grid": {},
        "run": {},
        "active_thorns": default_thorns,
        "gauge": {},
    }
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise ValueError("Each configuration must be a dictionary")
        unknown = overrides.keys() - values.keys()
        if unknown:
            raise ValueError("Unknown configuration settings: " + ", ".join(sorted(unknown)))
        values.update(overrides)

    if values["profile"] not in ("local", "semiprod"):
        raise ValueError('profile must be "local" or "semiprod"')
    for name in ("compact", "xunit"):
        if type(values[name]) is not bool:
            raise ValueError(f"{name} must be True or False")
    for name in ("ecc_cor_velx", "ecc_cor_velz"):
        velocity_pair(values[name], name)
    for name in ("grid", "run", "gauge"):
        if not isinstance(values[name], dict):
            raise ValueError(f"{name} overrides must be a dictionary")
        values[name] = dict(values[name])
    output_name = values["name"]
    if output_name is not None:
        if (not isinstance(output_name, str) or not output_name.strip()
                or output_name in (".", "..") or Path(output_name).name != output_name):
            raise ValueError("name must be a filename stem, not a directory path")
    if not isinstance(id_dir, (str, Path)) or not str(id_dir).strip():
        raise ValueError("Set id_dir to the COCAL ID directory")
    values["id_dir"] = Path(id_dir).expanduser().resolve()
    return values


def velocity_pair(value, name):
    """Validate a shared component or a pair in COCAL patch-1/patch-2 order."""
    pair = value if isinstance(value, (list, tuple)) else (value, value)
    if len(pair) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in pair):
        raise ValueError(f"{name} must be a finite number or two finite numbers")
    return pair


def has_bns_velocity(cfg):
    return any(v != 0 for key in ("ecc_cor_velx", "ecc_cor_velz")
               for v in velocity_pair(cfg[key], key))


def select_config(target):
    """A bare integer selects configs[index]; any other argument is an ID path."""
    if target.isdecimal():
        index = int(target)
        if not isinstance(configs, list) or index >= len(configs):
            raise ValueError(f"No configuration {index}; add it to configs near the top of this file")
        if not isinstance(configs[index], dict):
            raise ValueError(f"Configuration {index} must be a dictionary")
        overrides = dict(configs[index])
        if "id_dir" not in overrides:
            raise ValueError(f"Configuration {index} needs id_dir")
        id_dir = overrides.pop("id_dir")
        return id_dir, overrides, index
    return target, {}, None


# One function per thorn returns that thorn's parameters (unqualified names),
# or a Block when it also sets the section title or integral labels. Stellar
# (RNS/BNS) and black-hole (BBH/BBHT) IDs share each function; where their
# settings differ, both are written there, the black-hole case first. Only
# active thorns are called, and an empty result writes no block.
Block = namedtuple("Block", "parameters title labels", defaults=(None, None))


def yes_no(flag):
    return "yes" if flag else "no"


def render_parfile(blocks, active, title, profile):
    """Assemble selected blocks and check their structure, not Cactus expressions.

    Cactus -P handles expression syntax and compiled parameter names/types/ranges.
    The generator only checks errors it can identify without parsing that language.
    """
    sections = [
        f"# {title}\n"
        f"# Generated by generate_parfile.py; settings: {profile}.\n",
        'ActiveThorns = "\n  ' + '\n  '.join(active) + '\n"',
    ]
    emitted = set()
    for thorn, block in blocks.items():
        namespace = thorn
        parameters = {key: str(value) for key, value in block["parameters"].items()
                      if value is not None}
        if not parameters:
            continue

        labels = block["labels"]
        if labels:
            def slot_number(item):
                match = re.search(r"\[(\d+)\]$", item[0])
                return int(match[1]) if match else 0
            parameters = dict(sorted(parameters.items(), key=slot_number))

        lines = []
        width = max(len(key) for key in parameters)
        previous_slot = None
        for key, value in parameters.items():
            # An index may itself be a Cactus expression. Check only the base name.
            base_name = key.partition("[")[0]
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", base_name):
                raise ValueError(f"Invalid parameter name in {thorn} block: {key}")
            full_name = f"{namespace}::{key}"
            if full_name.lower() in emitted:
                raise ValueError(f"Duplicate generated parameter: {full_name}")
            emitted.add(full_name.lower())

            if not value.strip():
                raise ValueError(f"Empty value for {full_name}")

            if labels or thorn == "SphericalSurface":
                match = re.search(r"\[(\d+)\]$", key)
                slot = match[1] if match else None
                if slot != previous_slot and lines:
                    lines.append("")
                    if labels and slot is not None:
                        lines.append(f"# Integral {slot}: {labels[int(slot)]}")
                previous_slot = slot
            lines.append(f"{namespace}::{key:<{width}} = {value}")
        sections.append(f"# {block['title']}\n" + "\n".join(lines))

    return "\n\n".join(sections) + "\n"


def cold_eos(data, rho):
    """Cold pressure and specific internal energy of the COCAL polytrope at rho."""
    gammas, bounds = data["EOS_gamma"], data["EOS_boundaries"]
    k, eps_offset, piece = data["EOS_k0"], 0.0, 0
    for i, boundary in enumerate(bounds):
        if rho < boundary:
            break
        # Continuity of P and eps at the boundary.
        k_next = k * boundary**(gammas[i] - gammas[i + 1])
        eps_offset += k * boundary**(gammas[i] - 1) / (gammas[i] - 1) - k_next * boundary**(gammas[i + 1] - 1) / (gammas[i + 1] - 1)
        k, piece = k_next, i + 1
    gamma = gammas[piece]
    return k * rho**gamma, eps_offset + k * rho**(gamma - 1) / (gamma - 1)


def carpetx_run(cfg, grid):
    """Cadence and runtime controls; output every coarse step, which CarpetX's
    subcycled levels share."""
    local = cfg["profile"] == "local"
    every = 2**(grid["levels"] - 1)
    run = {"iterations": 8 if local else 100000000, "final_time": 1000, "dtfac": 0.25 if local else 0.3,
           "out_every": every, "out3d_every": 64 * every, "walltime_hours": 1 if local else 12,
           "checkpoint_hours": -1 if local else 0.9}
    if cfg["run"].keys() - run.keys():
        raise ValueError("run accepts " + ", ".join(run))
    run.update(cfg["run"])
    for name in ("out_every", "out3d_every"):
        if type(run[name]) is not int or run[name] < 1:
            raise ValueError(f"{name} must be a positive integer")
    return run


class CarpetXSetup:
    """The resolved inputs and the layout the CarpetX blocks share."""

    def __init__(self, cfg, data, grid, run, active):
        self.cfg, self.data, self.grid, self.run, self.active = cfg, data, grid, run, active
        self.bns = data["kind"] == "bns"
        self.local = cfg["profile"] == "local"
        self.centers, self.radii = data["centers"], data["max_coordinate_star_radii"]
        self.eta = cfg["gauge"].get("eta", 1 / data["source_adm_mass"])
        # CarpetX's base grid: whole blocks of 8 cells of the coarse spacing.
        dx = grid["coarse_dx"]
        self.ncells = [8 * math.ceil(2 * extent / dx / 8) for extent in grid["domain"]]
        self.extent = [n * dx / 2 for n in self.ncells]
        # BNS semiproduction adds shared outer levels to the two moving stacks.
        self.offset = 1 if self.bns and not self.local else 0
        self.atmosphere = matter_limits(data)["atmosphere"]
        # Prescribed spheres: one about each star, then fixed global ones.
        stellar_extent = max(abs(x) + r for x, r in zip(self.centers, self.radii))
        outer = min(self.extent)
        globals_ = [f * outer for f in (0.6, 0.7, 0.8, 0.9) if stellar_extent + 4 * dx < f * outer < outer - 4 * dx]
        names = ["LHS BNS", "RHS BNS"] if self.bns else ["star"]
        self.spheres = ([dict(name=n, x=x, radius=1.05 * r) for n, x, r in zip(names, self.centers, self.radii)]
                        + [dict(name=f"r = {r / outer:g} xmax", x=0, radius=r) for r in globals_])
        self.global_radii = globals_


def cx_cactus(s):
    return {"cctk_show_schedule": "no", "presync_mode": '"mixed-error"', "terminate": '"either"',
            "cctk_itlast": s.run["iterations"], "cctk_final_time": real(s.run["final_time"])}


def cx_carpetx(s):
    run, every = s.run, s.run["out_every"]
    grid = {"verbose": "no", "poison_undefined_values": "no", "ghost_size": GHOST_SIZE,
            "max_num_levels": s.grid["levels"], "regrid_every": every, "regrid_error_threshold": 0.9,
            "refine_grid_layout": "no", "use_subcycling": "yes", "restrict_during_sync": "no",
            "prolongation_type": '"poly-cons3lfb"', "prolongation_order": PROLONGATION_ORDER,
            "interpolation_order": 3, "dtfac": real(run["dtfac"]), "out_performance_every": every}
    for axis, extent, n in zip("xyz", s.extent, s.ncells):
        grid.update({f"{axis}min": real(-extent), f"{axis}max": real(extent), f"ncells_{axis}": n,
                     f"blocking_factor_{axis}": 8, f"max_grid_size_{axis}": 64, f"max_tile_size_{axis}": 1024000,
                     f"boundary_{axis}": '"neumann"', f"boundary_upper_{axis}": '"neumann"'})
    fields = ("HydroBaseX::rho", "HydroBaseX::vel", "HydroBaseX::press", "ADMBaseX::lapse", "ADMBaseX::shift",
              "ADMBaseX::metric", "ADMBaseX::curv", "Z4c::HC", "Z4c::MtC")
    grid.update({"out_norm_vars": '"all"', "out_norm_omit_unstable": "yes", "out_norm_every": every,
                 "out_metadata": "yes", "out_openpmd_every": run["out3d_every"], "out_openpmd_vars": variables(*fields),
                 "checkpoint_method": '"openpmd"', "recover_method": '"openpmd"'})
    return grid


def cx_box_in_box(s):
    """A fixed box per star (BNS: tracking its centre of mass) and, for BNS
    semiproduction, the shared outer levels; level 0 is the whole domain."""
    grid = s.grid
    regions = []
    if s.offset:
        regions.append((grid["common_levels"], 0, grid["common_boxes"]))
    regions += [(grid["levels"], x, boxes) for x, boxes in zip(s.centers, grid["star_boxes"])]
    boxes = {"num_regions": len(regions)}
    for r, (levels, x, radii) in enumerate(regions, 1):
        boxes.update({f"shape_{r}": '"cube"', f"num_levels_{r}": levels, f"position_x_{r}": real(x),
                      f"radius_{r}": "[-1, " + ", ".join(real(v) for v in radii[:levels - 1]) + "]"})
    return boxes


def cx_ode_solvers(s):
    return {"verbose": "no", "method": '"RK4"'}


def cx_cocal_idx(s):
    data = s.data
    reader = {"COCAL_IDX_PathToID": quoted(data["id"]), "COCAL_IDX_verbose": "no"}
    if s.bns:
        cfg = s.cfg
        if cfg["compact"]:
            reader["COCAL_IDX_bns_compact"] = "yes"
        if cfg["xunit"]:
            reader["COCAL_IDX_bns_xunit"] = "yes"
        if isinstance(cfg["ecc_cor_velx"], (list, tuple)):
            reader.update({f"COCAL_IDX_ecc_cor_velx_star[{i}]": real(v) for i, v in enumerate(cfg["ecc_cor_velx"])})
        else:
            reader["COCAL_IDX_ecc_cor_velx"] = real(cfg["ecc_cor_velx"])
        velz = velocity_pair(cfg["ecc_cor_velz"], "ecc_cor_velz")
        if any(velz):
            reader.update({f"COCAL_IDX_ecc_cor_velz_star[{i}]": real(v) for i, v in enumerate(velz)})
        reader.update({f"COCAL_IDX_cen_x{i}": real(x) for i, x in enumerate(s.centers, 1)})
    else:
        reader["COCAL_IDX_rnstype"] = quoted(data["rnstype"])
    return Block(reader, "COCAL initial data")


def cx_adm_base_x(s):
    return {"initial_data": '"CocalBNS"' if s.bns else '"CocalRNS"', "initial_lapse": '"Cocal"',
            "initial_shift": '"zero"' if s.bns else '"Cocal"', "initial_dtlapse": '"zero"', "initial_dtshift": '"zero"'}


def cx_hydro_base_x(s):
    return {"initial_hydro": '"Cocal"'}


def cx_z4c(s):
    return {"kappa1": 0.02, "kappa2": 0.0, "f_mu_L": 2.0, "f_mu_S": 1.0, "eta": real(s.eta),
            "calc_ADM_vars": "yes", "calc_ADMRHS_vars": "no", "calc_constraints": "yes", "chi_floor": 1.0e-6,
            "alphaG_floor": 1.0e-8, "epsdiss": 0.32, "boundary_conditions": '"NewRadX"'}


def cx_aster_analysis(s):
    return {"compute_MHD": '"yes"', "compute_MHD_spherical": '"no"'}


def cx_aster_seeds(s):
    """Unmagnetized: AsterSeeds only fills Ye, temperature and entropy, after
    the initial data, and seeds no field."""
    return Block({"set_Ye_postinitial": '"yes"', "set_temperature_postinitial": '"yes"',
                  "set_entropy_postinitial": '"yes"', "test_type": '"3DTest"',
                  "test_case": '"magBNS"' if s.bns else '"magTOV"', "Afield_config": '"internal dipole"',
                  "Ab": 0.0, "press_cut": 0.04, "press_max": real(cold_eos(s.data, s.data["peak_density"])[0]),
                  "Avec_kappa": 2.0, "dipole_x": array(s.centers), "initial_beta": '"no"',
                  "set_coorbiting_vel": '"no"', "seed_every": 0}, "Unmagnetized initial state")


def cx_aster_x(s):
    return {"debug_mode": '"no"', "flux_type": '"HLLE"', "use_uct": '"yes"',
            "vector_potential_gauge": '"generalized Lorenz"',
            "lorenz_damp_fac": real(1.5 / (s.run["dtfac"] * s.grid["coarse_dx"])), "local_spatial_order": 4,
            "update_tmunu": '"yes"', "tmunu_interp_order": 4, "local_estimate_error": '"no"',
            "recon_type": '"z_vec"', "use_entropy_fix": '"no"'}


def cx_recon_x(s):
    return {"reconstruction_method": '"ppm"', "ppm_zone_flattening": '"yes"', "ppm_shock_detection": '"no"'}


def cx_eosx(s):
    """COCAL's cold polytrope for the initial data and an ideal gas of the same
    Gamma for the evolution, as in the examples in COCAL_IDX/par: AsterX needs a
    temperature, which EOSX's Hybrid EOS does not provide."""
    gamma, k = s.data["EOS_gamma"][0], s.data["EOS_k0"]
    return Block({"initial_data_eos": '"Polytropic"', "evolution_eos": '"IdealGas"', "poly_gamma": real(gamma),
                  "poly_k": real(k), "gl_gamma": real(gamma), "rho_max": 1e8, "eps_max": 1e8, "eps_min": 1e-12},
                 "EOS from the native COCAL input")


def cx_con2prim_factory(s):
    rho = s.atmosphere
    return {"unit_test": '"no"', "c2p_prime": '"Noble"', "c2p_second": '"Palenzuela"', "c2p_tol": 1e-8,
            "max_iter": 1000, "B_lim": 1e8, "vw_lim": 1e8, "Ye_lenient": '"yes"', "use_temperature": '"no"',
            "thermal_eos_atmo": '"no"', "rho_abs_min": real(rho),
            # A cold atmosphere: tau = rho * eps.
            "tauFluid_atmo": real(rho * cold_eos(s.data, rho)[1]), "atmo_tol": 1e-3, "Ye_atmo": 0.5}


def cx_io_util(s):
    run = s.run
    return {"out_dir": "$parfile", "out_every": run["out_every"], "checkpoint_dir": '"checkpoints"',
            "recover_dir": '"checkpoints"', "checkpoint_ID": "no", "checkpoint_every": -1,
            "checkpoint_every_walltime_hours": real(run["checkpoint_hours"]),
            "checkpoint_on_terminate": yes_no(not s.local), "recover": '"no"' if s.local else '"autoprobe"'}


def cx_timer_report(s):
    return {"out_every": s.run["out_every"], "out_filename": '"TimerReport"', "output_all_timers_together": "yes",
            "output_all_timers_readable": "yes", "n_top_timers": 100}


def cx_volume_integrals_grmhdx(s):
    out = {"outVolIntegral_dir": '"volume_integration"', "VolIntegral_out_every": s.run["out_every"],
           "verbose": 0, "enable_file_output": 1}
    if not s.bns:
        return Block({**out, "set_origin_with_VIX": "no", "NumIntegrals": 1,
                      "Integration_quantity_keyword[1]": '"restmass"'}, labels={1: "Whole-domain rest mass"})
    # Whole-domain CoM as the diagnostic origin; each star's CoM drives its box and sphere.
    matter = {**out, "set_origin_with_VIX": "yes", "NumIntegrals": 4,
              "Integration_quantity_keyword[1]": '"centerofmass"', "Integration_quantity_keyword[4]": '"restmass"'}
    labels = {1: "Whole-domain CoM", 4: "Whole-domain rest mass"}
    for star, (x, radius) in enumerate(zip(s.centers, s.grid["tracking_radii"])):
        slot, centre = star + 2, star + s.offset
        labels[slot] = ("Lhs" if star == 0 else "Rhs") + " CoM"
        matter.update({f"Integration_quantity_keyword[{slot}]": '"centerofmass"',
                       f"volintegral_sphere__center_x_initial[{slot}]": real(x),
                       f"volintegral_inside_sphere__radius[{slot}]": real(radius),
                       f"volintegral_sphere__tracks__amr_centre[{slot}]": centre,
                       f"amr_centre__tracks__volintegral_inside_sphere[{slot}]": centre,
                       f"sphericalsurface__tracks__volintegral_inside_sphere[{slot}]": star})
    return Block(matter, labels=labels)


def cx_volume_integrals_vacuumx(s):
    vacuum = {"HamiltonianVarString": '"Z4c::HC"', "Momentum0VarString": '"Z4c::MtCx"',
              "Momentum1VarString": '"Z4c::MtCy"', "Momentum2VarString": '"Z4c::MtCz"', "verbose": 0,
              "enable_file_output": 1, "outVolIntegral_dir": '"volume_integration"',
              "VolIntegral_out_every": s.run["out_every"]}
    quantities = [("H_M_CnstraintsL2", -1), ("H_M2_CnstraintsL2", -1), ("ADM_Mass", -1), ("ADM_Momentum", -1),
                  ("ADM_Angular_Momentum", -1)]
    if s.global_radii:
        # Finite-radius M and J on the innermost global sphere.
        quantities += [("ADM_Mass", s.global_radii[0]), ("ADM_Angular_Momentum", s.global_radii[0])]
    vacuum["NumIntegrals"] = len(quantities)
    labels = {}
    for slot, (quantity, radius) in enumerate(quantities, 1):
        vacuum[f"Integration_quantity_keyword[{slot}]"] = quoted(quantity)
        if radius > 0:
            vacuum[f"volintegral_inside_sphere__radius[{slot}]"] = real(radius)
        labels[slot] = f"{quantity}, " + ("whole domain" if radius < 0 else f"r={radius:g}")
    return Block(vacuum, labels=labels)


def cx_spherical_surface(s):
    surfaces = {"nsurfaces": len(s.spheres), "maxntheta": 39, "maxnphi": 76}
    for slot, sphere in enumerate(s.spheres):
        surfaces.update({f"name[{slot}]": quoted(sphere["name"]), f"auto_res[{slot}]": "no",
                         f"ntheta[{slot}]": 39, f"nphi[{slot}]": 76, f"set_spherical[{slot}]": "yes",
                         f"radius[{slot}]": real(sphere["radius"]), f"origin_x[{slot}]": real(sphere["x"])})
    return surfaces


def cx_quasi_local_measures(s):
    qlm = {"verbose": "no", "interpolator": '"CarpetX"', "interpolator_options": '"order=3"', "spatial_order": 4,
           "calculate_every": s.run["out_every"], "num_surfaces": len(s.spheres)}
    for slot, sphere in enumerate(s.spheres):
        qlm.update({f"surface_index[{slot}]": slot, f"surface_name[{slot}]": quoted(sphere["name"])})
    return qlm


# Every CarpetX-recipe thorn with parameters, in output order.
CARPETX_BLOCKS = {
    "Cactus": cx_cactus, "CarpetX": cx_carpetx, "BoxInBox": cx_box_in_box, "ODESolvers": cx_ode_solvers,
    "COCAL_IDX": cx_cocal_idx, "ADMBaseX": cx_adm_base_x, "HydroBaseX": cx_hydro_base_x, "Z4c": cx_z4c,
    "AsterAnalysis": cx_aster_analysis, "AsterSeeds": cx_aster_seeds, "AsterX": cx_aster_x,
    "ReconX": cx_recon_x, "EOSX": cx_eosx, "Con2PrimFactory": cx_con2prim_factory, "IOUtil": cx_io_util,
    "TimerReport": cx_timer_report, "VolumeIntegrals_GRMHDX": cx_volume_integrals_grmhdx,
    "VolumeIntegrals_vacuumX": cx_volume_integrals_vacuumx, "SphericalSurface": cx_spherical_surface,
    "QuasiLocalMeasures": cx_quasi_local_measures,
}


def generate(id_dir, overrides=None):
    """A CarpetX + AsterX + Z4c parfile for an RNS or BNS ID with a single polytrope."""
    directory = Path(id_dir).expanduser()
    if (directory / "bbhgrids_3D_mpt1.las").is_file() or (directory / "bhtpar.dat").is_file():
        raise ValueError("The generator covers RNS and BNS IDs; start black-hole runs from a parfile of your own")
    cfg = settings(id_dir, overrides)
    if cfg["gauge"].keys() - {"eta"}:
        raise ValueError("gauge accepts eta only")
    data = CocalMetadata(cfg["id_dir"]).read()
    if data["EOS_type"] != "Hybrid":
        raise ValueError("The generator covers polytropic EOS IDs; start tabulated runs from the examples in COCAL_IDX/par")
    if len(data["EOS_gamma"]) > 1:
        # EOSX needs pwpoly_segm_bound[0] = 0, which its parameter range (0:* rejects.
        raise ValueError("The generator covers single polytropes: EOSX's piecewise polytrope cannot "
                         "be set until its pwpoly_segm_bound range includes 0")
    if data.get("rnstype") == "MRNS_WL":
        raise ValueError("MRNS needs AsterX's vector potential (the AsterX-Msup branch); start from its examples")
    if data["kind"] != "bns" and (cfg["compact"] or cfg["xunit"] or has_bns_velocity(cfg)):
        raise ValueError("compact, xunit and eccentricity velocities apply to BNS only")
    active = list(cfg["active_thorns"])
    for thorn in ("CarpetX", "COCAL_IDX", "Z4c", "AsterX", "EOSX"):
        if thorn not in active:
            raise ValueError(f"The generator needs {thorn}; keep it in active_thorns")
    grid = resolve_grid(data, cfg["grid"], cfg["profile"] == "local")
    run = carpetx_run(cfg, grid)
    s = CarpetXSetup(cfg, data, grid, run, active)
    blocks = {}
    for thorn, function in CARPETX_BLOCKS.items():
        if thorn == "Cactus" or thorn in active:
            block = function(s)
            block = block if isinstance(block, Block) else Block(block)
            blocks[thorn] = dict(parameters=block.parameters, title=block.title or thorn, labels=block.labels or {})
    text = render_parfile(blocks, active, f"CarpetX + AsterX + Z4c: COCAL {data['kind'].upper()}", cfg["profile"])
    metadata = dict(data, profile=cfg["profile"], config_name=cfg["name"], active_thorns=active,
                    grid=grid, run=run, carpetx_ncells=s.ncells, carpetx_extent=s.extent,
                    outer_qlm_radii=s.global_radii, compact=cfg["compact"], xunit=cfg["xunit"],
                    ecc_cor_velx=cfg["ecc_cor_velx"], ecc_cor_velz=cfg["ecc_cor_velz"],
                    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    parfile_sha256=hashlib.sha256(text.encode()).hexdigest())
    return text, metadata


class CocalMetadata:
    """Read native ID metadata without loading the large fluid grids."""

    def __init__(self, directory):
        self.directory = Path(directory).resolve()

    def _numbers(self, line):
        return [float(word.replace("D", "e").replace("d", "e"))
                for word in line.split(":", 1)[0].split("#", 1)[0].split()]

    def _read_eos(self, path):
        """Use the same units and phase ordering as COCAL's peos_initialize."""
        lines = path.read_text().splitlines()
        phases = int(self._numbers(lines[0])[0])
        if not 1 <= phases <= 10:
            raise ValueError(f"{path}: expected a piecewise-polytropic EOS")
        rho0, pressure0 = self._numbers(lines[1])[:2]
        table = [self._numbers(line)[:2] for line in lines[2:phases + 3]][::-1]
        if len(table) != phases + 1 or any(len(row) != 2 for row in table):
            raise ValueError(f"{path}: incomplete EOS table")
        rho, gamma = zip(*table)
        if (not all(math.isfinite(x) and x > 0 for x in (*rho, rho0, pressure0))
                or not all(math.isfinite(x) and x > 1 for x in gamma)
                or any(a >= b for a, b in zip(rho, rho[1:]))):
            raise ValueError(f"{path}: invalid density boundaries or adiabatic indices")
        phase = next((i for i in range(1, phases + 1)
                      if rho[i - 1] <= rho0 <= rho[i]), None)
        if phase is None:
            raise ValueError(f"{path}: EOS reference density is outside the table")
        g, c, solar_mass = G_CGS, C_CGS, MSUN_CGS
        density_unit = DENSITY_UNIT
        pressure_unit = g**3 * solar_mass**2 / c**8
        k0 = pressure0 / rho0**gamma[phase] * pressure_unit / density_unit**gamma[phase]
        for i in range(phase - 1, 0, -1):
            k0 *= (rho[i] * density_unit)**(gamma[i + 1] - gamma[i])
        return dict(EOS_gamma=list(gamma[1:]), EOS_k0=k0,
                    EOS_boundaries=[x * density_unit for x in rho[1:-1]])

    def _fluid_constants(self, path):
        # Only the trailer is needed; do not load the large fluid grid.
        with path.open("rb") as stream:
            shape = [int(word) for word in stream.readline().split()]
            if len(shape) != 3 or any(size < 1 for size in shape):
                raise ValueError(f"{path}: expected three positive grid dimensions")
            start = stream.tell()
            record_width = len(stream.readline())
            stream.seek(start + math.prod(size + 1 for size in shape) * record_width)
            values = self._numbers(stream.readline().decode("ascii"))
        if len(values) < 3 or not all(math.isfinite(value) for value in values[:3]) or values[2] <= 0:
            raise ValueError(f"{path}: missing fluid constants after the grid records")
        return values[:3]

    def _surface_radius(self, path):
        with path.open() as stream:
            nt, np = map(int, stream.readline().split())
            values = [self._numbers(line)[0] for line in stream if line.strip()]
        if len(values) != (nt + 1) * (np + 1):
            raise ValueError(f"{path}: surface dimensions do not match its records")
        if not all(math.isfinite(x) and x > 0 for x in values):
            raise ValueError(f"{path}: surface radii must be finite and positive")
        return max(values)

    def _is_table(self, path):
        """A COCAL EOS table starts with its row count (teos_initialize reads i5, then the
        rows); polytrope exports may carry a placeholder file without one."""
        if not path.is_file():
            return False
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        words = lines[0].split() if lines else []
        return len(words) == 1 and words[0].isdigit() and int(words[0]) == len(lines) - 1 > 1

    def _rns_peak_density(self, directory):
        """rho_max (off-centre peaks) or else rho_c, in G = c = Msol = 1 units."""
        path = next((directory / name for name in ("rnsphyseq.dat", "rnsphyseq_v1.dat")
                     if (directory / name).is_file()), None)
        if path is None:
            raise ValueError(f"{directory}: no rnsphyseq.dat or rnsphyseq_v1.dat")
        values = {}
        for line in path.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() in ("rho_max", "rho_c"):
                values.setdefault(key.strip(), self._numbers(value)[0])
        if not values:
            raise ValueError(f"{path}: no rho_max or rho_c")
        return values.get("rho_max", values.get("rho_c"))

    def read(self):
        """Read unmagnetized RNS or BNS data; refuse ambiguous metadata."""
        directory = self.directory
        if (directory / "bnsflu_3D_mpt1.las").exists():
            teos1 = directory / "teos_parameter_mpt1.dat"
            teos2 = directory / "teos_parameter_mpt2.dat"
            if self._is_table(teos1) or self._is_table(teos2):
                if not self._is_table(teos1) or not self._is_table(teos2) or teos1.read_bytes() != teos2.read_bytes():
                    raise ValueError("Both BNS stars need identical tabulated EOS inputs")
                eos = {"EOS_type": "Tabulated"}
            else:
                eos = self._read_eos(directory / "peos_parameter_mpt1.dat")
                other = self._read_eos(directory / "peos_parameter_mpt2.dat")
                for key in eos:
                    a = eos[key] if isinstance(eos[key], list) else [eos[key]]
                    b = other[key] if isinstance(other[key], list) else [other[key]]
                    if len(a) != len(b) or not all(math.isclose(x, y, rel_tol=1e-12)
                                                  for x, y in zip(a, b)):
                        raise ValueError("GRHayLHD needs the same EOS for both stars")
                eos["EOS_type"] = "Hybrid"
            phy = {}
            for line in (directory / "bnsphyseq.dat").read_text().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() in ("R0", "d*R0", "restmass", "admmass_asymp", "rho_max"):
                        phy[key.strip()] = self._numbers(value.split("nc:", 1)[0])
            radii, scales, distances = [], [], []
            for patch in (1, 2):
                par = (directory / f"rnspar_mpt{patch}.dat").read_text().splitlines()
                kind = par[2].split()[2]
                if kind not in ("CO", "IR", "SP"):
                    raise ValueError(f"Unsupported BNS fluid type {kind}")
                omega, _, scale = self._fluid_constants(
                    directory / f"bnsflu_3D_mpt{patch}.las")
                if not math.isclose(scale, phy["R0"][0], rel_tol=1e-10):
                    raise ValueError("bnsphyseq.dat and the fluid export disagree on R0")
                # COCAL derives dis from its excision-grid radius, not rgmid.
                grid_data = (directory / f"grid_data_mpt{patch}.dat").read_text().splitlines()
                distance_line = next(i + 1 for i, line in enumerate(grid_data) if "dis<" in line)
                distance = self._numbers(grid_data[distance_line])[1]
                if not math.isclose(distance * scale, phy["d*R0"][patch - 1], rel_tol=1e-5):
                    raise ValueError("BNS patch centres disagree with bnsphyseq.dat")
                rsurf = self._numbers((directory / f"r_surf_mpt{patch}.dat").read_text())[0]
                radii.append(self._surface_radius(directory / f"bnssur_3D_mpt{patch}.las") * rsurf * scale)
                scales.append(scale)
                distances.append(distance)
            if not math.isclose(scales[0], scales[1], rel_tol=1e-10):
                raise ValueError("BNS patches use different coordinate scales")
            if not math.isclose(distances[0], distances[1], rel_tol=1e-8):
                raise ValueError("BNS patches use different midpoint distances")
            centers = [-distances[0] * scales[0], distances[1] * scales[1]]
            metadata = dict(kind="bns", centers=centers, max_coordinate_star_radii=radii,
                            source_adm_mass=phy["admmass_asymp"][0],
                            source_rest_masses=phy["restmass"], peak_density=max(phy["rho_max"]))
        elif (directory / "rnsflu_3D.las").exists():
            if any(directory.glob("rnsEMF*.las")) or (directory / "rns4ve_3D.las").exists():
                raise ValueError("This generator supports unmagnetized RNS/BNS only")
            if self._is_table(directory / "teos_parameter.dat"):
                eos = {"EOS_type": "Tabulated"}
            else:
                eos = self._read_eos(directory / "peos_parameter.dat")
                eos["EOS_type"] = "Hybrid"
            omega, _, scale = self._fluid_constants(directory / "rnsflu_3D.las")
            rows = [self._numbers(line) for line in (directory / "rnsphyplot_all.dat").read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
            matches = [row for row in rows if len(row) > 23
                       and math.isclose(row[2], scale, rel_tol=1e-9)
                       and math.isclose(row[18], omega / scale, rel_tol=1e-9, abs_tol=1e-14)]
            if len(matches) != 1:
                raise ValueError("Expected one RNS sequence matching the fluid radius and rotation rate")
            row = matches[0]
            metadata = dict(kind="rns", centers=[0.0],
                            rnstype="RNS_WL" if (directory / "rnsgra_hij_3D.las").exists() else "RNS_CF",
                            max_coordinate_star_radii=[self._surface_radius(directory / "rnssur_3D.las") * scale],
                            source_adm_mass=row[19], source_rest_masses=[row[21]], sequence=int(row[0]),
                            peak_density=self._rns_peak_density(directory))
        else:
            raise ValueError(f"{directory}: expected a COCAL RNS or BNS fluid export")
        if not all(math.isfinite(x) and x > 0 for x in
                   [metadata["source_adm_mass"], *metadata["source_rest_masses"],
                    *metadata["max_coordinate_star_radii"], metadata["peak_density"]]):
            raise ValueError("ID masses, stellar radii and peak density must be finite and positive")
        return dict(metadata, id=str(directory), **eos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", metavar="INDEX_OR_ID", help="configuration index or COCAL ID directory")
    parser.add_argument("--force", action="store_true", help="replace existing .par and .json outputs")
    args = parser.parse_args()
    try:
        id_dir, overrides, index = select_config(args.target)
        text, metadata = generate(id_dir, overrides)
        metadata["config_index"] = index
        output_name = metadata["config_name"] or Path(metadata["id"]).name
        output = Path.cwd() / (output_name + ".par")
        for path in (output, output.with_suffix(".json")):
            if path.exists() and not args.force:
                raise ValueError(f"{path.name} exists; use another directory or --force to replace it")
        output.write_text(text)
        output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Cannot generate parfile: {error}") from None
    print(output)
    grid = metadata["grid"]
    print(f'{metadata["kind"].upper()}, {metadata["profile"]}, dx={grid["finest_dx"]:g}, '
          f'{grid["levels"]} levels, dtfac={metadata["run"]["dtfac"]:g}, '
          f'base grid {array(metadata["carpetx_ncells"])} cells')
    print(f'Object centres x={array(metadata["centers"])}, output every {metadata["run"]["out_every"]}')
    if metadata["kind"] == "bns":
        print(f'BNS export settings: compact={metadata["compact"]}, xunit={metadata["xunit"]}, '
              f'ecc_cor_velx={metadata["ecc_cor_velx"]}, ecc_cor_velz={metadata["ecc_cor_velz"]}')


if __name__ == "__main__":
    main()
