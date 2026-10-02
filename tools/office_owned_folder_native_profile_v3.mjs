/* Fresh reviewed original Office roles; all identity values stay private. */
export function powerPointNativeProfile({folderHeading,itemRowsSelector,nameCellSelector,inventoryProof,
  signedInPrincipal,downloadSteps,deleteSteps,sourceReviewed=false}) {
 if(!folderHeading||!itemRowsSelector||!nameCellSelector||!inventoryProof||!signedInPrincipal||!Array.isArray(downloadSteps)||!downloadSteps.length||!Array.isArray(deleteSteps))throw new Error('actual_native_folder_principal_and_toolbar_profile_required');
 if(inventoryProof.mode!=='parent_card_count')throw new Error('actual_native_parent_card_inventory_profile_required');
 return {schema:'office-owned-folder-native-ui-profile-v3',source_reviewed:sourceReviewed,cell_id:'powerpoint-web',
  folder_heading:{role:'heading',name:folderHeading},item_rows_selector:itemRowsSelector,name_cell_selector:nameCellSelector,
  folder_inventory_proof:inventoryProof,signed_in_principal:signedInPrincipal,
  empty_state:{text:'This folder is empty'},download_surface:'folder_toolbar',
  upload_steps:[{role:'button',name:'Create or upload'},{role:'menuitem',name:'Files upload'}],
  open_steps:[{role:'menuitem',name:'Open'},{role:'menuitem',name:'Open in browser'}],
  editor_frame_selector:'iframe#WacFrame_PowerPoint_0',editor_ready:{selector:'#ModeSwitcher[aria-label*="Editing Selected"]'},
  saved_status:{selector:'#SaveStatusButton'},saved_status_attribute:'aria-label',saved_status_expected:'Saved to OneDrive\nClick the cloud icon to view file location',
  native_mode_selector:'#ModeSwitcher',native_mode_attribute:'aria-label',native_mode_editing_regex:'Editing Selected',
  download_steps:downloadSteps,delete_steps:deleteSteps};
}
