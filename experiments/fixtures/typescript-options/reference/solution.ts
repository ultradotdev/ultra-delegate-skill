export function normalizeOptions(value: unknown) {
 if(value===null || typeof value!=='object' || ![Object.prototype,null].includes(Object.getPrototypeOf(value))) throw new TypeError('object');
 const x=value as Record<string,unknown>;
 if(Object.keys(x).some(k=>!['limit','offset','label'].includes(k))) throw new TypeError('key');
 const field=(k:string,d:unknown)=>Object.hasOwn(x,k)&&x[k]!==undefined?x[k]:d;
 const limit=field('limit',20),offset=field('offset',0),label=field('label','');
 if(typeof limit!=='number'||!Number.isInteger(limit)||limit<1||limit>100 || typeof offset!=='number'||!Number.isSafeInteger(offset)||offset<0 || typeof label!=='string'||label.length>40)throw new TypeError('field');
 return {limit,offset,label};
}
