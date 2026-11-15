import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Clock3 } from 'lucide-react';
import { api, ApiError } from '../services/api';
import { currentUser } from '../services/auth';
import { findReusableOperation, saveOperation, statusFromServer, updateOperation, type OperationRequest, type StoredOperation } from '../services/operations';
import type { Ticket } from '../types';

const label=(s:string)=>s.replaceAll('_',' ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
const errorText=(e:unknown)=>e instanceof Error?e.message:'Something went wrong. Please retry with the saved operation key.';

async function send(row:StoredOperation, request:OperationRequest) {
  if(request.method==='CREATE') return api.create(request.body as {title:string;description:string;priority:string;status?:string},row.idempotency_key);
  const ticket={ticket_id:request.ticket_id||'',version:request.version||0} as Ticket;
  if(request.method==='UPDATE') return api.update(ticket,request.body as {title:string;description:string;priority:string;status:string},row.idempotency_key);
  return api.remove(ticket,row.idempotency_key);
}

export default function DurableTicketForm(){
  const {id}=useParams(); const edit=!!id;
  const [ticket,setTicket]=useState<Ticket|null>(null);
  const [form,setForm]=useState({title:'',description:'',priority:'MEDIUM',status:'OPEN'});
  const [loading,setLoading]=useState(edit),[saving,setSaving]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  useEffect(()=>{if(id)api.get(id).then(t=>{setTicket(t);setForm({title:t.title,description:t.description,priority:t.priority,status:t.status})}).catch(e=>setError(errorText(e))).finally(()=>setLoading(false));},[id]);
  async function submit(e:React.FormEvent){
    e.preventDefault(); setError(''); if(form.title.trim().length<3||form.description.trim().length<3){setError('Add a title and description with at least 3 characters.');return;}
    const user=await currentUser(); if(!user){setError('Sign in again before submitting this operation.');return;}
    const fingerprint=JSON.stringify([id,ticket?.version,form]);
    const previous=findReusableOperation(user.sub,fingerprint); const key=previous?.idempotency_key||crypto.randomUUID();
    const request:OperationRequest={method:edit?'UPDATE':'CREATE',ticket_id:id,version:ticket?.version,body:{...form}};
    const row:StoredOperation={operation_id:key,idempotency_key:key,owner_sub:user.sub,fingerprint,kind:edit?'UPDATE':'CREATE',ticket_id:id,status:'PENDING',updated_at:new Date().toISOString()};
    saveOperation(row,request); setSaving(true); setNotice('Saved operation is being submitted; status checks will continue across navigation and reloads.');
    try{const result=await send(row,request);updateOperation(key,{status:statusFromServer(result.status),ticket_id:result.ticket_id,message:result.status==='AMBIGUOUS'?'Queue acceptance could not be confirmed. Review before retrying.':undefined});setNotice(`Operation ${label(result.status)} · ${result.ticket_id}`);}
    catch(err){const state=err instanceof ApiError&&err.status<500?'FAILED':'AMBIGUOUS';updateOperation(key,{status:state,message:errorText(err)});setError(errorText(err));}
    finally{setSaving(false);}
  }
  if(loading)return <div className="loading-state">Loading ticket…</div>;
  return <><Link to={edit?`/tickets/${id}`:'/tickets'} className="back-link"><ArrowLeft size={16}/> Back to {edit?'ticket':'tickets'}</Link>
    <div className="page-heading"><div><span className="eyebrow">{edit?'EDIT RECORD':'NEW REQUEST'}</span><h1>{edit?'Update ticket':'Create a ticket'}</h1><p>{edit?'Changes use the version you last loaded.':'Capture the issue clearly so your team can resolve it quickly.'}</p></div></div>
    <form className="panel form-panel" onSubmit={submit}><div className="form-section"><h2>Ticket information</h2><p>Provide the details support needs to understand the issue.</p>
      <label>Title <span>*</span><input required minLength={3} maxLength={200} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
      <label>Description <span>*</span><textarea required minLength={3} maxLength={5000} rows={6} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><small>{form.description.length}/5000 characters</small></label>
      <div className="form-row"><label>Priority<select value={form.priority} onChange={e=>setForm({...form,priority:e.target.value})}>{['LOW','MEDIUM','HIGH','CRITICAL'].map(x=><option key={x}>{x}</option>)}</select></label>{edit&&<label>Status<select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}>{['OPEN','IN_PROGRESS','RESOLVED'].map(x=><option key={x}>{x}</option>)}</select></label>}</div>
    </div>{error&&<div className="error-box">{error}</div>}{notice&&<div className="notice info"><Clock3 size={16}/>{notice}</div>}
    <div className="form-actions"><Link className="button subtle" to={edit?`/tickets/${id}`:'/tickets'}>Cancel</Link><button className="button primary" disabled={saving}>{saving?'Submitting…':edit?'Save changes':'Submit ticket'} <ArrowRight size={16}/></button></div></form>
  </>;
}
