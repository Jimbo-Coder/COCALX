module COCAL_ID_interface_invhij_WL_export
implicit none
  interface 
  
subroutine COCAL_ID_invhij_WL_export(hxxd,hxyd,hxzd,hyyd,hyzd,hzzd,hxxu,hxyu,hxzu,hyyu,hyzu,hzzu)
      real(8), pointer :: hxxd(:,:,:), hxyd(:,:,:), hxzd(:,:,:), &
          &               hyyd(:,:,:), hyzd(:,:,:), hzzd(:,:,:), &
          &               hxxu(:,:,:), hxyu(:,:,:), hxzu(:,:,:), &
          &               hyyu(:,:,:), hyzu(:,:,:), hzzu(:,:,:)
  
end subroutine COCAL_ID_invhij_WL_export
  end interface
end module COCAL_ID_interface_invhij_WL_export