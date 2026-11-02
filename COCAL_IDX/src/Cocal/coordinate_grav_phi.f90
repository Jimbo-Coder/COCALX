!  phi_coordinate
!______________________________________________
module COCAL_ID_coordinate_grav_phi
use COCAL_ID_phys_constant,  only : pi, nnpg, long
use COCAL_ID_grid_parameter, only : npg
implicit none
  Real(long) :: dphig, dphiginv  
  Real(long) :: phig(0:nnpg), hphig(nnpg)
! Subroutine
contains
subroutine grid_phi       ! phi-coordinate. Angular part of the grid.     

implicit none
  Integer  ::  ip
! 
  dphig = 2.0e0*pi/REAL(npg)
  dphiginv=1.0e0/dphig
! 
  phig(0) = 0.0d0
  do ip = 1, npg
    phig(ip) = Real(ip)*dphig + phig(0)
    hphig(ip) = 0.5d0*(phig(ip) + phig(ip-1))
  end do
! 
end subroutine grid_phi    
end module COCAL_ID_coordinate_grav_phi