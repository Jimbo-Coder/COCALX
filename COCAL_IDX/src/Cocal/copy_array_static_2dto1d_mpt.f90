! ----------------------------------------------------------------------
!  Copy array
! ----------------------------------------------------------------------
module COCAL_ID_copy_array_static_2dto1d_mpt
use COCAL_ID_phys_constant, only : long, nnmpt
implicit none
contains
! - - - - -
! 
subroutine copy_arraystatic_2dto1d_mpt(impt,array1,array2,n1min,n1max)

implicit none
  integer, intent(in)  :: n1min, n1max, impt
!  real(long)           :: array1(-2:nnrg,1:nnmpt), array2(-2:nnrg)
  real(long) :: array1(n1min:n1max,1:nnmpt), array2(n1min:n1max)
      array2(n1min:n1max) &
  & = array1(n1min:n1max,impt)
end subroutine copy_arraystatic_2dto1d_mpt
end module COCAL_ID_copy_array_static_2dto1d_mpt