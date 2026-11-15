import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../services/api';
import { getOperationRequest, listOperations, statusFromServer, updateOperation, type OperationRequest, type StoredOperation } from '../services/operations';
import type { Ticket } from '../types';
import type { SessionUser } from '../services/auth';

export default function OperationCenter({user}:{user:SessionUser}){
  const [rows,setRows]=useState<StoredOperation[]>([]);
  const [retryingIds,setRetryingIds]=useState<string[]>([]);
  const [polling,setPolling]=useState(false);
  const pollRef=useRef<(operationId?:string)=>Promise<void>>(async()=>{});
  const pollingRef=useRef(false);
  const retryingRef=useRef(new Set<string>());
  const refresh=()=>setRows(listOperations(user.sub));
  useEffect(()=>{
    refresh(); let active=true;
    const poll=async(operationId?:string)=>{
      if(pollingRef.current)return;
      pollingRef.current=true; if(active)setPolling(true);
      try{
        for(const row of listOperations(user.sub)){
          if(operationId&&row.operation_id!==operationId)continue;
          if(row.status!=='PENDING'&&!(operationId===row.operation_id&&row.status==='AMBIGUOUS'))continue;
          if(retryingRef.current.has(row.operation_id))continue;
          try{
            const result=await api.operationStatus(row.operation_id);
            if(!active||retryingRef.current.has(row.operation_id))continue;
            const current=listOperations(user.sub).find(item=>item.operation_id===row.operation_id);
            if(!current||current.updated_at!==row.updated_at)continue;
            const status=statusFromServer(result.status);
            const next=row.status==='AMBIGUOUS'&&status==='PENDING'&&!result.last_error?.startsWith('SQS_REJECTED:')?'AMBIGUOUS':status;
            updateOperation(row.operation_id,{status:next,ticket_id:result.ticket_id,message:result.last_error});
          }catch(err){
            if(active&&err instanceof ApiError&&err.status===404){
              const current=listOperations(user.sub).find(item=>item.operation_id===row.operation_id);
              if(current?.updated_at===row.updated_at)updateOperation(row.operation_id,{status:'AMBIGUOUS',message:'The server has no confirmed status. Review before retrying.'});
            }
          }
        }
      }finally{pollingRef.current=false;if(active){setPolling(false);refresh();}}
    };
    pollRef.current=poll;
    void poll(); const timer=window.setInterval(()=>void poll(),4000);
    return()=>{active=false;window.clearInterval(timer)};
  },[user.sub]);

  async function retry(row:StoredOperation){
    if(retryingRef.current.has(row.operation_id))return;
    const request=getOperationRequest(row.operation_id); if(!request)return;
    retryingRef.current.add(row.operation_id);setRetryingIds([...retryingRef.current]);
    updateOperation(row.operation_id,{status:'PENDING',message:'Retrying with the original idempotency key.'});refresh();
    try{const result=await submit(row,request);updateOperation(row.operation_id,{status:statusFromServer(result.status),ticket_id:result.ticket_id,message:undefined});}
    catch(err){updateOperation(row.operation_id,{status:err instanceof ApiError&&err.status<500?'FAILED':'AMBIGUOUS',message:err instanceof Error?err.message:'Operation outcome is uncertain.'});}
    finally{retryingRef.current.delete(row.operation_id);setRetryingIds([...retryingRef.current]);refresh();}
  }
  if(!rows.length)return null;
  const visibleRows=[...rows.filter(row=>row.status==='PENDING'||row.status==='AMBIGUOUS'),...rows.filter(row=>row.status==='COMPLETED'||row.status==='FAILED').slice(0,8)];
  return <section className="panel operation-center" aria-label="Recent operations"><div className="panel-title"><div><h2>Recent operations</h2><p>Saved operation IDs resume status checks after navigation or reload.</p></div></div>
    {visibleRows.map(row=><div className="operation-row" key={row.operation_id}><div><b>{row.kind} {row.ticket_id?`ticket ${row.ticket_id.slice(0,8)}`:'ticket'}</b><small>{row.message||`Operation ${row.operation_id.slice(0,8)}`}</small></div><span className={`status-pill ${row.status.toLowerCase()}`}>{row.status}</span>{(row.status==='PENDING'||row.status==='AMBIGUOUS')&&<button className="button subtle" disabled={polling} onClick={()=>void pollRef.current(row.operation_id)}>Refresh status</button>}{((row.status==='AMBIGUOUS'&&!!getOperationRequest(row.operation_id))||(row.status==='PENDING'&&row.message?.startsWith('SQS_REJECTED:')))&&<button className="button subtle" disabled={polling||!getOperationRequest(row.operation_id)||retryingIds.includes(row.operation_id)} onClick={()=>void retry(row)}>{retryingIds.includes(row.operation_id)?'Retrying…':'Retry with same key'}</button>}</div>)}
  </section>;
}

async function submit(row:StoredOperation,request:OperationRequest){
  if(request.method==='CREATE')return api.create(request.body as {title:string;description:string;priority:string;status?:string},row.idempotency_key);
  const ticket={ticket_id:request.ticket_id||'',version:request.version||0} as Ticket;
  if(request.method==='UPDATE')return api.update(ticket,request.body as {title:string;description:string;priority:string;status:string},row.idempotency_key);
  return api.remove(ticket,row.idempotency_key);
}
