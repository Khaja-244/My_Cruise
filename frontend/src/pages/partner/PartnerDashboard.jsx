import PageHero from '../../components/ui/PageHero';
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { ItineraryEditor } from '../../components/forms/StructuredEditors';
import { Loading, ErrorBox, EmptyState } from '../../components/ui/States';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import NoticeDialog from '../../components/ui/NoticeDialog';

const money = (cents) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((Number(cents) || 0) / 100);
const emptyCruise = { name: '', slug: '', description: '', ship_id: '', ship_name: '', operator_name: '', embark_port_id: '', disembark_port_id: '', sailing_days: 7, start_sailing_date: '', return_date: '', base_price_cents: 0 };
const emptyDetail = { edit_id: '', edit_kind: '', deck_number: 1, deck_name: '', ct_name: '', ct_max_occupancy: 2, ct_base_price_cents: 0, ct_extra_price_cents: 0, ct_description: '', amenity_ids: [], deck_id: '', cabin_type_id: '', cabin_number: '', cabin_max_occupancy: 2, image_url: '', image_alt: '', itinerary_json: '[]' };
const emptySailing = { edit_id: '', departure_date: '', return_date: '', booking_closes_at: '', port_fee_per_guest_cents: 0 };

function Status({ value }) {
  const tone = ['approved', 'published', 'active', 'connected', 'confirmed', 'available'].includes(String(value)) ? 'status-good' : ['rejected', 'disabled', 'suspended', 'cancelled', 'blocked'].includes(String(value)) ? 'status-bad' : 'status-warn';
  return <span className={`status-pill ${tone}`}>{String(value || '—').replaceAll('_', ' ')}</span>;
}
function Field({ label, children }) { return <label className="block text-sm font-bold text-secondary"><span>{label}</span><div className="mt-1.5">{children}</div></label>; }

