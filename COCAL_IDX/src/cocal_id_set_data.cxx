#include <loop.hxx>

#include <cctk.h>
#include <cctk_Arguments.h>
#include <cctk_Parameters.h>

#include <array>

// The ADMBaseX and HydroBaseX values at one point (cocal_id_grid.F90).
extern "C" void COCAL_ID_eval_carpetx(double x, double y, double z,
                                      double *adm, double *matter, int *ok);

namespace COCAL_IDX {
using namespace Loop;

// The COCAL values at every point of a grid function's own centring, so
// no staggering offsets are needed: the metric at vertices, the fluid and
// B^i at cell centres and A_i on the cell edges.
namespace {
struct point_values {
  // alpha, beta^i, g_ij, K_ij
  std::array<double, 16> adm;
  // rho, press, eps, v^i, A_i, B^i, Aphi
  std::array<double, 13> matter;
  bool failed = false;

  void eval(const PointDesc &p) {
    int ok;
    COCAL_ID_eval_carpetx(p.x, p.y, p.z, adm.data(), matter.data(), &ok);
    failed = failed || !ok;
  }
};

void check(const point_values &v) {
  // Invalid: non-finite, nonpositive psi or alpha, or v >= 1.
  if (v.failed)
    CCTK_ERROR("COCAL_ID: a CarpetX point is outside the COCAL data or "
               "invalid there.");
}
} // namespace

// alpha and beta^i only when initial_lapse and initial_shift are "Cocal".
extern "C" void COCAL_ID_set_metric(CCTK_ARGUMENTS) {
  DECLARE_CCTK_ARGUMENTSX_COCAL_ID_set_metric;
  DECLARE_CCTK_PARAMETERS;

  const bool set_lapse = CCTK_EQUALS(initial_lapse, "Cocal");
  const bool set_shift = CCTK_EQUALS(initial_shift, "Cocal");
  point_values v;
  grid.loop_all<0, 0, 0>(grid.nghostzones, [&](const PointDesc &p) {
    v.eval(p);
    const auto &s = v.adm;
    if (set_lapse)
      alp(p.I) = s[0];
    if (set_shift) {
      betax(p.I) = s[1];
      betay(p.I) = s[2];
      betaz(p.I) = s[3];
    }
    gxx(p.I) = s[4];
    gxy(p.I) = s[5];
    gxz(p.I) = s[6];
    gyy(p.I) = s[7];
    gyz(p.I) = s[8];
    gzz(p.I) = s[9];
    kxx(p.I) = s[10];
    kxy(p.I) = s[11];
    kxz(p.I) = s[12];
    kyy(p.I) = s[13];
    kyz(p.I) = s[14];
    kzz(p.I) = s[15];
  });
  check(v);
}

// MRNS data give A_i (COCAL_IDX_read_magnetic_potential) or B^i; the other,
// and both for other IDs, are zero.
extern "C" void COCAL_ID_set_hydro(CCTK_ARGUMENTS) {
  DECLARE_CCTK_ARGUMENTSX_COCAL_ID_set_hydro;
  DECLARE_CCTK_PARAMETERS;

  const bool potential = CCTK_EQUALS(initial_data, "CocalRNS") &&
                         CCTK_EQUALS(COCAL_IDX_rnstype, "MRNS_WL") &&
                         COCAL_IDX_read_magnetic_potential;

  point_values v;
  grid.loop_all<1, 1, 1>(grid.nghostzones, [&](const PointDesc &p) {
    v.eval(p);
    const auto &s = v.matter;
    rho(p.I) = s[0];
    press(p.I) = s[1];
    eps(p.I) = s[2];
    velx(p.I) = s[3];
    vely(p.I) = s[4];
    velz(p.I) = s[5];
    Bvecx(p.I) = s[9];
    Bvecy(p.I) = s[10];
    Bvecz(p.I) = s[11];
  });
  grid.loop_all<1, 0, 0>(grid.nghostzones, [&](const PointDesc &p) {
    if (potential)
      v.eval(p);
    Avecx(p.I) = potential ? v.matter[6] : 0;
  });
  grid.loop_all<0, 1, 0>(grid.nghostzones, [&](const PointDesc &p) {
    if (potential)
      v.eval(p);
    Avecy(p.I) = potential ? v.matter[7] : 0;
  });
  grid.loop_all<0, 0, 1>(grid.nghostzones, [&](const PointDesc &p) {
    if (potential)
      v.eval(p);
    Avecz(p.I) = potential ? v.matter[8] : 0;
  });
  check(v);
}

} // namespace COCAL_IDX
