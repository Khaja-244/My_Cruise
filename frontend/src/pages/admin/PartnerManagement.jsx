import PageHero from '../../components/ui/PageHero';
import React, {useState} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {api} from '../../api/client';

const money = cents => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format((Number(cents) || 0) / 100);

export default function PartnerManagement() {
  const qc = useQueryClient();
  const [tab, setTab] = useState('applications');
  const [selectedApplication, setSelectedApplication] = useState('');
  const [selectedPartner, setSelectedPartner] = useState('');
  const [selectedWebsite, setSelectedWebsite] = useState('');
  const [selectedCruise, setSelectedCruise] = useState(null);
  const [commission, setCommission] = useState({commission_type: 'percent', commission_value: 10});
  const [reviewNote, setReviewNote] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [newPartner, setNewPartner] = useState({business_name: '', contact_name: '', email: '', phone: ''});

  const query = (key, url, enabled = true) => useQuery({queryKey: ['partner-admin', key, url], queryFn: () => api.get(url).then(r => r.data), enabled});
  const apps = query('applications', '/partners/applications');
  const partners = query('partners', '/partners/list');
  const pending = query('pending-cruises', '/partners/cruises/pending');
  const sites = query('websites', '/partners/websites/admin');
  const allCruises = query('all-cruises', '/admin/cruises');
  const partnerSites = (sites.data || []).filter(w => w.partner_id === selectedPartner);
  const exposureUrl = selectedPartner ? `/partners/${selectedPartner}/exposures${selectedWebsite ? `?website_id=${selectedWebsite}` : ''}` : '';
  const exposures = query('exposures', exposureUrl, !!selectedPartner);
  const keys = query('keys', selectedPartner ? `/partners/${selectedPartner}/api-keys` : '', !!selectedPartner);

  const action = useMutation({
    mutationFn: ({url, method = 'post', data}) => api[method](url, data),
    onSuccess: () => {setReviewNote(''); setNotice('Action completed successfully.'); setError(''); qc.invalidateQueries({queryKey: ['partner-admin']});},
    onError: e => {setError(e.response?.data?.error?.message || 'The action could not be completed.'); setNotice('');},
  });

  const reviewApplication = (applicationId, approved) => {
    if (!applicationId) return;
    action.mutate({url: `/partners/applications/${applicationId}/review`, data: {approved, reason: reviewNote || undefined}});
  };
  const reviewCruise = (id, approved) => action.mutate({url: `/partners/cruises/${id}/review`, data: {approved, reason: reviewNote || undefined}});
  const issueKey = async id => {
    try {
      const r = await api.post('/partners/api-keys', null, {params: {partner_id: id}});
      setNotice(`API key issued. Copy it now: ${r.data.api_key}`); setError(''); qc.invalidateQueries({queryKey: ['partner-admin']});
    } catch (e) {setError(e.response?.data?.error?.message || 'Could not issue API key.'); setNotice('');}
  };
  const saveCommission = () => selectedCruise && action.mutate({url: `/partners/cruises/${selectedCruise.id}/commission`, method: 'patch', data: {commission_type: commission.commission_type, commission_value: Number(commission.commission_value)}});
  const createPartner = () => action.mutate({url: '/partners', data: newPartner});

  const tabs = [['applications', 'Applications'], ['cruises', 'Partner Cruises'], ['partners', 'Partner Agencies'], ['exposure', 'Website Cruise Exposure'], ['websites', 'Websites']];
  return <div><PageHero eyebrow="Partner operations" title="Partner management" subtitle="Review partner applications, cruises, commissions, agencies and website exposure." /><div className="container-app py-10 lg:py-14">
    <p className="eyebrow">Partner operations</p><h1 className="text-4xl font-extrabold mt-2">Partner management</h1><p className="muted mt-2">Approve partners, review cruises, configure commission and control website integrations.</p>
    {(notice || error) && <div className={`mt-5 rounded-xl border p-4 text-sm ${error ? 'bg-error-soft border-error text-error' : 'bg-success-soft border-success text-success'}`}>{error || notice}</div>}
    <div className="flex flex-wrap gap-2 mt-7">{tabs.map(([key, label]) => <button key={key} className={`btn ${tab === key ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab(key)}>{label}</button>)}</div>

    {tab === 'applications' && <div className="card p-6 mt-6"><h2 className="text-xl font-extrabold">Partner applications</h2><div className="space-y-3 mt-4">{(apps.data || []).map(row => <div key={row.id} className="rounded-xl bg-surface-muted p-4"><div className="flex flex-wrap justify-between gap-3"><div><b>{row.business_name}</b><p className="muted text-sm">{row.contact_name} · {row.email} · {row.status}</p></div>{row.status === 'pending' && <div className="flex gap-2"><button className="btn btn-primary py-2" onClick={() => {setSelectedApplication(row.id); setReviewNote('');}}>Select</button><button className="btn btn-outline py-2" onClick={() => reviewApplication(row.id, true)}>Approve</button><button className="btn btn-outline py-2 text-error" onClick={() => reviewApplication(row.id, false)}>Reject</button></div>}</div></div>)}{selectedApplication && <div className="border-t pt-5 mt-5"><label className="text-sm font-bold">Review note<input className="input mt-2" placeholder="Optional approval note or rejection reason" value={reviewNote} onChange={e => setReviewNote(e.target.value)}/></label><div className="flex gap-2 mt-3"><button className="btn btn-primary" onClick={() => reviewApplication(selectedApplication, true)}>Approve selected</button><button className="btn btn-outline text-error" onClick={() => reviewApplication(selectedApplication, false)}>Reject selected</button></div></div>}</div></div>}

    {tab === 'cruises' && <div className="space-y-4 mt-6">{(pending.data || []).map(row => <div className="card p-5" key={row.id}><div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"><div><h3 className="font-extrabold text-lg">{row.name}</h3><p className="muted text-sm">{money(row.base_price_cents)} · {row.approval_status} · Commission: {row.commission_type ? `${row.commission_type} ${row.commission_value}` : 'not configured'}</p></div><div className="flex flex-wrap gap-2"><button className="btn btn-outline" onClick={() => {setSelectedCruise(row);setCommission({commission_type: row.commission_type || 'percent', commission_value: row.commission_value ?? 10});}}>Set commission</button><button className="btn btn-primary" disabled={!row.commission_type} onClick={() => reviewCruise(row.id, true)}>Approve</button><button className="btn btn-outline text-error" onClick={() => reviewCruise(row.id, false)}>Reject</button></div></div></div>)}{selectedCruise && <div className="card p-6"><h2 className="font-extrabold text-xl">Commission — {selectedCruise.name}</h2><p className="muted text-sm mt-1">All commission values are maintained in USD.</p><div className="grid sm:grid-cols-2 gap-3 mt-4"><select className="input" value={commission.commission_type} onChange={e => setCommission({...commission, commission_type: e.target.value})}><option value="percent">Percentage</option><option value="flat">Flat USD</option></select><input className="input" type="number" min="0" max={commission.commission_type === 'percent' ? 100 : undefined} step="0.01" value={commission.commission_value} onChange={e => setCommission({...commission, commission_value: e.target.value})}/></div><button className="btn btn-primary mt-4" onClick={saveCommission}>Save commission</button></div>}</div>}

    {tab === 'partners' && <><div className="card p-6 mt-6"><h2 className="text-xl font-extrabold">Add partner agency</h2><div className="grid md:grid-cols-4 gap-3 mt-4"><input className="input" placeholder="Business name" value={newPartner.business_name} onChange={e => setNewPartner({...newPartner, business_name: e.target.value})}/><input className="input" placeholder="Contact name" value={newPartner.contact_name} onChange={e => setNewPartner({...newPartner, contact_name: e.target.value})}/><input className="input" type="email" placeholder="Email" value={newPartner.email} onChange={e => setNewPartner({...newPartner, email: e.target.value})}/><input className="input" placeholder="Phone" value={newPartner.phone} onChange={e => setNewPartner({...newPartner, phone: e.target.value})}/></div><button className="btn btn-primary mt-4" onClick={createPartner}>Add partner</button></div><Table cols={['business_name','contact_name','email','status','integration_status']} rows={partners.data || []} actions={row => <><button className="text-accent font-bold" onClick={() => action.mutate({url: `/partners/${row.id}/status`, method: 'patch', data: {status: row.status === 'active' ? 'disabled' : 'active'}})}>{row.status === 'active' ? 'Disable' : 'Enable'}</button><button className="text-accent font-bold ml-3" onClick={() => issueKey(row.id)}>Issue API key</button><button className="text-accent font-bold ml-3" onClick={() => setSelectedPartner(row.id)}>Manage keys</button></>}/>{selectedPartner && <div className="card p-6 mt-6"><h2 className="text-xl font-extrabold">API keys</h2>{(keys.data || []).map(k => <div key={k.id} className="flex justify-between rounded-lg bg-surface-muted p-3 mt-2"><span className="font-mono">{k.prefix}… · {k.active ? 'active' : 'revoked'}</span>{k.active && <button className="text-error font-bold" onClick={() => action.mutate({url: `/partners/api-keys/${k.id}/revoke`, data: null})}>Revoke</button>}</div>)}</div>}</>}

    {tab === 'exposure' && <div className="card p-6 mt-6"><h2 className="text-xl font-extrabold">Website cruise exposure</h2><div className="grid md:grid-cols-2 gap-3 mt-4"><select className="input" value={selectedPartner} onChange={e => {setSelectedPartner(e.target.value);setSelectedWebsite('');}}><option value="">Select partner</option>{(partners.data || []).map(p => <option key={p.id} value={p.id}>{p.business_name}</option>)}</select><select className="input" value={selectedWebsite} onChange={e => setSelectedWebsite(e.target.value)} disabled={!selectedPartner}><option value="">Legacy partner-level exposure</option>{partnerSites.map(w => <option key={w.id} value={w.id}>{w.name} — {w.website_url}</option>)}</select></div>{selectedPartner && <div className="space-y-2 mt-5">{(allCruises.data || []).filter(c => c.approval_status === 'approved' && c.status === 'published').map(c => {const exposed = (exposures.data || []).find(x => x.cruise_id === c.id)?.enabled; return <div key={c.id} className="flex justify-between rounded-lg bg-surface-muted p-3"><span>{c.name}</span><button className="font-bold text-accent" onClick={() => action.mutate({url: `/partners/${selectedPartner}/exposures/${c.id}${selectedWebsite ? `?website_id=${selectedWebsite}` : ''}`, method: 'put', data: {enabled: !exposed}})}>{exposed ? 'Exposed — disable' : 'Not exposed — enable'}</button></div>;})}</div>}</div>}

    {tab === 'websites' && <Table cols={['partner_name','name','website_url','integration_status']} rows={sites.data || []} actions={row => <button className="text-accent font-bold" onClick={() => action.mutate({url: `/partners/websites/${row.id}/status`, method: 'patch', data: {integration_status: row.integration_status === 'connected' ? 'suspended' : 'connected'}})}>{row.integration_status === 'connected' ? 'Suspend' : 'Activate'}</button>}/>} 
  </div></div>;
}
function Table({cols, rows, actions}) {return <div className="card overflow-x-auto mt-6"><table className="w-full text-sm"><thead className="bg-surface-muted"><tr>{cols.map(c => <th key={c} className="text-left px-5 py-4 capitalize">{c.replaceAll('_',' ')}</th>)}<th className="px-5 py-4 text-right">Actions</th></tr></thead><tbody className="divide-y">{rows.map(r => <tr key={r.id}>{cols.map(c => <td key={c} className="px-5 py-4 max-w-[260px] truncate">{String(r[c] ?? '—')}</td>)}<td className="px-5 py-4 text-right">{actions(r)}</td></tr>)}</tbody></table>{!rows.length && <p className="p-8 muted">No records found.</p>}</div>;}
