export function applyBatch(state: {id:string,count:number}[], operations: unknown) {
 if(!Array.isArray(operations))throw new TypeError('operations');
 const result=state.map(x=>({...x}));
 for(const op of operations){
  if(op===null||typeof op!=='object'||![Object.prototype,null].includes(Object.getPrototypeOf(op)))throw new TypeError('operation');
  const keys=Object.keys(op).sort();
  const expected=op.type==='put'?['count','id','type']:op.type==='remove'?['id','type']:[];
  if(JSON.stringify(keys)!==JSON.stringify(expected)||typeof op.id!=='string'||!op.id||op.type==='put'&&(!Number.isSafeInteger(op.count)||op.count<0))throw new TypeError('fields');
  const i=result.findIndex(x=>x.id===op.id);
  if(op.type==='remove'){if(i>=0)result.splice(i,1);}
  else if(i>=0)result[i]={id:op.id,count:op.count};else result.push({id:op.id,count:op.count});
 }
 return result;
}
