#include <loop.hxx>

#include <cctk.h>
#include <cctk_Arguments.h>
#include <cctk_Parameters.h>

#include <array>
#include <cmath>

// The ADMBaseX and HydroBaseX values at one point (cocal_id_grid.F90).
extern "C" void COCAL_ID_eval_carpetx(double x, double y, double z,
                                      double *adm, double *matter, int *ok);

namespace COCAL_IDX {
using namespace Loop;

// AsterX's vector potential: A_i as set in HydroBaseX (the same edge
// centrings), and Psi = sqrt(det g) Aphi at the vertices. Both are zero
// unless MRNS_WL data give the potential (COCAL_IDX_read_magnetic_potential).
extern "C" void COCAL_ID_set_asterx(CCTK_ARGUMENTS) {
  DECLARE_CCTK_ARGUMENTSX_COCAL_ID_set_asterx;
  DECLARE_CCTK_PARAMETERS;

  const bool potential = CCTK_EQUALS(initial_data, "CocalRNS") &&
                         CCTK_EQUALS(COCAL_IDX_rnstype, "MRNS_WL") &&
                         COCAL_IDX_read_magnetic_potential;

  grid.loop_all<1, 0, 0>(grid.nghostzones,
                         [&](const PointDesc &p) { Avec_x(p.I) = Avecx(p.I); });
  grid.loop_all<0, 1, 0>(grid.nghostzones,
                         [&](const PointDesc &p) { Avec_y(p.I) = Avecy(p.I); });
  grid.loop_all<0, 0, 1>(grid.nghostzones,
                         [&](const PointDesc &p) { Avec_z(p.I) = Avecz(p.I); });

  bool failed = false;
  grid.loop_all<0, 0, 0>(grid.nghostzones, [&](const PointDesc &p) {
    if (!potential) {
      Psi(p.I) = 0;
      return;
    }
    std::array<double, 16> adm;
    std::array<double, 13> matter;
    int ok;
    COCAL_ID_eval_carpetx(p.x, p.y, p.z, adm.data(), matter.data(), &ok);
    failed = failed || !ok;
    const double gxx = adm[4], gxy = adm[5], gxz = adm[6];
    const double gyy = adm[7], gyz = adm[8], gzz = adm[9];
    const double detg = gxx * (gyy * gzz - gyz * gyz) -
                        gxy * (gxy * gzz - gyz * gxz) +
                        gxz * (gxy * gyz - gyy * gxz);
    Psi(p.I) = std::sqrt(detg) * matter[12];
  });
  if (failed)
    CCTK_ERROR("COCAL_ID: a CarpetX point is outside the COCAL data or "
               "invalid there.");
}

} // namespace COCAL_IDX
