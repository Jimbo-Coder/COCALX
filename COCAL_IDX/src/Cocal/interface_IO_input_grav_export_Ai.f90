module COCAL_ID_interface_IO_input_grav_export_Ai
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_grav_export_Ai(filenm,coc2cac_readformat, va,vaxd,vayd,vazd)
      real(8), pointer :: va(:,:,:), vaxd(:,:,:), vayd(:,:,:), vazd(:,:,:)
      character(len=*) :: filenm,coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_grav_export_Ai
  end interface
end module COCAL_ID_interface_IO_input_grav_export_Ai