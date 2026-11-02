module COCAL_ID_interface_IO_input_CF_surf_export
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_CF_surf_export(filenm,coc2cac_readformat, rs)
      real(8), pointer :: rs(:,:)
      character(len=*) :: filenm,coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_CF_surf_export
  end interface
end module COCAL_ID_interface_IO_input_CF_surf_export