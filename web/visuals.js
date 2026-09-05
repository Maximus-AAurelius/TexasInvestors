'use strict';
async function loadVisuals(lead) {
  const panel = document.querySelector('#visual-panel');
  if (!panel) return;
  try {
    const visual = await api('/api/visuals?id=' + encodeURIComponent(lead.id));
    if (state.selected !== lead.id || !panel.isConnected) return;
    renderVisuals(panel, lead, visual);
  } catch (error) { if (panel.isConnected) panel.textContent = 'Property visuals could not load: ' + error.message; }
}
function renderVisuals(panel, lead, visual) {
  const query = new URLSearchParams({api:'1',query:lead.address+', '+lead.county+' County, Texas'});
  panel.innerHTML = `<h3>Property photos & location</h3>${visual.has_photo?`<figure class="property-photo"><img src="/api/photo?id=${encodeURIComponent(lead.id)}&v=${encodeURIComponent(visual.updated_at)}" alt="User-attached photo for ${esc(lead.address)}"><figcaption>${esc(visual.caption||'User-attached property photo')} · Taken: ${esc(visual.photo_date||'Date not recorded')}</figcaption></figure>`:'<p class="notice">No property photo attached yet. Add your own photo or one you have permission to use.</p>'}<div class="visual-links"><a target="_blank" rel="noreferrer" href="https://www.google.com/maps/search/?${query}">Find address in Google Maps ↗</a>${visual.satellite_url?`<a target="_blank" rel="noreferrer" href="${esc(visual.satellite_url)}">Satellite view ↗</a><a target="_blank" rel="noreferrer" href="${esc(visual.street_view_url)}">Street View ↗</a>`:''}</div><p class="muted">Map imagery opens on Google Maps. Check the address and imagery date; Street View may show a nearby road or be unavailable.</p><details><summary>Set satellite / Street View location</summary><p class="muted">Find the property in Google Maps, right-click its location and copy the latitude and longitude. Save them below after checking the correct property.</p><form id="location-form"><div class="form-grid"><label>Latitude<input name="latitude" type="number" min="-90" max="90" step="any" required value="${esc(visual.latitude??'')}"></label><label>Longitude<input name="longitude" type="number" min="-180" max="180" step="any" required value="${esc(visual.longitude??'')}"></label></div><button>Save location</button>${visual.latitude!==null?'<button type="button" id="clear-location" class="secondary">Clear location</button>':''}</form></details><details><summary>${visual.has_photo?'Replace / remove photo':'Attach a property photo'}</summary><form id="photo-form"><label>JPEG, PNG or WebP · up to 2 MB<input name="photo" type="file" accept="image/jpeg,image/png,image/webp" required></label><label>Source / caption<input name="caption" maxlength="500" placeholder="Own visit, seller-provided with permission..."></label><label>Date taken (if known)<input name="photo_date" type="date"></label><p class="muted">Saved locally. Replaces the existing cover photo. Uploads are resized and metadata is removed.</p><button>Save photo</button>${visual.has_photo?'<button type="button" id="remove-photo" class="secondary">Remove photo</button>':''}</form></details><p id="visual-status" role="status"></p>`;
  const save = async (payload, button) => {
    button.disabled=true;
    panel.querySelector('#visual-status').textContent='Saving...';
    try { const updated=await api('/api/visuals',{id:lead.id,...payload}); if(panel.isConnected&&state.selected===lead.id) {renderVisuals(panel,lead,updated);panel.querySelector('#visual-status').textContent='Saved locally';if(payload.action==='location'||payload.action==='clear_location')await refreshResearch(lead);} }
    catch(error) { if(panel.isConnected) panel.querySelector('#visual-status').textContent=error.message; }
    finally {button.disabled=false;}
  };
  panel.querySelector('#location-form').onsubmit=event=>{event.preventDefault();save({action:'location',...Object.fromEntries(new FormData(event.currentTarget))},event.currentTarget.querySelector('button'));};
  panel.querySelector('#photo-form').onsubmit=async event=>{
    event.preventDefault(); const form=event.currentTarget,file=form.elements.photo.files[0];
    if(!file||file.size>2000000){panel.querySelector('#visual-status').textContent='Choose a photo under 2 MB.';return;}
    const caption=form.elements.caption.value,photo_date=form.elements.photo_date.value;
    const reader=new FileReader();reader.onerror=()=>{if(panel.isConnected)panel.querySelector('#visual-status').textContent='The photo could not be read.';};
    reader.onload=()=>save({action:'photo',image:String(reader.result).split(',')[1],caption,photo_date},form.querySelector('button'));
    reader.readAsDataURL(file);
  };
  const remove=panel.querySelector('#remove-photo');if(remove)remove.onclick=()=>save({action:'remove_photo'},remove);
  const clear=panel.querySelector('#clear-location');if(clear)clear.onclick=()=>save({action:'clear_location'},clear);
}
