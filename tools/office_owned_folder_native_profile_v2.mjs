/* Profile based on observed original OneDrive/PowerPoint roles and DOM nodes.
 * A fresh folder's exact heading, row/name/count selectors and the download
 * menu sequence must be observed and source-reviewed before native dispatch.
 * No file/account IDs or task answers are embedded in this public source.
 */
export function powerPointNativeProfile({folderHeading,itemRowsSelector,nameCellSelector,folderCount,downloadSteps,deleteSteps,sourceReviewed=false}) {
 if(!folderHeading||!itemRowsSelector||!nameCellSelector||!folderCount||!Array.isArray(downloadSteps)||!Array.isArray(deleteSteps))throw new Error('actual_native_folder_and_menu_profile_required');
 return {schema:'office-owned-folder-native-ui-profile-v2',source_reviewed:sourceReviewed,cell_id:'powerpoint-web',
  folder_heading:{role:'heading',name:folderHeading},item_rows_selector:itemRowsSelector,name_cell_selector:nameCellSelector,folder_count:folderCount,
  upload_steps:[{role:'button',name:'Create or upload'},{role:'menuitem',name:'Files upload'}],
  open_steps:[{role:'menuitem',name:'Open'},{role:'menuitem',name:'Open in browser'}],
  editor_frame_selector:'iframe#WacFrame_PowerPoint_0',editor_ready:{selector:'#ModeSwitcher[aria-label*="Editing Selected"]'},
  native_mode_selector:'#ModeSwitcher',native_mode_attribute:'aria-label',native_mode_editing_regex:'Editing Selected',
  download_steps:downloadSteps,delete_steps:deleteSteps};
}
