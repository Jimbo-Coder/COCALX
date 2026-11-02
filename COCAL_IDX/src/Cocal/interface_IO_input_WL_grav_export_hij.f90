module COCAL_ID_interface_IO_input_WL_grav_export_hij
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_WL_grav_export_hij(filenm,coc2cac_readformat,hxxd,hxyd,hxzd,hyyd,hyzd,hzzd)
      real(8), pointer :: hxxd(:,:,:), hxyd(:,:,:), hxzd(:,:,:), &
          &               hyyd(:,:,:), hyzd(:,:,:), hzzd(:,:,:)
      character(len=*) :: filenm, coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_WL_grav_export_hij
  end interface
end module COCAL_ID_interface_IO_input_WL_grav_export_hij