module COCAL_ID_interface_IO_input_star4ve_export
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_star4ve_export(filenm,coc2cac_readformat, utf,uxf,uyf,uzf)
      real(8), pointer :: utf(:,:,:), uxf(:,:,:), uyf(:,:,:), uzf(:,:,:)
      character(len=*) :: filenm,coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_star4ve_export
  end interface
end module COCAL_ID_interface_IO_input_star4ve_export