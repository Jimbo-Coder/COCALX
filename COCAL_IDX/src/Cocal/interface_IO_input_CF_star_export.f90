module COCAL_ID_interface_IO_input_CF_star_export
implicit none
  interface 
  
subroutine COCAL_ID_IO_input_CF_star_export(filenm,coc2cac_readformat,emd,rs,omef,ome,ber,radi)
      real(8), pointer :: emd(:,:,:), rs(:,:), omef(:,:,:)
      real(8) ::  ome,ber,radi
      character(len=*) :: filenm, coc2cac_readformat
  
end subroutine COCAL_ID_IO_input_CF_star_export
  end interface
end module COCAL_ID_interface_IO_input_CF_star_export