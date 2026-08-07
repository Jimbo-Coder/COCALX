#include <loop.hxx>

#include <cctk.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

static_assert(std::is_same_v<CCTK_REAL, double>,
              "The COCAL Fortran reader requires CCTK_REAL to be double");

extern "C" void COCAL_IDX_FillCoordinates(
    const std::intptr_t cctkGH_address, const int centering_i,
    const int centering_j, const int centering_k, const int nx, const int ny,
    const int nz, CCTK_REAL *const coordinates) {
  const auto *const cctkGH = reinterpret_cast<const cGH *>(cctkGH_address);
  const Loop::GridDescBase grid(cctkGH);

  if (centering_i < 0 || centering_i > 1 || centering_j < 0 ||
      centering_j > 1 || centering_k < 0 || centering_k > 1) {
    CCTK_VError(__LINE__, __FILE__, CCTK_THORNSTRING,
                "Invalid CarpetX centering (%d,%d,%d)", centering_i,
                centering_j, centering_k);
  }
  if (nx != grid.ash[0] || ny != grid.ash[1] || nz != grid.ash[2]) {
    CCTK_VError(__LINE__, __FILE__, CCTK_THORNSTRING,
                "Coordinate buffer shape (%d,%d,%d) does not match the "
                "CarpetX allocated shape (%d,%d,%d)",
                nx, ny, nz, grid.ash[0], grid.ash[1], grid.ash[2]);
  }

  const Loop::vect<int, Loop::dim> centering{centering_i, centering_j,
                                              centering_k};
  grid.loop_idx(Loop::where_t::everywhere, centering,
                [&](const Loop::PointDesc &p) {
                  const std::size_t index =
                      static_cast<std::size_t>(p.I[0]) +
                      static_cast<std::size_t>(nx) *
                          (static_cast<std::size_t>(p.I[1]) +
                           static_cast<std::size_t>(ny) *
                               static_cast<std::size_t>(p.I[2]));
                  coordinates[3 * index + 0] = p.X[0];
                  coordinates[3 * index + 1] = p.X[1];
                  coordinates[3 * index + 2] = p.X[2];
                });
}
