module interface_IO_input_CF_flco_export
implicit none
  interface

subroutine IO_input_CF_flco_export(filenm,coc2cac_readformat, emd,ome,ber,radi,xcm)
      real(8), pointer :: emd(:,:,:)
      real(8) ::  ome,ber,radi,xcm
      character(len=*) :: filenm,coc2cac_readformat

end subroutine IO_input_CF_flco_export
  end interface
end module interface_IO_input_CF_flco_export
