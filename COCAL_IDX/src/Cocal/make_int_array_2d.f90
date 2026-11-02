! ----------------------------------------------------------------------
!  Allocate 2D array
! ----------------------------------------------------------------------
module COCAL_ID_make_int_array_2d
use COCAL_ID_phys_constant, only : long
implicit none
contains
! 2D array
subroutine alloc_int_array2d(array,n1min,n1max,n2min,n2max)

implicit none
  integer,Intent(IN)  :: n1min, n1max, n2min, n2max
  integer             :: status
  integer, Pointer    :: array(:,:)
  Allocate(array(n1min:n1max,n2min:n2max),stat=status)
end subroutine alloc_int_array2d
end module COCAL_ID_make_int_array_2d