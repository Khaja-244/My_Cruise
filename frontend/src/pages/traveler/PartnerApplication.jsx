import PageHero from '../../components/ui/PageHero';
import React,{useEffect,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api} from '../../api/client';
import {useAuth} from '../../context/AuthContext';
export default function PartnerApplication(){
 const qc=useQueryClient(); const {user}=useAuth(); const [form,setForm]=useState({business_name:'',contact_name:'',email:user?.email||'',phone:'',documents:''});
 useEffect(()=>{ if(user?.email) setForm(current=>({...current,email:user.email})); },[user?.email]);
 const {data,isLoading}=useQuery({queryKey:['partner-application'],queryFn:()=>api.get('/partners/application/me').then(r=>r.data)});
 const submit=useMutation({mutationFn:()=>api.post('/partners/applications',{...form,email:user?.email||form.email,documents:form.documents?{notes:form.documents}:null}),onSuccess:()=>qc.invalidateQueries({queryKey:['partner-application']})});
 if(isLoading)return <div className="container-app py-12">Loading…</div>;
 if(data)return <div className="container-app py-12"><div className="max-w-2xl card p-8"><p className="eyebrow">Partner onboarding</p><h1 className="text-3xl font-extrabold mt-2">Application status</h1><p className="mt-4">Business: <b>{data.business_name}</b></p><p className="mt-2">Status: <b className="capitalize">{data.status}</b></p>{data.reason&&<p className="mt-2 text-secondary">Review note: {data.reason}</p>}</div></div>;
 return <div><PageHero eyebrow="Partner onboarding" title="Apply to become a partner" subtitle="Submit your business details. An administrator reviews the application before partner access is created." /><div className="container-app py-10 lg:py-14"><div className="max-w-3xl"><div className="card p-7 mt-7 grid md:grid-cols-2 gap-4">{[['business_name','Business name'],['contact_name','Contact name'],['email','Business email'],['phone','Phone']].map(([k,l])=><label key={k} className="space-y-2"><span className="text-sm font-bold">{l}</span><input className="input" type={k==='email'?'email':'text'} value={form[k]} readOnly={k==='email'} disabled={k==='email'} onChange={e=>setForm({...form,[k]:e.target.value})}/></label>)}<label className="md:col-span-2 space-y-2"><span className="text-sm font-bold">Documents / additional information</span><textarea className="input min-h-28" value={form.documents} onChange={e=>setForm({...form,documents:e.target.value})}/></label><button className="btn btn-primary md:col-span-2" disabled={submit.isPending} onClick={()=>submit.mutate()}>{submit.isPending?'Submitting…':'Submit application'}</button>{submit.isError&&<p className="text-error md:col-span-2">{submit.error?.response?.data?.error?.message||'Could not submit application.'}</p>}</div></div></div></div>
}
