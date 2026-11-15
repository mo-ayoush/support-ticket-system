import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

const mocks=vi.hoisted(()=>({operationStatus:vi.fn(),create:vi.fn(),update:vi.fn(),remove:vi.fn()}));
vi.mock('../src/services/api',()=>({api:{operationStatus:mocks.operationStatus,create:mocks.create,update:mocks.update,remove:mocks.remove},ApiError:class extends Error{constructor(message:string,public status:number){super(message)}}}));
import OperationCenter from '../src/components/OperationCenter';
import { saveOperation, type StoredOperation } from '../src/services/operations';

const user={sub:'owner-1',email:'owner@example.test',groups:['SupportUsers']};
const operation:StoredOperation={operation_id:'stable-operation-id',idempotency_key:'stable-operation-id',owner_sub:user.sub,fingerprint:'fingerprint',kind:'CREATE',status:'PENDING',updated_at:'2026-11-14T10:00:00Z'};
beforeEach(()=>{localStorage.clear();sessionStorage.clear();vi.clearAllMocks();});
afterEach(()=>{cleanup();vi.useRealTimers()});

describe('operation recovery UI',()=>{
  it('resumes polling from persisted operation state after a page reload',async()=>{
    saveOperation(operation,{method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    mocks.operationStatus.mockResolvedValue({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'COMPLETED'});
    const first=render(<OperationCenter user={user}/>);
    expect(await screen.findByText('COMPLETED')).toBeInTheDocument();
    first.unmount();
    render(<OperationCenter user={user}/>);
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(mocks.operationStatus).toHaveBeenCalledWith(operation.operation_id);
  });

  it('retries a definite queue rejection with the persisted idempotency key',async()=>{
    saveOperation({...operation,message:'SQS_REJECTED:ThrottlingException'}, {method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    mocks.operationStatus.mockResolvedValue({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'PENDING',last_error:'SQS_REJECTED:ThrottlingException'});
    mocks.create.mockResolvedValue({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'SENT'});
    render(<OperationCenter user={user}/>);
    fireEvent.click(await screen.findByRole('button',{name:/retry with same key/i}));
    expect(await screen.findByText('PENDING')).toBeInTheDocument();
    expect(mocks.create).toHaveBeenCalledWith({title:'Issue',description:'Details',priority:'HIGH'},operation.idempotency_key);
  });

  it('shows ambiguous outcomes without offering an automatic retry',async()=>{
    saveOperation({...operation,status:'AMBIGUOUS',message:'SNS publish may have been accepted.'});
    mocks.operationStatus.mockResolvedValue({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'AMBIGUOUS',last_error:'TimeoutError'});
    render(<OperationCenter user={user}/>);
    expect(await screen.findByText('AMBIGUOUS')).toBeInTheDocument();
    expect(screen.queryByRole('button',{name:/retry/i})).not.toBeInTheDocument();
    expect(mocks.operationStatus).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole('button',{name:/refresh status/i}).at(-1)!);
    expect(mocks.operationStatus).toHaveBeenCalledWith(operation.operation_id);
  });

  it('does not overlap automatic polling while a status request is pending',async()=>{
    vi.useFakeTimers();
    saveOperation(operation,{method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    let resolve!: (value: {operation_id:string;ticket_id:string;status:string})=>void;
    mocks.operationStatus.mockReturnValue(new Promise(resolveResult=>{resolve=resolveResult;}));
    await act(async()=>{render(<OperationCenter user={user}/>)});
    expect(mocks.operationStatus).toHaveBeenCalledTimes(1);
    await act(async()=>{await vi.advanceTimersByTimeAsync(12000)});
    expect(mocks.operationStatus).toHaveBeenCalledTimes(1);
    await act(async()=>resolve({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'PENDING'}));
  });

  it('does not let an old polling response overwrite a newer terminal state',async()=>{
    vi.useFakeTimers();
    saveOperation(operation,{method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    let resolve!: (value: {operation_id:string;ticket_id:string;status:string})=>void;
    mocks.operationStatus.mockReturnValue(new Promise(resolveResult=>{resolve=resolveResult;}));
    await act(async()=>{render(<OperationCenter user={user}/>)});
    const {updateOperation}=await import('../src/services/operations');
    updateOperation(operation.operation_id,{status:'COMPLETED'});
    await act(async()=>resolve({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'PENDING'}));
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
  });

  it('prevents duplicate retry submissions while the first retry is in flight',async()=>{
    saveOperation({...operation,message:'SQS_REJECTED:ThrottlingException'}, {method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    mocks.operationStatus.mockResolvedValue({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'PENDING',last_error:'SQS_REJECTED:ThrottlingException'});
    let resolve!: (value:{operation_id:string;ticket_id:string;status:string})=>void;
    mocks.create.mockReturnValue(new Promise(resolveResult=>{resolve=resolveResult}));
    render(<OperationCenter user={user}/>);
    const retry=await screen.findByRole('button',{name:/retry with same key/i});
    fireEvent.click(retry);
    fireEvent.click(retry);
    expect(mocks.create).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button',{name:/retrying/i})).toBeDisabled();
    await act(async()=>resolve({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'SENT'}));
  });

  it('cleans up automatic polling when the operation panel unmounts',async()=>{
    vi.useFakeTimers();
    saveOperation(operation,{method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    mocks.operationStatus.mockResolvedValue({operation_id:operation.operation_id,ticket_id:'ticket-1',status:'PENDING'});
    let view!: ReturnType<typeof render>;
    await act(async()=>{view=render(<OperationCenter user={user}/>)});
    expect(mocks.operationStatus).toHaveBeenCalledTimes(1);
    view.unmount();
    await act(async()=>{await vi.advanceTimersByTimeAsync(12000)});
    expect(mocks.operationStatus).toHaveBeenCalledTimes(1);
  });
});
