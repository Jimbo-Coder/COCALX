subroutine COCAL_ID_allocate_grid_parameter_binary_excision_mpt

use COCAL_ID_phys_constant, only : nmpt
use COCAL_ID_grid_parameter_binary_excision_mpt
use COCAL_ID_make_int_array_2d
use COCAL_ID_make_array_2d
implicit none
!
  call alloc_int_array2d(grid_param_bin_ex_int_ , 1, 10, 1, nmpt)
  call alloc_array2d(grid_param_bin_ex_real_ , 1, 10, 1, nmpt)
!
end subroutine COCAL_ID_allocate_grid_parameter_binary_excision_mpt