export default function PartnerDashboard() {
  const qc = useQueryClient();
  const [tab, setTab] = useState('overview');
  const [selectedCruise, setSelectedCruise] = useState('');
  const [editingCruise, setEditingCruise] = useState(null);
  const [cruiseForm, setCruiseForm] = useState(emptyCruise);
  const [detail, setDetail] = useState(emptyDetail);
  const [sailingForm, setSailingForm] = useState(emptySailing);
  const [website, setWebsite] = useState({ name: '', website_url: '' });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [inventorySailing, setInventorySailing] = useState('');
  const [inventoryEdits, setInventoryEdits] = useState({});

  const dashboard = useQuery({ queryKey: ['partner-dashboard'], queryFn: async () => (await api.get('/partners/dashboard')).data });
  const bookings = useQuery({ queryKey: ['partner-bookings'], queryFn: async () => (await api.get('/partners/bookings')).data });
  const ports = useQuery({ queryKey: ['partner-ports'], queryFn: async () => (await api.get('/ports')).data });
  const amenities = useQuery({ queryKey: ['partner-amenities'], queryFn: async () => (await api.get('/amenities')).data });
  const cruiseDetail = useQuery({ queryKey: ['partner-cruise', selectedCruise], queryFn: async () => (await api.get(`/partners/cruises/${selectedCruise}`)).data, enabled: !!selectedCruise });
  const inventory = useQuery({ queryKey: ['partner-inventory', inventorySailing], queryFn: async () => (await api.get(`/partners/sailings/${inventorySailing}/inventory`)).data, enabled: !!inventorySailing });

  const selectedCruiseRow = useMemo(() => dashboard.data?.cruises?.find(x => x.id === selectedCruise), [dashboard.data, selectedCruise]);

  const notifySuccess = text => { setMessage(text); setError(''); setNotice(text); };
  const notifyError = e => { const text = e.response?.data?.error?.message || e.message || 'The request could not be completed.'; setError(text); setMessage(''); setNotice(text); };

  const saveCruise = useMutation({
    mutationFn: async () => {
      if (editingCruise) {
        return api.patch(`/partners/cruises/${editingCruise}`, {
          name: cruiseForm.name, slug: cruiseForm.slug, description: cruiseForm.description,
          sailing_days: Number(cruiseForm.sailing_days), base_price_cents: Number(cruiseForm.base_price_cents),
          start_sailing_date: cruiseForm.start_sailing_date || null, return_date: cruiseForm.return_date || null,
          embark_port_id: cruiseForm.embark_port_id, disembark_port_id: cruiseForm.disembark_port_id,
        });
      }
      return api.post('/partners/cruises', { ...cruiseForm, sailing_days: Number(cruiseForm.sailing_days), base_price_cents: Number(cruiseForm.base_price_cents), ship_id: cruiseForm.ship_id || null, start_sailing_date: cruiseForm.start_sailing_date || null, return_date: cruiseForm.return_date || null });
    },
    onSuccess: () => { setEditingCruise(null); setCruiseForm(emptyCruise); notifySuccess(editingCruise ? 'Cruise updated and resubmitted for approval.' : 'Cruise created and submitted for approval.'); qc.invalidateQueries({ queryKey: ['partner-dashboard'] }); },
    onError: notifyError,
  });
  const deleteCruise = useMutation({ mutationFn: id => api.delete(`/partners/cruises/${id}`), onSuccess: () => { setDeleteTarget(null); setSelectedCruise(''); notifySuccess('Cruise removed.'); qc.invalidateQueries({ queryKey: ['partner-dashboard'] }); }, onError: notifyError });

  const detailAction = useMutation({
    mutationFn: async ({ kind, edit_id }) => {
      if (kind === 'deck') return api.post(`/partners/cruises/${selectedCruise}/decks`, { deck_number: Number(detail.deck_number), name: detail.deck_name });
      if (kind === 'deckUpdate') return api.patch(`/partners/cruises/${selectedCruise}/decks/${edit_id || detail.edit_id}`, { deck_number: Number(detail.deck_number), name: detail.deck_name });
      if (kind === 'deckDelete') return api.delete(`/partners/cruises/${selectedCruise}/decks/${edit_id || detail.edit_id}`);
      if (kind === 'type') return api.post(`/partners/cruises/${selectedCruise}/cabin-types`, { name: detail.ct_name, description: detail.ct_description, max_occupancy: Number(detail.ct_max_occupancy), base_price_cents: Number(detail.ct_base_price_cents), price_per_extra_guest_cents: Number(detail.ct_extra_price_cents), amenity_ids: detail.amenity_ids });
      if (kind === 'typeUpdate') return api.patch(`/partners/cruises/${selectedCruise}/cabin-types/${edit_id || detail.edit_id}`, { name: detail.ct_name, description: detail.ct_description, max_occupancy: Number(detail.ct_max_occupancy), base_price_cents: Number(detail.ct_base_price_cents), price_per_extra_guest_cents: Number(detail.ct_extra_price_cents), amenity_ids: detail.amenity_ids });
      if (kind === 'typeDelete') return api.delete(`/partners/cruises/${selectedCruise}/cabin-types/${edit_id || detail.edit_id}`);
      if (kind === 'cabin') return api.post(`/partners/cruises/${selectedCruise}/cabins`, { deck_id: detail.deck_id, cabin_type_id: detail.cabin_type_id, cabin_number: detail.cabin_number, max_occupancy: Number(detail.cabin_max_occupancy) });
      if (kind === 'cabinUpdate') return api.patch(`/partners/cruises/${selectedCruise}/cabins/${edit_id || detail.edit_id}`, { deck_id: detail.deck_id, cabin_type_id: detail.cabin_type_id, cabin_number: detail.cabin_number, max_occupancy: Number(detail.cabin_max_occupancy) });
      if (kind === 'cabinDelete') return api.delete(`/partners/cruises/${selectedCruise}/cabins/${edit_id || detail.edit_id}`);
      if (kind === 'image') return api.post(`/partners/cruises/${selectedCruise}/images`, { url: detail.image_url, alt_text: detail.image_alt, is_cover: true, sort_order: 0 });
      if (kind === 'imageUpdate') return api.patch(`/partners/cruises/${selectedCruise}/images/${edit_id || detail.edit_id}`, { url: detail.image_url, alt_text: detail.image_alt, is_cover: detail.image_cover, sort_order: Number(detail.image_sort_order || 0) });
      if (kind === 'imageDelete') return api.delete(`/partners/cruises/${selectedCruise}/images/${edit_id || detail.edit_id}`);
      if (kind === 'itinerary') return api.put(`/partners/cruises/${selectedCruise}/itinerary`, JSON.parse(detail.itinerary_json));
      if (kind === 'sailing') return api.post(`/partners/cruises/${selectedCruise}/sailings`, { ...sailingForm, port_fee_per_guest_cents: Number(sailingForm.port_fee_per_guest_cents), booking_closes_at: new Date(sailingForm.booking_closes_at).toISOString() });
      if (kind === 'sailingUpdate') return api.patch(`/partners/cruises/${selectedCruise}/sailings/${edit_id || sailingForm.edit_id}`, { departure_date: sailingForm.departure_date, return_date: sailingForm.return_date, port_fee_per_guest_cents: Number(sailingForm.port_fee_per_guest_cents), booking_closes_at: new Date(sailingForm.booking_closes_at).toISOString() });
      if (kind === 'sailingDelete') return api.delete(`/partners/cruises/${selectedCruise}/sailings/${edit_id || sailingForm.edit_id}`);
      throw new Error('Unsupported action');
    },
    onSuccess: () => { setDetail(emptyDetail); setSailingForm(emptySailing); notifySuccess('Cruise setup saved. Changes are pending admin approval.'); qc.invalidateQueries({ queryKey: ['partner-cruise', selectedCruise] }); qc.invalidateQueries({ queryKey: ['partner-dashboard'] }); },
    onError: notifyError,
  });

  const addWebsite = useMutation({ mutationFn: () => api.post('/partners/websites', website), onSuccess: () => { setWebsite({ name: '', website_url: '' }); notifySuccess('Website registered. Admin must activate the integration.'); qc.invalidateQueries({ queryKey: ['partner-dashboard'] }); }, onError: notifyError });
  const inventoryUpdate = useMutation({ mutationFn: ({ sailingId, cabinId, data }) => api.patch(`/partners/sailings/${sailingId}/inventory/${cabinId}`, data), onSuccess: () => { notifySuccess('Inventory updated.'); qc.invalidateQueries({ queryKey: ['partner-inventory', inventorySailing] }); qc.invalidateQueries({ queryKey: ['partner-dashboard'] }); }, onError: notifyError });

  if (dashboard.isLoading) return <div className="container-app py-14"><Loading label="Loading partner workspace…" /></div>;
  if (dashboard.isError) return <div className="container-app py-14"><ErrorBox retry={dashboard.refetch} /> </div>;
  const rawData = dashboard.data && typeof dashboard.data === 'object' ? dashboard.data : {};
  const data = {
    partner: rawData.partner && typeof rawData.partner === 'object' ? rawData.partner : { business_name: 'Partner workspace', status: '—', integration_status: '—' },
    cruises: Array.isArray(rawData.cruises) ? rawData.cruises : [],
    bookings: Array.isArray(rawData.bookings) ? rawData.bookings : [],
    websites: Array.isArray(rawData.websites) ? rawData.websites : [],
    api_keys: Array.isArray(rawData.api_keys) ? rawData.api_keys : [],
    earnings_cents: Number(rawData.earnings_cents) || 0,
  };
  const portItems = Array.isArray(ports.data) ? ports.data : [];
  const amenityItems = Array.isArray(amenities.data) ? amenities.data : [];
  const detailData = cruiseDetail.data && typeof cruiseDetail.data === 'object' ? cruiseDetail.data : {};
  const detailCabinTypes = Array.isArray(detailData.cabin_types) ? detailData.cabin_types : [];
  const detailSailings = Array.isArray(detailData.sailings) ? detailData.sailings : [];
  const inventoryRows = Array.isArray(inventory.data) ? inventory.data : [];

  const startEdit = (cruise) => {
    setEditingCruise(cruise.id);
    setCruiseForm({
      name: cruise.name || '',
      slug: cruise.slug || '',
      description: cruise.description || '',
      ship_id: cruise.ship_id || '',
      ship_name: '',
      operator_name: '',
      embark_port_id: cruise.embark_port_id || '',
      disembark_port_id: cruise.disembark_port_id || '',
      sailing_days: cruise.sailing_days || 7,
      start_sailing_date: cruise.start_sailing_date || '',
      return_date: cruise.return_date || '',
      base_price_cents: cruise.base_price_cents || 0,
    });
    setTab('cruises');
    setError('');
    setMessage('');

    // Move the edit form into view so the user can immediately continue editing.
    setTimeout(() => {
      document.getElementById('partner-cruise-edit-form')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }, 50);
  };
  const openCruise = id => { setSelectedCruise(id); setInventorySailing(''); setTab('setup'); setError(''); setMessage(''); };
  const updateInventory = row => {
    const draft = inventoryEdits[row.cabin_id] || {};
    inventoryUpdate.mutate({ sailingId: inventorySailing, cabinId: row.cabin_id, data: { price_cents: draft.price_cents === '' || draft.price_cents == null ? row.price_cents : Number(draft.price_cents), status: draft.status || row.status } });
  };

  return <div className="container-app py-10 lg:py-14 space-y-7">
    <NoticeDialog open={!!notice} title="Partner update" message={notice} onClose={() => setNotice('')} />
    <ConfirmDialog open={!!deleteTarget} title="Delete cruise?" message={deleteTarget ? `Remove “${deleteTarget.name}”? A cruise with confirmed bookings cannot be deleted.` : ''} confirmLabel="Delete cruise" busy={deleteCruise.isPending} onCancel={() => setDeleteTarget(null)} onConfirm={() => deleteCruise.mutate(deleteTarget.id)} />

    <header className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5">
      <div><p className="eyebrow">Partner dashboard</p><h1 className="page-heading text-4xl font-extrabold tracking-tight mt-2">Welcome, Partner.</h1><p className="muted mt-2 max-w-2xl">Manage cruises, live inventory, bookings, commission and partner websites from one workspace.</p><p className="text-sm muted mt-2">Business: <span className="partner-business-name font-bold">{data.partner.business_name}</span></p></div>
      <div className="flex flex-wrap gap-2"><Status value={data.partner.status} /><Status value={data.partner.integration_status} /></div>
    </header>

    {(message || error) && <div role="status" className={`rounded-xl border p-4 text-sm ${error ? 'bg-error-soft border-error text-error' : 'bg-success-soft border-success text-success'}`}>{error || message}</div>}

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric title="Cruises" value={data.cruises.length} /><Metric title="Partner bookings" value={data.bookings.length} /><Metric title="Commission earned" value={money(data.earnings_cents)} /><Metric title="Websites" value={data.websites.length} /></div>

    <div className="partner-tabs-bar sticky top-[73px] z-20 -mx-3 px-3 py-3 backdrop-blur border-b overflow-x-auto"><div className="flex gap-2 min-w-max">{[['overview','Overview'],['cruises','Cruises'],['setup','Cruise setup'],['inventory','Inventory'],['bookings','Bookings'],['websites','Websites']].map(([key,label]) => <button key={key} className={`btn ${tab === key ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab(key)}>{label}</button>)}</div></div>

    {tab === 'overview' && <div className="grid lg:grid-cols-[1.1fr_.9fr] gap-6">
      <section className="card p-6"><p className="eyebrow">Readiness</p><h2 className="section-title mt-2">Partner launch checklist</h2><div className="mt-6 space-y-3">{[
        ['Cruise created', data.cruises.length > 0], ['Approved cruise', data.cruises.some(x => x.approval_status === 'approved')], ['Live sailing', data.cruises.some(x => x.status === 'published')], ['Partner website registered', data.websites.length > 0], ['API integration connected', data.partner.integration_status === 'connected']
      ].map(([label,ok]) => <div key={label} className="flex items-center justify-between rounded-xl bg-surface-muted p-4"><span className="font-semibold">{label}</span><span className={ok ? 'text-success font-extrabold' : 'text-warning font-extrabold'}>{ok ? '✓ Ready' : 'Pending'}</span></div>)}</div></section>
      <section className="card p-6"><p className="eyebrow">Recent activity</p><h2 className="text-xl font-extrabold mt-2">Latest bookings</h2><div className="space-y-3 mt-5">{data.bookings.slice(0,5).map(b => <div key={b.reference} className="rounded-xl border border-default p-4"><div className="flex justify-between gap-3"><b>{b.reference}</b><Status value={b.status}/></div><p className="text-sm muted mt-2">{b.customer_name || 'Customer'} · {money(b.total_cents)}</p></div>)}{!data.bookings.length && <EmptyState title="No bookings yet" description="Partner website bookings will appear here."/>}</div></section>
    </div>}

    {tab === 'cruises' && <div className="space-y-6">
      <section className="card p-6"><div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4"><div><p className="eyebrow">Catalog</p><h2 className="section-title mt-2">Your cruises</h2><p className="muted mt-2">Every create/edit resubmits the cruise for admin approval.</p></div><button className="btn btn-primary" onClick={() => {setEditingCruise(null);setCruiseForm(emptyCruise);setError('');setMessage('');}}>+ New cruise</button></div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mt-6">{data.cruises.map(c => <article key={c.id} className="rounded-2xl border border-default p-5 bg-surface"><div className="flex justify-between gap-3"><div><h3 className="font-extrabold text-lg">{c.name}</h3><p className="text-sm muted mt-1">{c.sailing_days} days · from {money(c.base_price_cents)}</p></div><Status value={c.approval_status}/></div><div className="flex flex-wrap gap-2 mt-4"><Status value={c.status}/><span className="text-xs font-bold text-muted">Commission: {c.commission_type ? `${c.commission_type} ${c.commission_value}` : 'pending admin setup'}</span></div><div className="grid grid-cols-2 gap-2 mt-5"><button className="btn btn-outline" onClick={() => openCruise(c.id)}>Manage</button><button className="btn btn-outline" onClick={() => startEdit(c)}>Edit</button></div><button className="w-full mt-2 rounded-xl border border-error py-2.5 text-sm font-bold text-error hover:bg-error-soft" onClick={() => setDeleteTarget(c)}>Delete cruise</button></article>)}{!data.cruises.length && <div className="col-span-full"><EmptyState title="No cruises yet" description="Create your first partner cruise to start the approval workflow."/></div>}</div>
      </section>
      <section id="partner-cruise-edit-form" className="card p-6 scroll-mt-24"><p className="eyebrow">{editingCruise ? 'Edit' : 'Create'}</p><h2 className="text-xl font-extrabold mt-2">{editingCruise ? 'Edit cruise' : 'Create cruise'}</h2><div className="grid md:grid-cols-2 gap-4 mt-5"><Field label="Cruise name"><input className="input" value={cruiseForm.name} onChange={e=>setCruiseForm({...cruiseForm,name:e.target.value})}/></Field><Field label="Unique slug"><input className="input" value={cruiseForm.slug} onChange={e=>setCruiseForm({...cruiseForm,slug:e.target.value})}/></Field>{!editingCruise && <><Field label="Use an existing ship (optional)"><input className="input" value={cruiseForm.ship_id} onChange={e=>setCruiseForm({...cruiseForm,ship_id:e.target.value})}/></Field><Field label="New ship name"><input className="input" value={cruiseForm.ship_name} onChange={e=>setCruiseForm({...cruiseForm,ship_name:e.target.value})}/></Field><Field label="Ship operator"><input className="input" value={cruiseForm.operator_name} onChange={e=>setCruiseForm({...cruiseForm,operator_name:e.target.value})}/></Field></>}<Field label="Embark port"><select className="input" value={cruiseForm.embark_port_id} onChange={e=>setCruiseForm({...cruiseForm,embark_port_id:e.target.value})}><option value="">Select port</option>{portItems.map(p=><option key={p.id} value={p.id}>{p.name} — {p.city}</option>)}</select></Field><Field label="Disembark port"><select className="input" value={cruiseForm.disembark_port_id} onChange={e=>setCruiseForm({...cruiseForm,disembark_port_id:e.target.value})}><option value="">Select port</option>{portItems.map(p=><option key={p.id} value={p.id}>{p.name} — {p.city}</option>)}</select></Field><Field label="Start sailing date"><input className="input" type="date" value={cruiseForm.start_sailing_date} onChange={e=>setCruiseForm({...cruiseForm,start_sailing_date:e.target.value})} /></Field><Field label="Return date"><input className="input" type="date" value={cruiseForm.return_date} onChange={e=>setCruiseForm({...cruiseForm,return_date:e.target.value})} /></Field><Field label="Sailing days"><input className="input" type="number" min="1" value={cruiseForm.sailing_days} onChange={e=>setCruiseForm({...cruiseForm,sailing_days:e.target.value})}/></Field><Field label="Base price (USD)"><input className="input" type="number" min="0" step="0.01" value={(Number(cruiseForm.base_price_cents)||0)/100} onChange={e=>setCruiseForm({...cruiseForm,base_price_cents:Math.round(Number(e.target.value||0)*100)})}/></Field><Field label="Description"><textarea className="input min-h-28" value={cruiseForm.description} onChange={e=>setCruiseForm({...cruiseForm,description:e.target.value})}/></Field></div><div className="flex flex-wrap gap-2 mt-5"><button className="btn btn-primary" disabled={saveCruise.isPending || !cruiseForm.name || !cruiseForm.slug} onClick={()=>saveCruise.mutate()}>{saveCruise.isPending ? 'Saving…' : editingCruise ? 'Save & resubmit' : 'Create & submit'}</button>{editingCruise && <button className="btn btn-outline" onClick={()=>{setEditingCruise(null);setCruiseForm(emptyCruise)}}>Cancel edit</button>}</div></section>
    </div>}

    {tab === 'setup' && <section className="space-y-6">{!selectedCruise ? <div className="card p-10"><EmptyState title="Choose a cruise" description="Select Manage from the Cruises tab to configure decks, cabins, amenities, images, itinerary and sailings."/></div> : cruiseDetail.isLoading ? <div className="card p-8"><Loading label="Loading cruise setup…"/></div> : cruiseDetail.isError ? <div className="card p-8"><ErrorBox retry={cruiseDetail.refetch}/></div> : <>
      <div className="card p-6"><div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4"><div><p className="eyebrow">Cruise setup</p><h2 className="section-title mt-2">{cruiseDetail.data.name}</h2><div className="flex flex-wrap gap-2 mt-3"><Status value={cruiseDetail.data.approval_status}/><Status value={cruiseDetail.data.status}/></div></div><button className="btn btn-outline" onClick={()=>setTab('cruises')}>← Back to cruises</button></div></div>
      <div className="grid lg:grid-cols-2 gap-6">
        <section className="card p-6"><h3 className="text-xl font-extrabold">Decks</h3><div className="grid grid-cols-[120px_1fr_auto] gap-2 mt-4"><input className="input" type="number" min="1" value={detail.deck_number} onChange={e=>setDetail({...detail,deck_number:e.target.value})}/><input className="input" placeholder="Deck name" value={detail.deck_name} onChange={e=>setDetail({...detail,deck_name:e.target.value})}/><button className="btn btn-outline" onClick={()=>detailAction.mutate({kind:'deck'})}>Add</button></div><div className="space-y-2 mt-4">{cruiseDetail.data.decks?.map(d=><div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-muted p-3" key={d.id}><span className="tag">Deck {d.deck_number} · {d.name}</span><span className="flex gap-3"><button type="button" className="table-action" onClick={()=>setDetail(current=>({...current,edit_id:d.id,edit_kind:'deck',deck_number:d.deck_number,deck_name:d.name||''}))}>Edit</button><button type="button" className="text-xs font-extrabold text-error" onClick={()=>detailAction.mutate({kind:'deckDelete',edit_id:d.id})}>Delete</button></span></div>)}</div><button className="btn btn-outline mt-3" disabled={!detail.edit_id||detail.edit_kind!=='deck'||!detail.deck_name} onClick={()=>detailAction.mutate({kind:'deckUpdate',edit_id:detail.edit_id})}>Save loaded deck</button></section>
        <section className="card p-6"><h3 className="text-xl font-extrabold">Cabin types & amenities</h3><div className="grid md:grid-cols-2 gap-3 mt-4"><input className="input" placeholder="Cabin type" value={detail.ct_name} onChange={e=>setDetail({...detail,ct_name:e.target.value})}/><input className="input" type="number" min="1" placeholder="Max occupancy" value={detail.ct_max_occupancy} onChange={e=>setDetail({...detail,ct_max_occupancy:e.target.value})}/><input className="input" type="number" min="0" step="0.01" placeholder="Base USD" value={(Number(detail.ct_base_price_cents)||0)/100} onChange={e=>setDetail({...detail,ct_base_price_cents:Math.round(Number(e.target.value||0)*100)})}/><input className="input" type="number" min="0" step="0.01" placeholder="Extra guest USD" value={(Number(detail.ct_extra_price_cents)||0)/100} onChange={e=>setDetail({...detail,ct_extra_price_cents:Math.round(Number(e.target.value||0)*100)})}/><textarea className="input md:col-span-2" placeholder="Cabin description" value={detail.ct_description} onChange={e=>setDetail({...detail,ct_description:e.target.value})}/></div><div className="flex flex-wrap gap-2 mt-3">{amenityItems.map(a=><label key={a.id} className={`tag cursor-pointer ${detail.amenity_ids.includes(a.id) ? 'tag-active' : ''}`}><input className="sr-only" type="checkbox" checked={detail.amenity_ids.includes(a.id)} onChange={e=>setDetail({...detail,amenity_ids:e.target.checked ? [...detail.amenity_ids,a.id] : detail.amenity_ids.filter(id=>id!==a.id)})}/>{a.name}</label>)}</div><div className="flex flex-wrap gap-2 mt-4"><button className="btn btn-outline" disabled={!detail.ct_name} onClick={()=>detailAction.mutate({kind:'type'})}>Add cabin type</button><button className="btn btn-primary" disabled={detail.edit_kind!=='type'||!detail.edit_id||!detail.ct_name} onClick={()=>detailAction.mutate({kind:'typeUpdate',edit_id:detail.edit_id})}>Save loaded cabin type</button>{detail.edit_kind==='type'&&<button className="btn btn-outline" onClick={()=>setDetail(emptyDetail)}>Cancel edit</button>}</div><div className="space-y-2 mt-4">{detailCabinTypes.map(t=><div key={t.id} className="rounded-xl bg-surface-muted p-3"><div className="flex justify-between gap-3"><div><b>{t.name}</b><span className="text-sm font-bold ml-3">{money(t.base_price_cents)}</span><p className="text-xs muted mt-1">Up to {t.max_occupancy} · {t.amenities?.map(a=>a.name).join(', ') || 'No amenities'}</p></div><div className="flex gap-2"><button className="text-xs font-bold text-accent" onClick={()=>setDetail(d=>({...d,edit_id:t.id,edit_kind:'type',ct_name:t.name,ct_description:t.description||'',ct_max_occupancy:t.max_occupancy,ct_base_price_cents:t.base_price_cents,ct_extra_price_cents:t.price_per_extra_guest_cents,amenity_ids:(t.amenities||[]).map(a=>a.id)}))}>Edit</button><button className="text-xs font-bold text-error" onClick={()=>detailAction.mutate({kind:'typeDelete',edit_id:t.id})}>Delete</button></div></div></div>)}</div></section>
        <section className="card p-6"><h3 className="text-xl font-extrabold">Physical cabins</h3><div className="grid md:grid-cols-4 gap-2 mt-4"><select className="input" value={detail.deck_id} onChange={e=>setDetail({...detail,deck_id:e.target.value})}><option value="">Deck</option>{cruiseDetail.data.decks?.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><select className="input" value={detail.cabin_type_id} onChange={e=>setDetail({...detail,cabin_type_id:e.target.value})}><option value="">Type</option>{detailCabinTypes.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select><input className="input" placeholder="Cabin no." value={detail.cabin_number} onChange={e=>setDetail({...detail,cabin_number:e.target.value})}/><input className="input" type="number" min="1" placeholder="Occupancy" value={detail.cabin_max_occupancy} onChange={e=>setDetail({...detail,cabin_max_occupancy:e.target.value})}/></div><div className="flex flex-wrap gap-2 mt-3"><button className="btn btn-outline" disabled={!detail.deck_id||!detail.cabin_type_id||!detail.cabin_number} onClick={()=>detailAction.mutate({kind:'cabin'})}>Add cabin</button><button className="btn btn-primary" disabled={detail.edit_kind!=='cabin'||!detail.edit_id||!detail.deck_id||!detail.cabin_type_id||!detail.cabin_number} onClick={()=>detailAction.mutate({kind:'cabinUpdate',edit_id:detail.edit_id})}>Save loaded cabin</button>{detail.edit_kind==='cabin'&&<button className="btn btn-outline" onClick={()=>setDetail(emptyDetail)}>Cancel edit</button>}</div><div className="mt-4 max-h-56 overflow-auto space-y-2">{cruiseDetail.data.cabins?.map(c=><div key={c.id} className="flex justify-between items-center gap-2 rounded-xl bg-surface-muted p-3 text-sm"><span><b>{c.cabin_number}</b><span className="muted ml-2">{c.deck_name} · {c.cabin_type_name} · max {c.max_occupancy}</span></span><span className="flex gap-2"><button className="text-xs font-bold text-accent" onClick={()=>setDetail(d=>({...d,edit_id:c.id,edit_kind:'cabin',deck_id:c.deck_id,cabin_type_id:c.cabin_type_id,cabin_number:c.cabin_number,cabin_max_occupancy:c.max_occupancy}))}>Edit</button><button className="text-xs font-bold text-error" onClick={()=>detailAction.mutate({kind:'cabinDelete',edit_id:c.id})}>Delete</button></span></div>)}</div></section>
        <section className="card p-6"><h3 className="text-xl font-extrabold">Cruise images</h3><div className="grid md:grid-cols-[1fr_1fr_auto] gap-2 mt-4"><input className="input" placeholder="Public image URL" value={detail.image_url} onChange={e=>setDetail({...detail,image_url:e.target.value})}/><input className="input" placeholder="Alt text" value={detail.image_alt} onChange={e=>setDetail({...detail,image_alt:e.target.value})}/><button className="btn btn-outline" disabled={!detail.image_url} onClick={()=>detailAction.mutate({kind:'image'})}>Add image</button></div><div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">{cruiseDetail.data.images?.map(img=><div key={img.id} className="rounded-xl border p-3"><img src={img.url} alt={img.alt_text || cruiseDetail.data.name} className="h-36 w-full object-cover rounded-xl" loading="lazy"/><div className="flex justify-between items-center mt-2"><span className="text-xs muted truncate">{img.alt_text || 'Cruise image'}{img.is_cover?' · cover':''}</span><span className="flex gap-2"><button className="text-xs font-bold text-accent" onClick={()=>{setDetail(d=>({...d,edit_id:img.id,edit_kind:'image',image_url:img.url,image_alt:img.alt_text||'',image_cover:img.is_cover,image_sort_order:img.sort_order}));}}>Load edit</button><button className="text-xs font-bold text-error" onClick={()=>detailAction.mutate({kind:'imageDelete',edit_id:img.id})}>Delete</button></span></div></div>)}</div><div className="flex flex-wrap gap-2 mt-3"><button className="btn btn-primary" disabled={detail.edit_kind!=='image'||!detail.edit_id||!detail.image_url} onClick={()=>detailAction.mutate({kind:'imageUpdate',edit_id:detail.edit_id})}>Save loaded image</button>{detail.edit_kind==='image'&&<button className="btn btn-outline" onClick={()=>setDetail(emptyDetail)}>Cancel edit</button>}</div></section>
      </div>
      <section className="card p-6"><ItineraryEditor value={detail.itinerary_json} onChange={value=>setDetail({...detail,itinerary_json:value})} ports={ports.data||[]}/><button className="btn btn-primary mt-4" onClick={()=>detailAction.mutate({kind:'itinerary'})}>Save itinerary</button></section>
      <section className="card p-6"><div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4"><div><h3 className="text-xl font-extrabold">Sailings</h3><p className="muted text-sm mt-1">A sailing creates the shared availability record for every physical cabin on the ship.</p></div></div><div className="grid md:grid-cols-4 gap-3 mt-4"><input className="input" type="date" value={sailingForm.departure_date} onChange={e=>setSailingForm({...sailingForm,departure_date:e.target.value})}/><input className="input" type="date" value={sailingForm.return_date} onChange={e=>setSailingForm({...sailingForm,return_date:e.target.value})}/><input className="input" type="datetime-local" value={sailingForm.booking_closes_at} onChange={e=>setSailingForm({...sailingForm,booking_closes_at:e.target.value})}/><input className="input" type="number" min="0" step="0.01" placeholder="Port fee USD / guest" value={(Number(sailingForm.port_fee_per_guest_cents)||0)/100} onChange={e=>setSailingForm({...sailingForm,port_fee_per_guest_cents:Math.round(Number(e.target.value||0)*100)})}/></div><button className="btn btn-outline mt-3" disabled={!sailingForm.departure_date||!sailingForm.return_date||!sailingForm.booking_closes_at} onClick={()=>detailAction.mutate({kind:'sailing'})}>Add sailing</button><div className="mt-5 grid md:grid-cols-2 gap-3">{detailSailings.map(s=><div key={s.id} className="rounded-xl border border-default p-4"><div className="flex justify-between gap-3"><div><b>{s.departure_date} → {s.return_date}</b><Status value={s.status}/></div><span className="flex gap-2"><button className="text-xs font-bold text-accent" onClick={()=>setSailingForm({edit_id:s.id,departure_date:s.departure_date,return_date:s.return_date,booking_closes_at:String(s.booking_closes_at||'').slice(0,16),port_fee_per_guest_cents:s.port_fee_per_guest_cents || 0})}>Edit</button><button className="text-xs font-bold text-error" onClick={()=>detailAction.mutate({kind:'sailingDelete',edit_id:s.id})}>Delete</button></span></div><p className="text-xs muted mt-2">{s.id}</p></div>)}</div><div className="flex flex-wrap gap-2 mt-3"><button className="btn btn-primary" disabled={!sailingForm.edit_id||!sailingForm.departure_date||!sailingForm.return_date||!sailingForm.booking_closes_at} onClick={()=>detailAction.mutate({kind:'sailingUpdate',edit_id:sailingForm.edit_id})}>Save loaded sailing</button>{sailingForm.edit_id&&<button className="btn btn-outline" onClick={()=>setSailingForm(emptySailing)}>Cancel edit</button>}</div></section>
    </>}</section>}

    {tab === 'inventory' && <section className="card p-6"><p className="eyebrow">Central inventory</p><h2 className="section-title mt-2">Availability control</h2><p className="muted mt-2">This is the same inventory used by direct my_cruise and partner booking channels. Booked or held cabins cannot be edited.</p><div className="grid md:grid-cols-2 gap-3 mt-6"><select className="input" value={selectedCruise} onChange={e=>{setSelectedCruise(e.target.value);setInventorySailing('')}}><option value="">Select cruise</option>{data.cruises.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select><select className="input" value={inventorySailing} onChange={e=>setInventorySailing(e.target.value)} disabled={!selectedCruise}><option value="">Select sailing</option>{cruiseDetail.data?.sailings?.map(s=><option key={s.id} value={s.id}>{s.departure_date} → {s.return_date}</option>)}</select></div>{inventory.isLoading&&<div className="mt-6"><Loading label="Loading inventory…"/></div>}{inventory.isError&&<div className="mt-6"><ErrorBox retry={inventory.refetch}/></div>}{inventory.data&&<div className="overflow-x-auto mt-6"><table className="w-full text-sm"><thead className="bg-surface-muted border-b"><tr><th className="px-4 py-3 text-left">Cabin</th><th className="px-4 py-3 text-left">Status</th><th className="px-4 py-3 text-left">Price USD</th><th className="px-4 py-3 text-right">Action</th></tr></thead><tbody className="divide-y">{inventoryRows.map(row=>{const draft=inventoryEdits[row.cabin_id]||{};const locked=['booked','held'].includes(row.status);return <tr key={row.cabin_id}><td className="px-4 py-3 font-bold">{row.cabin_number}</td><td className="px-4 py-3"><select className="input max-w-40" value={draft.status||row.status} disabled={locked} onChange={e=>setInventoryEdits({...inventoryEdits,[row.cabin_id]:{...draft,status:e.target.value}})}><option value="available">Available</option><option value="blocked">Blocked</option><option value="booked" disabled>Booked</option><option value="held" disabled>Held</option></select></td><td className="px-4 py-3"><input className="input max-w-36" type="number" min="0" step="0.01" disabled={locked} value={draft.price_cents != null ? Number(draft.price_cents)/100 : Number(row.price_cents)/100} onChange={e=>setInventoryEdits({...inventoryEdits,[row.cabin_id]:{...draft,price_cents:Math.round(Number(e.target.value||0)*100)}})}/></td><td className="px-4 py-3 text-right"><button className="btn btn-outline py-2" disabled={locked||inventoryUpdate.isPending} onClick={()=>updateInventory(row)}>{locked?'Locked':'Save'}</button></td></tr>})}</tbody></table></div>}</section>}

    {tab === 'bookings' && <section className="card p-6"><div className="flex items-end justify-between gap-3"><div><p className="eyebrow">Partner bookings</p><h2 className="section-title mt-2">Traveler reservations</h2></div><button className="btn btn-outline" onClick={()=>bookings.refetch()}>Refresh</button></div>{bookings.isLoading?<div className="mt-6"><Loading/></div>:bookings.isError?<div className="mt-6"><ErrorBox retry={bookings.refetch}/></div>:<div className="overflow-x-auto mt-6"><table className="w-full text-sm"><thead className="bg-surface-muted border-b"><tr><th className="px-4 py-3 text-left">Reference</th><th className="px-4 py-3 text-left">Traveler</th><th className="px-4 py-3 text-left">Cruise / sailing</th><th className="px-4 py-3 text-left">Payment</th><th className="px-4 py-3 text-left">Status</th><th className="px-4 py-3 text-right">Total</th><th className="px-4 py-3 text-right">Commission</th></tr></thead><tbody className="divide-y">{bookings.data?.map(b=><tr key={b.reference}><td className="px-4 py-3 font-bold">{b.reference}</td><td className="px-4 py-3">{b.customer?.name}<div className="text-xs muted">{b.customer?.email}</div></td><td className="px-4 py-3">{b.cruise?.name}<div className="text-xs muted">{b.sailing?.departure_date} → {b.sailing?.return_date}</div></td><td className="px-4 py-3">{b.payment?.status || '—'}</td><td className="px-4 py-3"><Status value={b.status}/></td><td className="px-4 py-3 text-right">{money(b.total_cents)}</td><td className="px-4 py-3 text-right">{money(b.commission_cents)}</td></tr>)}</tbody></table>{!bookings.data?.length&&<div className="py-10"><EmptyState title="No partner bookings" description="Bookings created through your partner integration will appear here."/></div>}</div>}</section>}

    {tab === 'websites' && <section className="grid lg:grid-cols-[.9fr_1.1fr] gap-6"><div className="card p-6"><p className="eyebrow">Distribution</p><h2 className="text-xl font-extrabold mt-2">Register partner website</h2><p className="muted text-sm mt-2">Register your website here. An admin reviews and activates it before the website can use the partner API.</p><div className="space-y-4 mt-5"><Field label="Website name"><input className="input" value={website.name} onChange={e=>setWebsite({...website,name:e.target.value})} placeholder="Oceanic Travel"/></Field><Field label="Website URL"><input className="input" type="url" value={website.website_url} onChange={e=>setWebsite({...website,website_url:e.target.value})} placeholder="https://your-travel-website.com"/></Field><button
            type="button"
            className="btn btn-primary w-full"
            disabled={addWebsite.isPending}
            onClick={() => {
              if (!website.name.trim() || !website.website_url.trim()) {
                const text = 'Enter both the website name and website URL before registering.';
                setError(text);
                setMessage('');
                setNotice(text);
                return;
              }

              addWebsite.mutate();
            }}
          >
            {addWebsite.isPending ? 'Registering…' : 'Register website'}
          </button></div></div><div className="card p-6"><p className="eyebrow">Integrations</p><h2 className="text-xl font-extrabold mt-2">Your websites</h2><div className="space-y-3 mt-5">{data.websites.map(w=><div key={w.id} className="rounded-xl border border-default p-4"><div className="flex flex-wrap justify-between gap-3"><div><b>{w.name}</b><p className="text-sm muted mt-1 break-all">{w.website_url}</p></div><Status value={w.integration_status}/></div><div className="mt-3 rounded-xl bg-surface-muted p-3 text-xs leading-5 text-secondary"><b>What happens next?</b><br/>1. You register the website.<br/>2. Admin activates the integration.<br/>3. Your website uses the partner API to show approved cruises and the same live cabin inventory.</div></div>)}{!data.websites.length&&<EmptyState title="No websites registered" description="Register your first partner website to begin the integration workflow."/>}</div></div></section>}
  </div>;
}
function Metric({ title, value }) { return <div className="card p-5"><p className="muted text-sm">{title}</p><p className="text-2xl font-extrabold text-primary mt-2">{value}</p></div>; }
