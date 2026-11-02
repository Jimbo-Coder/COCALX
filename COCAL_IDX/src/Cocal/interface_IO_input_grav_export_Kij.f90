module COCAL_ID_interface_IO_input_grav_export_Kij
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_grav_export_Kij(filenm,kxx,kxy,kxz,kyy,kyz,kzz)
      real(8), pointer :: kxx(:,:,:), kxy(:,:,:), kxz(:,:,:), &
          &               kyy(:,:,:), kyz(:,:,:), kzz(:,:,:)
      character(len=*) :: filenm
  
end subroutine COCAL_ID_IO_input_grav_export_Kij
  end interface
end module COCAL_ID_interface_IO_input_grav_export_Kij