module COCAL_ID_interface_IO_input_gradvep_export 
implicit none
  interface
  
subroutine COCAL_ID_IO_input_gradvep_export(filenm,coc2cac_readformat, vepxf, vepyf, vepzf)
      real(8), pointer :: vepxf(:,:,:), vepyf(:,:,:), vepzf(:,:,:)
      character(len=*) :: filenm,coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_gradvep_export
  end interface
end module COCAL_ID_interface_IO_input_gradvep_export