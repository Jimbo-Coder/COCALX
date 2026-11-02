module COCAL_ID_interface_IO_input_CF_grav_export
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_CF_grav_export(filenm,coc2cac_readformat, psi,alph,bvxd,bvyd,bvzd)
      real(8), pointer :: psi(:,:,:), alph(:,:,:), bvxd(:,:,:), bvyd(:,:,:), bvzd(:,:,:)
      character(len=*) :: filenm, coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_CF_grav_export
  end interface
end module COCAL_ID_interface_IO_input_CF_grav_export