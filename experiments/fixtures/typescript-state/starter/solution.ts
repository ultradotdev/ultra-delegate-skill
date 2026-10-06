export function applyBatch(state: any[], operations: any) {
 for(const op of operations){
  const i=state.findIndex(x=>x.id===op.id);
  if(op.type==='remove'){if(i>=0)state.splice(i,1);}
  else if(i>=0)state[i].count=op.count;
  else state.push({id:op.id,count:op.count});
 }
 return state;
}
