! The values at one point, for the C++ loops of cocal_id_set_data.cxx.
! Included by COCAL_ID_master.F90.

! The ADMBaseX and HydroBaseX values at (x,y,z): adm = alpha, beta^i, g_ij,
! K_ij and matter = rho, press, eps, v^i, A_i, B^i, Aphi. ok = 0 outside the
! COCAL data or for an invalid state (non-finite, nonpositive psi or alpha, or
! v >= 1).
subroutine COCAL_ID_eval_carpetx(x, y, z, adm, matter, ok) bind(c, name="COCAL_ID_eval_carpetx")
  use, intrinsic :: iso_c_binding, only : c_double, c_int
  use COCAL_ID_state
  use COCAL_ID_eval
  implicit none
  real(c_double), value :: x, y, z
  real(c_double), intent(out) :: adm(16), matter(13)
  integer(c_int), intent(out) :: ok
  real(8) :: s(NSTATE)
  logical :: valid

  call COCAL_ID_eval_point(x, y, z, s, valid)
  adm = s(S_ALP:S_K + 5)
  matter = [s(S_RHO:S_VEL + 2), s(S_AVEC:S_AVEC + 2), s(S_BVEC:S_BVEC + 2), s(S_APHI)]
  ok = merge(1, 0, valid)
end subroutine COCAL_ID_eval_carpetx
