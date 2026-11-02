subroutine COCAL_ID_copy_grid_parameter_binary_excision_to_mpt(impt)

use COCAL_ID_grid_parameter_binary_excision_mpt
use COCAL_ID_grid_parameter_binary_excision
implicit none
  integer :: i, impt
!  
  i=0
  i=i+1; grid_param_bin_ex_int_(i,impt) = ex_nrg 
  i=i+1; grid_param_bin_ex_int_(i,impt) = ex_ndis

  i=0
  i=i+1; grid_param_bin_ex_real_(i,impt) = ex_radius
  i=i+1; grid_param_bin_ex_real_(i,impt) = ex_rgin
  i=i+1; grid_param_bin_ex_real_(i,impt) = ex_rgmid
  i=i+1; grid_param_bin_ex_real_(i,impt) = ex_rgout

end subroutine COCAL_ID_copy_grid_parameter_binary_excision_to_mpt
